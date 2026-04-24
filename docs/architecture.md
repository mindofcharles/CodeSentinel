# System Architecture

CodeSentinel is built as a modular CLI application. This document describes the internal components and their interactions.

## Component Overview

### 1. `src/main.py` (Entry Point)

- Handles CLI arguments using `argparse`.

- Orchestrates the flow between the Scanner, AI Engine, and Reporter.

- Manages the logic for switching between Standard and Deep analysis modes.

### 2. `Scanner` (`src/scanner.py`)

- **File Discovery**: Recursively walks the target directory while respecting `IGNORE_DIRS`.
- **Tree-sitter Integration**: Uses Tree-sitter parsers to understand the AST (Abstract Syntax Tree) of Python and JavaScript files.
- **Skeleton Extraction**: Extracts signatures (class/function names) to provide a high-level overview of a file without its implementation details.
- **Dependency Resolution**: Identifies local imports/requires and resolves them to absolute file paths on disk.

### 3. `AIEngine` (`src/ai_engine.py`)

- **Client Management**: Wraps the OpenAI Python client.
- **Prompt Engineering**: Contains specialized system prompts for security auditing.
- **Context Construction**: Formats the main file and its dependencies (if in Deep mode) into a prompt for the LLM.

### 4. `Reporter` (`src/reporter.py`)

- **Visuals**: Uses the `rich` library to print tables, trees, and panels to the console.
- **Streaming Reports**: Writes results to JSON files in real-time to prevent data loss in case of a crash.
- **Statistics**: Tracks the count of Safe, Warning, Danger, and Error results.

### 5. `Config` (`src/config_parser.py` & `config.yaml`)

- Centralized configuration using a class-based parser that reads from `config.yaml`.
- Supports default values that can be overridden by environment variables or CLI flags.

## Data Flow

1. **Initialization**: `main.py` loads the configuration and initializes `Scanner`, `AIEngine`, and `Reporter`.
2. **Discovery**: `Scanner.get_files()` yields a list of target files.
3. **Analysis Loop**:
    - If **Standard**: `Scanner.read_file()` -> `AIEngine.analyze_code()`.
    - If **Deep**:
        - `Scanner.extract_dependencies()`.
        - For each dependency: `Scanner.get_skeleton()` or `Scanner.read_file()`.
        - `AIEngine.analyze_deep(file, content, dependencies)`.
4. **Reporting**: `Reporter.log_result()` updates the CLI and writes to JSON.
5. **Finalization**: `Reporter.finalize_reports()` closes file handles and prints a summary table.
