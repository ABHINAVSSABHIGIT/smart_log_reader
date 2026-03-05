"""Log analysis: filtering, fuzzy error grouping, statistics."""
from __future__ import annotations
from datetime import datetime
from typing import Iterator, Optional

from rapidfuzz import fuzz

from .models import AnalysisResult, ErrorGroup, LogEntry

SIMILARITY_THRESHOLD = 85


def _core_issue(msg: str) -> str:
    """Extract first meaningful line as core issue."""
    for line in msg.split("\n"):
        s = line.strip()
        if s:
            return s[:200]
    return msg[:200]


def filter_entries(
    entries: Iterator[LogEntry],
    level: str = "ALL",
    keyword: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> Iterator[LogEntry]:
    """Apply level, keyword, and time-range filters."""
    import re
    kw_re = re.compile(keyword, re.IGNORECASE) if keyword else None

    for e in entries:
        if level != "ALL" and e.level != level.upper():
            continue
        if start_time and e.timestamp and e.timestamp < start_time:
            continue
        if end_time and e.timestamp and e.timestamp > end_time:
            continue
        if kw_re and not kw_re.search(e.message) and not kw_re.search(e.full_entry):
            continue
        yield e


def group_errors(entries: list[LogEntry], threshold: int = SIMILARITY_THRESHOLD) -> list[ErrorGroup]:
    """Group similar ERROR entries using fuzzy matching."""
    errors = [e for e in entries if e.level == "ERROR"]
    if not errors:
        return []

    groups: list[ErrorGroup] = []
    for entry in errors:
        core = _core_issue(entry.message)
        matched = False
        for g in groups:
            if fuzz.token_sort_ratio(core, g.core_issue) >= threshold:
                g.count += 1
                g.entries.append(entry)
                if entry.timestamp:
                    if g.first_seen is None or entry.timestamp < g.first_seen:
                        g.first_seen = entry.timestamp
                    if g.last_seen is None or entry.timestamp > g.last_seen:
                        g.last_seen = entry.timestamp
                entry.category = g.core_issue[:80]
                entry.occurrence_count = g.count
                matched = True
                break
        if not matched:
            g = ErrorGroup(
                representative=entry.message,
                core_issue=core,
                count=1,
                first_seen=entry.timestamp,
                last_seen=entry.timestamp,
                entries=[entry],
            )
            groups.append(g)
            entry.category = core[:80]

    for g in groups:
        for e in g.entries:
            e.occurrence_count = g.count
    groups.sort(key=lambda g: g.count, reverse=True)
    return groups


def analyze(
    entries: list[LogEntry],
    do_group: bool = True,
    detected_format: str = "generic",
) -> AnalysisResult:
    """Build full analysis result from filtered entries."""
    result = AnalysisResult(detected_format=detected_format)
    result.entries = entries
    result.parsed_entries = len(entries)

    for e in entries:
        result.total_lines += 1
        lvl = e.level
        if lvl == "ERROR":
            result.error_count += 1
        elif lvl == "WARNING":
            result.warning_count += 1
        elif lvl == "INFO":
            result.info_count += 1
        elif lvl == "DEBUG":
            result.debug_count += 1
        if e.timestamp:
            if result.time_span_start is None or e.timestamp < result.time_span_start:
                result.time_span_start = e.timestamp
            if result.time_span_end is None or e.timestamp > result.time_span_end:
                result.time_span_end = e.timestamp

    if do_group:
        result.error_groups = group_errors(entries)
        result.unique_errors = len(result.error_groups)
    return result