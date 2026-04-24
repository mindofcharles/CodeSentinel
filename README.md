# CodeSentinel 🛡️

> [!WARNING]
> This project is simple. \
> The results provided by this project cannot be fully trusted.

(I'm actively using this project myself, and I'll continue to improve it whenever I have time.)

CodeSentinel is an AI-powered security auditor designed to scan project directories for malicious intent, dangerous coding practices, and obfuscated payloads. By leveraging Large Language Models (LLMs) and Tree-sitter, it provides both surface-level scans and deep, dependency-aware analysis.

> [!NOTE]
> Read-only scan of target files/directories \
> no modifications are made to the scanned content.

## ✨ Features

- **AI-Powered Analysis**: Uses LLMs to audit code for backdoors, SQL injection, `eval()` usage, and more.
- **Deep Analysis Mode**: Traces cross-file logic by providing the AI with the context of local dependencies (either full code or skeletal structures).
- **Multi-Language Support**: Optimized for Python and JavaScript/TypeScript using Tree-sitter.
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
   pip install -r requirements.txt
   ```

## ⚙️ Configuration

Edit `config.yaml` or use environment variables to configure the scanner:

- `openai_api_key`: Your API key (default: `any-key-for-local`).
- `openai_base_url`: The API endpoint (e.g., `http://localhost:1234/v1` for LM Studio).
- `ai_model`: The name of the model to use.

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

## 📊 Reports

Reports are saved in the `reports/scan_YYYYMMDD_HHMMSS/` directory:

- `full_report.json`: Detailed results for every scanned file.
- `problems_report.json`: Filtered results containing only `[DANGER]` and `[WARNING]` status.
- `project_structure.txt`: A text-based visualization of the scanned directory.
- `logs/`: Raw AI interaction logs, mirroring the scanned project's structure.

## 🧪 Testing

Run the test suite:

```bash
python -m unittest discover test
```

---
*Documentation maintained by mindofcharles. Last updated: 2026-04-24.*
