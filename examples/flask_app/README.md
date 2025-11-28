# Flask Example with LogCost

This example demonstrates how to integrate LogCost into a simple Flask application.

## What it does

The Flask app logs various messages at different levels:
- `INFO`: Request handling logs
- `DEBUG`: Detailed processing logs
- `WARNING`: Potential issues

LogCost tracks all these logs and measures their cost.

## Setup

1. Install dependencies:
```bash
pip install flask logcost
```

2. Run the app:
```bash
python app.py
```

The server starts at `http://localhost:5000`

## Making Requests

```bash
# Simple request
curl http://localhost:5000/

# Request with parameter (triggers debug logging)
curl http://localhost:5000/process/123

# Endpoint that generates a warning
curl http://localhost:5000/warning
```

## View Results

After making requests, export the LogCost stats:

```bash
python -c "import logcost; logcost.export('/tmp/flask_logcost.json')"
```

Analyze the results:

```bash
python -m logcost.cli analyze /tmp/flask_logcost.json --provider gcp --top 5
```

## Key Integration Points

The Flask app uses LogCost with minimal setup:

```python
import logcost

app = Flask(__name__)
logger = logging.getLogger(__name__)

# LogCost is automatically active on import
# All logging is tracked
```

No additional configuration needed - LogCost hooks the logging module automatically.

## Cost Insights

For this simple demo, costs will be minimal. But in production, you'd see:

- DEBUG logs in loops adding up to significant costs
- Library tracing (Flask, Werkzeug) generating extra logs
- Verbose error messages producing large payloads

LogCost identifies these patterns so you can fix them.
