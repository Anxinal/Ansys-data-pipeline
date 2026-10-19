from .Component import Component
from .utils import safe


class LineComponent(Component):
    """A line or polyline: adds length, points and segment types."""

    object_type = "Line"

    def info(self):
        obj = self.obj
        units = self.app.modeler.model_units
        return {
            **super().info(),
            "length": f"{safe(lambda: sum(edge.length for edge in obj.edges))} {units}",
            "polyline": safe(lambda: obj.is_polyline),
            "points": safe(lambda: obj.points),
            "segment types": safe(lambda: obj.segment_types),
        }
