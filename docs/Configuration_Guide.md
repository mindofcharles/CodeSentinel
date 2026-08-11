# Configuration Guide

CodeSentinel can be configured through three primary methods, prioritized as follows:

1. **CLI Arguments** (Highest priority)
2. **Environment Variables**
3. **`config.yaml`** (Default values)

The default file is resolved relative to the CodeSentinel source tree, not the current working directory. Use `--config PATH` or the `CODESENTINEL_CONFIG` environment variable to select another main file.

## Core Settings

| Setting | `config.yaml` key | CLI Argument | Env Variable |
| :--- | :--- | :--- | :--- |
| API Key | `openai_api_key` | `--env-key` | `OPENAI_API_KEY` |
| Base URL | `openai_base_url` | `--url` | - |
| Model Name | `ai_model` | `--model` | - |
| Temperature | `ai_temperature` | `--temperature` | - |
| Max Tokens | `ai_max_tokens` | `--max-tokens` | - |
| Context Window | `ai_context_window` | `--context-window` | - |
| Tokenizer JSON | `tokenizer_path` | `--tokenizer` | - |
| Dependency Depth | `dependency_max_depth` | `--dependency-depth` | - |

## Modular Configuration (`config/`)

To keep settings organized, CodeSentinel splits its configuration into modular files using the `includes` directive in the main `config.yaml`:

- `config/file_rules.yaml`: Contains lists of `target_extensions` and `ignore_dirs`.
- `config/prompts.yaml`: Contains the system and user prompts for different analysis modes.
- `config/tree_sitter.yaml`: Contains the syntax AST rules for dependency extraction.

If any file specified in the `includes` section is missing, CodeSentinel will immediately exit with an error to ensure consistent behavior.

## File Handling Settings

Modify `max_file_size` directly in `config.yaml`, and manage extensions/ignores in `config/file_rules.yaml`:

- `max_file_size`: (Default: 10MB) Hard disk-read byte limit. Token budgeting applies an additional prompt limit.
- `target_extensions`: A list of file extensions that the scanner will process (e.g., `.py`, `.js`, `.go`).
- `ignore_dirs`: A list of directory names to skip (e.g., `.git`, `node_modules`, `venv`).

## Tree-sitter Parsers

The base `tree-sitter` package enables structural parsing, but each language needs its own parser package, such as `tree-sitter-python` or `tree-sitter-javascript`.

The pinned requirements include every configured parser. If one cannot be loaded, CodeSentinel warns before scanning and skips structural extraction for that language.

## Token and Dependency Budgets

- `ai_context_window`: Total model context capacity.
- `ai_max_tokens`: Tokens reserved for the response.
- `ai_token_safety_margin`: Capacity reserved for provider-specific chat-template overhead.
- `main_file_token_budget`: Maximum for the primary file.
- `dependency_token_budget`: Shared maximum for dependency context.
- `dependency_file_token_budget`: Per-dependency maximum.
- `dependency_max_depth` and `max_dependencies`: Bound recursive graph traversal.

Set `tokenizer_path` to the model's `tokenizer.json` for exact model tokenization. If empty, CodeSentinel uses `tokenizers` ByteLevel splitting plus a conservative UTF-8 byte estimate.

## Reporting and Sensitive Logs

- `report_sync_interval`: Processed files between progress/fsync checkpoints.
- `max_tree_entries`: Skips expensive tree rendering for larger scans.
- `save_interaction_logs`: Disabled by default because prompts may contain secrets and proprietary source.
- `redact_interaction_logs`: Applies basic API-key, credential, access-token, and PEM redaction.
- `follow_symlinks`: Disabled by default. Enabled links must still resolve inside the scan root.

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
