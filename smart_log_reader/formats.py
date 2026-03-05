"""Concrete log format parsers."""
from __future__ import annotations
import re
from typing import Optional

from .models import LogEntry
from .base import BaseParser, normalize_level, safe_parse_ts


# ---------- Python / Django / Flask ----------
# Pattern: 2024-01-15 10:23:45,123 - module - ERROR - message
#   or:    2024-01-15 10:23:45,123 ERROR module message
class PythonParser(BaseParser):
    name = "python"
    # Matches: 2024-01-15 10:23:45,123 - module - ERROR - message
    #      or: 2024-01-15 10:23:45.123 module ERROR message
    primary_pattern = re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[,\.]\d{3})"
        r"\s+[-:]\s+(?P<src>[\w\.]+)\s+[-:]\s+"
        r"(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)"
        r"\s+[-:]\s+(?P<msg>.*)",
        re.IGNORECASE,
    )
    _alt = re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[,\.]\d{3})"
        r"\s+(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)"
        r"\s+(?P<src>[\w\.]*)?\s*(?P<msg>.*)",
        re.IGNORECASE,
    )

    def parse_line(self, line: str) -> Optional[LogEntry]:
        s = line.strip()
        m = self.primary_pattern.match(s) or self._alt.match(s)
        if not m:
            return None
        return LogEntry(
            raw=line,
            timestamp=safe_parse_ts(m.group("ts")),
            level=normalize_level(m.group("level")),
            source=m.group("src") or "",
            message=m.group("msg").strip(),
            full_entry=line,
        )

    @classmethod
    def confidence(cls, sample_lines: list[str]) -> float:
        hits = sum(1 for l in sample_lines if cls.primary_pattern.search(l) or cls._alt.search(l))
        return hits / max(len(sample_lines), 1)


class DjangoParser(PythonParser):
    """Django uses Python logging; extends PythonParser with Django-specific pattern."""
    name = "django"
    # Django: [15/Jan/2024 10:23:45] ERROR [django.request:234] message
    primary_pattern = re.compile(
        r"^(?:\[?(?P<ts>\d{2}/\w{3}/\d{4}\s+\d{2}:\d{2}:\d{2})\]?\s+)?"
        r"(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)"
        r"\s+\[?(?P<src>[\w\.]+)?(?::\d+)?\]?\s*(?P<msg>.*)",
        re.IGNORECASE,
    )

    def parse_line(self, line: str) -> Optional[LogEntry]:
        m = self.primary_pattern.match(line.strip())
        if not m:
            # Fall back to Python patterns explicitly (not via self which uses Django's pattern)
            s = line.strip()
            m = PythonParser.primary_pattern.match(s) or PythonParser._alt.match(s)
            if not m:
                return None
            return LogEntry(
                raw=line,
                timestamp=safe_parse_ts(m.group("ts")),
                level=normalize_level(m.group("level")),
                source=m.group("src") or "",
                message=m.group("msg").strip(),
                full_entry=line,
            )
        return LogEntry(
            raw=line,
            timestamp=safe_parse_ts(m.group("ts") or ""),
            level=normalize_level(m.group("level")),
            source=m.group("src") or "",
            message=m.group("msg").strip(),
            full_entry=line,
        )


class FlaskParser(PythonParser):
    """Flask uses Python logging; extends PythonParser with Werkzeug access log pattern."""
    name = "flask"
    _werkzeug = re.compile(
        r'^(?P<ip>[\d\.]+)\s+-\s+-\s+\[(?P<ts>[^\]]+)\]\s+"(?P<msg>[^"]+)"\s+(?P<status>\d+)'
    )

    @classmethod
    def confidence(cls, sample_lines: list[str]) -> float:
        # Werkzeug lines have " - - " which nginx access logs also have,
        # but Flask Python-logging lines help disambiguate
        werkzeug_hits = sum(1 for l in sample_lines if cls._werkzeug.search(l))
        python_hits = sum(1 for l in sample_lines
                         if PythonParser.primary_pattern.search(l) or PythonParser._alt.search(l))
        # If we see both werkzeug AND python log lines, it's almost certainly Flask
        if werkzeug_hits and python_hits:
            return (werkzeug_hits + python_hits) / max(len(sample_lines), 1)
        # Werkzeug-only is ambiguous with nginx; score slightly lower
        return werkzeug_hits * 0.6 / max(len(sample_lines), 1)

    def parse_line(self, line: str) -> Optional[LogEntry]:
        m = self._werkzeug.match(line.strip())
        if m:
            status = int(m.group("status"))
            level = "ERROR" if status >= 500 else "WARNING" if status >= 400 else "INFO"
            return LogEntry(
                raw=line,
                timestamp=safe_parse_ts(m.group("ts")),
                level=level,
                source="werkzeug",
                message=m.group("msg").strip(),
                full_entry=line,
            )
        return super().parse_line(line)


