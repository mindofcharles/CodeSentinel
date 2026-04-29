import pathlib
import subprocess
import sys
import unittest


class TestMainCLI(unittest.TestCase):
    def test_dry_run_scans_fixtures_without_ai_or_reports(self):
        project_root = pathlib.Path(__file__).resolve().parent.parent

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.main",
                "--dir",
                "test/fixtures",
                "--dry-run",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Found: safe.py", result.stdout)
        self.assertIn("Found: danger.py", result.stdout)
        self.assertNotIn("Checking AI API connectivity", result.stdout)


if __name__ == "__main__":
    unittest.main()
