import unittest

from core.config_schema import ConfigValidationError, validate_agent_config, validate_deployment_profiles


class ConfigSchemaTests(unittest.TestCase):
    def test_agent_config_discards_unknown_fields(self):
        clean = validate_agent_config({"default_provider": "codex", "custom": {"endpoint": "https://example.test", "model": "m", "secret": "no"}, "unknown": True})
        self.assertNotIn("unknown", clean)
        self.assertNotIn("secret", clean["custom"])

    def test_malformed_agent_config_is_rejected(self):
        with self.assertRaises(ConfigValidationError):
            validate_agent_config([])

    def test_custom_deployment_rejects_shell_compounds(self):
        profile = [{"id": "x", "name": "Test", "apps": [{"command": "editor; reboot"}]}]
        with self.assertRaises(ConfigValidationError):
            validate_deployment_profiles(profile)

    def test_simple_custom_deployment_is_valid(self):
        profile = [{"id": "x", "name": "Test", "apps": [{"command": "code --new-window"}], "services": ["docker.service"], "urls": ["https://example.test"]}]
        self.assertEqual(validate_deployment_profiles(profile)[0]["id"], "x")


if __name__ == "__main__":
    unittest.main()
