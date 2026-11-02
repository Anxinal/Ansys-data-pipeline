"""Keep the connection alive through validation errors so state can be restored."""
from contextlib import contextmanager
from ansys.aedt.core import settings


@contextmanager
def keep_session_on_error():
    original = settings.release_on_exception
    settings.release_on_exception = False
    try:
        yield
    finally:
        settings.release_on_exception = original
