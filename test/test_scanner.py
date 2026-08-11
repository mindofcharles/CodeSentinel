import unittest
import os
import pathlib
import sys
import tempfile
from src.scanner import FileReadError, Scanner
from src.config_parser import config

class TestScanner(unittest.TestCase):
    def setUp(self):
        self.base_dir = pathlib.Path(__file__).parent.parent
        self.fixtures_dir = self.base_dir / "test" / "fixtures"
        self.scanner = Scanner(str(self.fixtures_dir))
        self.scanner.pre_scan_check()

    def test_has_tree_sitter(self):
        from src.scanner import HAS_TREE_SITTER
        self.assertTrue(HAS_TREE_SITTER)

    def test_get_files(self):
        files = list(self.scanner.get_files())
        filenames = [f.name for f in files]
        self.assertIn("safe.py", filenames)
        self.assertIn("danger.py", filenames)

    def test_read_file(self):
        safe_path = self.fixtures_dir / "safe.py"
        content = self.scanner.read_file(safe_path)
        self.assertIn("def hello():", content)

    def test_is_target_file(self):
        self.assertTrue(self.scanner.is_target_file(pathlib.Path("test.py")))
        self.assertTrue(self.scanner.is_target_file(pathlib.Path("test.js")))
        self.assertFalse(self.scanner.is_target_file(pathlib.Path("test.txt")))

    def test_extract_dependencies(self):
        import_test_path = self.fixtures_dir / "import_test.py"
        content = self.scanner.read_file(import_test_path)
        deps = self.scanner.extract_dependencies(import_test_path, content)
        
        # Should find 'safe.py' as a dependency
        dep_names = [d.name for d in deps]
        self.assertIn("safe.py", dep_names)

    def test_extract_relative_import_dependencies(self):
        main_path = self.base_dir / "src" / "main.py"
        scanner = Scanner(str(self.base_dir / "src"))
        scanner.pre_scan_check()

        deps = scanner.extract_dependencies(main_path, scanner.read_file(main_path))
        dep_names = {d.name for d in deps}

        self.assertIn("scanner.py", dep_names)
        self.assertIn("ai_engine.py", dep_names)
        self.assertIn("reporter.py", dep_names)
        self.assertIn("config_parser.py", dep_names)
        self.assertNotIn("Scanner.py", dep_names)

    def test_skeleton_does_not_include_body_capture_lines(self):
        safe_path = self.fixtures_dir / "safe.py"
        skeleton = self.scanner.get_skeleton(safe_path)

        self.assertIn("def hello(): ...", skeleton)
        self.assertNotIn('print("Hello world") ...', skeleton)

    def test_read_file_failure_raises(self):
        missing_path = self.fixtures_dir / "missing.py"

        with self.assertRaises(FileReadError):
            self.scanner.read_file(missing_path)

    def test_recursive_dependencies_use_distinct_relative_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            (root / "pkg_a").mkdir()
            (root / "pkg_b").mkdir()
            (root / "main.py").write_text("import pkg_a.mod\nimport pkg_b.mod\n", encoding="utf-8")
            (root / "pkg_a/mod.py").write_text("import pkg_a.helper\n", encoding="utf-8")
            (root / "pkg_b/mod.py").write_text("import pkg_b.helper\n", encoding="utf-8")
            (root / "pkg_a/helper.py").write_text("def a(): pass\n", encoding="utf-8")
            (root / "pkg_b/helper.py").write_text("def b(): pass\n", encoding="utf-8")
            scanner = Scanner(str(root))
            scanner.pre_scan_check()

            main_path = root / "main.py"
            context = scanner.collect_dependency_context(
                main_path,
                scanner.read_file(main_path),
                max_depth=2,
            )

            self.assertEqual(
                {"pkg_a/mod.py", "pkg_b/mod.py", "pkg_a/helper.py", "pkg_b/helper.py"},
                set(context),
            )

    def test_external_file_symlink_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = pathlib.Path(tmpdir)
            target = base / "target"
            target.mkdir()
            external = base / "external.py"
            external.write_text("print('outside')", encoding="utf-8")
            (target / "linked.py").symlink_to(external)
            scanner = Scanner(str(target))

            self.assertEqual([], list(scanner.get_files()))

if __name__ == "__main__":
    unittest.main()
