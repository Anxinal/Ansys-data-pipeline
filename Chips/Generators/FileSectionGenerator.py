"""Generate section candidates from board-specific pools of numerical pins."""
from pathlib import Path

from ..Positions import AllCombinationSampler
from .FeasibleChipSectionGenerator import FeasibleChipSectionGenerator
from .SectionPositions import sample_candidates
from .SectionRows import read_rows


class FileSectionGenerator(FeasibleChipSectionGenerator):
    """Batch-generate all combinations by default, or use an injected sampler.

    Instruction lines accept two or more Sphere_positions; CSV accepts a
    sphere_positions pool or legacy vcc_pin/gnd_pin columns. The first member
    of each combination is VCC, the second GND. Each keeps its own height.
    """

    read_rows = staticmethod(read_rows)

    def __init__(self, chip, path, sampler=None, sample_count=-1):
        super().__init__(chip)
        self.path = Path(path)
        self.sampler = sampler if sampler is not None else AllCombinationSampler()
        self.sample_count = sample_count

    def generate(self):
        candidates = []
        for line, row in self.read_rows(self.path):
            try:
                candidates.extend(sample_candidates(self.chip, row, self.sampler, self.sample_count))
            except (LookupError, ValueError) as error:
                raise type(error)(f"{self.path}, line {line}: {error}") from None
        yield from candidates
