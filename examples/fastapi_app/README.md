# FastAPI Example

Demonstrates integrating LogCost with an async FastAPI service.

```bash
pip install fastapi uvicorn
python main.py
```

Hit `http://localhost:8000` and `/users/alice` to generate logs, then export stats:

```python
import logcost
logcost.export("/tmp/fastapi_logcost.json")
```

Analyze with:

```bash
python -m logcost.cli analyze /tmp/fastapi_logcost.json --provider gcp
```
