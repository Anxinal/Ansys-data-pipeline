from .Components.utils import find_component, format_info


class Terminal:
    """GND or VCC: a component or an excitation, located by its center."""

    def __init__(self, components, label, name):
        """Find the terminal called ``name`` among ``components``.

        ``name`` is matched (case-insensitive) against the component names first,
        then against the excitations assigned to those components.
        """
        if not components:
            raise ValueError(f"{label} terminal needs at least one component to search")
        self.label = label
        self.component = None
        self.boundary = None

        component = next((c for c in components if c.name.lower() == name.lower()), None)
        if component is not None:
            self.component = component
            self.name = component.name
            self.position = component.center
            return

        # Not an object: look for an excitation of that name assigned to the components.
        boundaries = components[0].app.boundaries
        boundary = next((b for b in boundaries if b.name.lower() == name.lower()), None)
        if boundary is None:
            available = [c.name for c in components] + [b.name for b in boundaries]
            raise LookupError(f'No component or excitation named "{name}" for {label}. Available: {available}')
        self.boundary = boundary
        self.name = boundary.name
        # Excitations sit on faces or whole objects; average their centers.
        face_ids = set(boundary.props.get("Faces", []))
        centers = [face.center for c in components for face in c.obj.faces if face.id in face_ids]
        centers += [find_component(components, obj, label).center for obj in boundary.props.get("Objects", [])]
        if not centers:
            raise LookupError(f'Excitation "{name}" for {label} is not assigned to any of the given components')
        self.position = [sum(axis) / len(centers) for axis in zip(*centers)]

    def info(self):
        return {
            "name": self.name,
            "kind": f"excitation ({self.boundary.type})" if self.boundary else f"{self.component.obj.object_type} object",
            "position": self.position,
        }

    def __str__(self):
        """The terminal, followed by the object it is or the excitation's settings."""
        details = {**self.info()}
        if self.component is not None:
            details["component"] = self.component.info()
        else:
            details["excitation"] = dict(self.boundary.props)
        return f'{self.label} "{self.name}"\n{format_info(details)}'
