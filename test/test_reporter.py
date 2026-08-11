import json
import io
import tempfile
import unittest
from pathlib import Path

from rich.console import Console

from src.reporter import Reporter


class TestReporter(unittest.TestCase):
    def test_finalize_reports_writes_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = Reporter()
            reporter.console = Console(file=io.StringIO())
            reporter.report_dir = tmpdir
            reporter.init_reports(total_files=2)
            reporter.log_result("sample.py", "ERROR", "boom")
            reporter.log_result("warning.py", "[WARNING]", "review this")
            reporter.finalize_reports("completed")

            scan_dirs = list(Path(tmpdir).iterdir())
            self.assertEqual(1, len(scan_dirs))

            with open(scan_dirs[0] / "full_report.json", encoding="utf-8") as f:
                full_report = json.load(f)
            with open(scan_dirs[0] / "problems_report.json", encoding="utf-8") as f:
                problems_report = json.load(f)

            self.assertEqual("sample.py", full_report["results"][0]["file"])
            self.assertEqual(1, problems_report["summary"]["total_problems"])
            self.assertEqual("warning.py", problems_report["results"][0]["file"])
            self.assertEqual(1, full_report["summary"]["errors"])
            self.assertEqual("completed", full_report["meta"]["scan_status"])
            self.assertEqual(1.0, full_report["meta"]["coverage"])

    def test_finalize_empty_reports_writes_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = Reporter()
            reporter.console = Console(file=io.StringIO())
            reporter.report_dir = tmpdir
            reporter.init_reports(total_files=0)
            reporter.finalize_reports()

            scan_dirs = list(Path(tmpdir).iterdir())
            self.assertEqual(1, len(scan_dirs))

            with open(scan_dirs[0] / "full_report.json", encoding="utf-8") as f:
                full_report = json.load(f)
            with open(scan_dirs[0] / "problems_report.json", encoding="utf-8") as f:
                problems_report = json.load(f)

            self.assertEqual([], full_report["results"])
            self.assertEqual([], problems_report["results"])
            self.assertEqual(0, problems_report["summary"]["total_problems"])

    def test_interaction_logs_are_opt_in_and_redacted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = Reporter(save_interaction_logs=True, redact_interaction_logs=True)
            reporter.console = Console(file=io.StringIO())
            reporter.report_dir = tmpdir
            reporter.init_reports(total_files=1)
            reporter.log_interaction(
                "src/sample.py",
                {
                    "api_key": "sk-secretsecretsecret",
                    "request_messages": [{"content": "token sk-anothersecret12345"}],
                },
            )

            with open(reporter.logs_path / "src/sample.py.log", encoding="utf-8") as log_file:
                saved = log_file.read()
            self.assertNotIn("secretsecretsecret", saved)
            self.assertNotIn("anothersecret12345", saved)
            self.assertIn("REDACTED", saved)


if __name__ == "__main__":
    unittest.main()
