import pathlib
import tempfile
import unittest

import tree_sitter

from src.config_parser import config
from src.scanner import Scanner


class TestTreeSitterConfig(unittest.TestCase):
    def test_all_configured_parsers_load_and_queries_compile(self):
        samples = {
            "sample.py": "def sample(): pass\n",
            "sample.js": "import './dependency.js';\nfunction sample() {}\n",
            "dependency.js": "export const value = 1;\n",
            "sample.ts": "import './dependency';\nfunction sample(): void {}\n",
            "dependency.ts": "export const value: number = 1;\n",
            "sample.tsx": "const sample = () => <div />\n",
            "sample.cpp": "void sample() {}\n",
            "sample.go": "package sample\nfunc sample() {}\n",
            "sample.rs": "fn sample() {}\n",
            "Sample.java": "class Sample { void sample() {} }\n",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            for filename, content in samples.items():
                (root / filename).write_text(content, encoding="utf-8")
            scanner = Scanner(str(root))
            scanner.pre_scan_check()

            for language_name, language_config in config.TREE_SITTER.items():
                extension = language_config["extensions"][0]
                self.assertIn(extension, scanner.ts_languages, language_name)
                language = scanner.ts_languages[extension]
                tree_sitter.Query(language, language_config["skeleton_query"])
                tree_sitter.Query(language, language_config["deps_query"])

            js_path = root / "sample.js"
            ts_path = root / "sample.ts"
            self.assertIn(
                "dependency.js",
                {path.name for path in scanner.extract_dependencies(js_path, scanner.read_file(js_path))},
            )
            self.assertIn(
                "dependency.ts",
                {path.name for path in scanner.extract_dependencies(ts_path, scanner.read_file(ts_path))},
            )
