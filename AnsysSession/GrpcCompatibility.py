"""Scoped workaround for PyAEDT 1.0.1 design-proxy metadata assignment."""
from contextlib import contextmanager
from importlib.metadata import version
from threading import RLock


_activation_lock = RLock()


@contextmanager
def local_grpc_metadata():
    """Keep internal AedtAPI metadata local during design activation.

    PyAEDT 1.0.1 writes ret.AedtAPI when an API call returns a design proxy.
    AedtPropServer treats that write as a possible remote property and queries
    GetPropNames, which stalls for newly pasted designs on AEDT 2025 R2.
    Intercept only this internal attribute; preserve real property handling and
    restore the original setter when the operation finishes or raises.
    """
    if version("pyaedt") != "1.0.1":
        yield
        return
    from ansys.aedt.core.internal.grpc_plugin_dll_class import AedtPropServer

    with _activation_lock:
        original = AedtPropServer.__setattr__

        def set_attribute(proxy, name, value):
            if name == "AedtAPI":
                object.__getattribute__(proxy, "__dict__")[name] = value
            else:
                original(proxy, name, value)

        AedtPropServer.__setattr__ = set_attribute
        try:
            yield
        finally:
            AedtPropServer.__setattr__ = original
