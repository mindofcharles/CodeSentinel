import argparse
import sys
import os
from .scanner import Scanner
from .ai_engine import AIEngine
from .reporter import Reporter
from .config import config

def extract_status(text: str) -> str:
    """Extracts a short status tag from the analysis text."""
    text_upper = text.upper()
    
    # Prioritize explicit tags
    if "[DANGER]" in text_upper: return "[DANGER]"
    if "[WARNING]" in text_upper: return "[WARNING]"
    if "[SAFE]" in text_upper: return "[SAFE]"
    
    # Strict ERROR detection: Must start with ERROR or contain ERROR:
    if text_upper.startswith("ERROR") or "ERROR:" in text_upper:
        return "ERROR"
        
    return "UNKNOWN"

def main():
    parser = argparse.ArgumentParser(description="CodeSentinel - AI Powered Project Scanner")
    parser.add_argument("--dir", "-d", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument("--dry-run", action="store_true", help="List files without scanning")
    parser.add_argument("--url", help="Override API Base URL (e.g. https://api.openai.com/v1)")
    parser.add_argument("--env-key", help="Name of the environment variable holding the API Key (default: OPENAI_API_KEY)")
    parser.add_argument("--deep", action="store_true", help="Enable deep analysis mode (follows imports/dependencies)")
    parser.add_argument("--full-deps", action="store_true", help="Include full dependency code instead of skeletons in deep analysis")
    parser.add_argument("--model", help="Specify the AI model to use")
    parser.add_argument("--max-tokens", type=int, help="Maximum tokens for AI response")
    parser.add_argument("--temperature", type=float, help="Temperature for AI sampling (0.0 - 1.0)")
    
    args = parser.parse_args()

    # Initialize components
    reporter = Reporter()
    reporter.print_header()

    # Update configuration
    if args.model:
        config.AI_MODEL = args.model

    if args.max_tokens:
        config.AI_MAX_TOKENS = args.max_tokens
    
    if args.temperature is not None:
        config.AI_TEMPERATURE = args.temperature

    if not config.AI_MODEL and not args.dry_run:
        reporter.console.print("[bold red]Error:[/bold red] AI_MODEL is not set. Use --model <name> or update src/config.py")
        sys.exit(1)

    if args.env_key:
        custom_key = os.getenv(args.env_key)
        if custom_key:
            config.OPENAI_API_KEY = custom_key
        else:
            reporter.console.print(f"[bold yellow]Warning:[/bold yellow] Environment variable '{args.env_key}' not set or empty.")

    if args.url:
        config.OPENAI_BASE_URL = args.url
    
    target_path = os.path.abspath(args.dir)
    if not os.path.exists(target_path):
        reporter.console.print(f"[bold red]Error:[/bold red] Target directory '{target_path}' does not exist.")
        sys.exit(1)

    scanner = Scanner(target_path)
    ai_engine = AIEngine()

    reporter.console.print(f"Target: [bold]{target_path}[/bold]")
    reporter.console.print(f"Model: [bold]{config.AI_MODEL}[/bold]")
    mode_str = "Deep (Dependency Tracking)" if args.deep else "Standard"
    reporter.console.print(f"Mode: [bold]{mode_str}[/bold]")
    
    # Print Directory Tree
    reporter.print_target_tree(scanner)

    reporter.console.print("Scanning files...\n")

    files_found = 0
    analyzed_files = set()
    
    try:
        all_files = list(scanner.get_files())
        
        # Initialize streaming reports
        if not args.dry_run:
            reporter.init_reports(len(all_files))
            
        for file_path in all_files:
            files_found += 1
            # Use relative path for reporting
            rel_file_path = os.path.relpath(file_path, target_path)

            if args.dry_run:
                reporter.console.print(f"[dim]Found: {rel_file_path}[/dim]")
                continue

            if args.deep:
                if file_path in analyzed_files:
                    continue
                
                content = scanner.read_file(file_path)
                if not content.strip():
                    reporter.log_result(rel_file_path, "[SAFE]", "Empty file")
                    continue

                # Identify dependencies
                deps_paths = scanner.extract_dependencies(file_path, content)
                
                if not deps_paths:
                    reporter.console.print(f"[dim]Analyzing {rel_file_path}...[/dim]", end="\r")
                    analysis_result = ai_engine.analyze_code(file_path.name, content)
                    
                    if not analysis_result.strip():
                        analysis_result = "ERROR: AI returned an empty response."
                    
                    reporter.log_result(rel_file_path, extract_status(analysis_result), analysis_result)
                else:
                    # Fetch dependency content (full or skeleton)
                    deps_context = {}
                    for dp in deps_paths:
                        if args.full_deps:
                            deps_context[dp.name] = scanner.read_file(dp)
                        else:
                            deps_context[dp.name] = scanner.get_skeleton(dp)
                    
                    context_type = "FULL" if args.full_deps else "skeletons"
                    reporter.console.print(f"[dim]Deep Analyzing {rel_file_path} with {len(deps_paths)} deps ({context_type})...[/dim]", end="\r")
                    analysis_result = ai_engine.analyze_deep(file_path.name, content, deps_context, full_context=args.full_deps)
                    
                    if not analysis_result.strip():
                        analysis_result = "ERROR: AI returned an empty response."
                    
                    full_result = "[DEEP] " + analysis_result
                    reporter.log_result(rel_file_path, extract_status(analysis_result), full_result)
                
                analyzed_files.add(file_path)

            else:
                # Standard Mode
                content = scanner.read_file(file_path)
                if not content.strip():
                    reporter.log_result(rel_file_path, "[SAFE]", "Empty file")
                    continue

                reporter.console.print(f"[dim]Analyzing {rel_file_path}...[/dim]", end="\r")
                analysis_result = ai_engine.analyze_code(file_path.name, content)
                
                if not analysis_result.strip():
                    analysis_result = "ERROR: AI returned an empty response."
                
                reporter.log_result(rel_file_path, extract_status(analysis_result), analysis_result)

    except KeyboardInterrupt:
        reporter.console.print("\n[bold yellow]Scan interrupted by user.[/bold yellow]")
    
    if files_found == 0:
        reporter.console.print("[yellow]No relevant source files found to scan.[/yellow]")
    else:
        if not args.dry_run:
            reporter.print_summary()
            reporter.finalize_reports()

if __name__ == "__main__":
    main()
