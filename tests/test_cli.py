from typer.testing import CliRunner
from smart_log_reader.cli import app

runner = CliRunner()

def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Intelligent log reader" in result.stdout

def test_cli_read_file(sample_python_log):
    result = runner.invoke(app, ["-f", str(sample_python_log), "-l", "ERROR"])
    assert result.exit_code == 0
    assert "Connection failed" in result.stdout
    assert "App started" not in result.stdout

def test_cli_no_file_found(tmp_path):
    bad_file = tmp_path / "does_not_exist.log"
    result = runner.invoke(app, ["-f", str(bad_file)])
    assert result.exit_code == 1
    assert "not found" in result.stdout

def test_cli_export_json_excel(sample_python_log, tmp_path):
    out_json = tmp_path / "out.json"
    result = runner.invoke(app, ["-f", str(sample_python_log), "--export", "json", "-o", str(out_json)])
    assert result.exit_code == 0
    assert out_json.exists()
    
    out_excel = tmp_path / "out.xlsx"
    result_xl = runner.invoke(app, ["-f", str(sample_python_log), "--export", "excel", "-o", str(out_excel)])
    assert result_xl.exit_code == 0
    assert out_excel.exists()
