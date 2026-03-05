"""Rich terminal output."""
from __future__ import annotations
from rich.console import Console
from rich.table import Table
from rich.text import Text
from .models import AnalysisResult

LEVEL_STYLE = {
    "ERROR": "bold red",
    "WARNING": "yellow",
    "INFO": "green",
    "DEBUG": "dim",
    "UNKNOWN": "white",
}


def display(result: AnalysisResult, console: Console | None = None, max_lines: int = 200) -> None:
    c = console or Console()

    tbl = Table(title="Log Analysis Summary", show_header=True, header_style="bold cyan")
    tbl.add_column("Metric", style="bold")
    tbl.add_column("Value", justify="right")
    tbl.add_row("Detected Format", result.detected_format)
    tbl.add_row("Total Entries", str(result.parsed_entries))
    tbl.add_row("Errors", f"[red]{result.error_count}[/red]")
    tbl.add_row("Warnings", f"[yellow]{result.warning_count}[/yellow]")
    tbl.add_row("Info", f"[green]{result.info_count}[/green]")
    tbl.add_row("Debug", str(result.debug_count))
    tbl.add_row("Unique Error Groups", str(result.unique_errors))
    if result.time_span_start:
        tbl.add_row("Time Range", f"{result.time_span_start} → {result.time_span_end}")
    c.print(tbl)

    if result.error_groups:
        c.print("\n[bold red]Error Groups (by frequency):[/bold red]")
        for i, g in enumerate(result.error_groups[:20], 1):
            c.print(f"  [bold white]#{i}[/bold white] [red]×{g.count}[/red]  {g.core_issue[:120]}")

    c.print(f"\n[bold]Log Entries (showing up to {max_lines}):[/bold]\n")
    for entry in result.entries[:max_lines]:
        style = LEVEL_STYLE.get(entry.level, "white")
        ts_str = f"[cyan]{entry.timestamp}[/cyan] " if entry.timestamp else ""
        level_tag = f"[{style}][{entry.level:>7}][/{style}]"
        src = f" [dim]{entry.source}[/dim]" if entry.source else ""
        msg_first_line = entry.message.split("\n")[0][:200]
        c.print(f"  {ts_str}{level_tag}{src} {msg_first_line}")

    if len(result.entries) > max_lines:
        c.print(f"\n  [dim]... and {len(result.entries) - max_lines} more entries (use --export to see all)[/dim]")
