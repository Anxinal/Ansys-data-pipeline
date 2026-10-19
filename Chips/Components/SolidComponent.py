from .Component import Component
from .utils import safe


class SolidComponent(Component):
    """A solid body: adds volume and mass."""

    object_type = "Solid"

    def info(self):
        obj = self.obj
        units = self.app.modeler.model_units
        return {
            **super().info(),
            "volume": f"{safe(lambda: obj.volume)} {units}^3",
            "mass (kg)": safe(lambda: obj.mass),
        }
