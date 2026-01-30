import os
import pathlib
import re
from typing import List, Generator, Tuple
from .config import config

# Optional Tree-sitter support
try:
    import tree_sitter
    import tree_sitter_python
    import tree_sitter_javascript
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False

class Scanner:
    def __init__(self, target_dir: str):
        self.target_dir = pathlib.Path(target_dir)
        self.ts_languages = {}
        if HAS_TREE_SITTER:
            self._setup_tree_sitter()

    def _setup_tree_sitter(self):
        """Initializes Tree-sitter language objects."""
        try:
            self.ts_languages['.py'] = tree_sitter.Language(tree_sitter_python.language())
            self.ts_languages['.js'] = tree_sitter.Language(tree_sitter_javascript.language())
            self.ts_languages['.ts'] = self.ts_languages['.js']
            self.ts_languages['.jsx'] = self.ts_languages['.js']
            self.ts_languages['.tsx'] = self.ts_languages['.js']
        except Exception as e:
            print(f"Warning: Tree-sitter initialization failed: {e}")

    def is_ignored(self, path: pathlib.Path) -> bool:
        """
        Checks if a path should be ignored. 
        Only checks parts of the path that are within the target directory.
        """
        try:
            # Get the path relative to the target directory
            rel_path = path.relative_to(self.target_dir)
            for part in rel_path.parts:
                if part in config.IGNORE_DIRS:
                    return True
        except ValueError:
            # If path is not under target_dir, just check the name
            if path.name in config.IGNORE_DIRS:
                return True
        return False

    def is_target_file(self, path: pathlib.Path) -> bool:
        """Checks if the file extension is in the target list."""
        return path.suffix.lower() in config.TARGET_EXTENSIONS

    def get_files(self) -> Generator[pathlib.Path, None, None]:
        """Yields all valid files in the target directory."""
        if not self.target_dir.exists():
            raise FileNotFoundError(f"Directory not found: {self.target_dir}")

        for root, dirs, files in os.walk(self.target_dir):
            # Modify dirs in-place to skip ignored directories during os.walk
            dirs[:] = [d for d in dirs if d not in config.IGNORE_DIRS]
            
            for file in files:
                file_path = pathlib.Path(root) / file
                if not self.is_ignored(file_path) and self.is_target_file(file_path):
                    yield file_path

    def read_file(self, file_path: pathlib.Path) -> str:
        """Reads file content, handling encoding and size limits."""
        try:
            # Check size
            if file_path.stat().st_size > config.MAX_FILE_SIZE:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read(config.MAX_FILE_SIZE) + "\n\n...[TRUNCATED BY CODESENTINEL]..."
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def get_skeleton(self, file_path: pathlib.Path) -> str:
        """
        Extracts only the 'skeleton' of the code (classes, functions, and docstrings).
        Uses Tree-sitter for precision, falls back to first 500 chars if unavailable.
        """
        ext = file_path.suffix.lower()
        content = self.read_file(file_path)
        
        if not HAS_TREE_SITTER or ext not in self.ts_languages:
            return content[:500] + "\n...[TRUNCATED]..."

        try:
            parser = tree_sitter.Parser(self.ts_languages[ext])
            tree = parser.parse(bytes(content, "utf8"))
            
            # Query for class and function definitions
            query_scm = ""
            if ext == '.py':
                query_scm = """
                    (class_definition name: (identifier) @name body: (block) @body)
                    (function_definition name: (identifier) @name body: (block) @body)
                """
            elif ext in ['.js', '.ts', '.jsx', '.tsx']:
                query_scm = """
                    (class_definition name: (identifier) @name)
                    (function_definition name: (identifier) @name)
                    (method_definition name: (property_identifier) @name)
                    (variable_declarator name: (identifier) @name value: (arrow_function))
                """

            if not query_scm:
                return content[:500]

            query = tree_sitter.Query(self.ts_languages[ext], query_scm)
            captures = query.captures(tree.root_node)
            
            # Sort captures by start byte to process correctly
            # Note: tree-sitter-python/js may return nodes in varying order
            skeleton_parts = []
            
            # For simplicity, we'll just extract the first line of each definition
            # or use a more refined approach to keep signatures.
            processed_lines = set()
            lines = content.splitlines()
            
            for tag, nodes in captures.items():
                for node in nodes:
                    # We only want the signature, not the body
                    start_line = node.start_point[0]
                    if start_line not in processed_lines:
                        # Extract the line of the definition
                        sig_line = lines[start_line].strip()
                        skeleton_parts.append(sig_line + " ...")
                        processed_lines.add(start_line)
            
            return "\n".join(skeleton_parts) if skeleton_parts else content[:500]
        except:
            return content[:500]

    def extract_dependencies(self, file_path: pathlib.Path, content: str) -> List[pathlib.Path]:
        """
        Extracts local dependencies using Tree-sitter if available, 
        otherwise falls back to regex-based heuristic matching.
        """
        deps = []
        ext = file_path.suffix.lower()

        if HAS_TREE_SITTER and ext in self.ts_languages:
            deps = self._ts_extract_deps(file_path, content, ext)
        
        # If TS failed or is unavailable, use regex fallback
        if not deps:
            deps = self._regex_extract_deps(file_path, content, ext)
        
        return list(set(deps))

    def _ts_extract_deps(self, file_path: pathlib.Path, content: str, ext: str) -> List[pathlib.Path]:
        """Uses Tree-sitter Queries to find imports."""
        deps = []
        try:
            parser = tree_sitter.Parser(self.ts_languages[ext])
            tree = parser.parse(bytes(content, "utf8"))
            
            query_scm = ""
            if ext == '.py':
                query_scm = """
                    (import_from_statement module_name: (dotted_name) @mod)
                    (import_statement name: (dotted_name) @mod)
                    (import_from_statement 
                        module_name: (relative_import) 
                        name: (dotted_name) @mod)
                    (import_from_statement
                        module_name: (relative_import)
                        name: (aliased_import name: (dotted_name) @mod))
                """
            elif ext in ['.js', '.ts', '.jsx', '.tsx']:
                query_scm = """
                    (import_statement source: (string) @mod)
                    (call_expression 
                        function: (identifier) @func (#eq? @func "require")
                        arguments: (arguments (string) @mod))
                """

            if not query_scm:
                return []

            query = tree_sitter.Query(self.ts_languages[ext], query_scm)
            captures = query.captures(tree.root_node)

            for tag, nodes in captures.items():
                for node in nodes:
                    mod_name = content[node.start_byte:node.end_byte].strip("'\"")
                    
                    # Resolve paths
                    resolved = self._resolve_dependency(file_path, mod_name, ext)
                    if resolved:
                        deps.append(resolved)
        except Exception as e:
            # Silently fail and allow regex fallback
            pass
        return deps

    def _regex_extract_deps(self, file_path: pathlib.Path, content: str, ext: str) -> List[pathlib.Path]:
        """Existing regex-based extraction (Heuristic Fallback)."""
        deps = []
        if ext == '.py':
            patterns = [r'^import\s+([\w\.]+)', r'^from\s+([\w\.]+)\s+import']
            for line in content.splitlines():
                for p in patterns:
                    match = re.match(p, line.strip())
                    if match:
                        res = self._resolve_dependency(file_path, match.group(1), ext)
                        if res: deps.append(res)

        elif ext in ['.js', '.ts', '.jsx', '.tsx']:
            patterns = [r'from\s+[\'\'](\./.*|\.\./.*)[\'\']', r'require\s*\(\s*[\'\'](\./.*|\.\./.*)[\'\']\)']
            for line in content.splitlines():
                for p in patterns:
                    match = re.search(p, line)
                    if match:
                        res = self._resolve_dependency(file_path, match.group(1), ext)
                        if res: deps.append(res)
        return deps

    def _resolve_dependency(self, file_path: pathlib.Path, mod_name: str, ext: str) -> pathlib.Path:
        """Centralized logic to resolve a module name to a local path."""
        rel_path = mod_name.replace('.', '/')
        
        # Potential roots: file-relative and project-root
        potential_roots = [file_path.parent, self.target_dir]
        
        for root in potential_roots:
            # Different search strategies based on extension
            if ext == '.py':
                candidates = [root / f"{rel_path}.py", root / rel_path / "__init__.py"]
            else:
                # JS/TS
                candidates = [
                    root / rel_path,
                    pathlib.Path(str(root / rel_path) + ext),
                    root / rel_path / f"index{ext}"
                ]
            
            for candidate in candidates:
                if candidate.exists() and candidate.is_file():
                    return candidate.resolve()
        return None