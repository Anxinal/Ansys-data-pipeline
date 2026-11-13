"""Export |J| on an XY grid inside the selected conductor, in A/m^2."""
from pathlib import Path

from configs import DEFAULT_GRID_STEP, DEFAULT_OUTPUT_DIR, DEFAULT_SETUP, J_EXPRESSION, J_PLANE_FRACTION
from ...utils import file_stem
from ..Action import AnsysAction
from .JImage import write_j_image


class JExport(AnsysAction):
    def __init__(self, session, board, setup=DEFAULT_SETUP, output_dir=DEFAULT_OUTPUT_DIR/'J',
                 step=DEFAULT_GRID_STEP, plane_fraction=J_PLANE_FRACTION):
        super().__init__(session, 'Export_J')
        if step <= 0 or not 0 < plane_fraction < 1:
            raise ValueError('J needs positive grid spacing and an interior plane_fraction in (0, 1)')
        self.board, self.setup, self.step = board, setup, step
        self.output_dir, self.fraction = Path(output_dir).resolve(), plane_fraction

    def image_plane(self):
        xmin,ymin,zmin,xmax,ymax,zmax = self.board.bounding_box
        if zmax <= zmin:
            raise ValueError('Volume current density needs a conductor with nonzero thickness')
        z = zmin + self.fraction*(zmax-zmin)
        return (xmin,ymin,z),(xmax,ymax,z),(self.step,self.step,0)

    def act(self):
        session = self.session
        session.ensure_j_expression()
        start, stop, step = self.image_plane()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stem = f'{file_stem(session.project_name)}_{file_stem(session.design)}_{file_stem(self.setup)}_J'
        path = self.output_dir / (stem + '.fld')
        path.unlink(missing_ok=True)
        path.with_suffix('.npz').unlink(missing_ok=True)
        solution = session.solution_name(self.setup)
        session.export_field_on_grid(J_EXPRESSION, path, start, stop, step, solution)
        if not path.is_file() or path.stat().st_size < 100:
            self.error = f'AEDT did not write the J export {path}'
            return self.FAILURE
        self.result = write_j_image(path, start[2], session.units, solution)
        return self.SUCCESS
