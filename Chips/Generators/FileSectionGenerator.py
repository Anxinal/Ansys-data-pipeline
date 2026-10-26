import csv
from pathlib import Path

from ..Positions import NumericalPositionFixed, Position, TerminalPositionPair
from .FeasibleChipSectionGenerator import FeasibleChipSectionGenerator
from .SectionCandidate import SectionCandidate


class FileSectionGenerator(FeasibleChipSectionGenerator):
    """The candidates listed in a CSV file, one row each.

    Columns:
        board                 the board's name (required)
        vcc_pin, gnd_pin      VCC/GND positions (required): a pin count such as
                              126, or a cell label such as "G7"
        vcc, gnd              terminal names (optional; default: the chip's)
        sphere_vcc, sphere_gnd  sphere names (optional, both or neither; default: the chip's)

    Every row is checked against the chip as it is read, so a wrong name fails
    before anything is copied. Each terminal keeps its own height.
    """

    REQUIRED = ("board", "vcc_pin", "gnd_pin")

    def __init__(self, chip, path):
        super().__init__(chip)
        self.path = Path(path)

    def generate(self):
        with self.path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            missing = [column for column in self.REQUIRED if column not in (reader.fieldnames or [])]
            if missing:
                raise ValueError(f"{self.path} has no {missing} column(s); it needs {list(self.REQUIRED)}")
            for line, row in enumerate(reader, start=2):  # line 1 is the header
                try:
                    yield self._candidate(row)
                except (LookupError, ValueError) as e:
                    raise type(e)(f"{self.path}, line {line}: {e}") from None

    def _candidate(self, row):
        def cell(column):
            return (row.get(column) or "").strip() or None

        spheres = [cell("sphere_vcc"), cell("sphere_gnd")]
        if any(spheres) and not all(spheres):
            raise ValueError("give both sphere_vcc and sphere_gnd, or neither")
        section = self.chip.section(cell("board") or "", gnd=cell("gnd"), vcc=cell("vcc"),
                                    spheres=spheres if all(spheres) else None)
        origin = Position.board_origin(section.board)
        pair = TerminalPositionPair(self._position(cell("vcc_pin"), section.vcc, origin),
                                    self._position(cell("gnd_pin"), section.gnd, origin))
        return SectionCandidate(section, pair)

    @staticmethod
    def _position(text, terminal, origin):
        """A pin count ("126") or cell label ("G7") as a NumericalPositionFixed at the terminal's height."""
        if text is None:
            raise ValueError(f"no {terminal.label} pin")
        z = terminal.center[2]
        if text.isdigit():
            return NumericalPositionFixed.from_number(int(text), origin=origin, z=z)
        return NumericalPositionFixed.from_string(text, origin=origin, z=z)
