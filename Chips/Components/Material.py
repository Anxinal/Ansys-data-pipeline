from ansys.aedt.core.modules.material import MatProperties

from .utils import print_info, safe


class Material:
    """One material of the project, read and edited through the AEDT API."""

    def __init__(self, app, material):
        self.app = app
        self.material = material  # the PyAEDT Material

    @classmethod
    def from_name(cls, app, name):
        """The project's material called ``name``, or None if there is none."""
        if not name:
            return None
        material = app.materials[name]
        return cls(app, material) if material is not None else None

    @property
    def name(self):
        return self.material.name

    def info(self):
        """Every physical property AEDT defines for materials, as "value unit"."""
        info = {}
        for prop in MatProperties.aedtname:
            mat_prop = safe(lambda: getattr(self.material, prop))
            if mat_prop is not None and not isinstance(mat_prop, str):
                info[prop] = f"{mat_prop.value} {mat_prop.unit or ''}".rstrip()
        return info

    def print(self, info=None, indent=2):
        info = self.info() if info is None else info
        print(f"{' ' * indent}-- Material \"{self.name}\"")
        print_info(info, indent + 2)

    def edit(self, **changes):
        """Set material properties by the names info() shows, e.g. conductivity=5.8e7.

        Changes apply to every object that uses this material.
        Returns the edited values as read back from the session.
        """
        unknown = set(changes) - set(MatProperties.aedtname)
        if unknown:
            raise KeyError(f"{sorted(unknown)} are not material properties. Available: {MatProperties.aedtname}")
        for key, value in changes.items():
            setattr(self.material, key, value)
        return {key: getattr(self.material, key).value for key in changes}
