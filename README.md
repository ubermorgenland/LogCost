# LogCost

**Your cloud logging bill is $2,000/month. One debug statement in a hot path is responsible for $800 of it.**

LogCost finds expensive log statements in production Python services. Drop-in instrumentation (just `import logcost`) pinpoints which lines generate the most data, helping you cut cloud logging costs by 40-60% without guessing.

**Example:** A single `logger.debug(f"Processing {user_data}")` inside a request loop can log 50 MB/day at $15/month. LogCost shows you the exact file:line, call count, and bytes so you can fix the top 5 offenders and save hundreds monthly.

## Features

- **Zero-config tracking** - Monkey-patches `logging` and `print` to measure file/line, level, message template, call count, and bytes
- **Thread-safe** - Lock-protected tracking works across concurrent requests
- **Framework support** - Examples for Flask, FastAPI, Django, Kubernetes
- **Export options** - JSON, CSV, Prometheus, HTML reports
- **Cost analysis** - Compute GCP/AWS/Azure cost estimates and identify anti-patterns
- **Performance** - Low overhead design for production use

## Quick Start

```bash
pip install -e .
```

```python
import logcost
import logging

logging.getLogger().setLevel(logging.INFO)
logging.info("Processing user %s", 123)

stats_file = logcost.export("/tmp/logcost_stats.json")
print("Exported to", stats_file)
```

Analyze the results:

```bash
python -m logcost.cli analyze /tmp/logcost_stats.json --provider gcp --top 5
```

## Installation

```bash
# From source
git clone https://github.com/ubermorgenland/LogCost.git
cd LogCost
pip install -e .

# Run tests
pytest tests/

# Install with development dependencies
pip install -e ".[dev]"
```

## Usage

### Basic Tracking

```python
import logcost  # auto-installs tracker on import
import logging

logger = logging.getLogger(__name__)

# Your normal logging code
logger.info("Processing order %s", order_id)
logger.debug("User data for %s", user_id)
print("Debug output")  # print() is also tracked

# Export stats (automatically on exit, or manually)
stats_path = logcost.export("/tmp/logcost_stats.json")
```

### Skipping Helper Modules

If you wrap logging in helper utilities:

```python
import logcost

# Ignore helper frames to attribute cost to original caller
logcost.ignore_module("myapp.logging_helpers")
```

### Long-Running Services

For services that don't exit:

```python
import signal
import logcost

def handle_sigusr1(signum, frame):
    logcost.export("/tmp/logcost_snapshot.json")

signal.signal(signal.SIGUSR1, handle_sigusr1)
```

Or use the CLI:

```bash
python -m logcost.cli capture /tmp/logcost_stats.json
```

### Slack Notifications

Get proactive alerts about logging costs in your Slack channel:

**Setup:**
1. Create a Slack Incoming Webhook:
   - Go to https://api.slack.com/messaging/webhooks
   - Click "Create your Slack app" → "Incoming Webhooks"
   - Activate and create a webhook for your channel
   - Copy the webhook URL (e.g., `https://hooks.slack.com/services/T00.../B00.../XXX...`)

2. Configure environment variables:
```bash
export LOGCOST_SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
export LOGCOST_PROVIDER="gcp"  # or "aws", "azure"
export LOGCOST_NOTIFICATION_TOP_N="5"  # number of top logs to show
```

**Usage:**

Automatic notifications with periodic flush:
```python
import logcost

# Start periodic flush - automatically sends Slack notifications
logcost.start_periodic_flush("/var/log/logcost/stats.json")
# Notifications sent every 5 minutes (configurable via LOGCOST_FLUSH_INTERVAL)
```

Manual notification:
```python
import logcost
from logcost import send_notification_if_configured

stats = logcost.get_stats()
send_notification_if_configured(stats)  # Uses LOGCOST_SLACK_WEBHOOK env var
```

**Notification includes:**
- Total logging cost and volume
- Top N most expensive log statements with file:line references
- Anti-pattern warnings (DEBUG in production, high-frequency loops, large payloads)
- Week-over-week trend (if available)

**Security Note:** The webhook URL is a credential - treat it like a password. Never commit it to version control. Use environment variables, Kubernetes secrets, or secrets managers.

## CLI Commands

### Analyze

Show top expensive log statements:

```bash
python -m logcost.cli analyze stats.json --top 10 --provider gcp
```

### Report

Export analysis to JSON:

```bash
python -m logcost.cli report stats.json reports/analysis.json
```

### Estimate ROI

Calculate potential savings:

```bash
python -m logcost.cli estimate stats.json --reduction 0.4 --hours 12 --rate 120
```

- `--reduction`: Expected cost reduction (0.4 = 40%)
- `--hours`: Engineering hours to fix
- `--rate`: Hourly rate in USD

### Diff

Compare before/after:

```bash
python -m logcost.cli diff stats_before.json stats_after.json
```

### Capture

Snapshot running service:

```bash
python -m logcost.cli capture /tmp/logcost_stats.json
```

## Framework Integration

### Flask / WSGI

```python
import logcost
from flask import Flask

app = Flask(__name__)
logger = app.logger

@app.route("/")
def hello():
    logger.info("Homepage accessed")
    return "Hello"

if __name__ == "__main__":
    app.run()
    # Stats exported automatically on exit
```

See `examples/flask_app/` for full example.

### FastAPI / ASGI

```python
import logcost
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    logger.info("Root endpoint hit")
    return {"message": "Hello"}
```

The tracker works with async code since it hooks the core `logging` machinery.
See `examples/fastapi_app/` for complete demo.

