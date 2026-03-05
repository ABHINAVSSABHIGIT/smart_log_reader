from smart_log_reader.formats import PythonParser, NginxParser, GenericParser
from smart_log_reader.registry import detect_format

def test_detect_format(sample_python_log, sample_nginx_log):
    assert detect_format(str(sample_python_log)) == "python"
    assert detect_format(str(sample_nginx_log)) == "nginx"

def test_python_multiline_parsing(sample_python_log):
    parser = PythonParser()
    with open(sample_python_log, "r") as f:
        entries = list(parser.stream_entries(f))
    
    assert len(entries) == 3
    
    assert entries[0].level == "INFO"
    assert entries[0].message == "App started"
    
    assert entries[1].level == "ERROR"
    assert "Connection failed" in entries[1].message
    assert "ConnectionError" in entries[1].message
    assert "Traceback" in entries[1].message
    
    assert entries[2].level == "DEBUG"
    assert entries[2].message == "Retry attempt 1"

def test_nginx_parsing(sample_nginx_log):
    parser = NginxParser()
    with open(sample_nginx_log, "r") as f:
        entries = list(parser.stream_entries(f))
    
    assert len(entries) == 3
    assert entries[0].level == "INFO"
    assert entries[1].level == "ERROR"
    assert entries[2].level == "ERROR"
    assert "open()" in entries[2].message
