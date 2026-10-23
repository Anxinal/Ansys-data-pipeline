from .NumericalPositionFixed import NumericalPositionFixed


class NumericallyPlaced:
    """Mixin for the chip parts a NumericalPositionFixed applies to: the terminals and the board.

    Placing such a part changes only its ``position_value``, never its geometry.
    """

    position_value = None  # set by place_at(); None until the part is placed

    def place_at(self, position):
        """Set position_value from ``position`` (a NumericalPositionFixed); the object stays where it is."""
        if not isinstance(position, NumericalPositionFixed):
            raise TypeError(f"place_at needs a NumericalPositionFixed, got {type(position).__name__}")
        self.position_value = position.value
