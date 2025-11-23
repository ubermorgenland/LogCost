"""
Export helpers for LogCost stats.
"""

from __future__ import annotations

import csv
import html
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, Optional

from .analyzer import CostAnalyzer


def export_csv(stats: Dict[str, Dict], output_path: str) -> str:
    """Write stats to a CSV file with deterministic ordering."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["key", "file", "line", "level", "message_template", "count", "bytes"]

    with output.open("w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for key in sorted(stats):
            entry = stats[key]
            writer.writerow(
                {
                    "key": key,
                    "file": entry.get("file", ""),
                    "line": entry.get("line", 0),
                    "level": entry.get("level", ""),
                    "message_template": entry.get("message_template", ""),
                    "count": entry.get("count", 0),
                    "bytes": entry.get("bytes", 0),
                }
            )
    return str(output)


def export_prometheus(stats: Dict[str, Dict], output_path: str) -> str:
    """Write a Prometheus exposition format file."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# HELP logcost_statement_bytes Total bytes emitted by log statement.",
        "# TYPE logcost_statement_bytes counter",
    ]
    for key in sorted(stats):
        entry = stats[key]
        labels = {
            "file": entry.get("file", ""),
            "line": str(entry.get("line", 0)),
            "level": entry.get("level", ""),
        }
        label_str = ",".join(f'{k}="{_escape_label(v)}"' for k, v in labels.items())
        lines.append(f"logcost_statement_bytes{{{label_str}}} {entry.get('bytes', 0)}")

    lines.append(
        "# HELP logcost_statement_count Total count of log invocations per statement."
    )
    lines.append("# TYPE logcost_statement_count counter")
    for key in sorted(stats):
        entry = stats[key]
        labels = {
            "file": entry.get("file", ""),
            "line": str(entry.get("line", 0)),
            "level": entry.get("level", ""),
        }
        label_str = ",".join(f'{k}="{_escape_label(v)}"' for k, v in labels.items())
        lines.append(f"logcost_statement_count{{{label_str}}} {entry.get('count', 0)}")

    output.write_text("\n".join(lines) + "\n")
    return str(output)


def render_html_report(
    stats_file: str,
    output_path: str,
    provider: str = "gcp",
    currency: str = "USD",
    top_n: int = 10,
) -> str:
    """Render an HTML report using the analyzer."""
    analyzer = CostAnalyzer(stats_file=stats_file, provider=provider, currency=currency)
    report = analyzer.build_report(top_n=top_n)
    rows = "\n".join(_html_row(entry) for entry in report.top_entries)
    anti_patterns = "".join(f"<li>{html.escape(text)}</li>" for text in report.anti_patterns)
    recommendations = "".join(
        f"<li>{html.escape(text)}</li>" for text in report.recommendations
    )

    html_doc = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>LogCost Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; }}
    th {{ background: #f0f0f0; text-align: left; }}
  </style>
 </head>
 <body>
   <h1>LogCost Report</h1>
   <p>Provider: {html.escape(report.provider.upper())} | Currency: {html.escape(report.currency)}</p>
   <p>Total bytes: {report.total_bytes:,} | Estimated cost: {report.total_cost:.2f} {html.escape(report.currency)}</p>
   <h2>Top {len(report.top_entries)} Statements</h2>
   <table>
    <thead>
      <tr><th>Location</th><th>Level</th><th>Template</th><th>Count</th><th>Bytes</th><th>Cost ({html.escape(report.currency)})</th></tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
   </table>
   <h2>Anti-patterns</h2>
   <ul>{anti_patterns or "<li>None detected</li>"}</ul>
   <h2>Recommendations</h2>
   <ul>{recommendations}</ul>
 </body>
</html>
""".strip()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_doc)
    return str(output)


def _html_row(entry) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(entry.file)}:{entry.line}</td>"
        f"<td>{html.escape(entry.level)}</td>"
        f"<td>{html.escape(entry.message_template[:80])}</td>"
        f"<td>{entry.count}</td>"
        f"<td>{entry.bytes}</td>"
        f"<td>{entry.cost:.4f}</td>"
        "</tr>"
    )


def _escape_label(value: str) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )
