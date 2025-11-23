"""
Command-line interface for LogCost using argparse.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from .analyzer import CostAnalyzer
from .tracker import export as export_stats
from .exporters import export_csv, export_prometheus, render_html_report


def _load_stats(path: str) -> dict:
    return json.loads(Path(path).read_text())


def _cmd_analyze(args: argparse.Namespace) -> int:
    analyzer = CostAnalyzer(
        stats_file=args.stats_file,
        provider=args.provider,
        currency=args.currency,
    )
    report = analyzer.build_report(top_n=args.top)

    print(f"Provider: {report.provider.upper()}  Currency: {report.currency}")
    print(
        f"Total bytes: {report.total_bytes:,}  "
        f"Estimated cost: {report.total_cost:.2f} {report.currency}"
    )
    print("")
    print(f"Top {len(report.top_entries)} cost drivers:")
    for entry in report.top_entries:
        print(
            f"- {entry.file}:{entry.line} [{entry.level}] "
            f"{entry.message_template[:60]}... {entry.cost:.4f} {report.currency}"
        )

    if report.anti_patterns:
        print("\nDetected anti-patterns:")
        for pattern in report.anti_patterns:
            print(f"  * {pattern}")
    if report.recommendations:
        print("\nRecommendations:")
        for tip in report.recommendations:
            print(f"  * {tip}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    fmt = args.format
    if fmt == "html":
        render_html_report(
            stats_file=args.stats_file,
            output_path=args.output,
            provider=args.provider,
            currency=args.currency,
            top_n=args.top,
        )
        print(f"Wrote HTML report to {args.output}")
        return 0

    if fmt == "csv":
        stats = _load_stats(args.stats_file)
        export_csv(stats, args.output)
        print(f"Wrote CSV to {args.output}")
        return 0

    if fmt == "prometheus":
        stats = _load_stats(args.stats_file)
        export_prometheus(stats, args.output)
        print(f"Wrote Prometheus metrics to {args.output}")
        return 0

    analyzer = CostAnalyzer(
        stats_file=args.stats_file,
        provider=args.provider,
        currency=args.currency,
    )
    analysis = analyzer.build_report(top_n=args.top)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "provider": analysis.provider,
                "currency": analysis.currency,
                "total_bytes": analysis.total_bytes,
                "total_cost": analysis.total_cost,
                "entries": [entry.__dict__ for entry in analysis.entries],
                "anti_patterns": analysis.anti_patterns,
                "recommendations": analysis.recommendations,
            },
            indent=2,
        )
    )
    print(f"Wrote report to {output_path}")
    return 0


def _cmd_estimate(args: argparse.Namespace) -> int:
    analyzer = CostAnalyzer(stats_file=args.stats_file)
    roi = analyzer.estimate_roi(
        reduction_percent=args.reduction,
        hours_to_fix=args.hours,
        hourly_rate=args.rate,
    )
    print(
        f"Potential savings: {roi['potential_savings']:.2f}\n"
        f"Effort cost: {roi['effort_cost']:.2f}\n"
        f"Net savings: {roi['net_savings']:.2f}\n"
        f"ROI: {roi['roi']:.2f}"
    )
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    before = _load_stats(args.stats_file)
    after = _load_stats(args.updated_stats)
    added = set(after) - set(before)
    removed = set(before) - set(after)
    changed = {
        key: (before[key], after[key])
        for key in before.keys() & after.keys()
        if (
            before[key].get("bytes") != after[key].get("bytes")
            or before[key].get("count") != after[key].get("count")
        )
    }

    if not (added or removed or changed):
        print("No differences detected.")
        return 0

    if added:
        print("Added statements:")
        for key in added:
            entry = after[key]
            print(f"  + {key} bytes={entry.get('bytes')} count={entry.get('count')}")

    if removed:
        print("\nRemoved statements:")
        for key in removed:
            print(f"  - {key}")

    if changed:
        print("\nChanged statements:")
        for key, (before_entry, after_entry) in changed.items():
            print(
                f"  * {key}: bytes {before_entry.get('bytes')} -> {after_entry.get('bytes')}, "
                f"count {before_entry.get('count')} -> {after_entry.get('count')}"
            )
    return 0


def _cmd_capture(args: argparse.Namespace) -> int:
    exported = export_stats(args.output)
    print(f"Exported stats to {exported}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="logcost", description="LogCost CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="Display top cost drivers")
    analyze_parser.add_argument("stats_file")
    analyze_parser.add_argument("--provider", default="gcp")
    analyze_parser.add_argument("--currency", default="USD")
    analyze_parser.add_argument("--top", type=int, default=10)
    analyze_parser.set_defaults(func=_cmd_analyze)

    report_parser = subparsers.add_parser("report", help="Write analysis to a file")
    report_parser.add_argument("stats_file")
    report_parser.add_argument("output")
    report_parser.add_argument("--provider", default="gcp")
    report_parser.add_argument("--currency", default="USD")
    report_parser.add_argument(
        "--format",
        choices=["json", "html", "csv", "prometheus"],
        default="json",
        help="Output format",
    )
    report_parser.add_argument("--top", type=int, default=10, help="Top entries to include")
    report_parser.set_defaults(func=_cmd_report)

    estimate_parser = subparsers.add_parser("estimate", help="Estimate ROI")
    estimate_parser.add_argument("stats_file")
    estimate_parser.add_argument("--reduction", type=float, required=True)
    estimate_parser.add_argument("--hours", type=float, required=True)
    estimate_parser.add_argument("--rate", type=float, required=True)
    estimate_parser.set_defaults(func=_cmd_estimate)

    diff_parser = subparsers.add_parser("diff", help="Compare two stats files")
    diff_parser.add_argument("stats_file")
    diff_parser.add_argument("updated_stats")
    diff_parser.set_defaults(func=_cmd_diff)

    capture_parser = subparsers.add_parser("capture", help="Export current stats")
    capture_parser.add_argument("output")
    capture_parser.set_defaults(func=_cmd_capture)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
