# Integration Guide

## Flask / WSGI

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
```

LogCost installs automatically on import; call `logcost.export()` during shutdown or via `python -m logcost.cli capture` to persist stats.

## FastAPI / ASGI

See `examples/fastapi_app/main.py`. The tracker works with async code because it hooks the core `logging` machinery—just import `logcost` before creating the `FastAPI` app.

## Django

The Django example (`examples/django_app`) imports `logcost` inside `settings.py` so the tracker attaches before middleware/apps run. After running `python manage.py runserver`, hit endpoints to generate logs and export stats via `logcost.export()`.

## Kubernetes

- Mount a writable volume (e.g., `/var/log/logcost`).
- Call `logcost.export("/var/log/logcost/<pod>.json")` on intervals or use the CLI `capture` subcommand.
- Optional sidecar can read those JSON files and ship them to object storage or your SaaS (see `examples/kubernetes/deployment.yaml`).

## Skipping Helper Modules

If you wrap logging in helper utilities, call `logcost.ignore_module("myapp.logging_helpers")` so the tracker attributes cost to the original caller frame rather than your helper.
