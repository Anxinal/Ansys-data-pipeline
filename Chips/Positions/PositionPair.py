from dataclasses import dataclass

from .Position import Position


@dataclass(frozen=True)
class PositionPair:
    """The grid positions of VCC and GND for one copy; the two spheres sit on the same cells."""

    a: Position
    b: Position



class TerminalPositionPair(PositionPair):
    
    """{"VCC": Position, "GND": Position}, the form Chip.terminal_positions() returns."""
    def as_dict(self):
        """{"VCC": Position, "GND": Position}, the form Chip.terminal_positions() returns."""
        return {"VCC": self.a, "GND": self.b}

    def __str__(self):
        return f"VCC {self.a}; GND {self.b}"



