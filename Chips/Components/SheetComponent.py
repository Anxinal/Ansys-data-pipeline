from .Component import Component
from .utils import safe


class SheetComponent(Component):
    """A sheet (surface): adds area and, for flat sheets, the normal."""

    object_type = "Sheet"

    def info(self):
        faces = self.obj.faces
        units = self.app.modeler.model_units
        return {
            **super().info(),
            "area": f"{safe(lambda: sum(face.area for face in faces))} {units}^2",
            "normal": safe(lambda: faces[0].normal) if len(faces) == 1 else "<several faces>",
            "center": safe(lambda: faces[0].center) if len(faces) == 1 else "<several faces>",
        }
