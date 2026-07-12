"""Small dependency-free validators for user-editable Command Centre JSON."""

from copy import deepcopy

from .shell_actions import (
    ActionValidationError, parse_program_command, validate_environment,
    validate_service, validate_url,
)


class ConfigValidationError(ValueError):
    pass


def _text(value, field, maximum=500):
    if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
        raise ConfigValidationError(f"{field} must be text no longer than {maximum} characters")
    return value


def validate_agent_config(data):
    if not isinstance(data, dict):
        raise ConfigValidationError("Agent configuration must be an object")
    clean = {}
    if "default_provider" in data:
        clean["default_provider"] = _text(data["default_provider"], "default_provider", 40)
    for provider in ("deepseek", "custom", "ollama"):
        section = data.get(provider)
        if section is None:
            continue
        if not isinstance(section, dict):
            raise ConfigValidationError(f"{provider} must be an object")
        clean[provider] = {
            key: _text(value, f"{provider}.{key}", 2048)
            for key, value in section.items() if key in ("endpoint", "model")
        }
    return clean


def validate_deployment_profiles(data, *, trusted_shell=False):
    if not isinstance(data, list):
        raise ConfigValidationError("Deployment profiles must be an array")
    clean = []
    for index, raw in enumerate(data):
        if not isinstance(raw, dict):
            raise ConfigValidationError(f"Profile {index} must be an object")
        profile = deepcopy(raw)
        for field in ("id", "name"):
            _text(profile.get(field, ""), f"profile[{index}].{field}", 120)
        try:
            profile["environment"] = validate_environment(profile.get("environment", {}))
            profile["services"] = [validate_service(value) for value in profile.get("services", [])]
            profile["urls"] = [validate_url(value) for value in profile.get("urls", [])]
            for app in profile.get("apps", []):
                parse_program_command(app.get("command", ""))
            if not trusted_shell:
                for terminal in profile.get("terminals", []):
                    parse_program_command(terminal.get("command", "exec bash"))
                for action in profile.get("quick_actions", []):
                    parse_program_command(action.get("command", ""))
        except (ActionValidationError, AttributeError, TypeError) as error:
            raise ConfigValidationError(f"Invalid profile {profile.get('name', index)}: {error}") from error
        clean.append(profile)
    return clean
