from .Components import Component
from .Positions import NumericallyPlaced


class Board(NumericallyPlaced, Component):
    """The chip board: its component's data, plus the position_value a NumericalPositionFixed sets."""

    def __init__(self, component):
        super().__init__(component.name, component.type, component.bounding_box, component.face_ids,
                         component.material_name, component.is_model, component.boundaries)
