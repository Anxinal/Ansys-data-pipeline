from dataclasses import dataclass

from ..ChipSection import ChipSection
from ..Positions import NumericalPositionFixed, TerminalPositionPair


@dataclass(frozen=True)
class SectionCandidate:
    """One feasible combination: a ChipSection (board, terminals, spheres) and where its VCC/GND go.

    pair   TerminalPositionPair of NumericalPositionFixed positions: a for VCC, b for GND
    """

    section: ChipSection
    pair: TerminalPositionPair

    def __post_init__(self):
        for label, position in self.pair.as_dict().items():
            if not isinstance(position, NumericalPositionFixed):
                raise TypeError(f"{label} position must be a NumericalPositionFixed, got {type(position).__name__}")

    def __str__(self):
        return f'board "{self.section.board.name}": {self.pair}'
