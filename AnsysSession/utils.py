"""Helpers for the AEDT layer."""


def safe(getter):
    """Return getter(), or a short note if AEDT can't provide the value."""
    try:
        return getter()
    except Exception as e:
        return f"<unavailable: {e}>"
