#!/usr/bin/env python3
"""
LogCost Sidecar - Aggregates stats and sends notifications

This sidecar container watches for stats files written by LogCost-instrumented apps,
aggregates data over time, and sends periodic Slack notifications with trends.

Architecture:
- App container writes to /var/log/logcost/stats.json (shared volume)
- Sidecar reads, aggregates, stores history, and notifies
- Separation of concerns: app logs, sidecar reports

Environment Variables:
    LOGCOST_WATCH_PATH          Path to watch for stats.json (default: /var/log/logcost/stats.json)
    LOGCOST_NOTIFICATION_INTERVAL  Seconds between notifications (default: 3600 = 1 hour)
    LOGCOST_HISTORY_DIR         Directory for historical snapshots (default: /var/log/logcost/history)
    LOGCOST_HISTORY_RETENTION   Days to keep history (default: 7)
    LOGCOST_SLACK_WEBHOOK       Slack webhook URL (required)
    LOGCOST_PROVIDER            Cloud provider: gcp/aws/azure (default: gcp)
    LOGCOST_NOTIFICATION_TOP_N  Number of top logs in report (default: 5)
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from logcost.utils import get_env_int

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - LogCost Sidecar - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LogCostSidecar:
    """Sidecar that watches stats, aggregates, and notifies."""

    def __init__(self):
        self.watch_path = Path(os.getenv("LOGCOST_WATCH_PATH", "/var/log/logcost/stats.json"))
        self.notification_interval = get_env_int("LOGCOST_NOTIFICATION_INTERVAL", 3600)
        self.history_dir = Path(os.getenv("LOGCOST_HISTORY_DIR", "/var/log/logcost/history"))
        self.history_retention_days = get_env_int("LOGCOST_HISTORY_RETENTION", 7)
        self.slack_webhook = os.getenv("LOGCOST_SLACK_WEBHOOK")
        self.provider = os.getenv("LOGCOST_PROVIDER", "gcp")
        self.top_n = get_env_int("LOGCOST_NOTIFICATION_TOP_N", 5)

        # Create history directory
        self.history_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"LogCost Sidecar initialized")
        logger.info(f"  Watch path: {self.watch_path}")
        logger.info(f"  Notification interval: {self.notification_interval}s")
        logger.info(f"  History directory: {self.history_dir}")
        logger.info(f"  Slack configured: {bool(self.slack_webhook)}")
        logger.info(f"  Provider: {self.provider}")

    def load_stats(self) -> Optional[Dict]:
        """Load current stats from watched file."""
        try:
            if not self.watch_path.exists():
                logger.debug(f"Stats file not found: {self.watch_path}")
                return None

            with open(self.watch_path, 'r') as f:
                stats = json.load(f)

            logger.info(f"Loaded stats: {len(stats)} unique log statements")
            return stats
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse stats file: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading stats: {e}")
            return None

    def save_snapshot(self, stats: Dict, timestamp: datetime):
        """Save historical snapshot for trend analysis."""
        try:
            snapshot_file = self.history_dir / f"snapshot_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            with open(snapshot_file, 'w') as f:
                json.dump(stats, f, indent=2)
            logger.info(f"Saved snapshot: {snapshot_file.name}")
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")

    def load_previous_snapshot(self) -> Optional[Dict]:
        """Load the most recent historical snapshot for comparison."""
        try:
            snapshots = sorted(self.history_dir.glob("snapshot_*.json"))
            if len(snapshots) < 2:
                # Need at least 2 snapshots for comparison (current saved + previous)
                return None

            # Get second-to-last snapshot (last one is current)
            prev_snapshot = snapshots[-2]
            with open(prev_snapshot, 'r') as f:
                stats = json.load(f)

            logger.info(f"Loaded previous snapshot: {prev_snapshot.name}")
            return stats
        except Exception as e:
            logger.error(f"Failed to load previous snapshot: {e}")
            return None

    def cleanup_old_snapshots(self):
        """Remove snapshots older than retention period."""
        try:
            cutoff = datetime.now() - timedelta(days=self.history_retention_days)

            for snapshot_file in self.history_dir.glob("snapshot_*.json"):
                # Parse timestamp from filename: snapshot_YYYYMMDD_HHMMSS.json
                try:
                    timestamp_str = snapshot_file.stem.split('_', 1)[1]
                    snapshot_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')

                    if snapshot_time < cutoff:
                        snapshot_file.unlink()
                        logger.info(f"Deleted old snapshot: {snapshot_file.name}")
                except (ValueError, IndexError) as e:
                    logger.warning(f"Could not parse snapshot timestamp: {snapshot_file.name}")
        except Exception as e:
            logger.error(f"Error during snapshot cleanup: {e}")

    def send_notification(self, stats: Dict, previous_stats: Optional[Dict] = None):
        """Send Slack notification with current stats and trends."""
        if not self.slack_webhook:
            logger.debug("No Slack webhook configured, skipping notification")
            return

        try:
            # Import here to avoid circular dependency issues
            from logcost.notifiers import send_slack_notification

            success = send_slack_notification(
                webhook_url=self.slack_webhook,
                stats=stats,
                provider=self.provider,
                top_n=self.top_n,
                previous_stats=previous_stats
            )

            if success:
                logger.info("Slack notification sent successfully")
            else:
                logger.warning("Failed to send Slack notification")
        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    def run(self):
        """Main sidecar loop."""
        logger.info("Starting sidecar monitoring loop")

        while True:
            try:
                # Load current stats
                stats = self.load_stats()

                if stats:
                    timestamp = datetime.now()

                    # Save snapshot for future trend analysis
                    self.save_snapshot(stats, timestamp)

                    # Load previous snapshot for comparison
                    previous_stats = self.load_previous_snapshot()

                    # Send notification
                    self.send_notification(stats, previous_stats)

                    # Cleanup old snapshots
                    self.cleanup_old_snapshots()
                else:
                    logger.debug("No stats available yet, waiting...")

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            # Sleep until next notification interval
            logger.info(f"Sleeping for {self.notification_interval}s until next check")
            time.sleep(self.notification_interval)


def main():
    """Entry point for sidecar."""
    logger.info("=" * 60)
    logger.info("LogCost Sidecar starting...")
    logger.info("=" * 60)

    sidecar = LogCostSidecar()
    sidecar.run()


if __name__ == "__main__":
    main()
