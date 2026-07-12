import json
import tempfile
import unittest
from pathlib import Path

from core import shell_actions


class ShellActionTests(unittest.TestCase):
    def test_package_and_service_validation(self):
        self.assertEqual(shell_actions.validate_package("linux-cachyos"), "linux-cachyos")
        self.assertEqual(shell_actions.validate_service("docker.service"), "docker.service")
        for hostile in ("pkg;reboot", "$(id)", "../package", "name\ncommand"):
            with self.assertRaises(shell_actions.ActionValidationError):
                shell_actions.validate_package(hostile)
        with self.assertRaises(shell_actions.ActionValidationError):
            shell_actions.validate_service("docker.service;reboot")

    def test_program_commands_reject_shell_syntax(self):
        self.assertEqual(shell_actions.parse_program_command("flatpak run org.example.App"), ["flatpak", "run", "org.example.App"])
        for hostile in ("app; reboot", "app | sh", "app $(id)", "app > /tmp/file"):
            with self.assertRaises(shell_actions.ActionValidationError):
                shell_actions.parse_program_command(hostile)

    def test_url_and_environment_validation(self):
        self.assertEqual(shell_actions.validate_url("https://example.com/path"), "https://example.com/path")
        with self.assertRaises(shell_actions.ActionValidationError):
            shell_actions.validate_url("file:///etc/passwd")
        with self.assertRaises(shell_actions.ActionValidationError):
            shell_actions.validate_environment({"BAD-NAME": "value"})

    def test_audit_log_is_private_and_structured(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state" / "actions.jsonl"
            log = shell_actions.ActionAuditLog(path)
            log.record("test", ["true"], "completed", 0)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["argv"], ["true"])

    def test_untrusted_shell_script_is_refused(self):
        with self.assertRaises(shell_actions.ActionValidationError):
            shell_actions.audited_shell_script("echo unsafe", action="test")


if __name__ == "__main__":
    unittest.main()
