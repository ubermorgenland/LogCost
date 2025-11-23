"""
Cost analysis utilities for LogCost stats.

Consumes the tracker output and produces insights such as per-statement
costs, anti-pattern detections, and ROI estimates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

PRICING_PER_GB = {
    "gcp": 0.50,
    "aws": 0.57,
    "azure": 0.63,
}

DEFAULT_LOOP_THRESHOLD = 1000
DEFAULT_LARGE_MSG_THRESHOLD = 5_000  # bytes per call


@dataclass
class CostEntry:
    key: str
    file: str
    line: int
    level: str
    message_template: str
    count: int
    bytes: int
    bytes_per_call: float
    cost: float


@dataclass
class AnalysisReport:
    provider: str
    currency: str
    total_bytes: int
    total_cost: float
    entries: List[CostEntry]
    top_entries: List[CostEntry]
    anti_patterns: List[str]
    recommendations: List[str]


class CostAnalyzer:
    """Analyze tracker stats and produce cost insights."""

    def __init__(
        self,
        stats: Optional[Dict[str, Dict]] = None,
        stats_file: Optional[str] = None,
        provider: str = "gcp",
        currency: str = "USD",
        price_per_gb: Optional[float] = None,
    ) -> None:
        if stats is None and stats_file is None:
            raise ValueError("Either stats or stats_file must be provided")
        if stats is None:
            stats = self._load_stats(stats_file)  # type: ignore[arg-type]

        provider_key = provider.lower()
        if price_per_gb is None:
            try:
                price_per_gb = PRICING_PER_GB[provider_key]
            except KeyError as exc:
                raise ValueError(f"Unknown provider '{provider}'") from exc

        self.stats = stats or {}
        self.provider = provider_key
        self.currency = currency
        self.price_per_gb = price_per_gb

    @staticmethod
    def _load_stats(stats_file: str) -> Dict[str, Dict]:
        data = json.loads(Path(stats_file).read_text())
        if not isinstance(data, dict):
            raise ValueError("Stats file must contain a dictionary")
        return data

    def _iter_entries(self) -> Iterable[CostEntry]:
        for key, data in self.stats.items():
            bytes_count = int(data.get("bytes", 0))
            count = max(int(data.get("count", 0)), 0)
            bytes_per_call = bytes_count / count if count else 0.0
            cost = self._bytes_to_cost(bytes_count)
            yield CostEntry(
                key=key,
                file=str(data.get("file", "")),
                line=int(data.get("line", 0)),
                level=str(data.get("level", "")),
                message_template=str(data.get("message_template", "")),
                count=count,
                bytes=bytes_count,
                bytes_per_call=bytes_per_call,
                cost=cost,
            )

    def _bytes_to_cost(self, bytes_count: int) -> float:
        gb = bytes_count / (1024 ** 3)
        return gb * self.price_per_gb

    def build_report(self, top_n: int = 10) -> AnalysisReport:
        entries = list(self._iter_entries())
        entries.sort(key=lambda entry: entry.cost, reverse=True)
        top_entries = entries[:top_n]
        total_bytes = sum(entry.bytes for entry in entries)
        total_cost = sum(entry.cost for entry in entries)
        anti_patterns = self._detect_anti_patterns(entries)
        recommendations = self._build_recommendations(entries, anti_patterns)
        return AnalysisReport(
            provider=self.provider,
            currency=self.currency,
            total_bytes=total_bytes,
            total_cost=total_cost,
            entries=entries,
            top_entries=top_entries,
            anti_patterns=anti_patterns,
            recommendations=recommendations,
        )

    def _detect_anti_patterns(self, entries: List[CostEntry]) -> List[str]:
        findings: List[str] = []
        for entry in entries:
            if entry.count >= DEFAULT_LOOP_THRESHOLD:
                findings.append(
                    f"High log volume ({entry.count} calls) at {entry.file}:{entry.line}"
                )
            if entry.level.upper() == "DEBUG" and entry.cost > 0:
                findings.append(
                    f"DEBUG log in production at {entry.file}:{entry.line} costing {entry.cost:.2f} {self.currency}"
                )
            if entry.bytes_per_call >= DEFAULT_LARGE_MSG_THRESHOLD:
                findings.append(
                    f"Large log payload (~{int(entry.bytes_per_call)} bytes/call) at {entry.file}:{entry.line}"
                )
        return findings

    def _build_recommendations(
        self, entries: List[CostEntry], anti_patterns: List[str]
    ) -> List[str]:
        recommendations: List[str] = []
        if entries:
            heaviest = entries[0]
            recommendations.append(
                f"Refactor or sample {heaviest.file}:{heaviest.line} "
                f"({heaviest.message_template[:60]}...) to cut the largest cost contributor."
            )
        if anti_patterns:
            recommendations.append("Address detected anti-patterns to reduce cost spikes.")
        if not recommendations:
            recommendations.append("Logging costs look healthy. Continue monitoring.")
        return recommendations

    def estimate_roi(
        self,
        reduction_percent: float,
        hours_to_fix: float,
        hourly_rate: float,
    ) -> Dict[str, float]:
        """Estimate savings vs. optimization effort."""
        if not (0 <= reduction_percent <= 1):
            raise ValueError("reduction_percent must be between 0 and 1")
        if hours_to_fix < 0 or hourly_rate < 0:
            raise ValueError("hours_to_fix and hourly_rate must be non-negative")

        report = self.build_report()
        potential_savings = report.total_cost * reduction_percent
        effort_cost = hours_to_fix * hourly_rate
        net = potential_savings - effort_cost
        roi = (net / effort_cost) if effort_cost else float("inf") if net > 0 else 0.0
        return {
            "potential_savings": potential_savings,
            "effort_cost": effort_cost,
            "net_savings": net,
            "roi": roi,
        }
