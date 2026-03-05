"""Base parser with multi-line handling."""
from __future__ import annotations
import re
from datetime import datetime
from typing import Iterator, Optional, TextIO

from dateutil import parser as dtparser

from .models import LogEntry

# Broad pattern that matches most timestamp-prefixed log lines
_TIMESTAMP_START = re.compile(
    r"^\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}"  # ISO-ish
    r"|^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}"      # syslog
    r"|^\[\d{4}[-/]\d{2}[-/]\d{2}"                  # bracket-wrapped
)

LEVEL_NORM = {
    "CRITICAL": "ERROR", "FATAL": "ERROR", "SEVERE": "ERROR", "PANIC": "ERROR",
    "WARN": "WARNING", "WARNING": "WARNING",
    "ERROR": "ERROR", "INFO": "INFO", "DEBUG": "DEBUG",
    "NOTICE": "INFO", "LOG": "INFO", "NOTE": "INFO",
    "DEBUG1": "DEBUG", "DEBUG2": "DEBUG", "DEBUG3": "DEBUG",
    "DEBUG4": "DEBUG", "DEBUG5": "DEBUG",
}


def normalize_level(raw: str) -> str:
    return LEVEL_NORM.get(raw.upper(), raw.upper())


def safe_parse_ts(text: str) -> Optional[datetime]:
    """Try to parse a timestamp string, return None on failure."""
    if not text:
        return None
    try:
        return dtparser.parse(text, fuzzy=True)
    except (ValueError, OverflowError):
        return None


class BaseParser:
    """Base class all format parsers extend."""

    name: str = "generic"
    # Subclasses override with compiled regex
    primary_pattern: Optional[re.Pattern] = None
    # How confident is this parser for a sample line (0-1)

    @classmethod
    def confidence(cls, sample_lines: list[str]) -> float:
        """Return 0-1 confidence that these lines match this parser."""
        if cls.primary_pattern is None:
            return 0.05  # generic fallback
        hits = sum(1 for l in sample_lines if cls.primary_pattern.search(l))
        return hits / max(len(sample_lines), 1)

    def parse_line(self, line: str) -> Optional[LogEntry]:
        """Parse a single line. Return None if it's a continuation."""
        return LogEntry(raw=line, message=line.strip(), full_entry=line)

    def is_continuation(self, line: str) -> bool:
        """Return True if line is a continuation of the previous entry (stack trace etc)."""
        if not line.strip():
            return True
        return not bool(_TIMESTAMP_START.match(line))

    def stream_entries(self, fh: TextIO) -> Iterator[LogEntry]:
        """Stream parsed entries from a file handle, merging multi-line entries."""
        current: Optional[LogEntry] = None
        line_num = 0

        for raw_line in fh:
            line_num += 1
            # Try to parse as new entry
            if not self.is_continuation(raw_line):
                parsed = self.parse_line(raw_line)
                if parsed is not None:
                    if current is not None:
                        yield current
                    parsed.line_number = line_num
                    current = parsed
                    continue

            # It's a continuation line — append to current
            if current is not None:
                current.full_entry += raw_line
                # Append meaningful content to message
                stripped = raw_line.strip()
                if stripped:
                    current.message += "\n" + stripped
            else:
                # Orphan continuation — emit as standalone
                entry = LogEntry(raw=raw_line, message=raw_line.strip(), full_entry=raw_line, line_number=line_num)
                yield entry

        if current is not None:
            yield current