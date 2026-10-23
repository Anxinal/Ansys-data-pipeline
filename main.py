"""Open an AEDT chip project, solve it in the open session and export its Bz image.

Usage:
    .venv/bin/python main.py path/to/project.aedt [options]
    .venv/bin/python main.py path/to/project.aedt --extract     # new copy, then analyse it
    .venv/bin/python main.py path/to/project.aedt --copy BOARD_1 # analyse an existing copy

Run with --help for the options. The Bz image goes to configs.DEFAULT_OUTPUT_DIR
unless --output is given.
"""

import argparse
from pathlib import Path

import configs
from AnsysSession.Action.ExtractCopy import ExtractCopy, original_components
from AnsysSession.Session import Session
from AnsysSession.SwitchDesign import analyse_copy, run_bz_procedure
from Chips import ChipSection, PositionSampler
from Chips.Components.utils import print_info


def parse_args():
    parser = argparse.ArgumentParser(description="Solve an AEDT chip project and export the Bz field image above its board.")
    parser.add_argument("path", help=".aedt project file")
    parser.add_argument("--design", help="design to open (default: the project's active design)")
    parser.add_argument("--info", action="store_true", help="also print everything the project can tell about itself")

    analysis = parser.add_argument_group("analysis")
    analysis.add_argument("--setup", default=configs.DEFAULT_SETUP, help="setup to solve (default: %(default)s)")
    analysis.add_argument("--cores", type=int, help="number of cores for the solve")
    analysis.add_argument("--no-solve", action="store_true", help="use the setup's existing solution instead of solving")
    analysis.add_argument("--output", type=Path, default=configs.DEFAULT_OUTPUT_DIR, help="export folder (default: %(default)s)")
    analysis.add_argument("--scan-height", type=float, default=configs.DEFAULT_SCAN_HEIGHT,
                          help="image plane height above the board top, in model units (default: %(default)s)")
    analysis.add_argument("--step", type=float, default=configs.DEFAULT_GRID_STEP,
                          help="image pixel size, in model units (default: %(default)s)")

    copies = parser.add_argument_group("copies", "analyse an extracted copy in its own analysis design")
    which = copies.add_mutually_exclusive_group()
    which.add_argument("--extract", action="store_true",
                       help="copy the board, spheres and GND/VCC into a new group (BOARD_<n>) and analyse that copy")
    which.add_argument("--copy", metavar="GROUP", help="analyse an existing copy, e.g. BOARD_1")
    copies.add_argument("--rebuild", action="store_true", help="recreate the copy's analysis design if it exists")

    chip = parser.add_argument_group("chip parts", "names to use when the automatic choices don't match the model")
    chip.add_argument("--gnd", default=configs.DEFAULT_GND, help="GND component or excitation (default: %(default)s)")
    chip.add_argument("--vcc", default=configs.DEFAULT_VCC, help="VCC component or excitation (default: %(default)s)")
    chip.add_argument("--spheres", nargs=2, metavar="NAME", help="the two connection spheres")
    chip.add_argument("--board", help="the board to analyse; needed when the design has several")
    return parser.parse_args()


def main():
    args = parse_args()
    s = Session(args.path, design=args.design)
    try:
        if args.info:
            s.get_session_info()
        source_design = s.design
        group = args.copy
        if not group:
            # Find the chip first, so a naming problem shows up before a long solve.
            # Earlier copies are left out, so their spheres don't count as the chip's.
            snapshot = s.snapshot
            chip = ChipSection(original_components(snapshot), gnd=args.gnd, vcc=args.vcc, spheres=args.spheres,
                        board=args.board, units=snapshot.units)
            chip.print()
        if args.extract:
            positions = chip.extraction_positions(step=args.step, sampler=PositionSampler())
            extraction = ExtractCopy(s.app, snapshot, chip, positions)
            if extraction.act() != extraction.SUCCESS:
                raise RuntimeError(f"extract failed: {extraction.error}")
            s.refresh()
            group = extraction.result.group
            print(f"\nExtracted {group}: {list(extraction.result.copies.values())}")

        if group:
            result = analyse_copy(
                s, group, setup=args.setup, output_dir=args.output, scan_height=args.scan_height,
                step=args.step, cores=args.cores, solve=not args.no_solve, gnd=args.gnd, vcc=args.vcc,
                source_design=source_design, rebuild=args.rebuild,
            )
        else:
            result = run_bz_procedure(s, chip.board, setup=args.setup, output_dir=args.output,
                                      scan_height=args.scan_height, step=args.step, cores=args.cores,
                                      solve=not args.no_solve)
    finally:
        # run_bz_procedure saved the project at the end; nothing else is saved.
        s.release()

    print(f"\n=== Bz analysis {'=' * 59}")
    print_info(result)
    return result


if __name__ == "__main__":
    main()
