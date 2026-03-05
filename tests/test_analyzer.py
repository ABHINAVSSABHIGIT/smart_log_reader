import datetime
from smart_log_reader.analyzer import group_errors, filter_entries, analyze
from smart_log_reader.models import LogEntry

def test_error_grouping():
    entries = [
        LogEntry(raw="1", message="ConnectionError: Host unreachable at 192.168.1.100", level="ERROR"),
        LogEntry(raw="2", message="ConnectionError: Host unreachable at 10.0.0.15", level="ERROR"),
        LogEntry(raw="3", message="ValueError: Invalid config for user 1234", level="ERROR"),
        LogEntry(raw="4", message="ValueError: Invalid config for user 5678", level="ERROR"),
        LogEntry(raw="5", message="INFO: server started", level="INFO"),
    ]
    
    groups = group_errors(entries, threshold=85)
    assert len(groups) == 2
    assert groups[0].count == 2
    assert groups[1].count == 2
    assert "ConnectionError" in groups[0].representative or "ValueError" in groups[0].representative

def test_filter_entries():
    entries = [
        LogEntry(raw="", message="info msg", level="INFO", full_entry="info msg"),
        LogEntry(raw="", message="error connection", level="ERROR", full_entry="error connection"),
        LogEntry(raw="", message="warning msg", level="WARNING", full_entry="warning msg"),
    ]
    
    errors_only = list(filter_entries(entries, level="ERROR"))
    assert len(errors_only) == 1
    assert errors_only[0].level == "ERROR"
    
    kw_only = list(filter_entries(entries, keyword="connection"))
    assert len(kw_only) == 1
    assert kw_only[0].level == "ERROR"

def test_analyze():
    entries = [
        LogEntry(raw="e1", message="Error A", level="ERROR", timestamp=datetime.datetime(2024, 1, 1, 10, 0)),
        LogEntry(raw="e2", message="Error A", level="ERROR", timestamp=datetime.datetime(2024, 1, 1, 10, 1)),
        LogEntry(raw="i1", message="Info B", level="INFO", timestamp=datetime.datetime(2024, 1, 1, 10, 2)),
    ]
    
    result = analyze(entries, do_group=True, detected_format="python")
    assert result.total_lines == 3
    assert result.error_count == 2
    assert result.info_count == 1
    assert result.unique_errors == 1  # grouped Error A
    assert result.time_span_start == datetime.datetime(2024, 1, 1, 10, 0)
    assert result.time_span_end == datetime.datetime(2024, 1, 1, 10, 2)
