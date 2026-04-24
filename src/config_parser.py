import os
import yaml
import pathlib

class ConfigParser:
    def __init__(self):
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "any-key-for-local")
        self.OPENAI_BASE_URL = "http://localhost:1234/v1"
        self.AI_MODEL = "gpt-oss-20b-MXFP4.gguf"
        self.AI_TEMPERATURE = 0.2
        self.AI_MAX_TOKENS = 1000
        self.AI_MAX_RETRIES = 3
        self.MAX_FILE_SIZE = 10 * 1024 * 1024
        self.TARGET_EXTENSIONS = set()
        self.IGNORE_DIRS = set()
        self.TREE_SITTER = {}
        self.PROMPTS = {}

    def load(self, filepath="config.yaml"):
        config_path = pathlib.Path(filepath).resolve()
        
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            self.OPENAI_BASE_URL = data.get("openai_base_url", self.OPENAI_BASE_URL)
            self.AI_MODEL = data.get("ai_model", self.AI_MODEL)
            self.AI_TEMPERATURE = float(data.get("ai_temperature", self.AI_TEMPERATURE))
            self.AI_MAX_TOKENS = int(data.get("ai_max_tokens", self.AI_MAX_TOKENS))
            self.AI_MAX_RETRIES = int(data.get("ai_max_retries", self.AI_MAX_RETRIES))
            self.MAX_FILE_SIZE = int(data.get("max_file_size", self.MAX_FILE_SIZE))
            
            if "target_extensions" in data:
                self.TARGET_EXTENSIONS = set(data["target_extensions"])
            if "ignore_dirs" in data:
                self.IGNORE_DIRS = set(data["ignore_dirs"])
                
            self.TREE_SITTER = data.get("tree_sitter", {})
            self.PROMPTS = data.get("prompts", {})
            
            yaml_key = data.get("openai_api_key")
            if yaml_key:
                self.OPENAI_API_KEY = yaml_key

config = ConfigParser()
config.load("config.yaml")
