import json
import logging
import os
import subprocess
import sys
import threading

from logcost.tracker import LogCostTracker


def test_atexit_export(tmp_path):
    output_file = tmp_path / "atexit_stats.json"
    script = """
import logging
import logcost

logger = logging.getLogger("atexit-test")
logger.warning("atexit entry %s", 1)
"""
    env = os.environ.copy()
    env["LOGCOST_OUTPUT"] = str(output_file)
    subprocess.run([sys.executable, "-c", script], check=True, env=env)

    assert output_file.exists()
    data = json.loads(output_file.read_text())
    assert any(
        entry["message_template"] == "atexit entry %s" for entry in data.values()
    )


def test_concurrent_exports_same_path(tmp_path):
    tracker = LogCostTracker()
    for idx in range(5):
        tracker._track_call(logging.INFO, "multi %s", (idx,))

    output_file = tmp_path / "shared_stats.json"
    errors = []

    def worker():
        try:
            tracker.export(str(output_file))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    data = json.loads(output_file.read_text())
    assert data
    assert all("count" in entry for entry in data.values())
