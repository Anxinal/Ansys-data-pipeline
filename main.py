"""Open the AEDT project through the session class and show its information.

Usage:
    .venv/bin/python main.py path/to/project.aedt [--design NAME]
"""

import argparse

from Session import Session


def main():
    parser = argparse.ArgumentParser(description="Open an AEDT project and print its information.")
    parser.add_argument("path", help=".aedt project file")
    parser.add_argument("--design", help="design to open (default: the project's active design)")
    args = parser.parse_args()

    s = Session(args.path, design=args.design)
    try:
        info = s.get_session_info()
    finally:
        # Close without saving: call s.save() first if you made edits.
        s.release()
    return info


if __name__ == "__main__":
    main()
