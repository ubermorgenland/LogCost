# LogCost

Open-source runtime logging cost tracker for Python services. Drop-in instrument (just `import logcost`) that measures which log statements generate the most data and helps you cut cloud logging bills.

## Features

- Monkey-patches `logging` and `print` to measure file/line, level, message template, call count, and bytes for every log statement.
- Thread-safe tracking with zero code changes, framework integration examples (Flask, FastAPI), and export helpers (JSON, CSV, Prometheus, HTML).
- Analyzer/CLI to compute cloud-provider cost estimates, highlight anti-patterns, and compare runs (`analyze`, `report`, `estimate`, `diff`, `capture`).

## Quick Start

```bash
pip install -e .
python - <<'PY'
import logcost, logging

logging.getLogger().setLevel(logging.INFO)
logging.info("Processing user %s", 123)
stats_file = logcost.export("/tmp/logcost_stats.json")
print("Exported stats to", stats_file)
PY

python -m logcost.cli analyze /tmp/logcost_stats.json --provider gcp
```

For a full tutorial see `docs/quickstart.md`.

## CLI

```
python -m logcost.cli analyze stats.json --top 5
python -m logcost.cli report stats.json reports/analysis.json
python -m logcost.cli estimate stats.json --reduction 0.4 --hours 12 --rate 120
python -m logcost.cli diff stats_before.json stats_after.json
python -m logcost.cli capture /tmp/logcost_stats.json
```

## Examples

- `examples/flask_app` – classic Flask demo with tracked routes.
- `examples/fastapi_app` – async FastAPI example showing integration with ASGI apps.
- `examples/django_app` – minimal Django project with LogCost enabled in `settings.py`.
- `examples/kubernetes` – deployment manifest + sidecar capture instructions.

## License

MIT. Contributions welcome! See `docs/faq.md` for common questions.***
