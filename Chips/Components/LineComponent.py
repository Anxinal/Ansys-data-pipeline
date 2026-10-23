from .Component import Component


class LineComponent(Component):
    """A line or polyline (length comes from AnsysSession.DesignReader.details())."""

    object_type = "Line"
