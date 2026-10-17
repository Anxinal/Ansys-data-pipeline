"""Open an AEDT session from a local project file or folder.

The path can be an ``.aedt`` project file, its ``<name>.aedtresults`` folder,
or a folder containing exactly one ``.aedt`` project.

Usage:
    .venv/bin/python -i opensession.py path/to/project.aedt [--gui]

With ``-i`` the opened session stays available as ``session`` in the REPL.
"""

import argparse
import sys
from pathlib import Path


def find_project_file(path):
    """Resolve a file or folder to the .aedt project to open."""
    path = Path(path).expanduser().resolve()
    if path.is_file():
        if path.suffix.lower() != ".aedt":
            raise ValueError(f"Not an AEDT project file: {path}")
        return path
    if not path.is_dir():
        raise FileNotFoundError(f"No such file or folder: {path}")

    if path.name.endswith(".aedtresults"):
        project = path.with_name(path.name.removesuffix(".aedtresults") + ".aedt")
        if project.is_file():
            return project

    candidates = sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".aedt")
    if not candidates:
        raise FileNotFoundError(f"No .aedt project found in {path}")
    if len(candidates) > 1:
        names = "\n  ".join(p.name for p in candidates)
        raise ValueError(f"Several .aedt projects found in {path}, pass one explicitly:\n  {names}")
    return candidates[0]


def open_session(path, gui=False, design=None):
    """Launch AEDT and load the project, returning the PyAEDT app for its active design."""
    from ansys.aedt.core import Desktop

    project_file = find_project_file(path)
    print(f"Opening {project_file} in AEDT...")
    desktop = Desktop(non_graphical=not gui, new_desktop=True)
    return desktop.load_project(str(project_file), design_name=design)


def main():
    parser = argparse.ArgumentParser(description="Open an AEDT session from a local project file or folder.")
    parser.add_argument("path", type=Path, help=".aedt project file, or a folder containing one")
    parser.add_argument("--gui", action="store_true", help="show the AEDT GUI")
    parser.add_argument("--design", help="design to activate (default: the project's active design)")
    args = parser.parse_args()
    return open_session(args.path, gui=args.gui, design=args.design)


if __name__ == "__main__":
    session = main()
    print(f"Session ready: {type(session).__name__}")
    if not sys.flags.interactive:
        input("Press Enter to close the session...")
