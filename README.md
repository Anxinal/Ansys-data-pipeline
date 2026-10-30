# Ansys-data-pipeline

Automates Bz (z-component of the magnetic flux density) data generation for a chip model in
Ansys Electronics Desktop (Maxwell 3D) through PyAEDT: open a project, find the chip's parts,
optionally make repositioned copies, solve, and export the Bz image above the board.

Requires a local AEDT install (2025.1) on Windows or Linux. Install the Python side with
`pip install -r requirements.txt`.

## Architecture

Two layers with a one-way dependency: the AEDT layer reads and writes the design; the chip
layer is plain data and logic and never talks to AEDT.

```
main.py                    runs what configs.py's "Run" section says; wires everything together
AnsysSession/              AEDT layer (the only code that imports PyAEDT)
  Session.py               open/close AEDT, active design, snapshot, save
  DesignReader.py          reads the design in bulk into a DesignSnapshot
  ModelEditor.py           every change to AEDT (move, copy, delete, properties, save, ...)
  CopyStore.py             records of extracted copies (<project>.pyaedt/copies.json)
  Report.py                full project report (Session.get_session_info())
  SwitchDesign.py          per-copy analysis designs; run_bz_procedure()
  Action/                  steps run in a design (AnsysAction / AnsysProcedure)
    Analysis.py            BzAnalysis: solve a setup
    Export.py              BzExport: export the Bz image (.fld + .npz)
    BzProcedure.py         BzAnalysis then BzExport
    ExtractCopy.py         copy board, spheres, GND/VCC into a new group
    PurgeHistory.py        optionally flatten modeling history of explicitly selected copies
    CopyandGenerate.py     copy one SectionCandidate, set its terminals, validate, solve, export
    SwitchBackToMain.py    return to the main design before the next copy
    SetTerminalPositions.py  place VCC/GND by their pin-count variables (PinCount, PinCountGND)
    MoveComponent.py, MoveCurrentConnectors.py, CheckValidity.py
Chips/                     chip layer (pure Python, no AEDT)
  DesignSnapshot.py        one design, read at one moment
  Components/              Component (+ Solid/Sheet/Line), Material, Boundary
  Chip.py, Terminal.py     finds GND/VCC, the two spheres and the boards
  ChipSection.py           a chip with one board: the section copied and analysed
  Generators/              FeasibleChipSectionGenerator (base), FileSectionGenerator (CSV),
                           SectionCandidate (a ChipSection + its VCC/GND positions)
  Positions/               Position (grid cell), position pairs, PositionSampler
configs.py                 all defaults (setup, grid step, scan height, names, ...)
tests/                     chip-layer tests on plain data
```

Rules of thumb:
- **Read** through `session.snapshot` (read once, kept until `session.refresh()`).
- **Change** the design only through `session.editor` or an action (actions use `self.editor`),
  then call `session.refresh()` before reading again.
- **Actions** return `SUCCESS` (0) or `FAILURE` (1) with `action.error`; an `AnsysProcedure`
  runs its actions in order and stops at the first failure (`procedure.failed`).

Run the tests (no AEDT needed): `python -m unittest discover tests`

## Tutorial: automatic Bz analysis

### From main.py

`python main.py` takes no options: set everything in the "Run" section of `configs.py`, then run it.

```python
DEFAULT_INPUT_PATH = "path/to/chip.aedt"
RUN_MODE = "analyse"    # solve and export Bz above the board (CORES = 8, SOLVE = False to reuse the solution)
RUN_MODE = "extract"    # new copy BOARD_<n>, then analyse it
RUN_MODE = "copy"       # analyse an existing copy: COPY_GROUP = "BOARD_1"
RUN_MODE = "sections"   # SECTIONS_FILE = "to_test.txt", EXTRACT_ONLY = True, SHOW_DESKTOP = True, DESIGN = "Maxwell3DDesign3"
```

The settings are checked before AEDT starts. `SHOW_DESKTOP` opens the AEDT GUI. `SECTIONS_FILE` accepts the CSV format below or one instruction per line:

```text
board = L4L3_Separate87 Sphere_positions = 399 258
```

