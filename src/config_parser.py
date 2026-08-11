import os
import pathlib
from typing import Any

import yaml


class ConfigError(RuntimeError):
    """Raised when CodeSentinel configuration is missing or invalid."""


class ConfigParser:
    def __init__(self):
        self._set_defaults()

    def _set_defaults(self):
        self.OPENAI_API_KEY = "any-key-for-local"
        self.OPENAI_BASE_URL = "http://localhost:1234/v1"
        self.AI_MODEL = "AI"
        self.AI_TEMPERATURE = 0.1
        self.AI_MAX_TOKENS = 2048
        self.AI_MAX_RETRIES = 3
        self.AI_CONTEXT_WINDOW = 32768
        self.AI_TOKEN_SAFETY_MARGIN = 512
        self.TOKENIZER_PATH = ""
        self.MAIN_FILE_TOKEN_BUDGET = 16000
        self.DEPENDENCY_TOKEN_BUDGET = 10000
        self.DEPENDENCY_FILE_TOKEN_BUDGET = 3000
        self.DEPENDENCY_MAX_DEPTH = 3
        self.MAX_DEPENDENCIES = 100
        self.MAX_FILE_SIZE = 10 * 1024 * 1024
        self.MAX_TREE_ENTRIES = 5000
        self.REPORT_SYNC_INTERVAL = 25
        self.SAVE_INTERACTION_LOGS = False
        self.REDACT_INTERACTION_LOGS = True
        self.FOLLOW_SYMLINKS = False
        self.TARGET_EXTENSIONS = set()
        self.IGNORE_DIRS = set()
        self.TREE_SITTER = {}
        self.PROMPTS = {}
        self.CONFIG_PATH = None

    @staticmethod
    def _project_config_path() -> pathlib.Path:
        return pathlib.Path(__file__).resolve().parent.parent / "config.yaml"

    @staticmethod
    def _as_bool(value: Any, setting: str) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        raise ConfigError(f"'{setting}' must be true or false.")

    def load(self, filepath=None):
        """Load YAML configuration, then apply environment overrides."""
        self._set_defaults()
        configured_path = filepath or os.getenv("CODESENTINEL_CONFIG")
        config_path = pathlib.Path(configured_path).expanduser() if configured_path else self._project_config_path()
        config_path = config_path.resolve()

        if not config_path.is_file():
            raise ConfigError(f"Configuration file '{config_path}' not found.")

        try:
            with open(config_path, "r", encoding="utf-8") as config_file:
                data = yaml.safe_load(config_file) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigError(f"Failed to load configuration '{config_path}': {exc}") from exc

        includes = data.pop("includes", {})
        if not isinstance(includes, dict):
            raise ConfigError("'includes' must be a mapping.")

        for include_path in includes.values():
            resolved_include = (config_path.parent / include_path).resolve()
            if not resolved_include.is_file():
                raise ConfigError(f"Included configuration file '{resolved_include}' not found.")
            try:
                with open(resolved_include, "r", encoding="utf-8") as include_file:
                    include_data = yaml.safe_load(include_file) or {}
            except (OSError, yaml.YAMLError) as exc:
                raise ConfigError(f"Failed to load included configuration '{resolved_include}': {exc}") from exc
            if not isinstance(include_data, dict):
                raise ConfigError(f"Included configuration '{resolved_include}' must contain a mapping.")
            data.update(include_data)

        try:
            self.OPENAI_API_KEY = str(data.get("openai_api_key") or self.OPENAI_API_KEY)
            self.OPENAI_BASE_URL = str(data.get("openai_base_url", self.OPENAI_BASE_URL))
            self.AI_MODEL = str(data.get("ai_model", self.AI_MODEL))
            self.AI_TEMPERATURE = float(data.get("ai_temperature", self.AI_TEMPERATURE))
            self.AI_MAX_TOKENS = int(data.get("ai_max_tokens", self.AI_MAX_TOKENS))
            self.AI_MAX_RETRIES = int(data.get("ai_max_retries", self.AI_MAX_RETRIES))
            self.AI_CONTEXT_WINDOW = int(data.get("ai_context_window", self.AI_CONTEXT_WINDOW))
            self.AI_TOKEN_SAFETY_MARGIN = int(data.get("ai_token_safety_margin", self.AI_TOKEN_SAFETY_MARGIN))
            tokenizer_path = str(data.get("tokenizer_path", self.TOKENIZER_PATH) or "")
            self.TOKENIZER_PATH = str((config_path.parent / tokenizer_path).resolve()) if tokenizer_path else ""
            self.MAIN_FILE_TOKEN_BUDGET = int(data.get("main_file_token_budget", self.MAIN_FILE_TOKEN_BUDGET))
            self.DEPENDENCY_TOKEN_BUDGET = int(data.get("dependency_token_budget", self.DEPENDENCY_TOKEN_BUDGET))
            self.DEPENDENCY_FILE_TOKEN_BUDGET = int(data.get("dependency_file_token_budget", self.DEPENDENCY_FILE_TOKEN_BUDGET))
            self.DEPENDENCY_MAX_DEPTH = int(data.get("dependency_max_depth", self.DEPENDENCY_MAX_DEPTH))
            self.MAX_DEPENDENCIES = int(data.get("max_dependencies", self.MAX_DEPENDENCIES))
            self.MAX_FILE_SIZE = int(data.get("max_file_size", self.MAX_FILE_SIZE))
            self.MAX_TREE_ENTRIES = int(data.get("max_tree_entries", self.MAX_TREE_ENTRIES))
            self.REPORT_SYNC_INTERVAL = int(data.get("report_sync_interval", self.REPORT_SYNC_INTERVAL))
            self.SAVE_INTERACTION_LOGS = self._as_bool(data.get("save_interaction_logs", self.SAVE_INTERACTION_LOGS), "save_interaction_logs")
            self.REDACT_INTERACTION_LOGS = self._as_bool(data.get("redact_interaction_logs", self.REDACT_INTERACTION_LOGS), "redact_interaction_logs")
            self.FOLLOW_SYMLINKS = self._as_bool(data.get("follow_symlinks", self.FOLLOW_SYMLINKS), "follow_symlinks")
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"Invalid configuration value: {exc}") from exc

        target_extensions = data.get("target_extensions", [])
        ignore_dirs = data.get("ignore_dirs", [])
        tree_sitter_config = data.get("tree_sitter", {})
        prompts = data.get("prompts", {})
        if not isinstance(target_extensions, list) or not all(
            isinstance(item, str) for item in target_extensions
        ):
            raise ConfigError("'target_extensions' must be a list of strings.")
        if not isinstance(ignore_dirs, list) or not all(isinstance(item, str) for item in ignore_dirs):
            raise ConfigError("'ignore_dirs' must be a list of strings.")
        if not isinstance(tree_sitter_config, dict):
            raise ConfigError("'tree_sitter' must be a mapping.")
        if not isinstance(prompts, dict):
            raise ConfigError("'prompts' must be a mapping.")
        self.TARGET_EXTENSIONS = set(target_extensions)
        self.IGNORE_DIRS = set(ignore_dirs)
        self.TREE_SITTER = tree_sitter_config
        self.PROMPTS = prompts
        self.CONFIG_PATH = config_path

        # Environment variables have higher priority than YAML.
        if os.getenv("OPENAI_API_KEY"):
            self.OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

        self._validate()
        return self

    def _validate(self):
        positive_settings = {
            "ai_max_tokens": self.AI_MAX_TOKENS,
            "ai_max_retries": self.AI_MAX_RETRIES,
            "ai_context_window": self.AI_CONTEXT_WINDOW,
            "main_file_token_budget": self.MAIN_FILE_TOKEN_BUDGET,
            "dependency_token_budget": self.DEPENDENCY_TOKEN_BUDGET,
            "dependency_file_token_budget": self.DEPENDENCY_FILE_TOKEN_BUDGET,
            "dependency_max_depth": self.DEPENDENCY_MAX_DEPTH,
            "max_dependencies": self.MAX_DEPENDENCIES,
            "max_file_size": self.MAX_FILE_SIZE,
            "max_tree_entries": self.MAX_TREE_ENTRIES,
            "report_sync_interval": self.REPORT_SYNC_INTERVAL,
        }
        for name, value in positive_settings.items():
            if value <= 0:
                raise ConfigError(f"'{name}' must be greater than zero.")
        if self.AI_TOKEN_SAFETY_MARGIN < 0:
            raise ConfigError("'ai_token_safety_margin' cannot be negative.")
        if self.AI_MAX_TOKENS + self.AI_TOKEN_SAFETY_MARGIN >= self.AI_CONTEXT_WINDOW:
            raise ConfigError("AI output tokens and safety margin must leave room for input tokens.")
        if not 0 <= self.AI_TEMPERATURE <= 2:
            raise ConfigError("'ai_temperature' must be between 0 and 2.")
        if not self.TARGET_EXTENSIONS:
            raise ConfigError("At least one target extension must be configured.")


config = ConfigParser().load()
