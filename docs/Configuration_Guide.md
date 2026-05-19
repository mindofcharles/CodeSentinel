# Configuration Guide

CodeSentinel can be configured through three primary methods, prioritized as follows:

1. **CLI Arguments** (Highest priority)
2. **Environment Variables**
3. **`config.yaml`** (Default values)

## Core Settings

| Setting | `config.yaml` key | CLI Argument | Env Variable |
| :--- | :--- | :--- | :--- |
| API Key | `openai_api_key` | `--env-key` | `OPENAI_API_KEY` |
| Base URL | `openai_base_url` | `--url` | - |
| Model Name | `ai_model` | `--model` | - |
| Temperature | `ai_temperature` | `--temperature` | - |
| Max Tokens | `ai_max_tokens` | `--max-tokens` | - |

## Modular Configuration (`config/`)

To keep settings organized, CodeSentinel splits its configuration into modular files using the `includes` directive in the main `config.yaml`:

- `config/file_rules.yaml`: Contains lists of `target_extensions` and `ignore_dirs`.
- `config/prompts.yaml`: Contains the system and user prompts for different analysis modes.
- `config/tree_sitter.yaml`: Contains the syntax AST rules for dependency extraction.

If any file specified in the `includes` section is missing, CodeSentinel will immediately exit with an error to ensure consistent behavior.

## File Handling Settings

Modify `max_file_size` directly in `config.yaml`, and manage extensions/ignores in `config/file_rules.yaml`:

- `max_file_size`: (Default: 10MB) Files exceeding this limit will be truncated before being sent to the AI.
- `target_extensions`: A list of file extensions that the scanner will process (e.g., `.py`, `.js`, `.go`).
- `ignore_dirs`: A list of directory names to skip (e.g., `.git`, `node_modules`, `venv`).

## Tree-sitter Parsers

The base `tree-sitter` package enables structural parsing, but each language needs its own parser package, such as `tree-sitter-python` or `tree-sitter-javascript`.

If a parser configured in `config.yaml` is missing, CodeSentinel warns before scanning and skips dependency extraction/skeleton extraction for that language. The scanner does not install parser packages automatically.

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
