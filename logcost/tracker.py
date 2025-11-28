"""
LogCost Tracker - Runtime log cost tracking via monkey-patching

This module patches Python's logging module to track every log call
with file/line attribution and byte counting.
"""

import builtins
import logging
import inspect
import json
import os
import tempfile
import warnings
import time
import threading
import traceback
from pathlib import Path
from threading import Lock, Thread, Event
from typing import Dict, Optional

from .utils import get_env_int, get_env_int_or_none

PRINT_LEVEL = logging.INFO + 5
logging.addLevelName(PRINT_LEVEL, "PRINT")


class LogCostTracker:
    """Tracks logging costs at runtime with minimal overhead."""

    def __init__(self):
        self.stats: Dict[str, Dict] = {}
        self._lock = Lock()
        self._original_log = None
        self._original_print = None
        self._original_findCaller = None
        self._installed = False
        self._skip_module_prefixes = {"logging", __name__}
        self._skip_path_suffixes = {
            "logging/__init__.py",
            "logcost/tracker.py",
            "importlib",
        }
        self._max_skip_prefixes = 64
        self._max_stack_depth = 25
        # Thread-local storage for caller frame info
        self._thread_local = threading.local()

        # Periodic flush and rotation configuration
        self._flush_interval = get_env_int("LOGCOST_FLUSH_INTERVAL", 300)  # 5 minutes default
        self._max_file_size = get_env_int("LOGCOST_MAX_FILE_SIZE", 10 * 1024 * 1024)  # 10MB default
        self._max_backups = get_env_int("LOGCOST_MAX_BACKUPS", 5)
        self._flush_thread: Optional[Thread] = None
        self._flush_stop_event = Event()
        self._auto_flush_enabled = False
        self._output_path: Optional[str] = None
        self._notification_interval = get_env_int("LOGCOST_NOTIFICATION_INTERVAL", 3600)
        self._notification_last_sent = 0.0
        test_delay = get_env_int_or_none("LOGCOST_NOTIFICATION_TEST_DELAY")
        self._notification_test_delay = test_delay if test_delay is not None else -1
        self._notification_test_sent = False
        self._start_time = time.time()

    def install(self):
        """Monkey-patch logging.Logger._log to track calls."""
        if self._installed:
            return

        self._original_log = logging.Logger._log
        self._original_findCaller = logging.Logger.findCaller

        # Create a wrapper that properly binds to this tracker instance
        tracker = self
        def tracked_log_wrapper(logger_self, level, msg, args, **kwargs):
            """Replacement for Logger._log that tracks the call."""
            # Get the correct caller frame before logging
            caller_frame = tracker._get_caller_frame()

            # Store caller info in thread-local so findCaller can use it
            if caller_frame:
                tracker._thread_local.caller_filename = caller_frame.f_code.co_filename
                tracker._thread_local.caller_lineno = caller_frame.f_lineno
                tracker._thread_local.caller_funcname = caller_frame.f_code.co_name

            try:
                # Track this log call
                tracker._track_call(level, msg, args)

                # Call original logging
                return tracker._original_log(logger_self, level, msg, args, **kwargs)
            finally:
                # Clear the thread-local data
                tracker._thread_local.caller_filename = None
                tracker._thread_local.caller_lineno = None
                tracker._thread_local.caller_funcname = None

        # Override findCaller to use our stored caller info instead of inspecting the stack
        def patched_findCaller(logger_self, stack_info=False, stacklevel=1):
            """Override findCaller to use the correct caller info from LogCost."""
            # Check if we have cached caller info from LogCost wrapper
            if (hasattr(tracker._thread_local, 'caller_filename') and
                tracker._thread_local.caller_filename is not None):
                filename = tracker._thread_local.caller_filename
                lineno = tracker._thread_local.caller_lineno
                funcname = tracker._thread_local.caller_funcname
                # Return in the format expected by logging module
                # (filename, lineno, func_name, stack_info_str)
                sinfo = None
                if stack_info:
                    sinfo = traceback.format_stack(stack_info)  # pragma: no cover
                return (filename, lineno, funcname, sinfo)
            else:
                # Fall back to original if no cached info
                return tracker._original_findCaller(logger_self, stack_info=stack_info, stacklevel=stacklevel)

        logging.Logger._log = tracked_log_wrapper
        logging.Logger.findCaller = patched_findCaller

        if self._original_print is None:
            self._original_print = builtins.print

            def tracked_print(*args, **kwargs):
                """Replacement for builtins.print that tracks the call."""
                sep = kwargs.get("sep", " ")
                end = kwargs.get("end", "\n")
                try:
                    message = sep.join(str(arg) for arg in args) + end
                except Exception:
                    message = " ".join(str(arg) for arg in args)
                # Record as a PRINT level and keep level numeric for consistency
                self._track_call(PRINT_LEVEL, message, ())
                return self._original_print(*args, **kwargs)

            builtins.print = tracked_print

        self._installed = True

    def _get_caller_frame(self):
        """Extract the first frame outside of logging internals.

        Returns the frame object or None if not found.
        """
        frame = inspect.currentframe()
        caller_frame = None

        # Walk up the stack looking for user code
        current = frame
        depth = 0
        while current and depth < self._max_stack_depth:
            depth += 1
            filename = current.f_code.co_filename
            module_name = current.f_globals.get("__name__", "")
            skip_logging = any(
                module_name.startswith(prefix)
                for prefix in self._skip_module_prefixes
                if module_name
            )
            skip_structures = any(
                filename.endswith(suffix) or suffix in filename
                for suffix in self._skip_path_suffixes
            )
            if not (skip_logging or skip_structures):
                caller_frame = current
                break
            current = current.f_back

        # Avoid reference cycles
        del frame
        frame = None
        del current
        current = None

        return caller_frame

    def _track_call(self, level, msg, args):
        """Track a single log call."""
        try:
            # Find the first frame outside of logging internals
            caller_frame = self._get_caller_frame()

            if caller_frame:
                file_path = caller_frame.f_code.co_filename
                line_no = caller_frame.f_lineno
            else:
                file_path = "unknown"
                line_no = 0

            # Normalize file path
            try:
                file_path = str(Path(file_path).relative_to(Path.cwd()))
            except ValueError:
                # If not relative to cwd, just use basename
                file_path = Path(file_path).name

            # Create tracking key
            if isinstance(level, str):
                level_name = level
            else:
                level_name = logging.getLevelName(level)
            # Aggregate by file:line:level only (not by message content)
            # This ensures all logs from the same line are counted together
            key = f"{file_path}:{line_no}|{level_name}"

            # Estimate bytes. If there are args, try formatting to capture the
            # actual serialized size; otherwise fall back to the template string.
            if args:
                try:
                    formatted_msg = str(msg) % args
                except (TypeError, ValueError):
                    # Intentionally swallow format errors to avoid breaking user
                    # logging. Emitting a warning would risk recursion (tracker
                    # logging about itself) and add hot-path overhead; instead
                    # we fall back to the raw template for a best-effort count.
                    formatted_msg = str(msg)
            else:
                formatted_msg = str(msg)

            bytes_count = len(formatted_msg.encode('utf-8'))

            # Update stats (thread-safe)
            with self._lock:
                if key not in self.stats:
                    self.stats[key] = {
                        "file": file_path,
                        "line": line_no,
                        "level": level_name,
                        "message_template": str(msg),
                        "count": 0,
                        "bytes": 0
                    }

                self.stats[key]["count"] += 1
                self.stats[key]["bytes"] += bytes_count

        except Exception:
            # Silently fail to avoid breaking logging
            pass

    def export(self, output_path: Optional[str] = None) -> str:
        """Export collected stats to JSON file."""
        if output_path is None:
            output_path = os.getenv("LOGCOST_OUTPUT", "/tmp/logcost_stats.json")

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            stats_copy = dict(self.stats)

        temp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                delete=False,
                dir=str(output_file.parent),
                prefix=output_file.name,
                suffix=".tmp"
            ) as tmp_file:
                json.dump(stats_copy, tmp_file, indent=2)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
                temp_path = Path(tmp_file.name)

            temp_path.replace(output_file)
            temp_path = None
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)

        return str(output_file)

    def get_stats(self) -> Dict:
        """Get current stats (thread-safe copy)."""
        with self._lock:
            return dict(self.stats)

    def reset(self):
        """Clear all collected stats."""
        with self._lock:
            self.stats.clear()

    def add_skip_module(self, module_prefix: str):
        """Skip module prefixes when determining the caller."""
        if not module_prefix:
            return
        if module_prefix in self._skip_module_prefixes:
            return
        if len(self._skip_module_prefixes) >= self._max_skip_prefixes:
            warnings.warn(
                "Maximum number of skip modules reached; ignoring additional entries.",
                RuntimeWarning,
                stacklevel=2,
            )
            return
        self._skip_module_prefixes.add(module_prefix)

    def _send_notification_if_configured(self, test_notification: bool = False):
        """Send notification if webhook is configured via environment variable."""
        try:
            # Import here to avoid circular dependency
            from .notifiers import send_notification_if_configured

            stats = self.get_stats()
            if stats:
                send_notification_if_configured(stats, test_notification=test_notification)
        except Exception:
            # Silently fail to avoid breaking the application
            pass

    def _rotate_file(self, output_path: str):
        """Rotate log file if it exceeds max size."""
        output_file = Path(output_path)
        if not output_file.exists():
            return

        file_size = output_file.stat().st_size
        if file_size < self._max_file_size:
            return

        # Rotate: file.json -> file.json.1, file.json.1 -> file.json.2, etc.
        for i in range(self._max_backups - 1, 0, -1):
            old_backup = Path(f"{output_path}.{i}")
            new_backup = Path(f"{output_path}.{i + 1}")
            if old_backup.exists():
                if new_backup.exists():
                    new_backup.unlink()
                old_backup.rename(new_backup)

        # Move current file to .1
        backup = Path(f"{output_path}.1")
        if backup.exists():
            backup.unlink()
        output_file.rename(backup)

    def _periodic_flush_worker(self):
        """Background worker that periodically flushes stats to disk."""
        while not self._flush_stop_event.wait(self._flush_interval):
            try:
                if self._output_path and self._installed:
                    self._rotate_file(self._output_path)
                    self.export(self._output_path)

                    # Notification cadence
                    now = time.time()
                    send_notification = False
                    test_notification = False

                    if (
                        not self._notification_test_sent
                        and self._notification_test_delay >= 0
                        and now - self._start_time >= self._notification_test_delay
                    ):
                        send_notification = True
                        test_notification = True
                        self._notification_test_sent = True

                    if now - self._notification_last_sent >= self._notification_interval:
                        send_notification = True

                    if send_notification:
                        self._send_notification_if_configured(test_notification=test_notification)
                        self._notification_last_sent = now
            except Exception:
                # Silently fail to avoid breaking the application
                pass

    def start_periodic_flush(self, output_path: Optional[str] = None):
        """Start periodic flushing of stats to disk.

        Args:
            output_path: Path to write stats. Uses LOGCOST_OUTPUT env var if not provided.
        """
        if self._auto_flush_enabled:
            return  # Already running

        if output_path is None:
            output_path = os.getenv("LOGCOST_OUTPUT", "/tmp/logcost_stats.json")

        self._output_path = output_path
        self._auto_flush_enabled = True
        self._flush_stop_event.clear()

        self._flush_thread = Thread(target=self._periodic_flush_worker, daemon=True)
        self._flush_thread.start()

    def stop_periodic_flush(self):
        """Stop periodic flushing and perform final export."""
        if not self._auto_flush_enabled:
            return

        self._auto_flush_enabled = False
        self._flush_stop_event.set()

        if self._flush_thread:
            self._flush_thread.join(timeout=5.0)
            self._flush_thread = None

        # Final flush
        if self._output_path and self._installed:
            try:
                self.export(self._output_path)
            except Exception:
                pass


