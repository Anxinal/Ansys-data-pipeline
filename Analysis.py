"""Bz field analysis of an opened session.

Solves the design's setup in the session (or reuses its solution), samples Bz,
the z-component of the magnetic flux density, on a flat image plane above the
chip board, and exports it to the output folder:

    <project>_<design>_<setup>_Bz.fld   raw AEDT grid export: x, y, z, Bz rows
    <project>_<design>_<setup>_Bz.npz   the Bz image: x [nx], y [ny], bz [ny, nx]

Coordinates are in the design's model units; Bz is in tesla.
"""

import re
from pathlib import Path

import numpy as np

# Defaults, overridable from main.py's options.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "Result" / "Bz"
DEFAULT_SETUP = "Setup1"
DEFAULT_SCAN_HEIGHT = 0.060  # image plane height above the board's top face, model units
DEFAULT_GRID_STEP = 0.030  # image pixel size, model units

# Fields-calculator named expression for the smoothed z-component of B;
# BzAnalysis creates it in the project when it is missing.
BZ_EXPRESSION = "smoothscalBz"


def file_stem(name):
    """Make an AEDT name (which may contain spaces or colons) safe for a file name."""
    return re.sub(r"[^\w.-]+", "_", name).strip("_")


def load_bz_image(fld_path):
    """Read an AEDT grid export of a scalar into (x [nx], y [ny], bz [ny, nx]).

    Rows are matched to pixels by their coordinates, so their order doesn't
    matter. Pixels AEDT leaves out stay NaN.
    """
    rows = []
    with open(fld_path, encoding="utf-8", errors="replace") as stream:
        for line in stream:
            parts = line.replace(",", " ").replace("D", "E").split()
            if len(parts) != 4:
                continue  # header lines
            try:
                rows.append([float(part) for part in parts])
            except ValueError:
                continue  # column-name line
    if not rows:
        raise ValueError(f"No x, y, z, value rows in {fld_path}")
    data = np.array(rows)
    x_coords = np.round(data[:, 0], 9)
    y_coords = np.round(data[:, 1], 9)
    x, y = np.unique(x_coords), np.unique(y_coords)
    bz = np.full((len(y), len(x)), np.nan)
    bz[np.searchsorted(y, y_coords), np.searchsorted(x, x_coords)] = data[:, 3]
    return x, y, bz


class BzAnalysis:
    """Solve a setup in an opened Session and export its Bz image."""

    def __init__(self, session, setup=DEFAULT_SETUP, output_dir=DEFAULT_OUTPUT_DIR):
        self.app = session.app
        if setup not in self.app.setup_names:
            raise ValueError(f'No setup "{setup}" in design "{self.app.design_name}". Available: {self.app.setup_names}')
        self.setup = setup
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.units = self.app.modeler.model_units

    @property
    def solution(self):
        """The setup's solution, e.g. "Setup1 : LastAdaptive"."""
        for solution in self.app.existing_analysis_sweeps:
            if solution.split(":")[0].strip() == self.setup:
                return solution
        return f"{self.setup} : LastAdaptive"

    def solve(self, cores=None):
        """Solve the setup in the open session and save the project so the solution is kept."""
        print(f'Solving "{self.setup}" in design "{self.app.design_name}"...')
        if not self.app.analyze_setup(self.setup, cores=cores):
            raise RuntimeError(f'AEDT failed to solve "{self.setup}". See the AEDT message manager for details.')
        self.app.save_project()

    def ensure_bz_expression(self):
        """Create the smoothed-Bz named expression if the project doesn't have it yet."""
        reporter = self.app.ofieldsreporter
        if reporter.DoesNamedExpressionExists(BZ_EXPRESSION):
            return
        reporter.CalcStack("clear")
        reporter.EnterQty("B")
        reporter.CalcOp("ScalarZ")
        reporter.CalcOp("Smooth")
        reporter.AddNamedExpression(BZ_EXPRESSION, "Fields")
        reporter.CalcStack("clear")

    def image_plane(self, board, scan_height=DEFAULT_SCAN_HEIGHT, step=DEFAULT_GRID_STEP):
        """(start, stop, step) of a grid over the board's XY extent, scan_height above its top."""
        xmin, ymin, _, xmax, ymax, zmax = board.obj.bounding_box
        z = zmax + scan_height
        return (xmin, ymin, z), (xmax, ymax, z), (step, step, 0)

    def export_bz(self, start, stop, step):
        """Export Bz on the grid to a .fld file in the output folder and return its path."""
        app = self.app
        self.output_dir.mkdir(parents=True, exist_ok=True)
        fld_path = self.output_dir / f"{file_stem(app.project_name)}_{file_stem(app.design_name)}_{file_stem(self.setup)}_Bz.fld"
        fld_path.unlink(missing_ok=True)  # don't mistake a previous run's file for this run's output

        # Export at the design's current variable values.
        variation = []
        for name, variable in app.variable_manager.independent_design_variables.items():
            variation += [f"{name}:=", [variable.expression]]
        export_options = ["NAME:ExportOption", "IncludePtInOutput:=", True, "RefCSName:=", "Global",
                          "PtInSI:=", False, "FieldInRefCS:=", True]

        reporter = app.ofieldsreporter
        reporter.CalcStack("clear")
        try:
            reporter.CopyNamedExprToStack(BZ_EXPRESSION)
            reporter.ExportOnGrid(
                str(fld_path),
                [f"{value}{self.units}" for value in start],
                [f"{value}{self.units}" for value in stop],
                [f"{value}{self.units}" for value in step],
                self.solution,
                variation,
                export_options,
                "Cartesian",
                [f"0{self.units}"] * 3,
                False,
            )
        finally:
            reporter.CalcStack("clear")
        if not fld_path.is_file() or fld_path.stat().st_size < 100:
            raise RuntimeError(f"AEDT did not write the Bz export {fld_path}")
        return fld_path

    def analyse(self, board, scan_height=DEFAULT_SCAN_HEIGHT, step=DEFAULT_GRID_STEP):
        """Export the Bz image above ``board`` (a Component) and return a summary of it."""
        self.ensure_bz_expression()
        start, stop, grid_step = self.image_plane(board, scan_height, step)
        fld_path = self.export_bz(start, stop, grid_step)

        x, y, bz = load_bz_image(fld_path)
        npz_path = fld_path.with_suffix(".npz")
        np.savez_compressed(npz_path, x=x, y=y, bz=bz, z=start[2], units=self.units, solution=self.solution)

        peak_y, peak_x = np.unravel_index(np.nanargmax(np.abs(bz)), bz.shape)
        return {
            "solution": self.solution,
            "image plane": f"z = {start[2]} {self.units}, {len(x)} x {len(y)} pixels of {step} {self.units}",
            "Bz min (T)": float(np.nanmin(bz)),
            "Bz max (T)": float(np.nanmax(bz)),
            "peak |Bz| (T)": float(abs(bz[peak_y, peak_x])),
            "peak at (x, y)": (float(x[peak_x]), float(y[peak_y])),
            "missing pixels": int(np.isnan(bz).sum()),
            "fld file": str(fld_path),
            "npz file": str(npz_path),
        }
