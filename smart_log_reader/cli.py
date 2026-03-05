"""CLI entry point using Typer."""
from __future__ import annotations
from pathlib import Path
from typing import Optional

import typer
from dateutil import parser as dtparser
from rich.console import Console

from .analyzer import analyze, filter_entries
from .display import display
from .registry import detect_format, get_parser

app = typer.Typer(
    name="smart-log-reader",
    help="Intelligent log reader and analyzer with color-coded output and smart error grouping.",
    add_completion=False,
)

LOG_TYPES = ["auto", "python", "django", "flask", "odoo", "nginx", "apache",
             "postgresql", "mysql", "mariadb", "generic", "jsonline"]
LEVELS = ["ALL", "ERROR", "WARNING", "INFO", "DEBUG"]
EXPORT_FORMATS = ["none", "json", "html"]


def _parse_time(val):
    if not val:
        return None
    try:
        return dtparser.parse(val, fuzzy=True)
    except (ValueError, OverflowError):
        raise typer.BadParameter(f"Cannot parse datetime: {val}")


def _safe_output_path(log_file: Path, fmt: str, user_output: Optional[Path]) -> Path:
    """
    Resolve the output path for export files.

    Priority:
      1. User explicitly provided --output  → honour it as-is (their responsibility).
      2. Otherwise                          → write to ~/.smart-log-reader/reports/
                                             with a timestamped name so we never hit
                                             PermissionError on /var/log/* or similar.
    """
    if user_output:
        return user_output

    from .html_export import safe_report_path
    ext = {"json": ".json", "html": ".html"}.get(fmt, ".out")
    return safe_report_path(log_file, suffix=ext)


def version_callback(value):
    if value:
        import importlib.metadata
        try:
            ver = importlib.metadata.version("smart-log-reader")
        except importlib.metadata.PackageNotFoundError:
            ver = "unknown"
        typer.echo(f"smart-log-reader v{ver}")
        raise typer.Exit()


@app.command()
def main(
    file: Path = typer.Option(..., "--file", "-f", help="Path to the log file."),
    log_type: str = typer.Option("auto", "--log-type", "-t",
                                 help=f"Log format: {', '.join(LOG_TYPES)}"),
    level: str = typer.Option("ALL", "--level", "-l",
                               help=f"Filter by level: {', '.join(LEVELS)}"),
    keyword: Optional[str] = typer.Option(None, "--keyword", "-k",
                                           help="Keyword or regex filter."),
    start_time: Optional[str] = typer.Option(None, "--start-time", "-s",
                                              help="Start time filter. (YYYY-MM-DD HH:MM:SS)"),
    end_time: Optional[str] = typer.Option(None, "--end-time", "-e",
                                            help="End time filter. (YYYY-MM-DD HH:MM:SS)"),
    export: str = typer.Option("none", "--export", "-x",
                                help=f"Export format: {', '.join(EXPORT_FORMATS)}"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Custom output path. Defaults to ~/.smart-log-reader/reports/<name>_<ts>.<ext>",
    ),
    group_errors: bool = typer.Option(True, "--group-errors/--no-group-errors", "-g",
                                       help="Enable error grouping."),
    color: bool = typer.Option(True, "--color/--no-color", help="Color output."),

    # ── serving flags ─────────────────────────────────────────────────────────
    serve: bool = typer.Option(
        False, "--serve",
        help=(
            "After HTML export, start a localhost-only HTTP server. "
            "Access via SSH tunnel: ssh -L <port>:127.0.0.1:<port> user@server"
        ),
    ),
    serve_public: bool = typer.Option(
        False, "--serve-public",
        help=(
            "[INSECURE — LAN/VPN only] Bind to 0.0.0.0 with a one-time token. "
            "Use only inside a trusted network. Never on a public internet-facing server."
        ),
    ),
    port: int = typer.Option(0, "--port", "-p",
                              help="Port for --serve / --serve-public (0 = auto)."),

    version: Optional[bool] = typer.Option(None, "--version", "-v",
                                            callback=version_callback, is_eager=True),
):
    """Parse, analyze, and display log files with smart error grouping."""
    console = Console(force_terminal=color, no_color=not color)

    # ── validation ─────────────────────────────────────────────────────────────
    if not file.exists():
        console.print(f"[red]Error: File not found: {file}[/red]")
        raise typer.Exit(1)

    if log_type not in LOG_TYPES:
        console.print(f"[red]Invalid log type. Choose from: {', '.join(LOG_TYPES)}[/red]")
        raise typer.Exit(1)

    if export not in EXPORT_FORMATS:
        console.print(f"[red]Invalid export format. Choose from: {', '.join(EXPORT_FORMATS)}[/red]")
        raise typer.Exit(1)

    if (serve or serve_public) and export not in ("html", "none"):
        console.print("[yellow]--serve requires HTML export. Switching --export to html.[/yellow]")
    if serve or serve_public:
        export = "html"

    if serve and serve_public:
        console.print("[red]Use either --serve (localhost) or --serve-public, not both.[/red]")
        raise typer.Exit(1)

    # ── parse & filter ─────────────────────────────────────────────────────────
    fmt = log_type if log_type != "auto" else detect_format(str(file))
    console.print(f"[dim]Using parser: {fmt}[/dim]")

    parser = get_parser(fmt)
    st = _parse_time(start_time)
    et = _parse_time(end_time)

    with open(file, "r", errors="replace") as fh:
        raw_entries = parser.stream_entries(fh)
        filtered    = filter_entries(raw_entries, level=level, keyword=keyword,
                                     start_time=st, end_time=et)
        entries = list(filtered)

    if not entries:
        console.print("[yellow]No log entries matched your filters.[/yellow]")
        raise typer.Exit(0)

    result = analyze(entries, do_group=group_errors, detected_format=fmt)

    # ── terminal display ───────────────────────────────────────────────────────
    display(result, console=console)

    # ── export ─────────────────────────────────────────────────────────────────
    if export == "none":
        return

    out_path = _safe_output_path(file, export, output)

    if export == "json":
        from .json_export import export_json
        export_json(result, out_path)
        console.print(f"\n[bold green]Exported JSON →[/bold green] {out_path}")

    elif export == "html":
        from .html_export import export_html, serve_html, prune_old_reports

        export_html(result, out_path)
        prune_old_reports(keep=20)   # keep the last 20 reports, silently drop older ones
        console.print(f"\n[bold green]Exported HTML →[/bold green] {out_path}")
        console.print(f"[dim]Reports folder: {out_path.parent}[/dim]")

        if serve or serve_public:
            serve_html(out_path, port=port, public=serve_public)
        else:
            console.print(
                "\n[dim]Tip: add [bold]--serve[/bold] to view in a browser via SSH tunnel, "
                "or copy the file to your local machine with:[/dim]"
            )
            console.print(
                f"[dim cyan]  scp <user>@<server>:{out_path} ~/Downloads/[/dim cyan]"
            )


app()