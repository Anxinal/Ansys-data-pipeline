"""Open an AEDT chip project, solve it in the open session and export its Bz image.

Usage:
    .venv/bin/python main.py path/to/project.aedt [options]

Run with --help for the options. The Bz image goes to Analysis.DEFAULT_OUTPUT_DIR
unless --output is given.
"""

import argparse
from pathlib import Path

import Analysis
from Analysis import BzAnalysis
from Chips import Chip
from Chips.Components.utils import print_info
from Session import Session


def parse_args():
    parser = argparse.ArgumentParser(description="Solve an AEDT chip project and export the Bz field image above its board.")
    parser.add_argument("path", help=".aedt project file")
    parser.add_argument("--design", help="design to open (default: the project's active design)")
    parser.add_argument("--info", action="store_true", help="also print everything the project can tell about itself")

    analysis = parser.add_argument_group("analysis")
    analysis.add_argument("--setup", default=Analysis.DEFAULT_SETUP, help="setup to solve (default: %(default)s)")
    analysis.add_argument("--cores", type=int, help="number of cores for the solve")
    analysis.add_argument("--no-solve", action="store_true", help="use the setup's existing solution instead of solving")
    analysis.add_argument("--output", type=Path, default=Analysis.DEFAULT_OUTPUT_DIR, help="export folder (default: %(default)s)")
    analysis.add_argument("--scan-height", type=float, default=Analysis.DEFAULT_SCAN_HEIGHT,
                          help="image plane height above the board top, in model units (default: %(default)s)")
    analysis.add_argument("--step", type=float, default=Analysis.DEFAULT_GRID_STEP,
                          help="image pixel size, in model units (default: %(default)s)")

    chip = parser.add_argument_group("chip parts", "names to use when the automatic choices don't match the model")
    chip.add_argument("--gnd", default="GND", help="GND component or excitation (default: %(default)s)")
    chip.add_argument("--vcc", default="VCC", help="VCC component or excitation (default: %(default)s)")
    chip.add_argument("--spheres", nargs=2, metavar="NAME", help="the two connection spheres")
    chip.add_argument("--board", help="the chip board")
    return parser.parse_args()


def main():
    args = parse_args()
    s = Session(args.path, design=args.design)
    try:
        if args.info:
            s.get_session_info()
        # Find the chip first, so a naming problem shows up before a long solve.
        chip = Chip(s.components, gnd=args.gnd, vcc=args.vcc, spheres=args.spheres, board=args.board)
        chip.print()

        analysis = BzAnalysis(s, setup=args.setup, output_dir=args.output)
        if not args.no_solve:
            analysis.solve(cores=args.cores)
        result = analysis.analyse(chip.board, scan_height=args.scan_height, step=args.step)
    finally:
        # The solve already saved the project; nothing else is saved.
        s.release()

    print(f"\n=== Bz analysis {'=' * 59}")
    print_info(result)
    return result


if __name__ == "__main__":
    main()
