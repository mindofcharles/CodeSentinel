# Configuration Guide

CodeSentinel can be configured through three primary methods, prioritized as follows:

1. **CLI Arguments** (Highest priority)
2. **Environment Variables**
3. **`src/config.py`** (Default values)

## Core Settings

| Setting | `src/config.py` variable | CLI Argument | Env Variable |
| :--- | :--- | :--- | :--- |
| API Key | `OPENAI_API_KEY` | `--env-key` | `OPENAI_API_KEY` |
| Base URL | `OPENAI_BASE_URL` | `--url` | - |
| Model Name | `AI_MODEL` | `--model` | - |
| Temperature | `AI_TEMPERATURE` | `--temperature` | - |
| Max Tokens | `AI_MAX_TOKENS` | `--max-tokens` | - |

## File Handling Settings

Modify these directly in `src/config.py`:

- `MAX_FILE_SIZE`: (Default: 10MB) Files exceeding this limit will be truncated before being sent to the AI.
- `TARGET_EXTENSIONS`: A set of file extensions that the scanner will process (e.g., `.py`, `.js`, `.go`).
- `IGNORE_DIRS`: A set of directory names to skip (e.g., `.git`, `node_modules`, `venv`).

## Environment Variables

### `OPENAI_API_KEY`

The API key for your LLM provider. If using a local provider like LM Studio, this can be set to any string.

### Custom Env Keys

You can use the `--env-key` flag to tell CodeSentinel to look for the API key in a different environment variable. For example:

```bash
# Set a custom key
export MY_SECRET_KEY="sk-..."
# Run scanner
python -m src.main --dir ./src --env-key MY_SECRET_KEY
```
