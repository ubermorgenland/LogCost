# LogCost Quickstart

1. **Install**

```bash
pip install -e .
```

2. **Instrument your service**

```python
import logcost  # auto-installs tracker
import logging

logger = logging.getLogger(__name__)
logger.info("Processing order %s", order_id)
```

3. **Export stats**

```python
stats_path = logcost.export("/tmp/logcost_stats.json")
```

4. **Analyze**

```bash
python -m logcost.cli analyze /tmp/logcost_stats.json --provider gcp --top 5
```

Use `python -m logcost.cli capture` to snapshot long-running services, or `render_html_report` to generate a shareable HTML summary.
