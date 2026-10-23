from .Component import Component


class SolidComponent(Component):
    """A solid body (volume and mass come from AnsysSession.DesignReader.details())."""

    object_type = "Solid"
