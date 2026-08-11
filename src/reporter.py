import json
import os
import pathlib
import re
import tempfile
from datetime import datetime

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree


class Reporter:
    def __init__(
        self,
        save_interaction_logs=False,
        redact_interaction_logs=True,
        report_sync_interval=25,
    ):
        self.console = Console()
        self.start_time = datetime.now()
        self.save_interaction_logs = save_interaction_logs
        self.redact_interaction_logs = redact_interaction_logs
        self.report_sync_interval = max(1, int(report_sync_interval))

        self.safe_count = 0
        self.danger_count = 0
        self.warning_count = 0
        self.error_count = 0
        self.processed_count = 0

        self.report_dir = "reports"
        self.scan_path = None
        self.logs_path = None
        self.full_jsonl_path = None
        self.problems_jsonl_path = None
        self.total_files = 0
        self.problems_count = 0
        self.last_tree = None
        self.finalized = False

    def print_header(self):
        self.console.print(
            Panel.fit("[bold green]CodeSentinel[/bold green] - AI Powered Malware Scanner")
        )

    def print_target_tree(self, scanner):
        """Print a cycle-safe tree without following directory symlinks."""
        root = scanner.target_dir
        tree = Tree(f"[bold blue]{escape(root.name)}[/bold blue]")
        visited = {root.resolve()}

        def build_tree(current_path, current_node):
            try:
                entries = sorted(
                    current_path.iterdir(), key=lambda entry: (not entry.is_dir(), entry.name.lower())
                )
            except (OSError, PermissionError):
                return

            for entry in entries:
                if scanner.is_ignored(entry):
                    continue
                if entry.is_symlink():
                    current_node.add(f"[dim cyan]{escape(entry.name)} → symlink[/dim cyan]")
                    continue
                try:
                    if entry.is_dir():
                        resolved = entry.resolve()
                        if resolved in visited:
                            current_node.add(
                                f"[dim cyan]{escape(entry.name)} → already visited[/dim cyan]"
                            )
                            continue
                        visited.add(resolved)
                        branch = current_node.add(f"[bold blue]{escape(entry.name)}[/bold blue]")
                        build_tree(entry, branch)
                    elif scanner.is_target_file(entry):
                        current_node.add(f"{escape(entry.name)} [bold green]✔[/bold green]")
                    else:
                        current_node.add(f"[dim]{escape(entry.name)}[/dim]")
                except OSError:
                    continue

        build_tree(root, tree)
        self.last_tree = tree
        self.console.print("\n[bold]Project Structure:[/bold]")
        self.console.print(tree)
        self.console.print("")

    def init_reports(self, total_files: int):
        scan_folder_name = f"scan_{self.start_time.strftime('%Y%m%d_%H%M%S')}"
        self.scan_path = pathlib.Path(self.report_dir) / scan_folder_name
        if self.scan_path.exists():
            scan_folder_name += f"_{self.start_time.strftime('%f')}"
            self.scan_path = pathlib.Path(self.report_dir) / scan_folder_name
        self.scan_path.mkdir(parents=True, exist_ok=False)
        self.logs_path = self.scan_path / "logs"
        if self.save_interaction_logs:
            self.logs_path.mkdir(parents=True, exist_ok=True)

        self.total_files = total_files
        self.full_jsonl_path = self.scan_path / "full_report.jsonl"
        self.problems_jsonl_path = self.scan_path / "problems_report.jsonl"
        self.full_jsonl_path.touch(mode=0o600)
        self.problems_jsonl_path.touch(mode=0o600)

        if self.last_tree:
            tree_path = self.scan_path / "project_structure.txt"
            with open(tree_path, "w", encoding="utf-8") as tree_file:
                file_console = Console(
                    file=tree_file, force_terminal=False, color_system=None, width=120
                )
                file_console.print(self.last_tree)

        self._write_progress("running")
        self._write_final_json_files("running")

    def _meta(self, scan_status: str):
        meta = {
            "scan_time": self.start_time.isoformat(),
            "scan_status": scan_status,
            "total_files": self.total_files,
            "processed_files": self.processed_count,
            "coverage": (self.processed_count / self.total_files) if self.total_files else 1.0,
        }
        if scan_status != "running":
            meta["end_time"] = datetime.now().isoformat()
        return meta

    def _atomic_write_json(self, path: pathlib.Path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_name = temporary_file.name
                json.dump(value, temporary_file, indent=2, ensure_ascii=False)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, path)
        finally:
            if temporary_name and os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def _write_progress(self, scan_status: str):
        if not self.scan_path:
            return
        self._atomic_write_json(
            self.scan_path / "progress.json",
            {
                "meta": self._meta(scan_status),
                "counts": {
                    "safe": self.safe_count,
                    "warnings": self.warning_count,
                    "danger": self.danger_count,
                    "errors": self.error_count,
                },
            },
        )

    def _atomic_write_report(self, path, jsonl_path, meta, summary):
        """Build a JSON report from JSONL in constant memory, then atomically replace it."""
        temporary_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_name = temporary_file.name
                temporary_file.write('{\n  "meta": ')
                json.dump(meta, temporary_file, ensure_ascii=False)
                temporary_file.write(',\n  "results": [')
                first = True
                if jsonl_path and jsonl_path.exists():
                    with open(jsonl_path, "r", encoding="utf-8") as jsonl_file:
                        for line_number, line in enumerate(jsonl_file, 1):
                            if not line.strip():
                                continue
                            try:
                                record = json.loads(line)
                            except json.JSONDecodeError as exc:
                                raise RuntimeError(
                                    f"Corrupt JSONL record at {jsonl_path}:{line_number}: {exc}"
                                ) from exc
                            temporary_file.write("\n    " if first else ",\n    ")
                            json.dump(record, temporary_file, ensure_ascii=False)
                            first = False
                if not first:
                    temporary_file.write("\n  ")
                temporary_file.write('],\n  "summary": ')
                json.dump(summary, temporary_file, ensure_ascii=False)
                temporary_file.write("\n}\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, path)
        finally:
            if temporary_name and os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def _write_final_json_files(self, scan_status: str):
        if not self.scan_path:
            return
        meta = self._meta(scan_status)
        self._atomic_write_report(
            self.scan_path / "full_report.json",
            self.full_jsonl_path,
            meta,
            {
                "safe": self.safe_count,
                "warnings": self.warning_count,
                "danger": self.danger_count,
                "errors": self.error_count,
            },
        )
        self._atomic_write_report(
            self.scan_path / "problems_report.json",
            self.problems_jsonl_path,
            meta,
            {"total_problems": self.problems_count},
        )

    @staticmethod
    def _append_jsonl(path: pathlib.Path, value, sync=False):
        with open(path, "a", encoding="utf-8") as jsonl_file:
            jsonl_file.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
            jsonl_file.flush()
            if sync:
                os.fsync(jsonl_file.fileno())

    @staticmethod
    def _redact(value):
        if isinstance(value, dict):
            redacted = {}
            for key, item in value.items():
                if re.search(
                    r"api[_-]?key|authorization|password|secret|access[_-]?token|bearer[_-]?token",
                    str(key),
                    re.I,
                ):
                    redacted[key] = "[REDACTED]"
                else:
                    redacted[key] = Reporter._redact(item)
            return redacted
        if isinstance(value, list):
            return [Reporter._redact(item) for item in value]
        if isinstance(value, str):
            value = re.sub(r"\bsk-[A-Za-z0-9_-]{12,}\b", "[REDACTED_API_KEY]", value)
            value = re.sub(
                r"-----BEGIN [^-]+-----.*?-----END [^-]+-----",
                "[REDACTED_PEM_BLOCK]",
                value,
                flags=re.DOTALL,
            )
        return value

    def log_interaction(self, file_path, interaction_data):
        if not self.save_interaction_logs or not self.logs_path:
            return
        relative_path = pathlib.PurePosixPath(str(file_path).replace("\\", "/"))
        if relative_path.is_absolute() or ".." in relative_path.parts:
            relative_path = pathlib.PurePosixPath("unsafe-path") / relative_path.name
        log_file = self.logs_path.joinpath(*relative_path.parts).with_suffix(
            relative_path.suffix + ".log"
        )
        log_file.parent.mkdir(parents=True, exist_ok=True)
        payload = self._redact(interaction_data) if self.redact_interaction_logs else interaction_data
        self._atomic_write_json(log_file, payload)

    def log_result(self, file_path, status, analysis):
        status_upper = str(status).upper()
        analysis_text = str(analysis)
        if "[DANGER]" in status_upper:
            category, color, icon = "danger", "red bold", "!!"
            self.danger_count += 1
        elif "[WARNING]" in status_upper:
            category, color, icon = "warning", "yellow", "?"
            self.warning_count += 1
        elif "[SAFE]" in status_upper:
            category, color, icon = "safe", "green", "OK"
            self.safe_count += 1
        else:
            category, color, icon = "error", "red", "E"
            status = "ERROR"
            self.error_count += 1

        result = {
            "file": str(file_path),
            "status": status,
            "analysis": analysis_text,
            "timestamp": datetime.now().isoformat(),
        }
        self.processed_count += 1
        self.console.print(
            f"[{color}][{icon}] {escape(os.path.basename(str(file_path)))}[/{color}]: "
            f"{escape(analysis_text)}"
        )

        should_sync = self.processed_count % self.report_sync_interval == 0
        if self.full_jsonl_path:
            self._append_jsonl(self.full_jsonl_path, result, sync=should_sync)
        if category in {"warning", "danger"} and self.problems_jsonl_path:
            self._append_jsonl(self.problems_jsonl_path, result, sync=should_sync)
            self.problems_count += 1
        if should_sync:
            self._write_progress("running")

    def finalize_reports(self, scan_status="completed"):
        if self.finalized or not self.scan_path:
            return
        self._write_progress(scan_status)
        self._write_final_json_files(scan_status)
        self.finalized = True
        self.console.print(f"\n[bold]Reports saved to directory:[/bold] {self.scan_path}")
        self.console.print("  - Full Report: full_report.json")
        self.console.print("  - Streaming Records: full_report.jsonl")
        self.console.print(f"  - Problems Only: problems_report.json ({self.problems_count} items)")
        if self.last_tree:
            self.console.print("  - Project Tree: project_structure.txt")
        if self.save_interaction_logs:
            self.console.print("  - Redacted Interaction Logs: logs/ directory")

    def print_summary(self):
        table = Table(title="Scan Summary")
        table.add_column("Status", justify="right", style="cyan", no_wrap=True)
        table.add_column("Count", style="magenta")
        table.add_row("Safe", str(self.safe_count))
        table.add_row("Warnings", str(self.warning_count))
        table.add_row("Danger", str(self.danger_count))
        table.add_row("Errors", str(self.error_count))
        self.console.print("\n")
        self.console.print(table)
