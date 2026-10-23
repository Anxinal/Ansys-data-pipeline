from .Components import Component
from .Components.utils import format_info
from .Positions import NumericallyPlaced


class Terminal(NumericallyPlaced, Component):
    """GND or VCC: the object that carries the terminal, with its role (``label``).

    Found by name among ``components``: an object's name, or the name of an
    excitation, in which case the terminal is the object that excitation is
    assigned to (``boundary`` keeps the excitation).
    """

    def __init__(self, components, label, name):
        if not components:
            raise ValueError(f"{label} terminal needs at least one component to search")
        component = next((c for c in components if c.name.lower() == name.lower()), None)
        boundary = None
        if component is None:
            component, boundary = self._find_by_excitation(components, label, name)
        super().__init__(component.name, component.type, component.bounding_box, component.face_ids,
                         component.material_name, component.is_model, component.boundaries)
        self.label = label
        self.boundary = boundary

    @staticmethod
    def _find_by_excitation(components, label, name):
        for component in components:
            for boundary in component.boundaries:
                if boundary.name.lower() == name.lower():
                    return component, boundary
        excitations = sorted({b.name for c in components for b in c.boundaries})
        raise LookupError(
            f'No component or excitation named "{name}" for {label}. '
            f"Components: {[c.name for c in components]}; excitations: {excitations}"
        )

    @property
    def point(self):
        """The object's center, or for an excitation on faces, the average center of those faces."""
        if self.boundary is not None and self.boundary.center is not None:
            return list(self.boundary.center)
        return self.center

    def info(self):
        """Chip-level summary: name, kind and position."""
        kind = f"{self.type} object"
        if self.boundary is not None:
            kind += f' with excitation "{self.boundary.name}" ({self.boundary.type})'
        return {"name": self.name, "kind": kind, "position": self.position}

    def describe(self, full=False):
        """The terminal's name, kind and position; with ``full``, also the object's details."""
        details = self.info()
        if full:
            details = {**details, "component": Component.info(self)}
            if self.boundary is not None:
                details["excitation"] = dict(self.boundary.props)
        return f'{self.label} "{self.name}"\n{format_info(details)}'

    def __str__(self):
        return self.describe()
