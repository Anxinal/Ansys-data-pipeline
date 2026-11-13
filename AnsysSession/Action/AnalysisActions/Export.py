"""The export step: sample Bz on an image plane above the board and write it to files.

Bz, the z-component of the magnetic flux density, is sampled on a flat grid
above the chip board and exported to the output folder:

    <project>_<design>_<setup>_Bz.fld   raw AEDT grid export: x, y, z, Bz rows
    <project>_<design>_<setup>_Bz.npz   the Bz image: x [nx], y [ny], bz [ny, nx]

Coordinates are in the design's model units; Bz is in tesla.
"""

from pathlib import Path

import numpy as np

from configs import BZ_EXPRESSION, DEFAULT_GRID_STEP, DEFAULT_OUTPUT_DIR, DEFAULT_SCAN_HEIGHT, DEFAULT_SETUP

from ...utils import file_stem
from ..Action import AnsysAction
from .ScalarImage import load_scalar_image as load_bz_image


class BzExport(AnsysAction):
    """Export the Bz image above ``board`` (a Component); the summary ends up in ``self.result``."""

    def __init__(self, session, board, setup=DEFAULT_SETUP, output_dir=DEFAULT_OUTPUT_DIR,
                 scan_height=DEFAULT_SCAN_HEIGHT, step=DEFAULT_GRID_STEP, label="export"):
        super().__init__(session, label)
        self.board = board
        self.setup = setup
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.scan_height = scan_height
        self.step = step
        self.units = session.units

    @property
    def solution(self):
        return self.session.solution_name(self.setup)

    def act(self):
        self.session.ensure_bz_expression()
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

    def image_plane(self):
        """(start, stop, step) of a grid over the board's XY extent, scan_height above its top."""
        xmin, ymin, _, xmax, ymax, zmax = self.board.bounding_box
        z = zmax + self.scan_height
        return (xmin, ymin, z), (xmax, ymax, z), (self.step, self.step, 0)

    def export_bz(self, start, stop, step):
        """Export Bz on the grid to a .fld file; its path, or None (with self.error) on failure."""
        session = self.session
        self.output_dir.mkdir(parents=True, exist_ok=True)
        fld_path = self.output_dir / f"{file_stem(session.project_name)}_{file_stem(session.design)}_{file_stem(self.setup)}_Bz.fld"
        fld_path.unlink(missing_ok=True)  # don't mistake a previous run's file for this run's output

        session.export_field_on_grid(BZ_EXPRESSION, fld_path, start, stop, step, self.solution)
        if not fld_path.is_file() or fld_path.stat().st_size < 100:
            self.error = f"AEDT did not write the Bz export {fld_path}"
            return None
        return fld_path
