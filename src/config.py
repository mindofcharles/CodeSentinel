import os

class Config:
    # ==========================================
    #           USER CONFIGURATION
    # ==========================================

    # 1. API KEY
    # Attempt to read from environment variable, otherwise use a default.
    # For local LLMs (Ollama, LM Studio), this value is often ignored but required.
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "any-key-for-local")

    # 2. API BASE URL
    # Uncomment the one that matches your setup:
    
    # -> OpenAI Official
    # OPENAI_BASE_URL = "https://api.openai.com/v1"
    
    # -> LM Studio (Default)
    OPENAI_BASE_URL = "http://localhost:1234/v1"
    
    # -> Ollama
    # OPENAI_BASE_URL = "http://localhost:11434/v1"

    # 3. MODEL NAME
    # Check your local model name (e.g. in LM Studio dashboard or `ollama list`)
    AI_MODEL = "gpt-oss-20b-MXFP4.gguf" # Replace with your local model name (e.g. "llama3", "qwen2.5-coder")

    # 4. GENERATION SETTINGS
    AI_TEMPERATURE = 0.2
    AI_MAX_TOKENS = 1000  # Increased default for better deep analysis

    # ==========================================
    #           SYSTEM SETTINGS
    # ==========================================
    
    # Files larger than this will be truncated (in bytes) to save context
    MAX_FILE_SIZE = 10240 * 1024  # 10MB
    
    # Extensions to analyze
    TARGET_EXTENSIONS = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', 
        '.java', '.c', '.cpp', '.h', '.cs', '.php', '.rb', 
        '.sh', '.bash', '.zsh', '.bat', '.ps1', '.cmd',
        '.html', '.xml', '.json', '.yaml', '.yml'
    }

    # Directories to ignore
    IGNORE_DIRS = {
        '.git', '.svn', '.hg', '.idea', '.vscode',
        'node_modules', 'venv', '.venv', 'env', 
        '__pycache__', 'dist', 'build', 'target',
        'bin', 'obj', 'lib', 'libs'
    }

config = Config()
