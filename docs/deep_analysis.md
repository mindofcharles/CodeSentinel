# Deep Analysis Mode

Standard security scanners often look at files in isolation. CodeSentinel's **Deep Analysis** mode allows the AI to understand the context in which a file operates by examining its local dependencies.

## How it Works

When `--deep` is enabled, CodeSentinel performs the following steps for each file:

1. **Dependency Extraction**: It uses Tree-sitter to find `import` statements (Python) or `require/import` statements (JS/TS).
2. **Path Resolution**: It attempts to find the corresponding source file on the local file system.
3. **Context Building**:
    - By default, it extracts a **Skeleton** of the dependency (class and function signatures).
    - If `--full-deps` is used, it reads the **entire source code** of the dependency.
4. **AI Audit**: The AI receives the main file's code *plus* the context of all resolved dependencies, allowing it to trace logic across file boundaries.

## Skeletons vs. Full Deps

### Skeletons (Default)

Skeletons are designed to save tokens and fit within the LLM's context window.

- **Pros**: Low token usage, faster, avoids "context stuffing".
- **Cons**: AI cannot see the implementation details of the dependency.
- **Example**:

  ```python
  class Database: ...
  def connect(connection_string): ...
  def execute_query(query): ...
  ```

### Full Dependencies (`--full-deps`)

- **Pros**: Most accurate analysis; AI can see exactly what the dependency does.
- **Cons**: High token usage, slower, may exceed model limits for large projects.

## Use Cases

- **Taint Analysis**: Seeing if user input from one file is passed to a dangerous function in another.
- **Detecting Malicious Wrappers**: Identifying a "safe-looking" function that actually calls a malicious implementation in a separate module.
- **Understanding Frameworks**: Giving the AI context on local utility classes used throughout the project.
