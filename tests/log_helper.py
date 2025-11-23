import logging


def log_via_helper(tracker, message):
    """Helper used to ensure tracker can skip helper modules."""
    tracker._track_call(logging.INFO, f"helper: {message}", ())
