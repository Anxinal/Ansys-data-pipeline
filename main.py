"""Open an AEDT chip project, solve it in the open session and export its Bz image.

Usage:
    .venv/bin/python main.py

There are no command-line options: every setting comes from configs.py, see
its "Run" section (RUN_MODE picks analyse, extract, copy or sections).
"""

from pathlib import Path

import configs
from Chips import Chip, ChipSection, PositionSampler
from Chips.Generators import FileSectionGenerator
from Chips.Components.utils import print_info

RUN_MODES = ("analyse", "extract", "copy", "sections")


def check_settings(settings=configs):
    """Raise ValueError for settings that can't work, before AEDT is started."""
    mode = settings.RUN_MODE
    if mode not in RUN_MODES:
        raise ValueError(f"configs.RUN_MODE must be one of {RUN_MODES}, not {mode!r}")
    if not settings.DEFAULT_INPUT_PATH:
        raise ValueError("no project file: set configs.DEFAULT_INPUT_PATH")
    if not Path(settings.DEFAULT_INPUT_PATH).is_file():
        raise ValueError(f"project file does not exist: {settings.DEFAULT_INPUT_PATH}")
    if mode == "copy" and not settings.COPY_GROUP:
        raise ValueError('RUN_MODE "copy" needs configs.COPY_GROUP, e.g. "BOARD_1"')
    if mode == "sections" and not Path(settings.SECTIONS_FILE or "").is_file():
        raise ValueError(f"section file does not exist: {settings.SECTIONS_FILE!r} (configs.SECTIONS_FILE)")
    for name in ("EXTRACT_ONLY", "PURGE_HISTORY"):
        if getattr(settings, name) and mode not in ("extract", "sections"):
            raise ValueError(f'configs.{name} needs RUN_MODE "extract" or "sections", not "{mode}"')


def bz_options(settings=configs):
    """The Bz analysis settings, as the keyword arguments of run_bz_procedure, analyse_copy and CopyandGenerate."""
    return dict(setup=settings.DEFAULT_SETUP, output_dir=settings.DEFAULT_OUTPUT_DIR,
                scan_height=settings.DEFAULT_SCAN_HEIGHT, step=settings.DEFAULT_GRID_STEP,
                cores=settings.CORES, solve=settings.SOLVE)


def run_sections(session, settings=configs):
    """Validate every file row before the first copy; isolate each pin pair in its own design."""
    from AnsysSession.Action.CopyandGenerate import CopyandGenerate
    from AnsysSession.Action.ExtractCopy import original_components

    snapshot = session.snapshot
    rows = FileSectionGenerator.read_rows(settings.SECTIONS_FILE)
    boards = list(dict.fromkeys((row.get("board") or "").strip() for _, row in rows))
    if not all(boards):
        raise ValueError(f"{settings.SECTIONS_FILE}: every section needs a board name")
    chip = Chip(original_components(snapshot), gnd=settings.DEFAULT_GND, vcc=settings.DEFAULT_VCC,
                spheres=settings.DEFAULT_SPEHRE, boards=boards, units=snapshot.units)
    candidates = list(FileSectionGenerator(chip, settings.SECTIONS_FILE))
    source_design = session.design
    results = []
    for candidate in candidates:
        session.switch_design(source_design)
        job = CopyandGenerate(session, candidate, **bz_options(settings), extract_only=settings.EXTRACT_ONLY,
                              purge_history=settings.PURGE_HISTORY)
        results.append(job.run())
    return results


def main(settings=configs):
    check_settings(settings)
    # Keep the settings check available without the optional AEDT dependency.
    from AnsysSession.Action.ExtractCopy import ExtractCopy, original_components
    from AnsysSession.Session import Session
    from AnsysSession.SwitchDesign import analyse_copy, run_bz_procedure

    mode = settings.RUN_MODE
    s = Session(settings.DEFAULT_INPUT_PATH, design=settings.DESIGN, non_graphical=not settings.SHOW_DESKTOP)
    try:
        if settings.SHOW_INFO:
            s.get_session_info()
        if mode == "sections":
            results = run_sections(s, settings)
            for result in results:
                print_info(result)
            return results
        source_design = s.design
        group = settings.COPY_GROUP if mode == "copy" else None
        if not group:
            # Find the chip first, so a naming problem shows up before a long solve.
            # Earlier copies are left out, so their spheres don't count as the chip's.
            snapshot = s.snapshot
            chip = ChipSection(original_components(snapshot), gnd=settings.DEFAULT_GND, vcc=settings.DEFAULT_VCC,
                               spheres=settings.DEFAULT_SPEHRE, board=settings.BOARD, units=snapshot.units)
            chip.print()
        if mode == "extract":
            positions = chip.extraction_positions(step=settings.DEFAULT_GRID_STEP, sampler=PositionSampler())
            record = ExtractCopy(s.app, snapshot, chip, positions).run()
            s.refresh()
            group = record.group
            print(f"\nExtracted {group}: {list(record.copies.values())}")
            if settings.PURGE_HISTORY:
                from AnsysSession.Action.PurgeHistory import PurgeHistory
                PurgeHistory(s.app, list(record.copies.values())).run()
                s.refresh()
            if settings.EXTRACT_ONLY:
                s.save()
                result = {"design": s.design, "group": group, "copies": record.copies,
                          "history purged": settings.PURGE_HISTORY}
                print_info(result)
                return result

        if group:
            result = analyse_copy(s, group, **bz_options(settings), gnd=settings.DEFAULT_GND,
                                  vcc=settings.DEFAULT_VCC, source_design=source_design, rebuild=settings.REBUILD)
        else:
            result = run_bz_procedure(s, chip.board, **bz_options(settings))
    finally:
        # Successful extraction-only runs also save before release.
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
