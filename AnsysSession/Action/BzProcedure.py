"""The Bz procedure: analyse (solve) the active design, then export its Bz image."""

from configs import DEFAULT_GRID_STEP, DEFAULT_OUTPUT_DIR, DEFAULT_SCAN_HEIGHT, DEFAULT_SETUP

from .Action import AnsysProcedure
from .Analysis import BzAnalysis
from .Export import BzExport


class BzProcedure(AnsysProcedure):
    """BzAnalysis then BzExport on the same app; without ``solve`` only the export runs.

    ``result`` is the export's summary once the procedure has run.
    """

    def __init__(self, app, board, setup=DEFAULT_SETUP, output_dir=DEFAULT_OUTPUT_DIR,
                 scan_height=DEFAULT_SCAN_HEIGHT, step=DEFAULT_GRID_STEP, cores=None, solve=True, label="bz"):
        self.export = BzExport(app, board, setup, output_dir, scan_height, step)
        actions = [BzAnalysis(app, setup, cores), self.export] if solve else [self.export]
        super().__init__(actions, app, label)

    def act(self):
        status = super().act()
        self.result = self.export.result
        return status
