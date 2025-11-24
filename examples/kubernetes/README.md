# LogCost Kubernetes Deployment

This directory contains Kubernetes manifests for deploying LogCost using the sidecar pattern.

## Architecture

The deployment uses two containers in each pod:

1. **App Container**: Your application with LogCost library installed
   - Imports `logcost` and calls `logcost.start_periodic_flush()`
   - Writes stats to `/var/log/logcost/stats.json` (shared volume)
   - Focuses on business logic with minimal overhead

2. **LogCost Sidecar Container**: Monitoring and notification container
   - Watches the shared stats file
   - Aggregates data over time
   - Stores historical snapshots (7 days retention by default)
   - Sends periodic Slack notifications (1 hour interval by default)
   - Provides week-over-week trend analysis

## Quick Start

### 1. Build the LogCost Docker Image

```bash
cd LogCost/
docker build -t logcost/logcost:latest .

# If using a registry, push the image
docker tag logcost/logcost:latest your-registry/logcost:latest
docker push your-registry/logcost:latest
```

### 2. Create Slack Webhook Secret

First, create a Slack Incoming Webhook:
- Go to https://api.slack.com/messaging/webhooks
- Create a new webhook for your channel
- Copy the webhook URL

Then create the Kubernetes secret:

```bash
kubectl create secret generic logcost-slack-webhook \
  --from-literal=webhook-url='https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
```

### 3. Update Your Application

Add LogCost to your application's Dockerfile:

```dockerfile
# In your app's Dockerfile
RUN pip install logcost
```

Add initialization code to your application:

```python
# In your app's main.py or __init__.py
import logcost

# Start periodic flush to shared volume
logcost.start_periodic_flush("/var/log/logcost/stats.json")

# Your normal logging continues as usual
import logging
logger = logging.getLogger(__name__)
logger.info("Application started")
```

### 4. Deploy to Kubernetes

Edit `deployment.yaml` to use your app's image:

```yaml
containers:
- name: app
  image: your-registry/myapp:latest  # Update this
```

Apply the deployment:

```bash
kubectl apply -f deployment.yaml
```

### 5. Verify Deployment

Check that both containers are running:

```bash
kubectl get pods -l app=myapp
kubectl describe pod <pod-name>
```

Check sidecar logs:

```bash
kubectl logs <pod-name> -c logcost-sidecar
```

You should see:
```
LogCost Sidecar starting...
LogCost Sidecar initialized
  Watch path: /var/log/logcost/stats.json
  Notification interval: 3600s
  Slack configured: True
```

## Configuration

### Environment Variables

**App Container:**
- `LOGCOST_OUTPUT`: Path to write stats file (default: `/tmp/logcost_stats.json`)
- `LOGCOST_FLUSH_INTERVAL`: Seconds between flushes (default: `300` = 5 minutes)
- `LOGCOST_MAX_FILE_SIZE`: Max file size before rotation (default: `10485760` = 10MB)

**Sidecar Container:**
- `LOGCOST_WATCH_PATH`: Path to stats file (default: `/var/log/logcost/stats.json`)
- `LOGCOST_NOTIFICATION_INTERVAL`: Seconds between notifications (default: `3600` = 1 hour)
- `LOGCOST_HISTORY_DIR`: Directory for snapshots (default: `/var/log/logcost/history`)
- `LOGCOST_HISTORY_RETENTION`: Days to keep history (default: `7`)
- `LOGCOST_PROVIDER`: Cloud provider: `gcp`, `aws`, or `azure` (default: `gcp`)
- `LOGCOST_NOTIFICATION_TOP_N`: Number of top logs in report (default: `5`)
- `LOGCOST_SLACK_WEBHOOK`: Slack webhook URL (from secret)

### Resource Limits

The sidecar is designed to be lightweight:

```yaml
resources:
  requests:
    memory: "64Mi"
    cpu: "50m"
  limits:
    memory: "128Mi"
    cpu: "100m"
```

Adjust based on your notification frequency and data volume.

## Notification Example

Slack notifications include:

- **Summary**: Total cost, data volume, log call count
- **Trends**: Week-over-week cost change (if available)
- **Top N Logs**: Most expensive log statements with file:line references
- **Warnings**: Anti-pattern detection (high-frequency logs, DEBUG in production, large payloads)

Example notification:

```
*LogCost Report - GCP*
Total: 124.5 MB ($0.062)
Log calls: 45,234
Trend: 📈 +12.5% from previous period

*🔥 Top 5 Most Expensive Logs:*
1. `api/handler.py:42` - $0.025 (50 MB, 1,234 calls)
   _Processing user data for request_
2. `worker/task.py:89` - $0.015 (30 MB, 890 calls)
   _Background job execution_
...

*⚠️ Warnings:*
• High-frequency log in api/handler.py:42 (1,234 calls)
• DEBUG logs in production detected
```

## Troubleshooting

### Sidecar not sending notifications

1. Check secret is mounted correctly:
```bash
kubectl exec <pod-name> -c logcost-sidecar -- env | grep LOGCOST_SLACK_WEBHOOK
```

2. Check sidecar logs for errors:
```bash
kubectl logs <pod-name> -c logcost-sidecar --tail=50
```

3. Verify stats file is being created:
```bash
kubectl exec <pod-name> -c app -- ls -lh /var/log/logcost/
```

### No stats file created

Check that your app is calling `logcost.start_periodic_flush()`:

```bash
kubectl logs <pod-name> -c app | grep -i logcost
```

### High memory usage in sidecar

Reduce notification frequency or retention period:

```yaml
- name: LOGCOST_NOTIFICATION_INTERVAL
  value: "7200"  # 2 hours instead of 1
- name: LOGCOST_HISTORY_RETENTION
  value: "3"  # 3 days instead of 7
```

## Advanced: Multiple Applications

To deploy LogCost with multiple applications, simply add the sidecar to each deployment:

```yaml
# app1-deployment.yaml
containers:
- name: app1
  image: your-registry/app1:latest
- name: logcost-sidecar
  image: logcost/logcost:latest
  # ... same sidecar config

# app2-deployment.yaml
containers:
- name: app2
  image: your-registry/app2:latest
- name: logcost-sidecar
  image: logcost/logcost:latest
  # ... same sidecar config
```

Each sidecar monitors its own app's stats file independently.

## Security Notes

- The Slack webhook URL is a credential - store it in a Kubernetes secret
- The sidecar runs as non-root user (UID 1000) for security
- Use `emptyDir` volume for stats file sharing (ephemeral, not persisted)
- Historical snapshots are lost on pod restart (by design for security)

## Next Steps

- Set up alerting rules in Slack for high costs
- Integrate with CI/CD to track cost changes across deployments
- Use `diff` command to compare before/after cost impacts
