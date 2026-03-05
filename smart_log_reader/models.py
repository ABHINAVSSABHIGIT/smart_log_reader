"""Data models for parsed log entries and analysis results."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class LogEntry:
    """A single parsed log entry."""
    raw: str
    timestamp: Optional[datetime] = None
    level: str = "UNKNOWN"
    source: str = ""
    message: str = ""
    full_entry: str = ""
    line_number: int = 0
    category: str = ""
    occurrence_count: int = 1


@dataclass
class ErrorGroup:
    """A group of similar error messages."""
    representative: str
    core_issue: str
    count: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    entries: list[LogEntry] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Complete analysis output."""
    total_lines: int = 0
    parsed_entries: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    debug_count: int = 0
    unique_errors: int = 0
    time_span_start: Optional[datetime] = None
    time_span_end: Optional[datetime] = None
    entries: list[LogEntry] = field(default_factory=list)
    error_groups: list[ErrorGroup] = field(default_factory=list)
    detected_format: str = "generic"
