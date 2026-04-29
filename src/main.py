import argparse
import sys
import os
from .scanner import FileReadError, Scanner
from .ai_engine import AIEngine
from .reporter import Reporter
from .config_parser import config

def main():
    parser = argparse.ArgumentParser(description="CodeSentinel - AI Powered Project Scanner")
    parser.add_argument("--dir", "-d", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument("--dry-run", action="store_true", help="List files without scanning")
    parser.add_argument("--url", help="Override API Base URL")
    parser.add_argument("--env-key", help="Environment variable for API Key")
    parser.add_argument("--deep", action="store_true", help="Enable deep analysis mode")
    parser.add_argument("--full-deps", action="store_true", help="Include full dependency code")
    parser.add_argument("--model", help="Specify the AI model to use")
    parser.add_argument("--max-tokens", type=int, help="Maximum tokens")
    parser.add_argument("--temperature", type=float, help="Temperature")
    
    args = parser.parse_args()

    reporter = Reporter()
    reporter.print_header()

    # Update config from args
    if args.model: config.AI_MODEL = args.model
    if args.max_tokens: config.AI_MAX_TOKENS = args.max_tokens
    if args.temperature is not None: config.AI_TEMPERATURE = args.temperature
    if args.url: config.OPENAI_BASE_URL = args.url
    if args.env_key:
        val = os.getenv(args.env_key)
        if val: config.OPENAI_API_KEY = val

    if not config.AI_MODEL and not args.dry_run:
        reporter.console.print("[bold red]Error:[/bold red] AI_MODEL is not set.")
        sys.exit(1)

    target_path = os.path.abspath(args.dir)
    if not os.path.exists(target_path):
        reporter.console.print(f"[bold red]Error:[/bold red] Target directory '{target_path}' does not exist.")
        sys.exit(1)

    scanner = Scanner(target_path)
    ai_engine = AIEngine()

    # Pre-scan checks
    scanner.pre_scan_check()
    
    if not args.dry_run:
        reporter.console.print("Checking AI API connectivity...", end="\r")
        if not ai_engine.check_connectivity():
            reporter.console.print("[bold red]Error:[/bold red] Could not connect to AI API. Check your URL and Key.")
            sys.exit(1)
        reporter.console.print("[green]AI API Connected successfully.[/green]   ")

    reporter.console.print(f"Target: [bold]{target_path}[/bold]")
    reporter.console.print(f"Model: [bold]{config.AI_MODEL}[/bold]")
    mode_str = "Deep (Dependency Tracking)" if args.deep else "Standard"
    reporter.console.print(f"Mode: [bold]{mode_str}[/bold]")
    
    reporter.print_target_tree(scanner)
    reporter.console.print("Scanning files...\n")

    files_found = 0
    analyzed_files = set()
    
    reports_initialized = False
    interrupted = False
    fatal_error = None
    
    try:
        try:
            all_files = list(scanner.get_files())
            if not args.dry_run:
                reporter.init_reports(len(all_files))
                reports_initialized = True
                
            for file_path in all_files:
                files_found += 1
                rel_file_path = os.path.relpath(file_path, target_path)

                if args.dry_run:
                    reporter.console.print(f"[dim]Found: {rel_file_path}[/dim]")
                    continue

                try:
                    analysis_data = None
                    interaction_log = None
                    if args.deep:
                        if file_path in analyzed_files: continue
                        
                        content = scanner.read_file(file_path)
                        if not content.strip():
                            reporter.log_result(rel_file_path, "[SAFE]", "Empty file")
                            continue

                        deps_paths = scanner.extract_dependencies(file_path, content)
                        if not deps_paths:
                            reporter.console.print(f"[dim]Analyzing {rel_file_path}...[/dim]", end="\r")
                            analysis_data, interaction_log = ai_engine.analyze_code(file_path.name, content)
                        else:
                            deps_context = {}
                            for dp in deps_paths:
                                deps_context[dp.name] = scanner.read_file(dp) if args.full_deps else scanner.get_skeleton(dp)
                            
                            reporter.console.print(f"[dim]Deep Analyzing {rel_file_path}...[/dim]", end="\r")
                            analysis_data, interaction_log = ai_engine.analyze_deep(file_path.name, content, deps_context, full_context=args.full_deps)
                        
                        analyzed_files.add(file_path)
                    else:
                        content = scanner.read_file(file_path)
                        if not content.strip():
                            reporter.log_result(rel_file_path, "[SAFE]", "Empty file")
                            continue

                        reporter.console.print(f"[dim]Analyzing {rel_file_path}...[/dim]", end="\r")
                        analysis_data, interaction_log = ai_engine.analyze_code(file_path.name, content)

                    if interaction_log:
                        reporter.log_interaction(rel_file_path, interaction_log)

                    # Process structured result
                    if analysis_data:
                        status = analysis_data.get("status", "UNKNOWN")
                        reason = analysis_data.get("reason", "No reason provided.")
                        
                        # Format status for reporter
                        if status == "SAFE": status_tag = "[SAFE]"
                        elif status == "WARNING": status_tag = "[WARNING]"
                        elif status == "DANGER": status_tag = "[DANGER]"
                        else: status_tag = "ERROR"
                        
                        reporter.log_result(rel_file_path, status_tag, reason)
                except FileReadError as e:
                    reporter.log_result(rel_file_path, "ERROR", str(e))

        except KeyboardInterrupt:
            interrupted = True
            reporter.console.print("\n[bold yellow]Scan interrupted by user.[/bold yellow]")
        except Exception as e:
            fatal_error = e
            reporter.console.print(f"\n[bold red]Fatal error:[/bold red] {e}")
    finally:
        if files_found == 0:
            reporter.console.print("[yellow]No relevant source files found to scan.[/yellow]")
        elif not args.dry_run:
            reporter.print_summary()
            if reports_initialized:
                reporter.finalize_reports()

    if fatal_error:
        sys.exit(1)
    if interrupted:
        sys.exit(130)

if __name__ == "__main__":
    main()
