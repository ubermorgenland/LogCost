import builtins
import json
import logging
import threading
from pathlib import Path

from tests import log_helper

import pytest

from logcost.tracker import LogCostTracker


@pytest.fixture()
def restore_monkey_patches():
    original_log = logging.Logger._log
    original_print = builtins.print
    yield
    logging.Logger._log = original_log
    builtins.print = original_print


def test_track_call_finds_user_frame():
    tracker = LogCostTracker()

    def helper():
        tracker._track_call(logging.INFO, "test message", ())

    helper()
    stats = tracker.get_stats()
    assert stats, "No stats recorded"
    entry = next(iter(stats.values()))
    assert entry["file"].endswith("tests/test_tracker.py")
    assert entry["line"] > 0


def test_track_call_counts_and_bytes():
    tracker = LogCostTracker()
    for _ in range(2):
        tracker._track_call(logging.WARNING, "hello %s", ("world",))

    entry = next(iter(tracker.get_stats().values()))
    assert entry["count"] == 2
    expected_bytes = len("hello world".encode("utf-8")) * 2
    assert entry["bytes"] == expected_bytes
    assert entry["message_template"] == "hello %s"


def test_track_call_handles_format_errors():
    tracker = LogCostTracker()
    tracker._track_call(logging.INFO, "value: %s %s", ("only_one",))

    entry = next(iter(tracker.get_stats().values()))
    # When formatting fails, the raw template is counted
    assert entry["bytes"] == len("value: %s %s".encode("utf-8"))
    assert entry["count"] == 1


def test_get_stats_returns_copy():
    tracker = LogCostTracker()
    tracker._track_call(logging.INFO, "msg", ())

    stats = tracker.get_stats()
    stats.clear()

    assert tracker.get_stats(), "Clearing copy should not clear tracker state"


def test_export_and_reset(tmp_path):
    tracker = LogCostTracker()
    tracker._track_call(logging.ERROR, "boom", ())

    output_path = tmp_path / "stats.json"
    exported = tracker.export(str(output_path))
    assert Path(exported).exists()
    with open(exported) as f:
        data = json.load(f)
    assert data

    tracker.reset()
    assert tracker.get_stats() == {}


def test_export_respects_env_var(tmp_path, monkeypatch):
    tracker = LogCostTracker()
    tracker._track_call(logging.INFO, "env msg", ())

    env_path = tmp_path / "env_stats.json"
    monkeypatch.setenv("LOGCOST_OUTPUT", str(env_path))

    exported = tracker.export()
    assert exported == str(env_path)
    assert env_path.exists()


def test_install_monkeypatches_logging(restore_monkey_patches):
    tracker = LogCostTracker()
    original_log = logging.Logger._log
    tracker.install()

    assert logging.Logger._log is not original_log

    logger = logging.getLogger("logcost-test")
    logger.warning("install worked %s", 1)

    stats = tracker.get_stats()
    assert stats
    entry = next(iter(stats.values()))
    assert entry["count"] == 1


def test_install_idempotent(restore_monkey_patches):
    tracker = LogCostTracker()
    original_log = logging.Logger._log

    tracker.install()
    first_wrapper = logging.Logger._log
    tracker.install()

    assert logging.Logger._log is first_wrapper
    assert tracker._original_log is original_log


def test_thread_safe_tracking():
    tracker = LogCostTracker()
    total_threads = 5
    per_thread = 50

    def worker():
        for _ in range(per_thread):
            tracker._track_call(logging.INFO, "thread-msg", ())

    threads = [threading.Thread(target=worker) for _ in range(total_threads)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    entry = next(iter(tracker.get_stats().values()))
    assert entry["count"] == total_threads * per_thread


def test_print_statements_tracked(restore_monkey_patches):
    tracker = LogCostTracker()
    tracker.install()

    print("print-test", 123, sep="|", end="")

    entry = next(iter(tracker.get_stats().values()))
    assert entry["level"] == "PRINT"
    assert entry["count"] == 1
    assert "print-test|123" in entry["message_template"]


def test_skip_module_prefix_finds_real_caller():
    tracker = LogCostTracker()

    log_helper.log_via_helper(tracker, "first")
    entry = next(iter(tracker.get_stats().values()))
    assert entry["file"].endswith("tests/log_helper.py")

    tracker.reset()
    tracker.add_skip_module("tests.log_helper")
    log_helper.log_via_helper(tracker, "second")
    entry = next(iter(tracker.get_stats().values()))
    assert entry["file"].endswith("tests/test_tracker.py")


def test_skip_module_limit(monkeypatch):
    tracker = LogCostTracker()
    tracker._skip_module_prefixes = set()
    tracker._max_skip_prefixes = 2
    tracker.add_skip_module("module.one")
    tracker.add_skip_module("module.two")
    with pytest.warns(RuntimeWarning):
        tracker.add_skip_module("module.three")
    assert len(tracker._skip_module_prefixes) == 2


def test_stack_depth_limit_results_in_unknown_file():
    tracker = LogCostTracker()
    tracker._max_stack_depth = 1
    tracker._track_call(logging.INFO, "depth test", ())
    entry = next(iter(tracker.get_stats().values()))
    assert entry["file"] == "unknown"
