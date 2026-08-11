import pathlib
import subprocess
import sys
import os
import unittest
import tempfile
from unittest.mock import patch

from src import main as main_module


class TestMainCLI(unittest.TestCase):
    def test_dry_run_scans_fixtures_without_ai_or_reports(self):
        project_root = pathlib.Path(__file__).resolve().parent.parent
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

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
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Found: safe.py", result.stdout)
        self.assertIn("Found: danger.py", result.stdout)
        self.assertNotIn("Checking AI API connectivity", result.stdout)

    def test_custom_config_path_is_applied(self):
        project_root = pathlib.Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "custom.yaml"
            config_path.write_text(
                "target_extensions: ['.py']\nignore_dirs: []\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.main",
                    "--config",
                    str(config_path),
                    "--dir",
                    "test/fixtures",
                    "--dry-run",
                    "--no-tree",
                ],
                cwd=project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Found: safe.py", result.stdout)

    def test_unexpected_file_failure_is_recorded_and_scan_continues(self):
        recorded = []

        class FakeConsole:
            def print(self, *args, **kwargs):
                pass

        class FakeReporter:
            def __init__(self, **kwargs):
                self.console = FakeConsole()
                self.last_tree = None

            def print_header(self):
                pass

            def init_reports(self, total_files):
                self.total_files = total_files

            def log_result(self, path, status, reason):
                recorded.append((path, status, reason))

            def log_interaction(self, path, interaction):
                pass

            def print_summary(self):
                pass

            def finalize_reports(self, status):
                self.final_status = status

        class FakeScanner:
            def __init__(self, target):
                self.target_dir = pathlib.Path(target)

            def pre_scan_check(self, files=None):
                pass

            def get_files(self):
                return iter([self.target_dir / "bad.py", self.target_dir / "good.py"])

            def read_file(self, path):
                if path.name == "bad.py":
                    raise RuntimeError("parser exploded")
                return "print('ok')"

        class FakeAIEngine:
            def check_connectivity(self):
                return True

            def analyze_code(self, filename, content):
                return {"status": "SAFE", "reason": "ok"}, {}

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(main_module, "Reporter", FakeReporter),
                patch.object(main_module, "Scanner", FakeScanner),
                patch.object(main_module, "AIEngine", FakeAIEngine),
                patch.object(
                    sys,
                    "argv",
                    [
                        "codesentinel",
                        "--dir",
                        tmpdir,
                        "--skip-connectivity-check",
                        "--no-tree",
                    ],
                ),
            ):
                exit_code = main_module.main()

        self.assertEqual(0, exit_code)
        self.assertEqual(2, len(recorded))
        self.assertEqual("ERROR", recorded[0][1])
        self.assertEqual("[SAFE]", recorded[1][1])


if __name__ == "__main__":
    unittest.main()
