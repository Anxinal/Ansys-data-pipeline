from dataclasses import dataclass

from configs import DEFAULT_GRID_STEP, MAX_COLUMN


@dataclass(frozen=True)
class Position:
    """A cell of a regular XY grid, e.g. a pixel of the Bz image, in model units.

    i, j     column (x) and row (y) index of the cell
    step     cell size (default: the Bz image pixel size)
    origin   (x, y) of cell (0, 0); for the Bz image that is the board's
             (xmin, ymin), see Position.board_origin()
    z        height of the position; None keeps the component's own height
    """

    i: int
    j: int
    step: float = DEFAULT_GRID_STEP
    origin: tuple = (0.0, 0.0)
    z: float | None = None

    @classmethod
    def from_point(cls, x, y, step=DEFAULT_GRID_STEP, origin=(0.0, 0.0), z=None):
        """The grid cell nearest to (x, y)."""
        return cls(round((x - origin[0]) / step), round((y - origin[1]) / step), step, tuple(origin), z)

    @classmethod
    def of_component(cls, component, step=DEFAULT_GRID_STEP, origin=(0.0, 0.0)):
        """The grid cell of a component's center, keeping its height."""
        x, y, z = component.center
        return cls.from_point(x, y, step, origin, z)

    @staticmethod
    def board_origin(board):
        """(x, y) of the Bz image's first pixel: the board's minimum corner."""
        xmin, ymin = board.bounding_box[:2]
        return (xmin, ymin)

    @property
    def num(self):
        """Running cell number on a grid configs.MAX_COLUMN wide, from 0: row * MAX_COLUMN + column."""
        return self.j * MAX_COLUMN + self.i

    @property
    def xy(self):
        return (self.origin[0] + self.i * self.step, self.origin[1] + self.j * self.step)

    def coordinates(self, z=None):
        """(x, y, z) of the cell; ``z`` is used when the position has no height of its own."""
        x, y = self.xy
        return (x, y, self.z if self.z is not None else z)

    def __str__(self):
        x, y = self.xy
        z = "" if self.z is None else f", z={self.z:.6g}"
        return f"cell ({self.i}, {self.j}) at x={x:.6g}, y={y:.6g}{z}"
