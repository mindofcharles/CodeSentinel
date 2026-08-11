import importlib
import os
import pathlib
from collections import OrderedDict, deque
from typing import Generator, List

from rich.console import Console
from rich.markup import escape

from .config_parser import config

console = Console()

try:
    import tree_sitter

    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False


class FileReadError(Exception):
    """Raised when a source file cannot be read for analysis."""


class Scanner:
    def __init__(self, target_dir: str):
        self.target_dir = pathlib.Path(target_dir).resolve()
        self.ts_languages = {}

    def pre_scan_check(self, files=None):
        """Load only Tree-sitter parsers needed by files present in the target."""
        if not HAS_TREE_SITTER:
            console.print(
                "[bold yellow]Warning: 'tree-sitter' is not installed. "
                "Structural analysis is disabled.[/bold yellow]"
            )
            return

        source_files = files if files is not None else self.get_files()
        present_extensions = {file_path.suffix.lower() for file_path in source_files}
        for lang_key, lang_conf in config.TREE_SITTER.items():
            extensions = set(lang_conf.get("extensions", []))
            if not present_extensions.intersection(extensions):
                continue

            package_name = lang_conf.get("package")
            if not package_name:
                continue
            try:
                module = importlib.import_module(package_name)
                language_function = lang_conf.get("language_function", "language")
                language_factory = getattr(module, language_function)
                language = tree_sitter.Language(language_factory())
                for extension in extensions:
                    self.ts_languages[extension] = language
            except (ImportError, AttributeError, TypeError) as exc:
                pip_package = package_name.replace("_", "-")
                console.print(
                    f"[bold yellow]Warning: Found '{lang_key}' files, but parser "
                    f"'{pip_package}' could not be loaded ({exc}). Structural analysis "
                    "for this language will be skipped.[/bold yellow]"
                )

    def _get_ts_language_and_queries(self, extension: str):
        if not HAS_TREE_SITTER or extension not in self.ts_languages:
            return None, None
        for lang_conf in config.TREE_SITTER.values():
            if extension in lang_conf.get("extensions", []):
                return self.ts_languages[extension], lang_conf
        return None, None

    def _is_within_target(self, path: pathlib.Path) -> bool:
        try:
            path.resolve().relative_to(self.target_dir)
            return True
        except (OSError, ValueError):
            return False

    def is_ignored(self, path: pathlib.Path) -> bool:
        try:
            relative_path = path.relative_to(self.target_dir)
        except ValueError:
            return True
        if any(part in config.IGNORE_DIRS for part in relative_path.parts):
            return True
        if path.is_symlink():
            return not config.FOLLOW_SYMLINKS or not self._is_within_target(path)
        return False

    def is_target_file(self, path: pathlib.Path) -> bool:
        return path.suffix.lower() in config.TARGET_EXTENSIONS

    def get_files(self) -> Generator[pathlib.Path, None, None]:
        if not self.target_dir.is_dir():
            raise FileNotFoundError(f"Directory not found: {self.target_dir}")

        visited_directories = set()
        for root, directories, files in os.walk(
            self.target_dir, followlinks=config.FOLLOW_SYMLINKS
        ):
            root_path = pathlib.Path(root)
            resolved_root = root_path.resolve()
            if resolved_root in visited_directories or not self._is_within_target(resolved_root):
                directories[:] = []
                continue
            visited_directories.add(resolved_root)

            safe_directories = []
            for directory in directories:
                directory_path = root_path / directory
                if directory in config.IGNORE_DIRS or self.is_ignored(directory_path):
                    continue
                try:
                    resolved_directory = directory_path.resolve()
                except OSError:
                    continue
                if resolved_directory not in visited_directories:
                    safe_directories.append(directory)
            directories[:] = sorted(safe_directories)

            for filename in sorted(files):
                file_path = root_path / filename
                if self.is_ignored(file_path) or not self.is_target_file(file_path):
                    continue
                if self._is_within_target(file_path):
                    yield file_path

    def read_file(self, file_path: pathlib.Path) -> str:
        """Read UTF-8 text, limiting disk bytes before token budgeting."""
        try:
            with open(file_path, "rb") as source_file:
                raw = source_file.read(config.MAX_FILE_SIZE + 1)
            truncated = len(raw) > config.MAX_FILE_SIZE
            content = raw[: config.MAX_FILE_SIZE].decode("utf-8", errors="ignore")
            if truncated:
                content += "\n\n...[TRUNCATED BY CODESENTINEL FILE SIZE LIMIT]..."
            return content
        except Exception as exc:
            raise FileReadError(f"Failed to read '{file_path}': {exc}") from exc

    def get_skeleton(self, file_path: pathlib.Path, content: str = None) -> str:
        extension = file_path.suffix.lower()
        if content is None:
            content = self.read_file(file_path)
        language, language_config = self._get_ts_language_and_queries(extension)
        if not language or not language_config or "skeleton_query" not in language_config:
            return content[:500] + "\n...[SKELETON FALLBACK TRUNCATED]..."

        try:
            parser = tree_sitter.Parser(language)
            source_bytes = content.encode("utf-8")
            tree = parser.parse(source_bytes)
            query = tree_sitter.Query(language, language_config["skeleton_query"])
            captures = self._query_captures(query, tree.root_node)
            skeleton_parts = []
            processed_lines = set()
            lines = content.splitlines()

            def process_node(node):
                start_line = node.start_point[0]
                if start_line not in processed_lines and start_line < len(lines):
                    skeleton_parts.append(lines[start_line].strip() + " ...")
                    processed_lines.add(start_line)

            for tag, nodes in self._capture_items(captures):
                if tag == "name":
                    for node in nodes:
                        process_node(node)
            return "\n".join(skeleton_parts) if skeleton_parts else content[:500]
        except Exception as exc:
            console.print(
                f"[dim yellow]Skeleton extraction failed for {escape(str(file_path))}: "
                f"{escape(str(exc))}[/dim yellow]"
            )
            return content[:500] + "\n...[SKELETON EXTRACTION FAILED]..."

    @staticmethod
    def _query_captures(query, root_node):
        if hasattr(query, "captures"):
            return query.captures(root_node)
        return tree_sitter.QueryCursor(query).captures(root_node)

    @staticmethod
    def _capture_items(captures):
        if isinstance(captures, dict):
            return captures.items()
        grouped = {}
        for node, tag in captures:
            grouped.setdefault(tag, []).append(node)
        return grouped.items()

    def extract_dependencies(self, file_path: pathlib.Path, content: str) -> List[pathlib.Path]:
        extension = file_path.suffix.lower()
        language, language_config = self._get_ts_language_and_queries(extension)
        if not language or not language_config or "deps_query" not in language_config:
            return []
        dependencies = self._ts_extract_dependencies(
            file_path, content, extension, language, language_config["deps_query"]
        )
        return sorted(set(dependencies), key=lambda path: str(path))

    def _ts_extract_dependencies(self, file_path, content, extension, language, query_source):
        dependencies = []
        try:
            source_bytes = content.encode("utf-8")
            parser = tree_sitter.Parser(language)
            tree = parser.parse(source_bytes)
            query = tree_sitter.Query(language, query_source)
            captures = self._query_captures(query, tree.root_node)
            for tag, nodes in self._capture_items(captures):
                if tag != "mod":
                    continue
                for node in nodes:
                    module_name = self._module_name_from_capture(node, source_bytes, extension)
                    resolved = self._resolve_dependency(file_path, module_name, extension)
                    if resolved:
                        dependencies.append(resolved)
        except Exception as exc:
            console.print(
                f"[dim yellow]Dependency extraction failed for {escape(str(file_path))}: "
                f"{escape(str(exc))}[/dim yellow]"
            )
        return dependencies

    def _module_name_from_capture(self, node, source_bytes: bytes, extension: str) -> str:
        module_name = source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")
        module_name = module_name.strip("'\"`<>")
        if extension == ".py":
            parent = node.parent
            if parent and parent.type == "import_from_statement":
                module_node = parent.child_by_field_name("module_name")
                if module_node:
                    captured_module = source_bytes[module_node.start_byte : module_node.end_byte].decode("utf-8")
                    if module_node.type == "relative_import" and captured_module.strip(".") == "":
                        return captured_module + module_name
                    return captured_module
        return module_name

    def _resolve_dependency(self, file_path: pathlib.Path, module_name: str, extension: str):
        if not module_name:
            return None

        roots = [file_path.parent, self.target_dir]
        relative_path = module_name
        if extension == ".py":
            if module_name.startswith("."):
                leading_dots = len(module_name) - len(module_name.lstrip("."))
                root = file_path.parent
                for _ in range(max(leading_dots - 1, 0)):
                    root = root.parent
                roots = [root]
                relative_path = module_name[leading_dots:].replace(".", "/")
            else:
                relative_path = module_name.replace(".", "/")
        elif extension in {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"}:
            if not module_name.startswith("."):
                return None
        elif extension == ".java":
            relative_path = module_name.replace(".", "/")
        elif extension == ".rs":
            relative_path = module_name.replace("crate::", "").replace("self::", "").replace("::", "/")

        for root in roots:
            base = root / relative_path
            if extension == ".py":
                candidates = [pathlib.Path(f"{base}.py"), base / "__init__.py"]
            elif extension == ".rs":
                candidates = [pathlib.Path(f"{base}.rs"), base / "mod.rs"]
            elif extension in {".c", ".cpp", ".cc", ".cxx", ".h", ".hpp"}:
                candidates = [base]
            else:
                candidates = [base, pathlib.Path(f"{base}{extension}"), base / f"index{extension}"]

            for candidate in candidates:
                try:
                    resolved = candidate.resolve()
                except OSError:
                    continue
                if self._is_within_target(resolved) and resolved.is_file():
                    return resolved
        return None

    def relative_name(self, file_path: pathlib.Path) -> str:
        try:
            return file_path.resolve().relative_to(self.target_dir).as_posix()
        except ValueError:
            return str(file_path.resolve())

    def collect_dependency_context(
        self,
        file_path: pathlib.Path,
        content: str,
        full_dependencies: bool = False,
        max_depth: int = None,
        max_dependencies: int = None,
    ) -> OrderedDict:
        """Collect a bounded, cycle-safe recursive local dependency graph."""
        depth_limit = max_depth or config.DEPENDENCY_MAX_DEPTH
        dependency_limit = max_dependencies or config.MAX_DEPENDENCIES
        context = OrderedDict()
        visited = {file_path.resolve()}
        queue = deque((dependency, 1) for dependency in self.extract_dependencies(file_path, content))

        while queue and len(context) < dependency_limit:
            dependency, depth = queue.popleft()
            resolved = dependency.resolve()
            if resolved in visited or depth > depth_limit:
                continue
            visited.add(resolved)

            dependency_content = self.read_file(resolved)
            context[self.relative_name(resolved)] = (
                dependency_content
                if full_dependencies
                else self.get_skeleton(resolved, dependency_content)
            )
            if depth < depth_limit:
                for nested in self.extract_dependencies(resolved, dependency_content):
                    if nested.resolve() not in visited:
                        queue.append((nested, depth + 1))
        return context
