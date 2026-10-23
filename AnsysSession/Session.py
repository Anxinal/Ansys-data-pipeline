"""An open AEDT project: starting and closing AEDT, the active design and its snapshot.

Reading goes through ``reader`` (DesignReader), every change through ``editor``
(ModelEditor). ``snapshot`` is read once and kept until ``refresh()``; call it
after changing the design.
"""

from ansys.aedt.core import Desktop

from .DesignReader import DesignReader
from .ModelEditor import ModelEditor
from .Report import ProjectReport


class Session:

    def __init__(self, path: str, design=None):
        self.path = path
        # No GUI: everything below goes through the AEDT API.
        desktop = Desktop(non_graphical=True, new_desktop=True)
        try:
            # The design's app object, e.g. ansys.aedt.core.Maxwell3d (not a Desktop).
            self.app = desktop.load_project(path, design_name=design)
        except Exception:
            desktop.release_desktop(close_projects=True, close_on_exit=True)
            raise
        if not self.app:
            desktop.release_desktop(close_projects=True, close_on_exit=True)
            raise RuntimeError(f"AEDT could not open {path}" + (f' (design "{design}")' if design else ""))
        self.reader = DesignReader(self.app)
        self.editor = ModelEditor(self.app)
        self._snapshot = None

    @property
    def design(self):
        return self.app.design_name

    @property
    def snapshot(self):
        """The active design as a DesignSnapshot (read once, then kept until refresh())."""
        if self._snapshot is None:
            self._snapshot = self.reader.snapshot()
        return self._snapshot

    def refresh(self):
        """Read the design again on next use, after it has changed."""
        self._snapshot = None

    def switch_design(self, name):
        """Make ``name`` the active design."""
        self.editor.set_active_design(name)
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
        return [m for m in (self.reader.material(name) for name in names) if m is not None]

    def get_material(self, name):
        material = next((m for m in self.materials if m.name.lower() == name.lower()), None)
        if material is None:
            raise KeyError(f'No material named "{name}" in use. Available: {[m.name for m in self.materials]}')
        return material

    def get_session_info(self, attr: str | None = None):
        """Print and return the project report, or one section of it (see Report.ProjectReport)."""
        return ProjectReport(self).show(attr)

    def edit(self, section: str, name: str, /, **changes):
        """Change one item through the editor (see ModelEditor.edit); the snapshot is re-read next time."""
        result = self.editor.edit(section, name, **changes)
        self.refresh()
        return result

    def generate_data(self):
        pass

    def save(self):
        """Write the edits made in this session to the .aedt project."""
        self.editor.save()

    def release(self):
        """Release the session"""
        self.app.release_desktop(close_projects=True, close_desktop=True)
