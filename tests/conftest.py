import pytest

@pytest.fixture
def sample_python_log(tmp_path):
    log_content = """2024-01-15 10:23:45,123 - app_module - INFO - App started
2024-01-15 10:23:46,124 - app_module - ERROR - Connection failed
Traceback (most recent call last):
  File "app.py", line 10, in <module>
    connect()
ConnectionError: Failed to connect to db
2024-01-15 10:23:47,125 - app_module - DEBUG - Retry attempt 1
"""
    file_path = tmp_path / "app.log"
    file_path.write_text(log_content)
    return file_path

@pytest.fixture
def sample_nginx_log(tmp_path):
    log_content = """127.0.0.1 - - [15/Jan/2024:10:23:45 +0000] "GET / HTTP/1.1" 200 612
127.0.0.1 - - [15/Jan/2024:10:23:46 +0000] "GET /api HTTP/1.1" 500 120
2024/01/15 10:23:47 [error] 1234#0: *1 open() "/usr/share/nginx/html/missing" failed (2: No such file or directory)
"""
    file_path = tmp_path / "nginx.log"
    file_path.write_text(log_content)
    return file_path
