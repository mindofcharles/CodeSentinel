# Deep Analysis Mode

Standard security scanners often look at files in isolation. CodeSentinel's **Deep Analysis** mode allows the AI to understand the context in which a file operates by examining its local dependencies.

## How it Works

When `--deep` is enabled, CodeSentinel performs the following steps for each file:

1. **Dependency Extraction**: It uses configured Tree-sitter grammars to find imports and includes.
2. **Path Resolution**: It resolves only local files contained by the scan root.
3. **Recursive Graph Traversal**: It follows dependencies to `dependency_max_depth`, stops cycles, de-duplicates paths, and respects `max_dependencies`.
4. **Context Building**:
    - By default, it extracts a **Skeleton** of the dependency (class and function signatures).
    - If `--full-deps` is used, it reads the **entire source code** of the dependency.
5. **Token Budgeting**: Main source and dependency context are independently fitted to configured token budgets.
6. **AI Audit**: The AI receives the fitted main file and dependency graph context.

If a configured parser cannot be loaded, CodeSentinel warns before scanning and skips structural dependency extraction for that language. The file can still be scanned in standard mode.

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
- **Cons**: Higher token usage and slower scans. Excess context is truncated before the request; provider-side context errors are reported without retrying.

## Limits and Safety

Deep mode provides bounded dependency context, not a formal static taint-analysis proof. Dynamic imports, reflection, generated code, framework routing, and unsupported package-resolution rules may remain invisible. Treat results as review assistance rather than a security guarantee.

## Use Cases

- **Taint Analysis**: Seeing if user input from one file is passed to a dangerous function in another.
- **Detecting Malicious Wrappers**: Identifying a "safe-looking" function that actually calls a malicious implementation in a separate module.
- **Understanding Frameworks**: Giving the AI context on local utility classes used throughout the project.
