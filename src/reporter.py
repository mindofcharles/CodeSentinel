from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.text import Text
from datetime import datetime
import json
import os
import pathlib

class Reporter:
    def __init__(self):
        self.console = Console()
        self.start_time = datetime.now()
        
        # Stats counters
        self.safe_count = 0
        self.danger_count = 0
        self.warning_count = 0
        self.error_count = 0
        
        # Streaming state
        self.report_dir = "reports"
        self.scan_path = None
        self.full_report_file = None
        self.problems_report_file = None
        
        self.full_has_items = False
        self.problems_has_items = False
        self.problems_count = 0
        
        # Tree visualization
        self.last_tree = None

    def print_header(self):
        self.console.print(Panel.fit(
            "[bold green]CodeSentinel[/bold green] - AI Powered Malware Scanner",
            subtitle="v1.0.0"
        ))

    def print_target_tree(self, scanner):
        """Prints a tree view of files to be scanned."""
        root = scanner.target_dir
        tree = Tree(f"[bold blue]{root.name}[/bold blue]")

        # Helper to recursively build tree
        def build_tree(current_path, current_node):
            # Get all entries
            try:
                entries = list(current_path.iterdir())
            except PermissionError:
                return

            # Sort: Directories first, then alphabetical
            entries.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

            for entry in entries:
                # Check if ignored
                if scanner.is_ignored(entry):
                    continue

                if entry.is_dir():
                    # Recurse
                    branch = current_node.add(f"[bold blue]{entry.name}[/bold blue]")
                    build_tree(entry, branch)
                else:
                    # Check if target file
                    if scanner.is_target_file(entry):
                        current_node.add(f"{entry.name} [bold green]✔[/bold green]")
                    else:
                        current_node.add(f"[dim]{entry.name}[/dim]")

        build_tree(root, tree)
        
        self.last_tree = tree
        self.console.print("\n[bold]Project Structure:[/bold]")
        self.console.print(tree)
        self.console.print("")

    def init_reports(self, total_files: int):
        """Initializes the report directory and opens files for streaming."""
        scan_folder_name = f"scan_{self.start_time.strftime('%Y%m%d_%H%M%S')}"
        self.scan_path = os.path.join(self.report_dir, scan_folder_name)
        
        if not os.path.exists(self.scan_path):
            os.makedirs(self.scan_path)
            
        # Save Tree structure if available
        if self.last_tree:
            tree_path = os.path.join(self.scan_path, "project_structure.txt")
            with open(tree_path, "w", encoding="utf-8") as f:
                # Use a separate console to write to file, removing color codes but keeping tree structure
                file_console = Console(file=f, force_terminal=False, color_system=None, width=120)
                file_console.print(self.last_tree)
        
        # Initialize Full Report
        full_path = os.path.join(self.scan_path, "full_report.json")
        self.full_report_file = open(full_path, 'w', encoding='utf-8')
        # Write header
        header = {
            "meta": {
                "scan_time": self.start_time.isoformat(),
                "total_files": total_files
            },
            "results": []
        }
        # Write everything up to the opening bracket of results
        json_str = json.dumps(header, indent=2)
        # Remove the closing ]} and potential newline to prepare for appending
        # Expected: ... "results": [] }
        # We want: ... "results": [
        preamble = json_str.rpartition('[')[0] + '['
        self.full_report_file.write(preamble)
        self.full_report_file.flush()

        # Initialize Problems Report
        problems_path = os.path.join(self.scan_path, "problems_report.json")
        self.problems_report_file = open(problems_path, 'w', encoding='utf-8')
        # We don't know total problems yet, so we use a placeholder or omit it
        p_header = {
            "meta": {
                "scan_time": self.start_time.isoformat(),
                "note": "See summary for total count"
            },
            "results": []
        }
        p_json_str = json.dumps(p_header, indent=2)
        p_preamble = p_json_str.rpartition('[')[0] + '['
        self.problems_report_file.write(p_preamble)
        self.problems_report_file.flush()

    def log_result(self, file_path, status, analysis):
        """
        Logs a single file analysis result.
        Writes to console and streams to file.
        """
        result_obj = {
            "file": str(file_path),
            "status": status,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        }

        # Update stats and determine color/icon
        status_upper = status.upper()
        # Note: Analysis text check removed from here to prevent duplicate counting logic.
        # We rely on the 'status' passed from main.py which is now robust.
        
        is_error = False
        is_danger = False
        is_warning = False
        is_safe = False

        if status_upper.startswith("ERROR") or "ERROR:" in status_upper:
            is_error = True
            self.error_count += 1
            color = "red"
            icon = "E"
        elif "[DANGER]" in status_upper:
            is_danger = True
            self.danger_count += 1
            color = "red bold"
            icon = "!!"
        elif "[WARNING]" in status_upper:
            is_warning = True
            self.warning_count += 1
            color = "yellow"
            icon = "?"
        elif "[SAFE]" in status_upper:
            is_safe = True
            self.safe_count += 1
            color = "green"
            icon = "OK"
        else:
            # Default to warning/info if status is UNKNOWN but let's check analysis text as fallback
            # This handles cases where main.py couldn't extract a clear tag
            a_up = analysis.upper()
            if "DANGER" in a_up or "MALICIOUS" in a_up:
                is_danger = True
                self.danger_count += 1
                color = "red bold"
                icon = "!!"
            elif "WARNING" in a_up or "SUSPICIOUS" in a_up:
                is_warning = True
                self.warning_count += 1
                color = "yellow"
                icon = "?"
            else:
                self.warning_count += 1
                color = "blue"
                icon = "i"

        # CLI Output
        filename = os.path.basename(file_path)
        self.console.print(f"[{color}][{icon}] {filename}[/{color}]: {analysis}")

        # Stream to Full Report
        if self.full_report_file:
            prefix = ",\n" if self.full_has_items else "\n"
            self.full_report_file.write(prefix + json.dumps(result_obj, indent=2))
            self.full_report_file.flush()
            self.full_has_items = True

        # Stream to Problems Report (if not safe)
        if not is_safe:
            if self.problems_report_file:
                prefix = ",\n" if self.problems_has_items else "\n"
                self.problems_report_file.write(prefix + json.dumps(result_obj, indent=2))
                self.problems_report_file.flush()
                self.problems_has_items = True
                self.problems_count += 1

    def finalize_reports(self):
        """Closes the JSON arrays and files."""
        # Close Full Report
        if self.full_report_file:
            self.full_report_file.write("\n  ]\n}")
            self.full_report_file.close()
            self.full_report_file = None

        # Close Problems Report
        if self.problems_report_file:
            # We can optionally append a summary object here if strictly valid JSON allows mixed types in array (no),
            # or just close the object.
            self.problems_report_file.write("\n  ],\n")
            # Hack to add summary at the end since we couldn't at the start
            summary_footer = json.dumps({"summary": {"total_problems": self.problems_count}}, indent=2)
            # Remove opening brace to merge
            self.problems_report_file.write('  "summary": {\n    "total_problems": ' + str(self.problems_count) + '\n  }\n}')
            self.problems_report_file.close()
            self.problems_report_file = None

        if self.scan_path:
            self.console.print(f"\n[bold]Reports saved to directory:[/bold] {self.scan_path}")
            self.console.print(f"  - Full Report: full_report.json")
            self.console.print(f"  - Project Tree: project_structure.txt")
            self.console.print(f"  - Problems Only: problems_report.json ({self.problems_count} items)")

    def print_summary(self):
        """Prints a summary table."""
        table = Table(title="Scan Summary")
        table.add_column("Status", justify="right", style="cyan", no_wrap=True)
        table.add_column("Count", style="magenta")
        
        table.add_row("Safe", str(self.safe_count))
        table.add_row("Warnings", str(self.warning_count))
        table.add_row("Danger", str(self.danger_count))
        table.add_row("Errors", str(self.error_count))
        
        self.console.print("\n")
        self.console.print(table)

    def close(self):
        """Safely closes files if open (destructor-like)."""
        if self.full_report_file:
            try:
                self.full_report_file.close()
            except: pass
        if self.problems_report_file:
            try:
                self.problems_report_file.close()
            except: pass
