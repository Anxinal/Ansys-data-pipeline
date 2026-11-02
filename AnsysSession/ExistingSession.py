"""Attach to an explicit AEDT server without ever launching another instance."""
import importlib
import socket
from ansys.aedt.core import Desktop
from .GrpcCompatibility import local_grpc_metadata, local_grpc_port_detection


def connect_existing(port, version="2025.1", non_graphical=False):
    with socket.create_connection(("127.0.0.1", port), timeout=3):
        pass
    module = importlib.import_module("ansys.aedt.core.desktop")

    def refuse_launch(*args, **kwargs):
        raise RuntimeError(f"Existing AEDT port {port} could not be attached; new-session launch refused")

    with local_grpc_metadata(), local_grpc_port_detection(port):
        original = module.launch_aedt
        module.launch_aedt = refuse_launch
        try:
            return Desktop(version=version, new_desktop=False, port=port,
                           non_graphical=non_graphical, close_on_exit=False)
        finally:
            module.launch_aedt = original
