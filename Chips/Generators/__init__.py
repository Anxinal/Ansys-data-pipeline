"""Generators of feasible chip sections: each yields SectionCandidates (a ChipSection and its VCC/GND positions)."""

from .FeasibleChipSectionGenerator import FeasibleChipSectionGenerator
from .FileSectionGenerator import FileSectionGenerator
from .SectionCandidate import SectionCandidate

__all__ = ["FeasibleChipSectionGenerator", "FileSectionGenerator", "SectionCandidate"]
