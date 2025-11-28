"""
LogCost Notifiers - Send logging cost reports to various channels

This module provides notification support for LogCost stats,
starting with Slack webhook integration for proactive alerts.
"""

import json
import os
from typing import Dict, List, Optional
from urllib import request, error as urllib_error

from .analyzer import CostAnalyzer
from .utils import get_env_int


def format_bytes(bytes_count: int) -> str:
    """Format bytes as human-readable string."""
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.2f} KB"
    elif bytes_count < 1024 * 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_count / (1024 * 1024 * 1024):.2f} GB"


def format_cost(cost: float) -> str:
    """Format cost as currency string."""
    return f"${cost:.2f}"


def _build_slack_message(
    stats: Dict,
    provider: str = "gcp",
    top_n: int = 5,
    previous_stats: Optional[Dict] = None,
    test_notification: bool = False
) -> Dict:
    """Build Slack message payload from LogCost stats.

    Args:
        stats: Current LogCost statistics
        provider: Cloud provider for cost calculation (gcp/aws/azure)
        top_n: Number of top expensive logs to include
        previous_stats: Optional previous stats for trend calculation

    Returns:
        Slack message payload dict
    """
    analyzer = CostAnalyzer(stats, provider=provider)
    report = analyzer.build_report(top_n=top_n)

    # Calculate totals
    total_bytes = report.total_bytes
    total_cost = report.total_cost
    total_calls = sum(entry.count for entry in report.entries)

    # Build header
    header_prefix = "*[Test]* " if test_notification else ""
    header = f"{header_prefix}*LogCost Report - {provider.upper()}*\n"
    header += f"Total: {format_bytes(total_bytes)} ({format_cost(total_cost)})\n"
    header += f"Log calls: {total_calls:,}\n"

    # Add trend if previous stats available
    if previous_stats:
        prev_analyzer = CostAnalyzer(previous_stats, provider=provider)
        prev_report = prev_analyzer.build_report(top_n=top_n)
        prev_cost = prev_report.total_cost

        if prev_cost > 0:
            change_pct = ((total_cost - prev_cost) / prev_cost) * 100
            trend_emoji = "📈" if change_pct > 0 else "📉"
            header += f"Trend: {trend_emoji} {change_pct:+.1f}% from previous period\n"

    # Top expensive logs section
    top_section = f"\n*🔥 Top {top_n} Most Expensive Logs:*\n"
    for i, entry in enumerate(report.top_entries, 1):
        top_section += (
            f"{i}. `{entry.file}:{entry.line}` - "
            f"{format_cost(entry.cost)} "
            f"({format_bytes(entry.bytes)}, {entry.count:,} calls)\n"
            f"   _{entry.message_template[:60]}..._\n"
        )

    # Warnings section (use anti_patterns from report)
    warnings_section = ""
    if report.anti_patterns:
        warnings_section = "\n*⚠️  Warnings:*\n"
        for warning in report.anti_patterns[:5]:  # Limit to 5 warnings
            warnings_section += f"• {warning}\n"

    # Build Slack blocks for rich formatting
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": header
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": top_section
            }
        }
    ]

    if warnings_section:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": warnings_section
            }
        })

    # Add footer with summary stats
    footer_text = (
        f"Total logs tracked: {len(stats)} unique locations | "
        f"Analyzed with LogCost"
    )
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": footer_text
            }
        ]
    })

    text_prefix = "[Test] " if test_notification else ""
    return {
        "text": f"{text_prefix}LogCost Report - {format_cost(total_cost)} total cost",
        "blocks": blocks
    }


def send_slack_notification(
    webhook_url: str,
    stats: Dict,
    provider: str = "gcp",
    top_n: int = 5,
    previous_stats: Optional[Dict] = None,
    test_notification: bool = False
) -> bool:
    """Send LogCost report to Slack via webhook.

    Args:
        webhook_url: Slack webhook URL
        stats: Current LogCost statistics
        provider: Cloud provider for cost calculation (gcp/aws/azure)
        top_n: Number of top expensive logs to include
        previous_stats: Optional previous stats for trend calculation

    Returns:
        True if notification sent successfully, False otherwise

    Example:
        >>> import logcost
        >>> from logcost.notifiers import send_slack_notification
        >>>
        >>> # After some logging...
        >>> stats = logcost.get_stats()
        >>> webhook = os.getenv("SLACK_WEBHOOK_URL")
        >>> send_slack_notification(webhook, stats, provider="gcp")
    """
    if not webhook_url:
        return False

    if not stats:
        return False

    try:
        # Build message
        message = _build_slack_message(stats, provider, top_n, previous_stats, test_notification)

        # Send POST request
        req = request.Request(
            webhook_url,
            data=json.dumps(message).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        with request.urlopen(req, timeout=10) as response:
            return response.status == 200

    except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError):
        # Silently fail to avoid breaking the application
        return False
    except Exception:
        # Catch-all for any other errors
        return False


def send_notification_if_configured(
    stats: Dict,
    provider: Optional[str] = None,
    previous_stats: Optional[Dict] = None,
    test_notification: bool = False
) -> bool:
    """Send notification if webhook URL is configured via environment variable.

    This is a convenience function that checks for LOGCOST_SLACK_WEBHOOK
    environment variable and sends notification if present.

    Args:
        stats: Current LogCost statistics
        provider: Cloud provider (defaults to LOGCOST_PROVIDER env var or "gcp")
        previous_stats: Optional previous stats for trend calculation

    Returns:
        True if notification sent successfully, False otherwise

    Environment variables:
        LOGCOST_SLACK_WEBHOOK: Slack webhook URL
        LOGCOST_PROVIDER: Cloud provider (gcp/aws/azure), defaults to "gcp"
        LOGCOST_NOTIFICATION_TOP_N: Number of top logs to include (default: 5)
    """
    webhook_url = os.getenv("LOGCOST_SLACK_WEBHOOK")
    if not webhook_url:
        return False

    if provider is None:
        provider = os.getenv("LOGCOST_PROVIDER", "gcp")

    top_n = get_env_int("LOGCOST_NOTIFICATION_TOP_N", 5)

    return send_slack_notification(
        webhook_url,
        stats,
        provider=provider,
        top_n=top_n,
        previous_stats=previous_stats,
        test_notification=test_notification,
    )
