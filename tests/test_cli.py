import json
from pathlib import Path

import pytest

from logcost import cli


def write_stats(base_path: Path) -> Path:
    base_path.mkdir(parents=True, exist_ok=True)
    stats = {
        "app.py:10|INFO|hello": {
            "file": "app.py",
            "line": 10,
            "level": "INFO",
            "message_template": "hello",
            "count": 3,
            "bytes": 300,
        },
        "app.py:20|DEBUG|debug": {
            "file": "app.py",
            "line": 20,
            "level": "DEBUG",
            "message_template": "debug",
            "count": 1,
            "bytes": 100,
        },
    }
    stats_path = base_path / "stats.json"
    stats_path.write_text(json.dumps(stats))
    return stats_path


def test_analyze_command(tmp_path, capsys):
    stats_path = write_stats(tmp_path / "analyze")
    exit_code = cli.main(["analyze", str(stats_path), "--provider", "gcp", "--top", "1"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Total bytes" in captured.out
    assert "Top 1 cost drivers" in captured.out


def test_report_command(tmp_path, capsys):
    stats_path = write_stats(tmp_path / "report")
    output_path = tmp_path / "report" / "report.json"
    exit_code = cli.main(["report", str(stats_path), str(output_path), "--top", "2"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Wrote report" in captured.out
    data = json.loads(output_path.read_text())
    assert data["total_bytes"] > 0


def test_report_html_format(tmp_path, capsys):
    stats_path = write_stats(tmp_path / "report_html")
    output_path = tmp_path / "report_html" / "report.html"
    exit_code = cli.main(
        ["report", str(stats_path), str(output_path), "--format", "html", "--top", "1"]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Wrote HTML report" in captured.out
    assert "<table>" in output_path.read_text()


def test_report_csv_format(tmp_path, capsys):
    stats_path = write_stats(tmp_path / "report_csv")
    output_path = tmp_path / "report_csv" / "report.csv"
    exit_code = cli.main(
        ["report", str(stats_path), str(output_path), "--format", "csv"]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Wrote CSV" in captured.out
    assert "message_template" in output_path.read_text()


def test_report_prometheus_format(tmp_path, capsys):
    stats_path = write_stats(tmp_path / "report_prom")
    output_path = tmp_path / "report_prom" / "report.prom"
    exit_code = cli.main(
        ["report", str(stats_path), str(output_path), "--format", "prometheus"]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Prometheus" in captured.out
    assert "logcost_statement_bytes" in output_path.read_text()


def test_estimate_command(tmp_path, capsys):
    stats_path = write_stats(tmp_path / "estimate")
    exit_code = cli.main(
        [
            "estimate",
            str(stats_path),
            "--reduction",
            "0.5",
            "--hours",
            "2",
            "--rate",
            "100",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Potential savings" in captured.out


def test_diff_command(tmp_path, capsys):
    stats_a = write_stats(tmp_path / "diff_a")
    stats_b = write_stats(tmp_path / "diff_b")
    data = json.loads(stats_b.read_text())
    data["app.py:10|INFO|hello"]["bytes"] = 500
    stats_b.write_text(json.dumps(data))

    exit_code = cli.main(["diff", str(stats_a), str(stats_b)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Changed statements" in captured.out


def test_capture_command(monkeypatch, tmp_path, capsys):
    output_path = tmp_path / "capture.json"

    def fake_export(path):
        Path(path).write_text("{}")
        return path

    monkeypatch.setattr(cli, "export_stats", fake_export)

    exit_code = cli.main(["capture", str(output_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Exported stats" in captured.out
    assert output_path.exists()
