import re
from dataclasses import dataclass

from configs import DEFAULT_GRID_STEP, MAX_COLUMN

from .Position import Position


@dataclass(frozen=True)
class NumericalPositionFixed(Position):
    """A grid Position at a fixed height: only the cell, i.e. x and y, varies.

    Made from a label such as "A15" (from_string) or a running cell number
    (from_number); z must always be given. Placing a terminal or the board on
    one records this position's ``value`` (its pin count) as the part's
    ``position_value`` (NumericallyPlaced.place_at); in AEDT, setting a
    terminal's pin-count variable moves it (see SetTerminalPositions).
    """

    def __post_init__(self):
        if self.z is None:
            raise ValueError(f"{type(self).__name__} needs a fixed height z, got None")

    @classmethod
    def from_string(cls, label, step=DEFAULT_GRID_STEP, origin=(0.0, 0.0), z=None):
        """The cell named by a label such as "A15": row A (the first), column 15.

        Rows are letters (A = 1st, B = 2nd, ..., AA = 27th); columns run from 1 to
        configs.MAX_COLUMN. Both count from 1, while i and j count from 0.
        """
        match = re.fullmatch(r"\s*([A-Za-z]+)\s*(\d+)\s*", label)
        if match is None:
            raise ValueError(f'Position label "{label}" is not a row letter followed by a column number, e.g. "A15"')
        letters, column = match.group(1).upper(), int(match.group(2))
        if not 1 <= column <= MAX_COLUMN:
            raise ValueError(f'Column {column} in "{label}" is outside 1..{MAX_COLUMN} (configs.MAX_COLUMN)')
        row = 0
        for letter in letters:
            row = row * 26 + ord(letter) - ord("A") + 1
        return cls(column - 1, row - 1, step, tuple(origin), z)

    @classmethod
    def from_number(cls, num, step=DEFAULT_GRID_STEP, origin=(0.0, 0.0), z=None):
        """The cell with running number ``num`` (see Position.num): row num // MAX_COLUMN, column num % MAX_COLUMN."""
        if not isinstance(num, int) or num < 0:
            raise ValueError(f"Cell number must be a non-negative integer, got {num!r}")
        j, i = divmod(num, MAX_COLUMN)
        return cls(i, j, step, tuple(origin), z)

    def with_number(self, num):
        """The cell with running number ``num`` on the same grid and at the same height."""
        return type(self).from_number(num, self.step, self.origin, self.z)

    @property
    def value(self):
        """The pin count of this cell: the ball index row by row from 0 (Position.num), as the
        design variables in configs.PIN_COUNT_VARIABLES take it."""
        return self.num
