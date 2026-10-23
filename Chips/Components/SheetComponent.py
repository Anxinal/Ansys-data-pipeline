from .Component import Component


class SheetComponent(Component):
    """A sheet, i.e. a surface (area and normal come from AnsysSession.DesignReader.details())."""

    object_type = "Sheet"
