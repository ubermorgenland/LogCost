import json
from types import SimpleNamespace

from logcost import notifiers


def _sample_stats():
    return {
        "app.py:10|INFO": {
            "file": "app.py",
            "line": 10,
            "level": "INFO",
            "message_template": "Processed %s",
            "count": 5,
            "bytes": 500,
        }
    }


def test_send_slack_notification_success(monkeypatch):
    captured = {}

    class DummyResponse(SimpleNamespace):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout=10):
        captured["url"] = request.full_url
        captured["data"] = json.loads(request.data.decode("utf-8"))
        return DummyResponse(status=200)

    monkeypatch.setattr(notifiers.request, "urlopen", fake_urlopen)

    ok = notifiers.send_slack_notification(
        "https://hooks.slack.com/services/test",
        _sample_stats(),
        provider="gcp",
        top_n=1,
    )

    assert ok is True
    assert captured["url"] == "https://hooks.slack.com/services/test"
    assert "blocks" in captured["data"]


def test_send_slack_notification_failure(monkeypatch):
    def fake_urlopen(*_, **__):
        raise notifiers.urllib_error.URLError("boom")

    monkeypatch.setattr(notifiers.request, "urlopen", fake_urlopen)
    ok = notifiers.send_slack_notification("https://hooks.slack.com/services/test", _sample_stats())
    assert ok is False


def test_send_notification_if_configured(monkeypatch):
    monkeypatch.setenv("LOGCOST_SLACK_WEBHOOK", "https://hooks.slack.com/services/test")
    monkeypatch.setenv("LOGCOST_PROVIDER", "aws")
    monkeypatch.setenv("LOGCOST_NOTIFICATION_TOP_N", "2")

    called = {}

    def fake_send(*args, **kwargs):
        called.update(kwargs)
        return True

    monkeypatch.setattr(notifiers, "send_slack_notification", fake_send)

    ok = notifiers.send_notification_if_configured(_sample_stats(), test_notification=True)
    assert ok is True
    assert called["provider"] == "aws"
    assert called["top_n"] == 2
    assert called["test_notification"] is True
