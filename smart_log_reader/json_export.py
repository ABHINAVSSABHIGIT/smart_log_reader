"""JSON export."""
from __future__ import annotations
import json
from pathlib import Path
from .models import AnalysisResult


def export_json(result: AnalysisResult, output_path: Path) -> Path:
    summary = {
        "detected_format": result.detected_format,
        "total_lines": result.total_lines,
        "error_count": result.error_count,
        "warning_count": result.warning_count,
        "info_count": result.info_count,
        "debug_count": result.debug_count,
        "unique_errors": result.unique_errors,
        "time_span_start": str(result.time_span_start) if result.time_span_start else None,
        "time_span_end": str(result.time_span_end) if result.time_span_end else None,
        "error_frequency": {
            g.core_issue[:100]: g.count for g in result.error_groups
        },
    }
    details = []
    for e in result.entries:
        details.append({
            "timestamp": str(e.timestamp) if e.timestamp else None,
            "level": e.level,
            "source": e.source,
            "message": e.message[:500],
            "full_entry": e.full_entry[:2000],
            "category": e.category,
            "occurrence_count": e.occurrence_count,
        })

    output_path.write_text(json.dumps({"summary": summary, "details": details}, indent=2, default=str))
    return output_path
