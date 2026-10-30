"""Switch the session to the analysis design of one extracted copy, then analyse it.

A copy (a group made by ExtractCopy, e.g. BOARD_1) lives in the main design next
to the originals. Its analysis design "<design>_<group>" is a duplicate of the
main design (same setups, excitations and mesh settings) with everything deleted
except that copy and the background region, so the solve only sees that copy's
board, spheres and GND/VCC. The main design is not changed.
"""

from Chips import ChipSection
from configs import (BACKGROUND_MATERIALS, BOARD_KEYWORDS, DEFAULT_GND, DEFAULT_GRID_STEP, DEFAULT_OUTPUT_DIR,
                     DEFAULT_SCAN_HEIGHT, DEFAULT_SETUP, DEFAULT_VCC)

from .Action.BzProcedure import BzProcedure
from .CopyStore import CopyStore


def analysis_design_name(source_design, group):
    return f"{source_design}_{group}"


def switch_to_copy(session, group, source_design=None, rebuild=False):
    """Make the copy's analysis design active, creating it if needed.

    Returns (design name, group name as spelled in AEDT).

    source_design   design holding the copy (default: the active design)
    rebuild         delete and recreate the analysis design if it already exists
    """
    source_design = source_design or session.design
    if session.design != source_design:
        session.switch_design(source_design)
    snapshot = session.snapshot

    # Use the group's own spelling, so "board_1" and "BOARD_1" mean the same design.
    match = snapshot.group(group)
    if match is None:
        raise LookupError(f'No group "{group}" in design "{source_design}". Groups: {list(snapshot.groups)}')
    name = analysis_design_name(source_design, match)
    editor = session.editor

    if name in session.app.design_list:
        if not rebuild:
            session.switch_design(name)
            return name, match
        editor.delete_design(name, fallback_design=source_design)

    members = {member.lower() for member in snapshot.members(match)}
    if not members:
        raise LookupError(f'Group "{match}" in design "{source_design}" is empty')

    name = editor.duplicate_design(name)  # the duplicate becomes the active design
    session.refresh()
    editor.delete([
        c.name
        for c in session.components
        if c.name.lower() not in members and c.material_name.lower() not in BACKGROUND_MATERIALS
    ])
    session.refresh()
    return name, match


def copy_chip(session, group, source_design, gnd=DEFAULT_GND, vcc=DEFAULT_VCC):
    """The ChipSection of a copy, in its analysis design.

    Uses the copy's CopyRecord. Copies made before records existed are found by
    their "<group>_<original>" names instead: the board is the copy whose
    original name contains one of BOARD_KEYWORDS, the spheres are found by
    geometry (only the copy's two remain in its analysis design).
    """
    snapshot = session.snapshot
    components = snapshot.components
    record = CopyStore(session.app).load(source_design, group)
    if record is not None:
        roles = record.roles
        return ChipSection(components, gnd=roles["gnd"], vcc=roles["vcc"], spheres=record.spheres, board=roles["board"],
                    units=snapshot.units)

    prefix = f"{group}_".lower()
    copies = [c for c in components if c.name.lower().startswith(prefix)]
    boards = [c for c in copies if any(k in c.name[len(prefix):].lower() for k in BOARD_KEYWORDS)]
    if len(boards) != 1:
        raise LookupError(f'Expected one board copy in group "{group}", found {[c.name for c in boards]}')
    names = {c.name.lower() for c in components} | {b.name.lower() for c in components for b in c.boundaries}

    def terminal_name(name):
        copied = f"{group}_{name}"
        return copied if copied.lower() in names else name

    return ChipSection(components, gnd=terminal_name(gnd), vcc=terminal_name(vcc), board=boards[0].name,
                units=snapshot.units)


def analyse_copy(session, group, setup=DEFAULT_SETUP, output_dir=DEFAULT_OUTPUT_DIR,
                 scan_height=DEFAULT_SCAN_HEIGHT, step=DEFAULT_GRID_STEP, cores=None, solve=True,
                 gnd=DEFAULT_GND, vcc=DEFAULT_VCC, source_design=None, rebuild=False):
    """Switch to the copy's analysis design, solve it and export its Bz image."""
    source_design = source_design or session.design
    design, group = switch_to_copy(session, group, source_design, rebuild)
    chip = copy_chip(session, group, source_design, gnd, vcc)
    chip.print()
    return {"design": design, **run_bz_procedure(session, chip.board, setup, output_dir, scan_height, step, cores, solve)}


def run_bz_procedure(session, board, setup=DEFAULT_SETUP, output_dir=DEFAULT_OUTPUT_DIR,
                     scan_height=DEFAULT_SCAN_HEIGHT, step=DEFAULT_GRID_STEP, cores=None, solve=True):
    """Run the Bz procedure (analyse, then export) in the active design, then save the project once.

    Returns the export summary.
    """
    result = BzProcedure(session.app, board, setup, output_dir, scan_height, step, cores, solve).run()
    session.save()
    return result
