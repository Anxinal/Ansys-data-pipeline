"""Open an AEDT chip project, solve it in the open session and export its Bz image.

Usage:
    .venv/bin/python main.py

There are no command-line options: every setting comes from configs.py, see
its "Run" section (RUN_MODE picks analyse or sections).
"""

from pathlib import Path

import configs
from Chips import ChipSection
from Chips.Components.utils import print_info

RUN_MODES = ("analyse", "sections")


def check_settings(settings=configs):
    """Raise ValueError for settings that can't work, before AEDT is started."""
    mode = settings.RUN_MODE
    if mode not in RUN_MODES:
        raise ValueError(f"configs.RUN_MODE must be one of {RUN_MODES}, not {mode!r}")
    if not settings.DEFAULT_INPUT_PATH:
        raise ValueError("no project file: set configs.DEFAULT_INPUT_PATH")
    if not Path(settings.DEFAULT_INPUT_PATH).is_file():
        raise ValueError(f"project file does not exist: {settings.DEFAULT_INPUT_PATH}")
    if mode == "sections" and not Path(settings.SECTIONS_FILE or "").is_file():
        raise ValueError(f"section file does not exist: {settings.SECTIONS_FILE!r} (configs.SECTIONS_FILE)")


def bz_options(settings=configs):
    """The Bz analysis settings, as the keyword arguments of BzProcedure."""
    return dict(setup=settings.DEFAULT_SETUP, output_dir=settings.DEFAULT_OUTPUT_DIR,
                scan_height=settings.DEFAULT_SCAN_HEIGHT, step=settings.DEFAULT_GRID_STEP,
                cores=settings.CORES, solve=settings.SOLVE)


def run_sections(session, settings=configs):
    """Solve every section of settings.SECTIONS_FILE in place in the source design."""
    from AnsysSession.Action.SelectAndAnalyseWorkflow.RootAnalysis import RootAnalysis

    run_dir = Path(settings.DEFAULT_OUTPUT_DIR) / "RootSections"
    return RootAnalysis(session, settings, bz_options(settings), run_dir).run()


def main(settings=configs):
    check_settings(settings)
    # Keep the settings check available without the optional AEDT dependency.
    from AnsysSession.Action.AnalysisActions.BzProcedure import BzProcedure
    from AnsysSession.Session import Session

    s = Session(settings.DEFAULT_INPUT_PATH, design=settings.DESIGN, non_graphical=not settings.SHOW_DESKTOP)
    try:
        if settings.SHOW_INFO:
            s.get_session_info()
        if settings.RUN_MODE == "sections":
            results = run_sections(s, settings)
            for result in results:
                print_info(result)
            return results
        # Find the chip first, so a naming problem shows up before a long solve.
        snapshot = s.snapshot
        chip = ChipSection(snapshot.components, gnd=settings.DEFAULT_GND, vcc=settings.DEFAULT_VCC,
                           spheres=settings.DEFAULT_SPEHRE, board=settings.BOARD, units=snapshot.units)
        chip.print()
        result = BzProcedure(s, chip.board, **bz_options(settings)).run()
        s.save()
    finally:
        s.release(close_desktop=not settings.SHOW_DESKTOP)

    print(f"\n=== Bz analysis {'=' * 59}")
    print_info(result)
    return result


if __name__ == "__main__":
    try:
        check_settings()
    except ValueError as e:
        raise SystemExit(f"main.py: {e}")
    main()
