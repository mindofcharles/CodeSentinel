# CodeSentinel 🛡️

> [!WARNING]
> This project is simple. \
> The results provided by this project cannot be fully trusted.

(I'm actively using this project myself, and I'll continue to improve it whenever I have time.)

CodeSentinel is an AI-powered security auditor designed to scan project directories for malicious intent, dangerous coding practices, and obfuscated payloads. By leveraging Large Language Models (LLMs) and Tree-sitter, it provides both surface-level scans and deep, dependency-aware analysis.

> [!NOTE]
> Read-only scan of target files/directories \
> no modifications are made to the scanned content.

Many thanks to Gemini and GPT for their help!

> [!TIP]
> If you notice any issues or have any suggestions and have the time, \
> please leave them in the Issues section. Thank you.

[👉 Project Architecture](docs/Architecture.md) | [👉 Documents](docs/)

## ✨ Features

- **AI-Powered Analysis**: Uses LLMs to audit code for backdoors, SQL injection, `eval()` usage, and more.
- **Deep Analysis Mode**: Recursively follows a bounded local dependency graph and provides full code or skeletal structures to the AI.
- **Token-Aware Prompts**: Uses `tokenizers` with a model `tokenizer.json`, or a conservative ByteLevel fallback, to stay inside the configured context window.
- **Multi-Language Support**: Includes parsers for Python, JavaScript, TypeScript/TSX, C/C++, Go, Rust, and Java.
- **Intelligent Skeletons**: Extracts class and function signatures to provide context without exhausting LLM token limits.
- **Detailed Reporting**: Generates interactive CLI output and structured JSON reports (Full scan vs. Problems only).
- **Flexible Backend**: Compatible with OpenAI, LM Studio, llama.cpp, and other OpenAI-compatible APIs.

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- (Optional) A local LLM runner like  llama.cpp, LM Studio, OpenAI ...

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourlayer/CodeSentinel.git
   cd CodeSentinel
   ```

2. Install dependencies:

   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.lock
   ```

## ⚙️ Configuration

CodeSentinel uses a modular configuration system. Edit the main `config.yaml` or the specific module files inside the `config/` directory (e.g., `config/file_rules.yaml`, `config/prompts.yaml`).

Key settings in `config.yaml`:

- `openai_api_key`: Your API key (default: `any-key-for-local`).
- `openai_base_url`: The API endpoint (e.g., `http://localhost:1234/v1` for LM Studio).
- `ai_model`: The name of the model to use.
- `ai_context_window`: Total model context size, including prompt and response.
- `tokenizer_path`: Optional model `tokenizer.json` path for exact token counting.
- `save_interaction_logs`: Saves redacted prompts only when explicitly enabled; default is `false`.

## 📖 Usage

### Standard Scan

Scan a directory using the default configuration:

```bash
python -m src.main --dir ./path/to/project
```

### Deep Analysis

Analyze files along with their local dependencies:

```bash
python -m src.main --dir ./path/to/project --deep
```

### Options

- `--dir <path>`, `-d <path>`: Directory to scan (default: current directory).
- `--dry-run`: List files that would be scanned without sending them to the AI.
- `--model <name>`: Override the model specified in config.
- `--url <url>`: Override the API base URL.
- `--full-deps`: In deep mode, include the full source code of dependencies instead of just skeletons.
- `--dependency-depth <n>`: Limit recursive dependency traversal.
- `--context-window <n>`: Override the model context-window size.
- `--tokenizer <path>`: Use a model-specific `tokenizer.json`.
- `--save-prompts`: Save redacted AI interactions (disabled by default).
- `--config <path>`: Load an alternate main configuration file.

## 📊 Reports

Reports are saved in the `reports/scan_YYYYMMDD_HHMMSS/` directory:

- `full_report.json`: Atomic final report with coverage, completion state, counters, and every result.
- `full_report.jsonl`: Append-only recovery stream written during scanning.
- `problems_report.json`: Filtered results containing only `[DANGER]` and `[WARNING]` status.
- `project_structure.txt`: A text-based visualization of the scanned directory.
- `progress.json`: Atomic progress snapshot updated periodically.
- `logs/`: Optional redacted interactions, created only with `--save-prompts`.

## 🧪 Testing

Run the test suite:

```bash
venv/bin/python test/main_test.py
```

The legacy unittest discovery command is also supported:

```bash
venv/bin/python -m unittest discover test
```

---
*Documentation maintained by mindofcharles and AI. Last updated: 2026-08-11.*
