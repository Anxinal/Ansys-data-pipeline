"""Open an AEDT chip project, solve it in the open session and export its Bz image.

Usage:
    .venv/bin/python main.py path/to/project.aedt [options]
    .venv/bin/python main.py path/to/project.aedt --extract     # new copy, then analyse it
    .venv/bin/python main.py path/to/project.aedt --copy BOARD_1 # analyse an existing copy

Run with --help for the options. Options with a setting in configs.py default to it,
and the project path defaults to configs.DEFAULT_INPUT_PATH.
"""

import argparse
from pathlib import Path

import configs
from Chips import Chip, ChipSection, PositionSampler
from Chips.Generators import FileSectionGenerator
from Chips.Components.utils import print_info


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Solve an AEDT chip project and export the Bz field image above its board.")
    parser.add_argument("path", nargs="?", default=configs.DEFAULT_INPUT_PATH,
                        help=".aedt project file (default: %(default)s)")
    parser.add_argument("--design", help="design to open (default: the project's active design)")
    parser.add_argument("--info", action="store_true", help="also print everything the project can tell about itself")
    parser.add_argument("--desktop", action="store_true", help="show the AEDT desktop")

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
                       help=f"copy the board, spheres and GND/VCC into a new group ({configs.DEFAULT_PREFIX}<n>) "
                            "and analyse that copy")
    which.add_argument("--copy", metavar="GROUP", help=f"analyse an existing copy, e.g. {configs.DEFAULT_PREFIX}1")
    which.add_argument("--sections", type=Path, help="extract sections from CSV or board/Sphere_positions instructions")
    copies.add_argument("--extract-only", action="store_true", help="save extracted sections without validation, solving or field export")
    copies.add_argument("--purge-history", action="store_true",
                        help="purge modeling history of new copies only, after placement; freezes their geometry")
    copies.add_argument("--rebuild", action="store_true", help="recreate the copy's analysis design if it exists")

    chip = parser.add_argument_group("chip parts", "names to use when the automatic choices don't match the model")
    chip.add_argument("--gnd", default=configs.DEFAULT_GND, help="GND component or excitation (default: %(default)s)")
    chip.add_argument("--vcc", default=configs.DEFAULT_VCC, help="VCC component or excitation (default: %(default)s)")
    chip.add_argument("--spheres", nargs=2, metavar="NAME", default=configs.DEFAULT_SPEHRE,
                      help="the two connection spheres (default: %(default)s)")
    chip.add_argument("--board", help="the board to analyse; needed when the design has several")
    args = parser.parse_args(argv)
    if not args.path:
        parser.error("no project file: pass one or set configs.DEFAULT_INPUT_PATH")
    if not Path(args.path).is_file():
        parser.error(f"project file does not exist: {args.path}")
    if args.sections and not args.sections.is_file():
        parser.error(f"section file does not exist: {args.sections}")
    if args.extract_only and not (args.extract or args.sections):
        parser.error("--extract-only requires --extract or --sections")
    if args.purge_history and not (args.extract or args.sections):
        parser.error("--purge-history requires --extract or --sections")
    return args


def run_sections(session, args):
    """Validate every file row before the first copy; isolate each pin pair in its own design."""
    from AnsysSession.Action.CopyandGenerate import CopyandGenerate
    from AnsysSession.Action.ExtractCopy import original_components

    snapshot = session.snapshot
    rows = FileSectionGenerator.read_rows(args.sections)
    boards = list(dict.fromkeys((row.get("board") or "").strip() for _, row in rows))
    if not all(boards):
        raise ValueError(f"{args.sections}: every section needs a board name")
    chip = Chip(original_components(snapshot), gnd=args.gnd, vcc=args.vcc, spheres=args.spheres,
                boards=boards, units=snapshot.units)
    candidates = list(FileSectionGenerator(chip, args.sections))
    source_design = session.design
    results = []
    for candidate in candidates:
        session.switch_design(source_design)
        job = CopyandGenerate(session, candidate, setup=args.setup, output_dir=args.output,
                              scan_height=args.scan_height, step=args.step, cores=args.cores,
                              solve=not args.no_solve, extract_only=args.extract_only,
                              purge_history=args.purge_history)
        results.append(job.run())
    return results


def main(argv=None):
    args = parse_args(argv)
    # Keep --help and input checks available without the optional AEDT dependency.
    from AnsysSession.Action.ExtractCopy import ExtractCopy, original_components
    from AnsysSession.Session import Session
    from AnsysSession.SwitchDesign import analyse_copy, run_bz_procedure

    s = Session(args.path, design=args.design, non_graphical=not args.desktop)
    try:
        if args.info:
            s.get_session_info()
        if args.sections:
            results = run_sections(s, args)
            for result in results:
                print_info(result)
            return results
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
            record = ExtractCopy(s.app, snapshot, chip, positions).run()
            s.refresh()
            group = record.group
            print(f"\nExtracted {group}: {list(record.copies.values())}")
            if args.purge_history:
                from AnsysSession.Action.PurgeHistory import PurgeHistory
                PurgeHistory(s.app, list(record.copies.values())).run()
                s.refresh()
            if args.extract_only:
                s.save()
                result = {"design": s.design, "group": group, "copies": record.copies,
                          "history purged": args.purge_history}
                print_info(result)
                return result

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
        # Successful extraction-only runs also save before release.
        s.release(close_desktop=not args.desktop)

    print(f"\n=== Bz analysis {'=' * 59}")
    print_info(result)
    return result


if __name__ == "__main__":
    main()
