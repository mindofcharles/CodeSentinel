import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config_parser import ConfigError, ConfigParser


class TestConfigParser(unittest.TestCase):
    def test_environment_api_key_overrides_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(
                "openai_api_key: yaml-key\n"
                "target_extensions: ['.py']\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"OPENAI_API_KEY": "environment-key"}):
                parsed = ConfigParser().load(config_path)

            self.assertEqual("environment-key", parsed.OPENAI_API_KEY)

    def test_missing_config_is_an_error(self):
        with self.assertRaises(ConfigError):
            ConfigParser().load("/definitely/missing/codesentinel.yaml")

    def test_invalid_context_budget_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(
                "target_extensions: ['.py']\n"
                "ai_context_window: 100\n"
                "ai_max_tokens: 100\n",
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError):
                ConfigParser().load(config_path)

    def test_extension_rules_must_be_a_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("target_extensions: '.py'\n", encoding="utf-8")
            with self.assertRaises(ConfigError):
                ConfigParser().load(config_path)