The first pin is VCC, the second GND. Board names must match the project exactly.
All instructions are checked before copying. `EXTRACT_ONLY` copies just the selected sheet,
two spheres and two terminals into a group in the existing design, then saves the project and
`copies.json` (including the requested pins as metadata). It does not create another design or
change the source design's global pin variables. Geometry is copied in place; this mode does
not implement sphere or terminal repositioning. It skips validation, solving, and field export.
With `SHOW_DESKTOP`, the desktop and project remain open for inspection after Python releases its session.

For slow runs, set `PURGE_HISTORY = True` with RUN_MODE "sections" or "extract". This runs the
`PurgeHistory` action only on the new copies, before saving (and after terminal placement
when generating Bz). Purging freezes their current geometry and removes editable history,
including expression-driven placement, so it is disabled by default. The source objects'
history is preserved. This can reduce later history regeneration; it does not accelerate the
initial copy operation, and a runtime improvement has not been benchmarked.

The action can also be used explicitly: `PurgeHistory(session.app, copied_names).act()`
(import from `AnsysSession.Action.PurgeHistory`), followed by `session.refresh()`.

Design switching/duplication includes a scoped compatibility guard for PyAEDT 1.0.1:
its internal `AedtAPI` connection metadata is stored locally so activation of a newly
pasted design does not trigger a remote `GetPropNames` lookup. Actual AEDT property
writes retain their normal behavior, and the guard is removed after each operation.

Set `DEFAULT_GND`, `DEFAULT_VCC`, `DEFAULT_SPEHRE` and `BOARD` in `configs.py` when the automatic part detection
doesn't match your model. Results go to `data_export_default/` (`configs.DEFAULT_OUTPUT_DIR`):
`<project>_<design>_<setup>_Bz.fld` (raw AEDT export) and `.npz` (`x`, `y`, `bz[ny, nx]` in tesla).

### From Python, in an opened session

```python
from AnsysSession.Action.ExtractCopy import original_components
from AnsysSession.Session import Session
from AnsysSession.SwitchDesign import run_bz_procedure
from Chips import ChipSection

session = Session("path/to/chip.aedt")              # opens AEDT without the GUI
try:
    snapshot = session.snapshot                      # the design as plain data
    chip = ChipSection(original_components(snapshot), board="ChipBoard", units=snapshot.units)  # one board
    chip.print()

    # Solve Setup1, export Bz 0.06 above the board on a 0.03 grid, then save once.
    result = run_bz_procedure(session, chip.board, setup="Setup1", cores=8)
    print(result["npz file"], result["peak |Bz| (T)"])
finally:
    session.release()                                # closes AEDT
```

To analyse a copy instead (each copy is solved in its own `<design>_<group>` design):

```python
from AnsysSession.SwitchDesign import analyse_copy
result = analyse_copy(session, "BOARD_1", cores=8)
```

To generate data for several chip sections, one copy at a time, list them in a CSV file
(one row per section; `vcc_pin`/`gnd_pin` are pin counts such as `126` or cell labels such as `G7`,
and the optional `vcc`, `gnd`, `sphere_vcc`, `sphere_gnd` columns name other parts):

```
board,vcc_pin,gnd_pin
Board1,126,166
Board2,G7,I9
```

```python
from AnsysSession.Action.CopyandGenerate import CopyandGenerate
from AnsysSession.Action.SwitchBackToMain import SwitchBackToMain
from Chips import Chip
from Chips.Generators import FileSectionGenerator

chip = Chip(original_components(session.snapshot), units=session.snapshot.units)   # all boards
for candidate in FileSectionGenerator(chip, "sections.csv"):
    job = CopyandGenerate(session, candidate, cores=8)
    if job.act() != job.SUCCESS:
        print(f"{job.failed.label} failed: {job.error}")
    SwitchBackToMain(session, job.main_design).act()
```

Load an exported image with `numpy.load(result["npz file"])`.

## Pakcages
The **ansysSession** package deals with abstracted interaction directly with the ansys aedt session

The **chips** package deals with the inner data processing of chips, including position selection and candidate generationt that does not require aedt to intervene

The **MField** Data deals with data augmentation after the data is already generated
