"""Open an AEDT chip project, solve it and export the selected field image.

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
    if getattr(settings, 'FIELD_QUANTITY', 'Bz') not in ('Bz', 'J'):
        raise ValueError('configs.FIELD_QUANTITY must be Bz or J')
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
    return dict(setup=settings.DEFAULT_SETUP,
                scan_height=settings.DEFAULT_SCAN_HEIGHT, step=settings.DEFAULT_GRID_STEP,
                cores=settings.CORES, solve=settings.SOLVE)


def run_sections(session, settings=configs):
    """Solve every section of settings.SECTIONS_FILE in place in the source design."""
    if getattr(settings, 'FIELD_QUANTITY', 'Bz') == 'J':
        return run_j_sections(session, settings)
    from AnsysSession.Action.SelectAndAnalyseWorkflow.RootAnalysis import RootAnalysis

    run_dir = Path(settings.DEFAULT_OUTPUT_DIR) / "RootSections"
    return RootAnalysis(session, settings, bz_options(settings), run_dir).run()


def j_options(settings=configs):
    """Current-density options, using the default conductor-interior plane."""
    return dict(setup=settings.DEFAULT_SETUP, step=settings.DEFAULT_GRID_STEP,
                plane_fraction=settings.J_PLANE_FRACTION, cores=settings.CORES, solve=settings.SOLVE)


def run_j_sections(session, settings=configs):
    """Solve section combinations in the root design and export |J| inside each board."""
    from AnsysSession.Action.SelectAndAnalyseWorkflow.RootAnalysis import RootAnalysis
    from AnsysSession.Action.AnalysisActions.JProcedure import JProcedure
    run_dir = Path(settings.DEFAULT_OUTPUT_DIR)/'J'/'RootSections'
    return RootAnalysis(session, settings, j_options(settings), run_dir, procedure=JProcedure).run()


def main(settings=configs):
    check_settings(settings)
    # Keep the settings check available without the optional AEDT dependency.
    from AnsysSession.Action.AnalysisActions.BzProcedure import BzProcedure
    from AnsysSession.Session import Session
    procedure, options = BzProcedure, bz_options(settings)
    if getattr(settings, 'FIELD_QUANTITY', 'Bz') == 'J':
        from AnsysSession.Action.AnalysisActions.JProcedure import JProcedure
        procedure, options = JProcedure, j_options(settings)

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
        result = procedure(s, chip.board, **options).run()
        s.save()
    finally:
        s.release(close_desktop=not settings.SHOW_DESKTOP)

    print(f"\n=== {getattr(settings, 'FIELD_QUANTITY', 'Bz')} analysis {'=' * 59}")
    print_info(result)
    return result


if __name__ == "__main__":
    try:
        check_settings()
    except ValueError as e:
        raise SystemExit(f"main.py: {e}")
    main()
