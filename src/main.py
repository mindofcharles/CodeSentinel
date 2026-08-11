import argparse
import os
import sys

from rich.markup import escape

from .ai_engine import AIEngine
from .config_parser import ConfigError, config
from .reporter import Reporter
from .scanner import FileReadError, Scanner


def build_argument_parser():
    parser = argparse.ArgumentParser(description="CodeSentinel - AI Powered Project Scanner")
    parser.add_argument("--dir", "-d", default=".", help="Directory to scan")
    parser.add_argument("--config", help="Path to the main YAML configuration")
    parser.add_argument("--dry-run", action="store_true", help="List files without AI analysis")
    parser.add_argument("--url", help="Override API base URL")
    parser.add_argument("--env-key", help="Environment variable containing the API key")
    parser.add_argument("--deep", action="store_true", help="Enable recursive dependency analysis")
    parser.add_argument("--full-deps", action="store_true", help="Include dependency implementation code")
    parser.add_argument("--dependency-depth", type=int, help="Maximum recursive dependency depth")
    parser.add_argument("--max-dependencies", type=int, help="Maximum dependencies per file")
    parser.add_argument("--model", help="AI model name")
    parser.add_argument("--max-tokens", type=int, help="Maximum response tokens")
    parser.add_argument("--context-window", type=int, help="Model context-window tokens")
    parser.add_argument("--tokenizer", help="Path to a tokenizer.json file")
    parser.add_argument("--temperature", type=float, help="Sampling temperature")
    parser.add_argument("--save-prompts", action="store_true", help="Save redacted AI interactions")
    parser.add_argument("--no-redact-logs", action="store_true", help="Disable interaction-log redaction")
    parser.add_argument("--follow-symlinks", action="store_true", help="Follow in-project symlinks")
    parser.add_argument("--skip-connectivity-check", action="store_true", help="Skip models.list API check")
    parser.add_argument("--no-tree", action="store_true", help="Do not render the project tree")
    return parser


def apply_cli_config(args):
    if args.config:
        config.load(args.config)
    if args.model is not None:
        config.AI_MODEL = args.model
    if args.max_tokens is not None:
        config.AI_MAX_TOKENS = args.max_tokens
    if args.context_window is not None:
        config.AI_CONTEXT_WINDOW = args.context_window
    if args.tokenizer is not None:
        config.TOKENIZER_PATH = os.path.abspath(os.path.expanduser(args.tokenizer))
    if args.temperature is not None:
        config.AI_TEMPERATURE = args.temperature
    if args.url is not None:
        config.OPENAI_BASE_URL = args.url
    if args.dependency_depth is not None:
        config.DEPENDENCY_MAX_DEPTH = args.dependency_depth
    if args.max_dependencies is not None:
        config.MAX_DEPENDENCIES = args.max_dependencies
    if args.save_prompts:
        config.SAVE_INTERACTION_LOGS = True
    if args.no_redact_logs:
        config.REDACT_INTERACTION_LOGS = False
    if args.follow_symlinks:
        config.FOLLOW_SYMLINKS = True
    if args.env_key:
        value = os.getenv(args.env_key)
        if not value:
            raise ConfigError(f"Environment variable '{args.env_key}' is not set or empty.")
        config.OPENAI_API_KEY = value
    config._validate()


