from abc import ABC, abstractmethod

from ..Chip import Chip


class FeasibleChipSectionGenerator(ABC):
    """Produces the feasible SectionCandidates of ``chip`` (the main design's Chip).

    Iterate over the generator, or call generate(), to get the candidates one
    at a time. Generators that need AEDT live in AnsysSession and subclass this.
    """

    def __init__(self, chip: Chip):
        self.chip = chip

    @abstractmethod
    def generate(self):
        """Yield SectionCandidates."""
        

    def __iter__(self):
        return iter(self.generate())