# ---------- Odoo ----------
# 2024-01-15 10:23:45,123 12345 INFO db_name odoo.module: message
class OdooParser(BaseParser):
    name = "odoo"
    primary_pattern = re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})"
        r"\s+\d+\s+(?P<level>\w+)"
        r"\s+\S+\s+(?P<src>[\w\.]+):\s*(?P<msg>.*)",
    )

    def parse_line(self, line: str) -> Optional[LogEntry]:
        m = self.primary_pattern.match(line.strip())
        if not m:
            return None
        return LogEntry(
            raw=line,
            timestamp=safe_parse_ts(m.group("ts")),
            level=normalize_level(m.group("level")),
            source=m.group("src"),
            message=m.group("msg").strip(),
            full_entry=line,
        )


# ---------- Nginx ----------
# Access: 127.0.0.1 - - [15/Jan/2024:10:23:45 +0000] "GET / HTTP/1.1" 200 612
# Error:  2024/01/15 10:23:45 [error] 1234#0: *1 message
class NginxParser(BaseParser):
    name = "nginx"
    _access = re.compile(
        r'^(?P<ip>[\d\.]+)\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+"(?P<msg>[^"]*)"'
        r"\s+(?P<status>\d+)"
    )
    _error = re.compile(
        r"^(?P<ts>\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})"
        r"\s+\[(?P<level>\w+)\]\s+(?P<pid>\d+#\d+:)?\s*(?P<msg>.*)"
    )
    primary_pattern = _access  # for confidence detection

    @classmethod
    def confidence(cls, sample_lines: list[str]) -> float:
        hits = sum(1 for l in sample_lines if cls._access.search(l) or cls._error.search(l))
        return hits / max(len(sample_lines), 1)

    def parse_line(self, line: str) -> Optional[LogEntry]:
        s = line.strip()
        m = self._access.match(s)
        if m:
            status = int(m.group("status"))
            level = "ERROR" if status >= 500 else "WARNING" if status >= 400 else "INFO"
            return LogEntry(
                raw=line, timestamp=safe_parse_ts(m.group("ts")),
                level=level, source="nginx-access",
                message=m.group("msg").strip(), full_entry=line,
            )
        m = self._error.match(s)
        if m:
            return LogEntry(
                raw=line, timestamp=safe_parse_ts(m.group("ts")),
                level=normalize_level(m.group("level")),
                source="nginx-error", message=m.group("msg").strip(), full_entry=line,
            )
        return None


# ---------- Apache ----------
# Access: 127.0.0.1 - frank [10/Oct/2000:13:55:36 -0700] "GET /a.gif HTTP/1.0" 200 2326
# Error:  [Sun Oct 10 10:23:45.123456 2024] [core:error] [pid 1234] message
class ApacheParser(BaseParser):
    name = "apache"
    _access = re.compile(
        r'^(?P<ip>[\d\.]+)\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+"(?P<msg>[^"]*)"'
        r"\s+(?P<status>\d+)"
    )
    _error = re.compile(
        r"^\[(?P<ts>[^\]]+)\]\s+\[(?:\w+:)?(?P<level>\w+)\]\s+(?:\[pid\s+\d+\])?\s*(?P<msg>.*)"
    )
    primary_pattern = _error

    @classmethod
    def confidence(cls, sample_lines: list[str]) -> float:
        hits = sum(1 for l in sample_lines if cls._access.search(l) or cls._error.search(l))
        return hits / max(len(sample_lines), 1)

    def parse_line(self, line: str) -> Optional[LogEntry]:
        s = line.strip()
        m = self._access.match(s)
        if m:
            status = int(m.group("status"))
            level = "ERROR" if status >= 500 else "WARNING" if status >= 400 else "INFO"
            return LogEntry(
                raw=line, timestamp=safe_parse_ts(m.group("ts")),
                level=level, source="apache-access",
                message=m.group("msg").strip(), full_entry=line,
            )
        m = self._error.match(s)
        if m:
            return LogEntry(
                raw=line, timestamp=safe_parse_ts(m.group("ts")),
                level=normalize_level(m.group("level")),
                source="apache-error", message=m.group("msg").strip(), full_entry=line,
            )
        return None