def main():
    args = build_argument_parser().parse_args()
    try:
        apply_cli_config(args)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    reporter = Reporter(
        save_interaction_logs=config.SAVE_INTERACTION_LOGS,
        redact_interaction_logs=config.REDACT_INTERACTION_LOGS,
        report_sync_interval=config.REPORT_SYNC_INTERVAL,
    )
    reporter.print_header()

    if not config.AI_MODEL and not args.dry_run:
        reporter.console.print("[bold red]Error:[/bold red] AI model is not set.")
        return 2

    target_path = os.path.abspath(args.dir)
    if not os.path.isdir(target_path):
        reporter.console.print(
            f"[bold red]Error:[/bold red] Target directory '{escape(target_path)}' does not exist."
        )
        return 2

    scanner = Scanner(target_path)
    reports_initialized = False
    interrupted = False
    fatal_error = None
    files_found = 0

    try:
        all_files = list(scanner.get_files())
        scanner.pre_scan_check(all_files)
        files_found = len(all_files)

        ai_engine = None
        if not args.dry_run:
            ai_engine = AIEngine()
            if not args.skip_connectivity_check:
                reporter.console.print("Checking AI API connectivity...", end="\r")
                if not ai_engine.check_connectivity():
                    reporter.console.print(
                        "[bold red]Error:[/bold red] Could not connect to AI API. "
                        "Check the URL and key, or use --skip-connectivity-check."
                    )
                    return 1
                reporter.console.print("[green]AI API connected successfully.[/green]   ")

        reporter.console.print(f"Target: [bold]{escape(target_path)}[/bold]")
        reporter.console.print(f"Model: [bold]{escape(config.AI_MODEL)}[/bold]")
        mode = "Deep (Recursive Dependency Tracking)" if args.deep else "Standard"
        reporter.console.print(f"Mode: [bold]{mode}[/bold]")
        reporter.console.print(f"Files: [bold]{files_found}[/bold]")

        if not args.no_tree and files_found <= config.MAX_TREE_ENTRIES:
            reporter.print_target_tree(scanner)
        elif not args.no_tree:
            reporter.console.print(
                f"[yellow]Project tree skipped: {files_found} target files exceed "
                f"max_tree_entries={config.MAX_TREE_ENTRIES}.[/yellow]"
            )

        if args.dry_run:
            for file_path in all_files:
                reporter.console.print(
                    f"[dim]Found: {escape(os.path.relpath(file_path, target_path))}[/dim]"
                )
            if not all_files:
                reporter.console.print("[yellow]No relevant source files found.[/yellow]")
            return 0

        reporter.init_reports(files_found)
        reports_initialized = True
        reporter.console.print("Scanning files...\n")

        for file_path in all_files:
            relative_path = os.path.relpath(file_path, target_path)
            interaction_log = None
            try:
                content = scanner.read_file(file_path)
                if not content.strip():
                    reporter.log_result(relative_path, "[SAFE]", "Empty file")
                    continue

                if args.deep:
                    dependencies = scanner.collect_dependency_context(
                        file_path,
                        content,
                        full_dependencies=args.full_deps,
                    )
                    if dependencies:
                        reporter.console.print(
                            f"[dim]Deep analyzing {escape(relative_path)}...[/dim]", end="\r"
                        )
                        analysis, interaction_log = ai_engine.analyze_deep(
                            file_path.name,
                            content,
                            dependencies,
                        )
                    else:
                        reporter.console.print(
                            f"[dim]Analyzing {escape(relative_path)}...[/dim]", end="\r"
                        )
                        analysis, interaction_log = ai_engine.analyze_code(file_path.name, content)
                else:
                    reporter.console.print(
                        f"[dim]Analyzing {escape(relative_path)}...[/dim]", end="\r"
                    )
                    analysis, interaction_log = ai_engine.analyze_code(file_path.name, content)

                if interaction_log:
                    reporter.log_interaction(relative_path, interaction_log)

                status = analysis.get("status", "ERROR") if isinstance(analysis, dict) else "ERROR"
                reason = (
                    analysis.get("reason", "No reason provided.")
                    if isinstance(analysis, dict)
                    else "AI returned an invalid result object."
                )
                status_tag = f"[{status}]" if status in {"SAFE", "WARNING", "DANGER"} else "ERROR"
                reporter.log_result(relative_path, status_tag, reason)
            except KeyboardInterrupt:
                raise
            except FileReadError as exc:
                reporter.log_result(relative_path, "ERROR", str(exc))
            except Exception as exc:
                reporter.log_result(
                    relative_path,
                    "ERROR",
                    f"Unexpected per-file failure ({type(exc).__name__}): {exc}",
                )

    except KeyboardInterrupt:
        interrupted = True
        reporter.console.print("\n[bold yellow]Scan interrupted by user.[/bold yellow]")
    except Exception as exc:
        fatal_error = exc
        reporter.console.print(f"\n[bold red]Fatal error:[/bold red] {escape(str(exc))}")
    finally:
        if reports_initialized:
            reporter.print_summary()
            status = "failed" if fatal_error else "interrupted" if interrupted else "completed"
            try:
                reporter.finalize_reports(status)
            except Exception as report_error:
                fatal_error = fatal_error or report_error
                reporter.console.print(
                    f"[bold red]Failed to finalize reports:[/bold red] {escape(str(report_error))}"
                )
        elif files_found == 0 and not args.dry_run:
            reporter.console.print("[yellow]No relevant source files found to scan.[/yellow]")

    if interrupted:
        return 130
    if fatal_error:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