# Global tracker instance
_tracker = LogCostTracker()


def install():
    """Install the log cost tracker."""
    _tracker.install()


def export(output_path: Optional[str] = None) -> str:
    """Export stats to file and return path."""
    return _tracker.export(output_path)


def get_stats() -> Dict:
    """Get current tracking stats."""
    return _tracker.get_stats()


def reset():
    """Reset tracking stats."""
    _tracker.reset()


def ignore_module(module_prefix: str):
    """Skip the given module prefix when attributing log calls."""
    _tracker.add_skip_module(module_prefix)


def start_periodic_flush(output_path: Optional[str] = None):
    """Start periodic flushing of stats to disk.

    Useful for long-running services to avoid data loss. If configured,
    this will also send notifications to Slack after each flush.

    Args:
        output_path: Path to write stats. Uses LOGCOST_OUTPUT env var if not provided.

    Environment variables:
        LOGCOST_FLUSH_INTERVAL: Seconds between flushes (default: 300)
        LOGCOST_MAX_FILE_SIZE: Max file size in bytes before rotation (default: 10MB)
        LOGCOST_MAX_BACKUPS: Number of backup files to keep (default: 5)
        LOGCOST_SLACK_WEBHOOK: Slack webhook URL for notifications (optional)
        LOGCOST_PROVIDER: Cloud provider for cost calculation (gcp/aws/azure, default: gcp)
        LOGCOST_NOTIFICATION_TOP_N: Number of top logs to include in notification (default: 5)
    """
    _tracker.start_periodic_flush(output_path)


def stop_periodic_flush():
    """Stop periodic flushing and perform final export."""
    _tracker.stop_periodic_flush()


# Auto-install on shutdown
import atexit
atexit.register(lambda: _tracker.stop_periodic_flush() if _tracker._auto_flush_enabled else (_tracker.export() if _tracker._installed else None))
