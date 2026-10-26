import csv
from pathlib import Path

from ..Positions import NumericalPositionFixed, Position, TerminalPositionPair
from .FeasibleChipSectionGenerator import FeasibleChipSectionGenerator
from .SectionCandidate import SectionCandidate


class CNNGenerator(FeasibleChipSectionGenerator):
    """
    The candidates are predicted using CNN algorithm with a simple classification task
    """


    def __init__(self, chip, path):
        super().__init__(chip)
        self.path = Path(path)

    def generate(self):
        pass


    def _candidate(self, row):
        pass




