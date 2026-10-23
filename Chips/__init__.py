"""The chip layer: plain data and logic about a chip, with no AEDT calls.

AnsysSession reads a design into a DesignSnapshot; the classes here work on it.
"""

from .Board import Board
from .Chip import Chip
from .ChipSection import ChipSection
from .CopyRecord import CopyRecord
from .DesignSnapshot import DesignSnapshot
from .Positions import (NumericallyPlaced, NumericalPositionFixed, Position, PositionPair, PositionSampler,
                        TerminalPositionPair)
from .Terminal import Terminal

__all__ = ["Board", "Chip", "ChipSection", "CopyRecord", "DesignSnapshot", "NumericallyPlaced", "NumericalPositionFixed", "Position",
           "PositionPair", "PositionSampler", "Terminal", "TerminalPositionPair"]
