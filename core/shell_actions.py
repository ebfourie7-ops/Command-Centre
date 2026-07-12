"""Validated command construction and structured execution auditing.

UI code should pass argument lists to this module. Shell programs are permitted
only through ``audited_shell_script`` and must be explicitly marked as trusted;
this keeps editable configuration from silently becoming executable code.
"""

import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse


PACKAGE_RE = re.compile(r"^[A-Za-z0-9@._+:-]+$")
SERVICE_RE = re.compile(r"^[A-Za-z0-9_.@:-]+\.service$")
COMMAND_RE = re.compile(r"^[A-Za-z0-9_.+:-]+$")
ENVIRONMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ActionValidationError(ValueError):
    """Raised when untrusted data cannot safely become a command argument."""


def _validated(value, pattern, label):
    value = str(value or "")
    if not pattern.fullmatch(value):
        raise ActionValidationError(f"Invalid {label}: {value!r}")
    return value


def validate_package(value):
    return _validated(value, PACKAGE_RE, "package name")


def validate_service(value):
    return _validated(value, SERVICE_RE, "service name")


def validate_command_name(value):
    return _validated(value, COMMAND_RE, "command name")


def validate_environment(environment):
    clean = {}
    for key, value in (environment or {}).items():
        key = _validated(key, ENVIRONMENT_RE, "environment variable name")
        value = str(value)
        if "\x00" in value or len(value) > 4096:
            raise ActionValidationError(f"Invalid value for environment variable {key}")
        clean[key] = value
    return clean


def validate_url(value, schemes=("http", "https")):
    value = str(value or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in schemes or not parsed.hostname or parsed.username or parsed.password:
        raise ActionValidationError(f"Invalid or unsupported URL: {value!r}")
    return value


def validate_user_path(value, home=None):
    home = Path(home or Path.home()).resolve()
    path = Path(os.path.expanduser(str(value or ""))).resolve()
    try:
        path.relative_to(home)
    except ValueError as error:
        raise ActionValidationError(f"Path is outside the user home directory: {path}") from error
    return path


def parse_program_command(value):
    """Parse a program launch string while rejecting shell syntax."""
    value = str(value or "").strip()
    if not value or any(token in value for token in (";", "|", "&", "`", "$(", "\n", "\r", ">", "<")):
        raise ActionValidationError("Program launch commands cannot contain shell syntax")
    try:
        arguments = shlex.split(value)
    except ValueError as error:
        raise ActionValidationError(f"Invalid program command: {error}") from error
    if not arguments:
        raise ActionValidationError("Program command is empty")
    validate_command_name(arguments[0])
    if any("\x00" in argument for argument in arguments):
        raise ActionValidationError("Program argument contains a null byte")
    return arguments


class ActionAuditLog:
    def __init__(self, path=None):
        self.path = Path(path or Path.home() / ".local/state/command-centre/actions.jsonl")

    def record(self, action, argv, status, exit_code=None, detail=""):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        if self.path.exists() and self.path.stat().st_size > 5 * 1024 * 1024:
            previous = self.path.with_suffix(".previous.jsonl")
            previous.unlink(missing_ok=True)
            self.path.replace(previous)
            previous.chmod(0o600)
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "action": str(action), "argv": list(argv), "status": str(status),
            "exit_code": exit_code, "detail": str(detail)[:2000],
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.path.chmod(0o600)


AUDIT_LOG = ActionAuditLog()


def run_argv(argv, *, action="command", timeout=15, cwd=None, env=None):
    argv = [str(argument) for argument in argv]
    if not argv or not os.path.isabs(argv[0]):
        validate_command_name(argv[0] if argv else "")
    AUDIT_LOG.record(action, argv, "started")
    try:
        result = subprocess.run(argv, check=False, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env)
    except (OSError, subprocess.TimeoutExpired) as error:
        AUDIT_LOG.record(action, argv, "failed", 127, str(error))
        raise
    AUDIT_LOG.record(action, argv, "completed" if result.returncode == 0 else "failed", result.returncode, result.stderr)
    return result


def audited_launch(argv, *, action="launch", cwd=None, env=None):
    argv = [str(argument) for argument in argv]
    if not argv or not os.path.isabs(argv[0]):
        validate_command_name(argv[0] if argv else "")
    AUDIT_LOG.record(action, argv, "launched")
    return subprocess.Popen(argv, cwd=cwd, env=env)


def audited_shell_script(script, *, action, trusted=False):
    if not trusted:
        raise ActionValidationError("Shell scripts require an explicitly trusted built-in action")
    script = str(script)
    if not script.strip() or "\x00" in script:
        raise ActionValidationError("Invalid shell script")
    AUDIT_LOG.record(action, ["bash", "-lc", script], "approved-shell")
    return script
