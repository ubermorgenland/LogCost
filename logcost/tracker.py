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
from pathlib import Path
from threading import Lock
from typing import Dict, Optional


class LogCostTracker:
    """Tracks logging costs at runtime with minimal overhead."""

    def __init__(self):
        self.stats: Dict[str, Dict] = {}
        self._lock = Lock()
        self._original_log = None
        self._original_print = None
        self._installed = False
        self._skip_module_prefixes = {"logging", __name__}
        self._skip_path_suffixes = {"logging/__init__.py", "logcost/tracker.py"}

    def install(self):
        """Monkey-patch logging.Logger._log to track calls."""
        if self._installed:
            return

        self._original_log = logging.Logger._log

        # Create a wrapper that properly binds to this tracker instance
        tracker = self
        def tracked_log_wrapper(logger_self, level, msg, args, **kwargs):
            """Replacement for Logger._log that tracks the call."""
            # Track this log call
            tracker._track_call(level, msg, args)

            # Call original logging
            return tracker._original_log(logger_self, level, msg, args, **kwargs)

        logging.Logger._log = tracked_log_wrapper

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
                # Record as a PRINT level
                self._track_call("PRINT", message, ())
                return self._original_print(*args, **kwargs)

            builtins.print = tracked_print

        self._installed = True

    def _track_call(self, level, msg, args):
        """Track a single log call."""
        try:
            # Find the first frame outside of logging internals
            # This is more robust than hardcoding frame depth
            frame = inspect.currentframe()
            caller_frame = None

            # Walk up the stack looking for user code
            current = frame
            while current:
                filename = current.f_code.co_filename
                module_name = current.f_globals.get("__name__", "")
                skip_logging = any(
                    module_name.startswith(prefix)
                    for prefix in self._skip_module_prefixes
                    if module_name
                )
                skip_structures = any(
                    filename.endswith(suffix) for suffix in self._skip_path_suffixes
                )
                if not (skip_logging or skip_structures or "importlib" in filename):
                    caller_frame = current
                    break
                current = current.f_back
            # Avoid reference cycles
            del frame
            frame = None
            del current
            current = None

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
            # Truncate message for key (first 50 chars)
            msg_key = str(msg)[:50] if msg else ""
            key = f"{file_path}:{line_no}|{level_name}|{msg_key}"

            # Estimate bytes
            # Format the message with args to get actual size
            if args:
                try:
                    formatted_msg = str(msg) % args
                except (TypeError, ValueError):
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
        if module_prefix:
            self._skip_module_prefixes.add(module_prefix)


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


# Auto-install on shutdown
import atexit
atexit.register(lambda: _tracker.export() if _tracker._installed else None)
