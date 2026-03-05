"""Parser registry and auto-detection logic."""
from __future__ import annotations
from typing import Type
from .base import BaseParser
from .formats import (
    PythonParser, DjangoParser, FlaskParser, OdooParser,
    NginxParser, ApacheParser, PostgresParser, MySQLParser,
    MariaDBParser, GenericParser, JSONLineParser,
)

PARSERS: dict[str, Type[BaseParser]] = {
    "python": PythonParser,
    "django": DjangoParser,
    "flask": FlaskParser,
    "odoo": OdooParser,
    "nginx": NginxParser,
    "apache": ApacheParser,
    "postgresql": PostgresParser,
    "mysql": MySQLParser,
    "mariadb": MariaDBParser,
    "generic": GenericParser,
    "jsonline": JSONLineParser,
}


def detect_format(filepath: str, sample_size: int = 30) -> str:
    """Read first N lines and pick the parser with highest confidence."""
    lines: list[str] = []
    try:
        with open(filepath, "r", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= sample_size:
                    break
                lines.append(line)
    except OSError:
        return "generic"

    if not lines:
        return "generic"

    best_name = "generic"
    best_score = 0.0
    for name, cls in PARSERS.items():
        score = cls.confidence(lines)
        if score > best_score:
            best_score = score
            best_name = name
    return best_name


def get_parser(name: str) -> BaseParser:
    """Instantiate a parser by name."""
    cls = PARSERS.get(name, GenericParser)
    return cls()
