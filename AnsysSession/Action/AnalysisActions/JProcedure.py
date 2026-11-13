"""Solve the selected design, then export current-density magnitude."""
from configs import DEFAULT_GRID_STEP, DEFAULT_OUTPUT_DIR, DEFAULT_SETUP, J_PLANE_FRACTION
from ..Action import AnsysProcedure
from .Analysis import BzAnalysis as SetupAnalysis
from .JExport import JExport


class JProcedure(AnsysProcedure):
    def __init__(self, session, board, setup=DEFAULT_SETUP, output_dir=DEFAULT_OUTPUT_DIR/'J',
                 step=DEFAULT_GRID_STEP, plane_fraction=J_PLANE_FRACTION, cores=None, solve=True):
        self.export = JExport(session, board, setup, output_dir, step, plane_fraction)
        actions = [SetupAnalysis(session, setup, cores), self.export] if solve else [self.export]
        super().__init__(actions, session, 'J')

    def act(self):
        status = super().act()
        self.result = self.export.result
        return status
