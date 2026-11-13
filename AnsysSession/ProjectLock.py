"""Find the owner of the configured project's lock without opening another session."""
import re
import shutil
from pathlib import Path

import psutil


def existing_project_port(project, output):
    lock = Path(str(project) + '.lock')
    if not lock.exists():
        return None
    text = lock.read_text()
    owner = re.search(r'DesktopProcessID=(\d+)', text)
    if not owner:
        raise RuntimeError(f'Cannot identify the session owning {lock}')
    if psutil.pid_exists(int(owner[1])):
        port = re.search(r'GRPCPort=(\d+)', text)
        if not port:
            raise RuntimeError(f'The configured project is open without a gRPC port: {lock}')
        return int(port[1])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(lock, output/'previous_stale_session.lock')
    lock.unlink()
    return None
