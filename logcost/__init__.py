"""
LogCost - Track what each log statement costs in production

Usage:
    import logcost  # ← That's it! Auto-installs tracking

    # Your existing code works unchanged
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Processing order %s", order_id)  # ← Now tracked!

    # Optional: Export stats manually
    logcost.export("/path/to/stats.json")

GitHub: https://github.com/logcost/logcost-python
Docs: https://logcost.io/docs
"""

__version__ = "0.1.0"

from .tracker import install, export, get_stats, reset, ignore_module
from .analyzer import CostAnalyzer
from .exporters import export_csv, export_prometheus, render_html_report

# Auto-install on import (the magic!)
install()

__all__ = [
    "install",
    "export",
    "get_stats",
    "reset",
    "ignore_module",
    "CostAnalyzer",
    "export_csv",
    "export_prometheus",
    "render_html_report",
]
