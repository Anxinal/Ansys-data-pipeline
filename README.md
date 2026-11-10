# Ansys-data-pipeline

Automates Bz (z-component of the magnetic flux density) data generation for a chip model in
Ansys Electronics Desktop (Maxwell 3D) through PyAEDT: open a project, find the chip's parts,
solve one design or a list of board sections in place, and export the Bz image above the board.

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
  Report.py                full project report (Session.get_session_info())
  Action/                  steps run in a design (AnsysAction / AnsysProcedure)
    AnalysisActions/
      Analysis.py          BzAnalysis: solve a setup
      Export.py            BzExport: export the Bz image (.fld + .npz)
      BzProcedure.py       BzAnalysis then BzExport
      CheckValidity.py     AEDT's Validation Check
    PurgeHistory.py        flatten modeling history of explicitly named objects
    SetTerminalPositions.py  place VCC/GND by their pin-count variables (PinCount, PinCountGND)
    MoveComponent.py, MoveCurrentConnectors.py
    SelectAndAnalyseWorkflow/  RootAnalysis: solve listed sections in place, one active board at a time
Chips/                     chip layer (pure Python, no AEDT)
  DesignSnapshot.py        one design, read at one moment
  Components/              Component (+ Solid/Sheet/Line), Material, Boundary
  Chip.py, Terminal.py     finds GND/VCC, the two spheres and the boards
  ChipSection.py           a chip with one board: the section analysed
  Generators/              FeasibleChipSectionGenerator (base), FileSectionGenerator (CSV),
                           SectionCandidate (a ChipSection + its VCC/GND positions)
  Positions/               Position (grid cell), position pairs, PositionSampler
configs.py                 all defaults (setup, grid step, scan height, names, ...)
tests/                     chip-layer tests on plain data
```

Rules of thumb:
- **Read** through `session.snapshot` (read once, kept until `session.refresh()`).
- **Change** the design only through `session`'s methods or an action (actions take the `session`),
  then call `session.refresh()` before reading again.
- **Actions** return `SUCCESS` (0) or `FAILURE` (1) with `action.error`; an `AnsysProcedure`
  runs its actions in order and stops at the first failure (`procedure.failed`).

Run the tests (no AEDT needed): `python -m unittest discover tests`

## Snapshot cells and connector movement

`scripts/sync_sphere_moves.py --port <existing AEDT port>` reads only the configured project's
configured design (`DESIGN = None` uses its active design). `--apply` adds a fixed base correction
and copies each terminal's pin-driven Move to its matching sphere, verifies the geometry, and saves
that project. Histories and results are recorded under `Result/Movement/`.

`python scripts/export_snapshot_grid.py` exports the measured `L4L3_Separate87` bottom snapshot
using that recorded movement mapping. `SNAPSHOT_GRID_STEP` is the physical cell size; connector
centers use the actual design pitches. The existing design has 0.798 mm X pitch, 0.800 mm Y pitch,
and an existing GND base offset of one X column relative to VCC. The requested 0.798 mm square
cells therefore leave 0.002 mm between rows. `DEFAULT_GRID_STEP` remains the Bz sampling step.

The grid stays fixed in model coordinates when the snapshot is cropped. Background, board and
final crop offsets are retained; pixel boundaries are projected and rounded in the original image
before translating them into a crop. The exporter does not resize the source or cells. Native cells
may differ by a pixel because of raster rounding; uniform cells use white padding only.
The ZIP in `Result/Grid/L4L3_Separate87_pin_aligned_0p798mm.zip` includes a native-scale overview,
both forms of the cells, and CSV/JSON records of physical centers, crop offsets and pin mappings.
Cells extending beyond the 20-by-20 pin array are flagged rather than assigned an invalid pin count.

## Tutorial: automatic Bz analysis

### From main.py

`python main.py` takes no options: set everything in the "Run" section of `configs.py`, then run it.

```python
DEFAULT_INPUT_PATH = "path/to/chip.aedt"
RUN_MODE = "analyse"    # solve and export Bz above the board (CORES = 8, SOLVE = False to reuse the solution)
RUN_MODE = "sections"   # solve each section in place: SECTIONS_FILE = "to_test.txt", DESIGN = "Maxwell3DDesign3"
```

The settings are checked before AEDT starts. `SHOW_DESKTOP` opens the AEDT GUI. `SECTIONS_FILE` accepts the CSV format below or one instruction per line:

```text
board = L4L3_Separate87 Sphere_positions = 399 258
```

The first pin is VCC, the second GND. Board names must match the project exactly.
All instructions are checked before anything changes. Every object is then taken out of the model
except the background, GND, VCC and the spheres, each case swaps in its board and sets the pin
variables, and the original model flags and pin values come back at the end, also after a failure.
The project is saved once, after that restore. Each case's exports and `result.json` go to
`RootSections/case_<n>_VCC<pin>_GND<pin>/` under `configs.DEFAULT_OUTPUT_DIR`.
With `SHOW_DESKTOP`, the desktop and project remain open for inspection after Python releases its session.

`PurgeHistory(session, names).act()` (from `AnsysSession.Action.PurgeHistory`), followed by
`session.refresh()`, freezes the named objects' current geometry and removes their editable
history, including expression-driven placement.

Design switching/duplication includes a scoped compatibility guard for PyAEDT 1.0.1:
its internal `AedtAPI` connection metadata is stored locally so activation of a newly
pasted design does not trigger a remote `GetPropNames` lookup. Actual AEDT property
writes retain their normal behavior, and the guard is removed after each operation.

Set `DEFAULT_GND`, `DEFAULT_VCC`, `DEFAULT_SPEHRE` and `BOARD` in `configs.py` when the automatic part detection
doesn't match your model. Results go to `Bz/` under `configs.DEFAULT_OUTPUT_DIR`:
`<project>_<design>_<setup>_Bz.fld` (raw AEDT export) and `.npz` (`x`, `y`, `bz[ny, nx]` in tesla).

### From Python, in an opened session

```python
from AnsysSession.Action.AnalysisActions.BzProcedure import BzProcedure
from AnsysSession.Session import Session
from Chips import ChipSection

session = Session("path/to/chip.aedt")              # opens AEDT without the GUI
try:
    snapshot = session.snapshot                      # the design as plain data
    chip = ChipSection(snapshot.components, board="ChipBoard", units=snapshot.units)  # one board
    chip.print()

    # Solve Setup1, export Bz 0.06 above the board on a 0.03 grid, then save once.
    result = BzProcedure(session, chip.board, setup="Setup1", cores=8).run()
    session.save()
    print(result["npz file"], result["peak |Bz| (T)"])
finally:
    session.release()                                # closes AEDT
```

To generate data for several chip sections, list them in a CSV file (one row per section;
`vcc_pin`/`gnd_pin` are pin counts such as `126` or cell labels such as `G7`) and run `RUN_MODE = "sections"`:

```
board,vcc_pin,gnd_pin
Board1,126,166
Board2,G7,I9
```

Load an exported image with `numpy.load(result["npz file"])`.

## Pakcages
The **ansysSession** package deals with abstracted interaction directly with the ansys aedt session

The **chips** package deals with the inner data processing of chips, including position selection and candidate generationt that does not require aedt to intervene

The **MField** Data deals with data augmentation after the data is already generated
