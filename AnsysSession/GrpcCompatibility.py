"""Scoped workaround for PyAEDT 1.0.1 design-proxy metadata assignment."""
from contextlib import contextmanager
from importlib.metadata import version
from threading import RLock
import importlib
import socket


_activation_lock = RLock()


@contextmanager
def local_grpc_port_detection(port=None):
    """Accept a reachable localhost port when process discovery misses it.

    The native AEDT client still performs its real RPC connection. This changes
    only the preliminary process-based check, for the selected port and scope.
    Leave port unset around a new Desktop constructor to check its assigned port.
    """
    module = importlib.import_module("ansys.aedt.core.desktop")
    with _activation_lock:
        original = module.is_grpc_session_active

        def detect(candidate, machine=None):
            detected = original(candidate, machine)
            if detected or (port is not None and candidate != port) or not candidate or machine not in (None, "", "localhost", "127.0.0.1", "::1"):
                return detected
            try:
                with socket.create_connection(("127.0.0.1", candidate), timeout=1):
                    return True
            except OSError:
                return False

        module.is_grpc_session_active = detect
        try:
            yield
        finally:
            module.is_grpc_session_active = original


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
