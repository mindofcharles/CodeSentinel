# System Architecture

CodeSentinel is built as a modular CLI application. This document describes the internal components and their interactions.

> [!NOTE]
> CodeSentinel is not fully developed yet.

## Component Overview

### 1. `src/main.py` (Entry Point)

- Handles CLI arguments using `argparse`.

- Orchestrates the flow between the Scanner, AI Engine, and Reporter.

- Manages the logic for switching between Standard and Deep analysis modes.

### 2. `Scanner` (`src/scanner.py`)

- **File Discovery**: Recursively walks the target directory while respecting `IGNORE_DIRS`.
- **Tree-sitter Integration**: Uses parsers for Python, JavaScript, TypeScript/TSX, C/C++, Go, Rust, and Java.
- **Skeleton Extraction**: Extracts signatures (class/function names) to provide a high-level overview of a file without its implementation details.
- **Dependency Resolution**: Builds a bounded, cycle-safe recursive graph and rejects dependencies outside the scan root.
- **Symlink Safety**: Does not follow symlinks by default and prevents external-path traversal and directory cycles.
- **Read Errors**: Raises a file-read error instead of passing error text to the AI as source code.

### 3. `AIEngine` (`src/ai_engine.py`)

- **Client Management**: Wraps the OpenAI Python client.
- **Prompt Engineering**: Contains specialized system prompts for security auditing.
- **Context Construction**: Formats the main file and its dependencies (if in Deep mode) into a prompt for the LLM.
- **Retry Handling**: Retries malformed/empty AI responses, but reports context-window/token-limit errors immediately.
- **Token Budgeting**: Reserves response and safety-margin tokens, then budgets the main file and dependencies with `tokenizers`.
- **Schema Validation**: Accepts only valid JSON with a `SAFE`, `WARNING`, or `DANGER` status and a non-empty reason.

### 4. `Reporter` (`src/reporter.py`)

- **Visuals**: Uses the `rich` library to print tables, trees, and panels to the console.
- **Streaming Reports**: Appends JSONL records, periodically syncs progress, and atomically builds final JSON in constant memory.
- **Statistics**: Tracks the count of Safe, Warning, Danger, and Error results.
- **Finalization**: Records `completed`, `interrupted`, or `failed` state, processed-file coverage, and end time.
- **Log Safety**: Prompts are not persisted by default; opt-in logs receive basic credential and PEM redaction.

### 5. `Config` (`src/config_parser.py` & `config.yaml`)

- Centralized configuration using a class-based parser that reads from `config.yaml`.
- Resolves default configuration relative to the project and uses CLI, environment, then YAML priority.

## Data Flow

1. **Initialization**: `main.py` loads the configuration and initializes `Scanner`, `AIEngine`, and `Reporter`.
2. **Discovery**: `Scanner.get_files()` yields a list of target files.
3. **Analysis Loop**:
    - If **Standard**: `Scanner.read_file()` -> `AIEngine.analyze_code()`.
    - If **Deep**:
        - `Scanner.collect_dependency_context()` recursively traverses local dependencies within configured limits.
        - Dependencies use project-relative names and skeleton or full-code context.
        - `AIEngine.analyze_deep(file, content, dependencies)`.
4. **Reporting**: `Reporter.log_result()` updates the CLI and appends a JSONL recovery record.
5. **Error Isolation**: Unexpected per-file failures are recorded and the scan continues.
6. **Finalization**: `Reporter.finalize_reports()` atomically creates reports and records final coverage after completion, interruption, or failure.
