import json
from pathlib import Path

from logcost.exporters import export_csv, export_prometheus, render_html_report


def sample_stats():
    return {
        "app.py:10|INFO|hello": {
            "file": "app.py",
            "line": 10,
            "level": "INFO",
            "message_template": "hello",
            "count": 3,
            "bytes": 300,
        },
        "worker.py:20|ERROR|bad": {
            "file": "worker.py",
            "line": 20,
            "level": "ERROR",
            "message_template": "bad",
            "count": 2,
            "bytes": 600,
        },
    }


def write_stats(tmp_path: Path) -> Path:
    stats_path = tmp_path / "stats.json"
    stats_path.write_text(json.dumps(sample_stats()))
    return stats_path


def test_export_csv(tmp_path):
    output = tmp_path / "stats.csv"
    export_csv(sample_stats(), str(output))
    content = output.read_text().strip().splitlines()
    assert content[0] == "key,file,line,level,message_template,count,bytes"
    assert "app.py:10|INFO|hello,app.py,10,INFO,hello,3,300" in content[1:]


def test_export_prometheus(tmp_path):
    output = tmp_path / "stats.prom"
    export_prometheus(sample_stats(), str(output))
    text = output.read_text()
    assert "logcost_statement_bytes" in text
    assert 'file="app.py"' in text
    assert "logcost_statement_count" in text


def test_render_html_report(tmp_path):
    stats_file = write_stats(tmp_path)
    output = tmp_path / "report.html"
    render_html_report(str(stats_file), str(output), provider="gcp")
    html_text = output.read_text()
    assert "<table>" in html_text
    assert "LogCost Report" in html_text
