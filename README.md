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
main.py                    command line; wires everything together
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
    CopyandGenerate.py     copy one board section, set its terminals, validate, solve, export
    SwitchBackToMain.py    return to the main design before the next copy
    SetTerminalPositions.py  set VCC/GND position values (ModelEditor.set_position_value)
    MoveComponent.py, MoveCurrentConnectors.py, CheckValidity.py
Chips/                     chip layer (pure Python, no AEDT)
  DesignSnapshot.py        one design, read at one moment
  Components/              Component (+ Solid/Sheet/Line), Material, Boundary
  Chip.py, Terminal.py     finds GND/VCC, the two spheres and the boards
  ChipSection.py           a chip with one board: the section copied and analysed
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

### From the command line

```
python main.py path/to/chip.aedt --cores 8                  # solve and export Bz above the board
python main.py path/to/chip.aedt --no-solve                 # reuse the existing solution
python main.py path/to/chip.aedt --extract                  # new copy BOARD_<n>, then analyse it
python main.py path/to/chip.aedt --copy BOARD_1             # analyse an existing copy
```

Use `--gnd`, `--vcc`, `--spheres`, `--board` when the automatic part detection doesn't match
your model, and `--help` for the rest. Results go to `data_export_default/` (`configs.DEFAULT_OUTPUT_DIR`):
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

To generate data for several boards of the main design, one copy at a time (each copy's
VCC/GND are set to a pair of `NumericalPositionFixed` positions):

```python
from AnsysSession.Action.CopyandGenerate import CopyandGenerate
from AnsysSession.Action.SwitchBackToMain import SwitchBackToMain
from Chips import Chip, NumericalPositionFixed, TerminalPositionPair

chip = Chip(original_components(session.snapshot), units=session.snapshot.units)   # all boards
pair = TerminalPositionPair(NumericalPositionFixed.from_string("A3", z=1.2),
                            NumericalPositionFixed.from_string("C7", z=1.2))
for board in chip.boards:
    job = CopyandGenerate(session, chip, board, pair, cores=8)
    if job.act() != job.SUCCESS:
        print(f"{job.failed.label} failed: {job.error}")
    SwitchBackToMain(session, job.main_design).act()
```

Load an exported image with `numpy.load(result["npz file"])`.
