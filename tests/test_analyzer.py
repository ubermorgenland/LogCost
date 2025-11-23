import json
from pathlib import Path

import pytest

from logcost.analyzer import CostAnalyzer, PRICING_PER_GB


def sample_stats():
    return {
        "app.py:10|INFO|User login": {
            "file": "app.py",
            "line": 10,
            "level": "INFO",
            "message_template": "User login",
            "count": 200,
            "bytes": 200 * 120,
        },
        "worker.py:20|DEBUG|Verbose data": {
            "file": "worker.py",
            "line": 20,
            "level": "DEBUG",
            "message_template": "Verbose data",
            "count": 5,
            "bytes": 5 * 8000,
        },
    }


def test_build_report_from_stats():
    analyzer = CostAnalyzer(stats=sample_stats(), provider="gcp")
    report = analyzer.build_report(top_n=1)

    assert report.total_bytes == (200 * 120) + (5 * 8000)
    assert len(report.top_entries) == 1
    top = report.top_entries[0]
    assert top.file == "worker.py"
    assert pytest.approx(top.cost, rel=1e-3) == (
        (5 * 8000) / (1024 ** 3) * PRICING_PER_GB["gcp"]
    )
    assert any("DEBUG log in production" in msg for msg in report.anti_patterns)


def test_build_report_from_file(tmp_path):
    stats_path = tmp_path / "stats.json"
    stats = sample_stats()
    stats_path.write_text(json.dumps(stats))

    analyzer = CostAnalyzer(stats_file=str(stats_path), provider="aws")
    report = analyzer.build_report()

    assert report.provider == "aws"
    assert report.entries[0].bytes > 0


def test_custom_price():
    analyzer = CostAnalyzer(stats=sample_stats(), price_per_gb=1.25, provider="custom")
    report = analyzer.build_report()
    total_bytes = report.total_bytes
    expected_cost = total_bytes / (1024 ** 3) * 1.25
    assert pytest.approx(report.total_cost, rel=1e-3) == expected_cost


def test_estimate_roi():
    analyzer = CostAnalyzer(stats=sample_stats())
    roi = analyzer.estimate_roi(reduction_percent=0.5, hours_to_fix=5, hourly_rate=100)

    assert roi["potential_savings"] > 0
    assert roi["effort_cost"] == 500
    assert "roi" in roi


def test_invalid_provider():
    with pytest.raises(ValueError):
        CostAnalyzer(stats=sample_stats(), provider="unknown")


def test_roi_validation():
    analyzer = CostAnalyzer(stats=sample_stats())
    with pytest.raises(ValueError):
        analyzer.estimate_roi(-0.1, 1, 1)
    with pytest.raises(ValueError):
        analyzer.estimate_roi(0.5, -1, 1)
