import os
import warnings
from typing import Optional


def get_env_int(name: str, default: int) -> int:
    """Return an integer environment variable value with fallback."""
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        warnings.warn(
            f"Invalid value for {name}: {value!r}. Using default {default}.",
            RuntimeWarning,
            stacklevel=2,
        )
        return default


def get_env_int_or_none(name: str) -> Optional[int]:
    """Return integer env value or None if unset/invalid."""
    value = os.getenv(name)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        warnings.warn(
            f"Invalid value for {name}: {value!r}. Ignoring.",
            RuntimeWarning,
            stacklevel=2,
        )
        return None
