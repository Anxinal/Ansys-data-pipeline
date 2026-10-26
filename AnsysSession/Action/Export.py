"""The export step: sample Bz on an image plane above the board and write it to files.

Bz, the z-component of the magnetic flux density, is sampled on a flat grid
above the chip board and exported to the output folder:

    <project>_<design>_<setup>_Bz.fld   raw AEDT grid export: x, y, z, Bz rows
    <project>_<design>_<setup>_Bz.npz   the Bz image: x [nx], y [ny], bz [ny, nx]

Coordinates are in the design's model units; Bz is in tesla.
"""

import re
from pathlib import Path

import numpy as np

from configs import BZ_EXPRESSION, DEFAULT_GRID_STEP, DEFAULT_OUTPUT_DIR, DEFAULT_SCAN_HEIGHT, DEFAULT_SETUP

from ..utils import file_stem
from .Action import AnsysAction
from .Analysis import solution_name


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


class BzExport(AnsysAction):
    """Export the Bz image above ``board`` (a Component); the summary ends up in ``self.result``."""

    def __init__(self, app, board, setup=DEFAULT_SETUP, output_dir=DEFAULT_OUTPUT_DIR,
                 scan_height=DEFAULT_SCAN_HEIGHT, step=DEFAULT_GRID_STEP, label="export"):
        super().__init__(app, label)
        self.board = board
        self.setup = setup
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.scan_height = scan_height
        self.step = step
        self.units = app.modeler.model_units
        self.result = None

    @property
    def solution(self):
        return solution_name(self.app, self.setup)

    def act(self):
        self.ensure_bz_expression()
        start, stop, grid_step = self.image_plane()
        fld_path = self.export_bz(start, stop, grid_step)
        if fld_path is None:
            return self.FAILURE

        x, y, bz = load_bz_image(fld_path)
        npz_path = fld_path.with_suffix(".npz")
        np.savez_compressed(npz_path, x=x, y=y, bz=bz, z=start[2], units=self.units, solution=self.solution)

        peak_y, peak_x = np.unravel_index(np.nanargmax(np.abs(bz)), bz.shape)
        self.result = {
            "solution": self.solution,
            "image plane": f"z = {start[2]} {self.units}, {len(x)} x {len(y)} pixels of {self.step} {self.units}",
            "Bz min (T)": float(np.nanmin(bz)),
            "Bz max (T)": float(np.nanmax(bz)),
            "peak |Bz| (T)": float(abs(bz[peak_y, peak_x])),
            "peak at (x, y)": (float(x[peak_x]), float(y[peak_y])),
            "missing pixels": int(np.isnan(bz).sum()),
            "fld file": str(fld_path),
            "npz file": str(npz_path),
        }
        return self.SUCCESS

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

    def image_plane(self):
        """(start, stop, step) of a grid over the board's XY extent, scan_height above its top."""
        xmin, ymin, _, xmax, ymax, zmax = self.board.bounding_box
        z = zmax + self.scan_height
        return (xmin, ymin, z), (xmax, ymax, z), (self.step, self.step, 0)

    def export_bz(self, start, stop, step):
        """Export Bz on the grid to a .fld file; its path, or None (with self.error) on failure."""
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
            self.error = f"AEDT did not write the Bz export {fld_path}"
            return None
        return fld_path
