# Django Example

Minimal Django project instrumented with LogCost.

## Setup

```bash
pip install django
python manage.py migrate
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` or `/user/alice/` to generate logs. Export stats:

```python
import logcost
logcost.export("/tmp/django_logcost.json")
```

Then analyze via:

```bash
python -m logcost.cli analyze /tmp/django_logcost.json --provider gcp
```
