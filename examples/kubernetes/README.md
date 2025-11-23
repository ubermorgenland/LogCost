# Kubernetes Example

Deploys your service with LogCost enabled plus a sidecar exporting stats.

1. Build/push your app image with `logcost` installed and imported on startup.
2. Apply `deployment.yaml`, which mounts `/var/log/logcost` for both containers.
3. The sidecar runs `python -m logcost.cli capture /var/log/logcost/stats.json` periodically (adapt via cron/job) to export stats that you can collect with tools like Fluent Bit or upload to object storage.

Modify the sidecar to push stats to your aggregator or send them to the paid LogCost service when available.
