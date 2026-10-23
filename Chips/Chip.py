"""The chip model, built from a group of components (e.g. a DesignSnapshot's).

The chip is described by:
    GND, VCC    the two terminals and their coordinate positions
    spheres     the two spheres connecting the conductors to the chip
    boards      the chip's boards (Boards); a ChipSection has exactly one

Each part is found automatically (see Chip.__init__), or by name when the
defaults don't match the project. Plain data: nothing here talks to AEDT.
"""

from configs import BACKGROUND_MATERIALS, BOARD_KEYWORDS, DEFAULT_GND, DEFAULT_VCC, SPHERE_KEYWORDS

from .Board import Board
from .Components.utils import boxes_touch, find_component, format_info
from .Terminal import Terminal


class Chip:
    """GND/VCC positions, the two connection spheres and the boards, from a group of components."""

    def __init__(self, components, gnd=DEFAULT_GND, vcc=DEFAULT_VCC, spheres=None, boards=None, units=""):
        """Find the chip parts in ``components`` (e.g. ``snapshot.components``).

        gnd, vcc   names of the GND and VCC components or excitations (case-insensitive).
        spheres    names of the two spheres; by default, the solids shaped like a
                   sphere (one face, equal x/y/z extents), else the components
                   whose names contain one of SPHERE_KEYWORDS (configs.py).
        boards     names of the boards; by default, every component whose name
                   contains one of BOARD_KEYWORDS (configs.py), e.g. "board" or "pcb".
        units      the design's model units, for printing (e.g. ``snapshot.units``)
        """
        self.components = list(components)
        if not self.components:
            raise ValueError("Chip needs at least one component")
        self.units = units
        self._info = None
        self._terminal_names = (gnd, vcc)  # as given, so section() finds the same terminals
        self.gnd = Terminal(self.components, "GND", gnd)
        self.vcc = Terminal(self.components, "VCC", vcc)
        self.spheres = self._find_spheres(spheres)
        self.boards = self._find_boards(boards)

    def _find_spheres(self, names):
        if names:
            spheres = [find_component(self.components, name, "sphere") for name in names]
            if len(spheres) != 2:
                raise LookupError(f"Expected 2 sphere names, got {names}")
            return spheres
        # Geometry only (bounding box and face IDs), never the object history.
        shaped = [c for c in self.components if c.looks_like_sphere()]
        if len(shaped) == 2:
            return shaped
        named = [c for c in self.components if any(k in c.name.lower() for k in SPHERE_KEYWORDS)]
        if len(named) == 2:
            return named
        raise LookupError(
            f"Expected 2 connection spheres; sphere-shaped solids: {[c.name for c in shaped]}, "
            f"named like a sphere: {[c.name for c in named]}. Pass spheres=[name1, name2] to pick them."
        )

    def _find_boards(self, names):
        if names:
            return [Board(find_component(self.components, name, "board")) for name in names]
        candidates = [c for c in self.components if any(k in c.name.lower() for k in BOARD_KEYWORDS)]
        if not candidates:
            raise LookupError(
                f"No component named like a board ({', '.join(BOARD_KEYWORDS)}). "
                f"Pass the board names to pick them from {[c.name for c in self.components]}."
            )
        return [Board(c) for c in candidates]

    def section(self, board):
        """The ChipSection of one of the chip's boards (a Board or its name), with the same terminals and spheres."""
        from .ChipSection import ChipSection  # ChipSection subclasses Chip

        name = board if isinstance(board, str) else board.name
        if name.lower() not in {b.name.lower() for b in self.boards}:
            raise LookupError(f'No board "{name}" in this chip. Boards: {[b.name for b in self.boards]}')
        gnd, vcc = self._terminal_names
        return ChipSection(self.components, gnd, vcc, spheres=[s.name for s in self.spheres], board=name,
                           units=self.units)

    def get_terminals(self):
        """(VCC terminal, GND terminal), both Components."""
        return self.vcc, self.gnd

    def get_spheres(self):
        """(sphere nearest VCC, the other sphere), by distance to the VCC position."""
        def distance_to_vcc(sphere):
            return sum((a - b) ** 2 for a, b in zip(sphere.center, self.vcc.point))

        # _find_spheres guarantees exactly two, so ordering them pairs them.
        near_vcc, near_gnd = sorted(self.spheres, key=distance_to_vcc)
        return near_vcc, near_gnd

    def sphere_connections(self, sphere):
        """Names of the chip-model components the sphere touches (its conductor and the chip).

        Compares bounding boxes, which enclose the sphere, so a component that
        only comes close to the sphere can also be listed.
        """
        box = sphere.bounding_box
        return [
            c.name
            for c in self.components
            if c is not sphere
            and boxes_touch(box, c.bounding_box)
            and c.is_model
            and c.material_name.lower() not in BACKGROUND_MATERIALS
        ]

    def info(self):
        """The chip-level fields of every part, computed once."""
        if self._info is None:
            self._info = self._read_info()
        return self._info

    def _read_info(self):
        return {
            "units": self.units,
            "GND": self.gnd.info(),
            "VCC": self.vcc.info(),
            "spheres": {
                sphere.name: {
                    "center": sphere.center,
                    "radius": max(sphere.dimensions) / 2,
                    "material": sphere.material_name,
                    "connects": self.sphere_connections(sphere),
                }
                for sphere in self.spheres
            },
            "boards": {
                board.name: {
                    "material": board.material_name,
                    "center": board.center,
                    "bounding box": board.bounding_box,
                    "dimensions (x, y, z)": board.dimensions,
                }
                for board in self.boards
            },
        }

    def describe(self, full=False):
        """Each chip part with its chip-level fields; with ``full``, also its component's information."""
        info = self.info()
        parts = [f"Chip  (units: {self.units})", self.gnd.describe(full), self.vcc.describe(full)]
        for sphere in self.spheres:
            details = info["spheres"][sphere.name]
            if full:
                details = {**details, "component": sphere.info()}
            parts.append(f'Sphere "{sphere.name}"\n{format_info(details)}')
        for board in self.boards:
            details = info["boards"][board.name]
            if full:
                details = {**details, "component": board.info()}
            parts.append(f'Board "{board.name}"\n{format_info(details)}')
        return "\n\n".join(parts)

    def __str__(self):
        return self.describe()

    def print(self, full=False):
        print(f"\n=== chip {'=' * 66}")
        print(self.describe(full))