### Django

Import in `settings.py` so tracker attaches before middleware:

```python
# settings.py
import logcost

# ... rest of settings
```

Run your app and export stats:

```bash
python manage.py runserver
# In another terminal
python -m logcost.cli capture /tmp/django_logcost.json
```

See `examples/django_app/` for full setup.

### Docker & Kubernetes (Sidecar Pattern)

For production deployments, LogCost uses a sidecar architecture that separates logging from monitoring:

**Architecture:**
- **App Container**: Your application with LogCost library installed, writes stats to shared volume
- **Sidecar Container**: LogCost monitoring container that watches stats, aggregates data, stores history, and sends notifications

**Benefits:** Separation of concerns, reusable sidecar, no application code changes after setup

#### Build and Publish Docker Image

Build locally:
```bash
cd LogCost/
docker build -t logcost/logcost:latest .
```

Publish to Docker Hub (requires Docker Hub account):
```bash
# Login to Docker Hub
docker login

# Build and push
docker build -t your-username/logcost:latest .
docker push your-username/logcost:latest

# Or build for multiple architectures (recommended)
docker buildx build --platform linux/amd64,linux/arm64 \
  -t your-username/logcost:latest \
  -t your-username/logcost:v0.1.0 \
  --push .
```

See [DOCKER.md](DOCKER.md) for complete publishing guide including GitHub Actions automation, other registries (GCR, ECR, ACR), security scanning, and versioning strategy.

#### Kubernetes Deployment

Add LogCost sidecar to your deployment:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-with-logcost
spec:
  template:
    spec:
      containers:
      # Your application
      - name: app
        image: your-registry/myapp:latest
        env:
        - name: LOGCOST_OUTPUT
          value: /var/log/logcost/stats.json
        - name: LOGCOST_FLUSH_INTERVAL
          value: "300"  # 5 minutes
        volumeMounts:
        - name: logcost-data
          mountPath: /var/log/logcost

      # LogCost sidecar
      - name: logcost-sidecar
        image: logcost/logcost:latest
        env:
        - name: LOGCOST_NOTIFICATION_INTERVAL
          value: "3600"  # 1 hour
        - name: LOGCOST_PROVIDER
          value: gcp  # or aws, azure
        - name: LOGCOST_SLACK_WEBHOOK
          valueFrom:
            secretKeyRef:
              name: logcost-slack-webhook
              key: webhook-url
        volumeMounts:
        - name: logcost-data
          mountPath: /var/log/logcost
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "128Mi"
            cpu: "100m"

      volumes:
      - name: logcost-data
        emptyDir: {}
```

Your app code needs one line:

```python
import logcost
logcost.start_periodic_flush("/var/log/logcost/stats.json")
```

The sidecar will automatically:
- Watch for stats updates
- Store historical snapshots (7 days retention)
- Send hourly Slack notifications with trends
- Detect anti-patterns (DEBUG in production, high-frequency logs, large payloads)

See `examples/kubernetes/` for complete manifests and setup instructions.

## Cost Calculation

The analyzer estimates cost using:

```
cost = (bytes_emitted / 1GB) × price_per_gb
```

**Default Pricing:**
- GCP: $0.50/GB
- AWS: $0.57/GB
- Azure: $0.63/GB

Override pricing:

```python
from logcost.analyzer import CostAnalyzer

analyzer = CostAnalyzer(stats, price_per_gb=0.75)
```

Or via CLI:

```bash
python -m logcost.cli analyze stats.json --provider gcp
```

### Anti-Pattern Detection

The analyzer flags:

- **High-frequency logs** - Statements executed >1,000 times (likely tight loops)
- **Debug logs in production** - DEBUG level logs producing non-zero cost
- **Large payloads** - Messages exceeding 5 KB per call

### ROI Calculation

```
potential_savings = total_cost × reduction_percent
effort_cost = hours_to_fix × hourly_rate
roi = (potential_savings - effort_cost) / effort_cost
```

Example:

```bash
python -m logcost.cli estimate stats.json --reduction 0.5 --hours 8 --rate 100
```

Output:
```
Potential monthly savings: $250.00
Effort cost: $800.00
ROI: -68.75% (not worth it)
```

## FAQ

**Does LogCost change my logging behavior?**
No. It wraps `logging.Logger._log` and `print` but always calls the original implementation after recording stats.

**What about other logging libs (structlog, loguru)?**
Most delegate to Python's `logging` module. If not, you can manually call `logcost.tracker._track_call()`. Adapters are planned.

**How often should I export?**
For scripts, rely on the built-in `atexit` export. For long-running services, export on intervals (cron, signal handler, or sidecar) to avoid losing stats on crashes.

**Is tracking configurable?**
Use `logcost.ignore_module("module.prefix")` to skip helper frames. Anti-pattern thresholds are constants in `logcost/analyzer.py` (PRs welcome for config support).

**Performance impact?**
Designed for low overhead (lock-protected dict updates + string formatting). Run the benchmark to measure on your hardware:

```bash
python benchmarks/tracker_benchmark.py --iterations 100000
```

## Examples

- **`examples/flask_app/`** - Classic Flask app with tracked routes
- **`examples/fastapi_app/`** - Async FastAPI integration
- **`examples/django_app/`** - Minimal Django project with LogCost
- **`examples/kubernetes/`** - K8s deployment + sidecar pattern

## Contributing

Contributions welcome! See `CONTRIBUTING.md` for guidelines.

## License

MIT License - see `LICENSE` file for details.