# ---------- PostgreSQL ----------
# 2024-01-15 10:23:45.123 UTC [12345] ERROR:  message
# 2024-01-15 10:23:45.123 +04 [12345] user@db ERROR:  message
# 2024-01-15 10:23:45 UTC [12345] LOG:  message
class PostgresParser(BaseParser):
    name = "postgresql"
    # Matches timezone as word (UTC) or offset (+04, -05:00, etc.)
    # Allows optional user@db before the level
    primary_pattern = re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[\.\d]*)"
        r"\s+(?:[A-Za-z]+|[+-]\d{2}(?::?\d{2})?)"          # timezone
        r"\s+\[\d+\]"                                        # [pid]
        r"\s+(?:\S+\s+)?"                                    # optional user@db
        r"(?P<level>DEBUG[1-5]?|INFO|NOTICE|WARNING|ERROR|LOG|FATAL|PANIC):\s+(?P<msg>.*)",
        re.IGNORECASE,
    )

    def parse_line(self, line: str) -> Optional[LogEntry]:
        m = self.primary_pattern.match(line.strip())
        if not m:
            return None
        return LogEntry(
            raw=line, timestamp=safe_parse_ts(m.group("ts")),
            level=normalize_level(m.group("level")),
            source="postgresql", message=m.group("msg").strip(), full_entry=line,
        )

    @classmethod
    def confidence(cls, sample_lines: list[str]) -> float:
        hits = sum(1 for l in sample_lines if cls.primary_pattern.search(l))
        return hits / max(len(sample_lines), 1)


# ---------- MySQL / MariaDB ----------
# 2024-01-15T10:23:45.123456Z 0 [ERROR] [MY-010326] message
# or: 2024-01-15 10:23:45 12345 [Warning] message
class MySQLParser(BaseParser):
    name = "mysql"
    primary_pattern = re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[\.\dZ]*)"
        r"\s+\d+\s+\[(?P<level>\w+)\]\s*(?:\[\w+-?\d*\])?\s*(?P<msg>.*)",
    )

    def parse_line(self, line: str) -> Optional[LogEntry]:
        m = self.primary_pattern.match(line.strip())
        if not m:
            return None
        return LogEntry(
            raw=line, timestamp=safe_parse_ts(m.group("ts")),
            level=normalize_level(m.group("level")),
            source="mysql", message=m.group("msg").strip(), full_entry=line,
        )


class MariaDBParser(MySQLParser):
    name = "mariadb"


class GenericParser(BaseParser):
    name = "generic"
    # Tries a very broad pattern: optional timestamp, optional level, message
    primary_pattern = re.compile(
        r"^(?P<ts>\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}[^\s]*)?"
        r"\s*\[?(?P<level>DEBUG|INFO|NOTICE|WARNING|WARN|ERROR|CRITICAL|FATAL|SEVERE|LOG)?\]?"
        r"\s*[-:]?\s*(?P<msg>.*)",
        re.IGNORECASE,
    )

    @classmethod
    def confidence(cls, sample_lines: list[str]) -> float:
        return 0.05  # always lowest priority

    def parse_line(self, line: str) -> Optional[LogEntry]:
        m = self.primary_pattern.match(line.strip())
        if m:
            return LogEntry(
                raw=line,
                timestamp=safe_parse_ts(m.group("ts") or ""),
                level=normalize_level(m.group("level") or "UNKNOWN"),
                message=m.group("msg").strip() or line.strip(),
                full_entry=line,
            )
        return LogEntry(raw=line, message=line.strip(), full_entry=line)


# JSON-line logs
class JSONLineParser(BaseParser):
    name = "jsonline"
    primary_pattern = re.compile(r"^\s*\{.*\}\s*$")

    def parse_line(self, line: str) -> Optional[LogEntry]:
        import json
        s = line.strip()
        if not s.startswith("{"):
            return None
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            return None
        ts_raw = obj.get("timestamp") or obj.get("time") or obj.get("@timestamp") or obj.get("asctime") or ""
        level = obj.get("level") or obj.get("levelname") or obj.get("severity") or "INFO"
        msg = obj.get("message") or obj.get("msg") or obj.get("text") or s
        src = obj.get("logger") or obj.get("name") or obj.get("module") or obj.get("source") or ""
        return LogEntry(
            raw=line,
            timestamp=safe_parse_ts(str(ts_raw)),
            level=normalize_level(str(level)),
            source=str(src),
            message=str(msg),
            full_entry=line,
        )

    def is_continuation(self, line: str) -> bool:
        return False