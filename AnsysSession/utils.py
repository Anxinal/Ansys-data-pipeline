"""Helpers for the AEDT layer."""

import re


def safe(getter):
    """Return getter(), or a short note if AEDT can't provide the value."""
    try:
        return getter()
    except Exception as e:
        return f"<unavailable: {e}>"


def file_stem(name):
    """Make an AEDT name (which may contain spaces or colons) safe for a file name."""
    return re.sub(r"[^\w.-]+", "_", name).strip("_")
