"""An open AEDT project: starting and closing AEDT, the active design and its snapshot.

Session is the only way into AEDT: it keeps the app, its DesignReader and its
ModelEditor private, and every read and change is one of its methods. Actions
take a Session for that reason. ``snapshot`` is read once and kept until
``refresh()``; call it after changing the design.
"""

from contextlib import contextmanager

from ansys.aedt.core import Desktop

from .DesignReader import DesignReader
from .ModelEditor import ModelEditor
from .Report import ProjectReport
from .GrpcCompatibility import local_grpc_port_detection
from .RootState import capture


class Session:

    def __init__(self, path: str, design=None, non_graphical=True):
        self.path = path
        with local_grpc_port_detection():
            desktop = Desktop(non_graphical=non_graphical, new_desktop=True)
        try:
            # The design's app object, e.g. ansys.aedt.core.Maxwell3d (not a Desktop).
            self._app = desktop.load_project(path, design_name=design)
        except Exception:
            desktop.release_desktop(close_projects=True, close_on_exit=True)
            raise
        if not self._app:
            desktop.release_desktop(close_projects=True, close_on_exit=True)
            raise RuntimeError(f"AEDT could not open {path}" + (f' (design "{design}")' if design else ""))
        self._reader = DesignReader(self._app)
        self._editor = ModelEditor(self._app)
        self._snapshot = None

    @property
    def design(self):
        return self._app.design_name

    @property
    def project_name(self):
        return self._app.project_name

    @property
    def design_list(self):
        """The names of the project's designs."""
        return self._app.design_list

    @property
    def units(self):
        """The active design's model units."""
        return self._app.modeler.model_units

    @property
    def setup_names(self):
        return self._app.setup_names

    @property
    def toolkit_directory(self):
        """PyAEDT's folder for the project (<project>.pyaedt)."""
        return self._app.toolkit_directory

    @property
    def snapshot(self):
        """The active design as a DesignSnapshot (read once, then kept until refresh())."""
        if self._snapshot is None:
            self._snapshot = self._reader.snapshot()
        return self._snapshot

    def refresh(self):
        """Read the design again on next use, after it has changed."""
        self._snapshot = None

    def switch_design(self, name):
        """Make ``name`` the active design."""
        self._editor.set_active_design(name)
        self.refresh()

    @property
    def components(self):
        return self.snapshot.components

    def get_component(self, name):
        """The component called ``name`` (case-insensitive)."""
        try:
            return self.snapshot.get_component(name)
        except LookupError as e:
            raise KeyError(str(e)) from None

    @property
    def materials(self):
        """The Materials used by the components, one per material."""
        names = sorted({c.material_name for c in self.components if c.material_name})
        return [m for m in (self._reader.material(name) for name in names) if m is not None]

    def get_material(self, name):
        material = next((m for m in self.materials if m.name.lower() == name.lower()), None)
        if material is None:
            raise KeyError(f'No material named "{name}" in use. Available: {[m.name for m in self.materials]}')
        return material

    def get_session_info(self, attr: str | None = None):
        """Print and return the project report, or one section of it (see Report.ProjectReport)."""
        return ProjectReport(self, self._app).show(attr)

    def edit(self, section: str, name: str, /, **changes):
        """Change one item through the editor (see ModelEditor.edit); the snapshot is re-read next time."""
        result = self._editor.edit(section, name, **changes)
        self.refresh()
        return result

    def deselect_all_for_analysis(self, selected, state_file):
        """Make every object inactive (out of the model), the background too.

        The original state, with ``selected`` recorded in it, is written to
        ``state_file`` first and returned, for the RestoreState action to undo this.
        """
        state, modeled, _ = capture(self, selected, state_file)
        self._editor.set_model_state(sorted(modeled), False)
        self.refresh()
        return state

    def select_for_analysis(self, name):
        """Make the object called ``name`` active (back in the model), e.g. after deselect_all_for_analysis."""
        names, _ = self._reader.model_objects()
        if name not in names:
            raise LookupError(f'No object "{name}" in design "{self.design}".')
        self._editor.set_model_state([name], True)
        self.refresh()

    def deselect_for_analysis(self, name):
        """Make the object called ``name`` inactive (out of the model)."""
        names, _ = self._reader.model_objects()
        if name not in names:
            raise LookupError(f'No object "{name}" in design "{self.design}"')
        self._editor.set_model_state([name], False)
        self.refresh()


    def generate_data(self):
        pass

    # --- reads (see DesignReader) -----------------------------------------
    def selected_components(self, names):
        """The named components, reading geometry only for them instead of a full snapshot."""
        return self._reader.selected_components(names)

    def details(self, component):
        """The extras of one object a report shows (id, solve inside, group, volume, area, ...)."""
        return self._reader.details(component)

    def model_objects(self):
        """(every object's name, the names of the objects taking part in the model)."""
        return self._reader.model_objects()

    def objects_with_materials(self, materials):
        return self._reader.objects_with_materials(materials)

    def variable_value(self, name):
        return self._reader.variable_value(name)

    def move_operations(self, name):
        """[(operation, [x, y, z expressions])] of the Move operations in an object's history."""
        return self._reader.move_operations(name)

    def solution_name(self, setup):
        return self._reader.solution_name(setup)

    def export_field_on_grid(self, expression, path, start, stop, step, solution):
        self._reader.export_field_on_grid(expression, path, start, stop, step, solution)

    def obtain_image_snapshot(self, component):
        """A BoardImage of ``component``; AEDT must run in graphical mode and configs.GRID_SIZE be set."""
        return self._reader.obtain_image_snapshot(component)

    def valid_check(self):
        """AEDT's Validation Check on the active design: (passed, messages, log file)."""
        return self._reader.valid_check()

    # --- changes (see ModelEditor); refresh() afterwards to re-read the design ---
    def move(self, name, vector):
        self._editor.move(name, vector)

    def move_with_expressions(self, name, vector):
        self._editor.move_with_expressions(name, vector)

    def move_to(self, name, position):
        self._editor.move_to(name, position)

    def set_model_state(self, names, model):
        self._editor.set_model_state(names, model)

    def set_move_vector(self, name, operation, vector):
        self._editor.set_move_vector(name, operation, vector)

    def copy_in_place(self, name):
        return self._editor.copy_in_place(name)

    def duplicate(self, name, vector):
        return self._editor.duplicate(name, vector)

    def rename(self, name, new_name):
        return self._editor.rename(name, new_name)

    def create_group(self, names, group):
        return self._editor.create_group(names, group)

    def delete(self, names):
        self._editor.delete(names)

    def purge_history(self, names):
        self._editor.purge_history(names)

    def set_pin_count(self, variable, count):
        self._editor.set_pin_count(variable, count)

    def set_pin_expression(self, variable, expression):
        self._editor.set_pin_expression(variable, expression)

    def ensure_bz_expression(self):
        self._editor.ensure_bz_expression()

    def solve(self, setup, cores=None):
        return self._editor.solve(setup, cores)

    def duplicate_design(self, name):
        """Duplicate the active design and make the duplicate active; returns its name."""
        return self._editor.duplicate_design(name)

    def delete_design(self, name, fallback_design=None):
        self._editor.delete_design(name, fallback_design=fallback_design)

    def save(self):
        """Write the edits made in this session to the .aedt project."""
        self._editor.save()

    def release(self, close_desktop=True):
        """Release Python's session, optionally leaving the GUI/project open."""
        self._app.release_desktop(close_projects=close_desktop, close_desktop=close_desktop)
