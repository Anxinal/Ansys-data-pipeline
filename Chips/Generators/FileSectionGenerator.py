import csv
import re
from pathlib import Path

from ..Positions import NumericalPositionFixed, Position, TerminalPositionPair
from .FeasibleChipSectionGenerator import FeasibleChipSectionGenerator
from .SectionCandidate import SectionCandidate

INSTRUCTION = re.compile(r"\s*board\s*=\s*(?P<board>\S+)\s+sphere_positions\s*=\s*(?P<pins>.*?)\s*", re.IGNORECASE)


class FileSectionGenerator(FeasibleChipSectionGenerator):
    """The candidates listed in a section file, one per line.

    The file is either a CSV file with the columns:
        board                 the board's name (required)
        vcc_pin, gnd_pin      VCC/GND positions (required): a pin count such as
                              126, or a cell label such as "G7"
        vcc, gnd              terminal names (optional; default: the chip's)
        sphere_vcc, sphere_gnd  sphere names (optional, both or neither; default: the chip's)

    or instruction lines, VCC's pin first:
        board = L4L3_Separate_87 Sphere_positions = 399 258

    Every row is checked against the chip as it is read, so a wrong name fails
    before anything is copied. Each terminal keeps its own height.
    """

    REQUIRED = ("board", "vcc_pin", "gnd_pin")

    def __init__(self, chip, path):
        super().__init__(chip)
        self.path = Path(path)

    def generate(self):
        for line, row in self.read_rows(self.path):
            try:
                yield self._candidate(row)
            except (LookupError, ValueError) as e:
                raise type(e)(f"{self.path}, line {line}: {e}") from None

    @classmethod
    def read_rows(cls, path):
        """[(line number, row)] of a section file, each row a dict with at least board, vcc_pin and gnd_pin."""
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        first = next((line for line in text.splitlines() if line.strip()), "")
        rows = cls._instruction_rows(path, text) if INSTRUCTION.fullmatch(first) else cls._csv_rows(path, text)
        if not rows:
            raise ValueError(f"{path} has no section instructions")
        return rows

    @staticmethod
    def _instruction_rows(path, text):
        rows = []
        for line, content in enumerate(text.splitlines(), start=1):
            if not content.strip():
                continue
            match = INSTRUCTION.fullmatch(content)
            pins = match.group("pins").split() if match else []
            if len(pins) != 2:
                raise ValueError(f'{path}, line {line}: expected "board = <name> Sphere_positions = <VCC pin> '
                                 f'<GND pin>", got "{content.strip()}"')
            rows.append((line, {"board": match.group("board"), "vcc_pin": pins[0], "gnd_pin": pins[1]}))
        return rows

    @classmethod
    def _csv_rows(cls, path, text):
        reader = csv.DictReader(text.splitlines())
        if reader.fieldnames is None:
            return []
        missing = [column for column in cls.REQUIRED if column not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path} has no {missing} column(s); it needs {list(cls.REQUIRED)}")
        return list(enumerate(reader, start=2))  # line 1 is the header

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
