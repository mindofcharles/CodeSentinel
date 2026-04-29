import os
import pathlib
from typing import List, Generator
from .config_parser import config
from rich.console import Console

console = Console()

# Optional Tree-sitter support
try:
    import tree_sitter
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False

class FileReadError(Exception):
    """Raised when a source file cannot be read for analysis."""

class Scanner:
    def __init__(self, target_dir: str):
        self.target_dir = pathlib.Path(target_dir)
        self.ts_languages = {}

    def pre_scan_check(self):
        """
        Pre-scan to determine which extensions are present in the target directory,
        and warn the user BEFORE scanning if the corresponding tree-sitter library is missing.
        """
        if not HAS_TREE_SITTER:
            console.print("[bold yellow]Warning: 'tree-sitter' base library is not installed. Please install it using 'pip install tree-sitter'. Structural analysis is disabled.[/bold yellow]")
            return

        present_extensions = set()
        try:
            for file_path in self.get_files():
                present_extensions.add(file_path.suffix.lower())
        except FileNotFoundError:
            pass

        for lang_key, lang_conf in config.TREE_SITTER.items():
            exts = set(lang_conf.get('extensions', []))
            if present_extensions.intersection(exts):
                pkg_name = lang_conf.get('package')
                if pkg_name:
                    try:
                        import importlib
                        ts_module = importlib.import_module(pkg_name)
                        lang = tree_sitter.Language(ts_module.language())
                        for ext in exts:
                            self.ts_languages[ext] = lang
                    except ImportError:
                        pip_pkg = pkg_name.replace('_', '-')
                        console.print(f"[bold yellow]Warning: Found files for '{lang_key}', but its Tree-sitter parser is not installed. Please install it using 'pip install {pip_pkg}'. Dependencies and advanced skeleton extraction will be skipped.[/bold yellow]")

    def _get_ts_language_and_queries(self, ext: str):
        """Returns the loaded language object and queries dict for a given extension."""
        if not HAS_TREE_SITTER or ext not in self.ts_languages:
            return None, None
            
        for lang_key, lang_conf in config.TREE_SITTER.items():
            if ext in lang_conf.get('extensions', []):
                return self.ts_languages[ext], lang_conf
                
        return None, None

    def is_ignored(self, path: pathlib.Path) -> bool:
        """
        Checks if a path should be ignored. 
        Only checks parts of the path that are within the target directory.
        """
        try:
            rel_path = path.relative_to(self.target_dir)
            for part in rel_path.parts:
                if part in config.IGNORE_DIRS:
                    return True
        except ValueError:
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
            dirs[:] = [d for d in dirs if d not in config.IGNORE_DIRS]
            for file in files:
                file_path = pathlib.Path(root) / file
                if not self.is_ignored(file_path) and self.is_target_file(file_path):
                    yield file_path

    def read_file(self, file_path: pathlib.Path) -> str:
        """Reads file content, handling encoding and size limits."""
        try:
            if file_path.stat().st_size > config.MAX_FILE_SIZE:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read(config.MAX_FILE_SIZE) + "\n\n...[TRUNCATED BY CODESENTINEL]..."
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            raise FileReadError(f"Failed to read '{file_path}': {e}") from e

    def get_skeleton(self, file_path: pathlib.Path) -> str:
        """
        Extracts only the 'skeleton' of the code (classes, functions, and docstrings).
        Uses Tree-sitter for precision, falls back to first 500 chars if unavailable.
        """
        ext = file_path.suffix.lower()
        content = self.read_file(file_path)
        
        ts_lang, lang_conf = self._get_ts_language_and_queries(ext)
        if not ts_lang or not lang_conf or 'skeleton_query' not in lang_conf:
            return content[:500] + "\n...[TRUNCATED]..."

        query_scm = lang_conf['skeleton_query']

        try:
            parser = tree_sitter.Parser(ts_lang)
            tree = parser.parse(bytes(content, "utf8"))
            
            query = tree_sitter.Query(ts_lang, query_scm)
            if hasattr(query, "captures"):
                captures = query.captures(tree.root_node)
            else:
                cursor = tree_sitter.QueryCursor(query)
                captures = cursor.captures(tree.root_node)
            
            skeleton_parts = []
            processed_lines = set()
            lines = content.splitlines()
            
            def process_node(node):
                start_line = node.start_point[0]
                if start_line not in processed_lines:
                    sig_line = lines[start_line].strip()
                    skeleton_parts.append(sig_line + " ...")
                    processed_lines.add(start_line)

            if isinstance(captures, dict):
                for tag, nodes in captures.items():
                    if tag != "name":
                        continue
                    for node in nodes:
                        process_node(node)
            else:
                for node, tag in captures:
                    if tag != "name":
                        continue
                    process_node(node)
            
            return "\n".join(skeleton_parts) if skeleton_parts else content[:500]
        except:
            return content[:500]

    def extract_dependencies(self, file_path: pathlib.Path, content: str) -> List[pathlib.Path]:
        """
        Extracts local dependencies strictly using Tree-sitter.
        Heuristic regex fallbacks have been removed in favor of accurate AST parsing.
        """
        deps = []
        ext = file_path.suffix.lower()

        ts_lang, lang_conf = self._get_ts_language_and_queries(ext)
        if ts_lang and lang_conf and 'deps_query' in lang_conf:
            deps = self._ts_extract_deps(file_path, content, ext, ts_lang, lang_conf['deps_query'])
        
        return list(set(deps))

    def _ts_extract_deps(self, file_path: pathlib.Path, content: str, ext: str, ts_lang, query_scm: str) -> List[pathlib.Path]:
        """Uses Tree-sitter Queries to find imports."""
        deps = []
        try:
            parser = tree_sitter.Parser(ts_lang)
            tree = parser.parse(bytes(content, "utf8"))
            
            query = tree_sitter.Query(ts_lang, query_scm)
            if hasattr(query, "captures"):
                captures = query.captures(tree.root_node)
            else:
                cursor = tree_sitter.QueryCursor(query)
                captures = cursor.captures(tree.root_node)

            def process_dep(node):
                mod_name = self._module_name_from_capture(node, content, ext)
                resolved = self._resolve_dependency(file_path, mod_name, ext)
                if resolved:
                    deps.append(resolved)

            if isinstance(captures, dict):
                for tag, nodes in captures.items():
                    for node in nodes:
                        process_dep(node)
            else:
                for node, tag in captures:
                    process_dep(node)
        except Exception as e:
            pass
        return deps

    def _module_name_from_capture(self, node, content: str, ext: str) -> str:
        """Normalizes captured import nodes into resolvable module names."""
        mod_name = content[node.start_byte:node.end_byte].strip("'\"")

        if ext == '.py':
            parent = node.parent
            if parent and parent.type == 'import_from_statement':
                module_node = parent.child_by_field_name('module_name')
                if module_node:
                    module_name = content[module_node.start_byte:module_node.end_byte]
                    if module_node.type == 'relative_import':
                        if module_name.strip('.') == '':
                            return module_name + mod_name
                        return module_name
                    return module_name

        return mod_name

    def _resolve_dependency(self, file_path: pathlib.Path, mod_name: str, ext: str) -> pathlib.Path:
        """Centralized logic to resolve a module name to a local path."""
        potential_roots = [file_path.parent, self.target_dir]

        if ext == '.py' and mod_name.startswith('.'):
            leading_dots = len(mod_name) - len(mod_name.lstrip('.'))
            rel_module = mod_name[leading_dots:]
            root = file_path.parent
            for _ in range(max(leading_dots - 1, 0)):
                root = root.parent
            potential_roots = [root]
            rel_path = rel_module.replace('.', '/')
        else:
            rel_path = mod_name.replace('.', '/')
        
        for root in potential_roots:
            if ext == '.py':
                candidates = [root / f"{rel_path}.py", root / rel_path / "__init__.py"]
            else:
                candidates = [
                    root / rel_path,
                    pathlib.Path(str(root / rel_path) + ext),
                    root / rel_path / f"index{ext}"
                ]
            
            for candidate in candidates:
                if candidate.exists() and candidate.is_file():
                    return candidate.resolve()
        return None
