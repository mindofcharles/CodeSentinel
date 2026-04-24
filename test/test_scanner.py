import unittest
import os
import pathlib
import sys
from src.scanner import Scanner
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

if __name__ == "__main__":
    unittest.main()
