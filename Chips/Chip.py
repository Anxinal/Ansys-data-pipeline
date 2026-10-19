"""The chip model, built from a group of components (e.g. Session.components).

The chip is described by:
    GND, VCC    the two terminals and their coordinate positions
    spheres     the two spheres connecting the conductors to the chip
    board       the chip board

Each part is found automatically (see Chip.__init__), or by name when the
defaults don't match the project.
"""

from .Components.utils import find_component, format_info, safe
from .Terminal import Terminal

# Materials that fill the air box around the model, never a chip part.
BACKGROUND_MATERIALS = {"vacuum", "air"}


def _boxes_touch(a, b, tolerance=1e-9):
    """True when two bounding boxes [xmin, ymin, zmin, xmax, ymax, zmax] overlap or touch."""
    return all(a[i] <= b[i + 3] + tolerance and b[i] <= a[i + 3] + tolerance for i in range(3))


class Chip:
    """GND/VCC positions, the two connection spheres and the board, from a group of components."""

    def __init__(self, components, gnd="GND", vcc="VCC", spheres=None, board=None):
        """Find the chip parts in ``components`` (e.g. ``Session.components``).

        gnd, vcc   names of the GND and VCC components or excitations (case-insensitive).
        spheres    names of the two spheres; by default, the components created with
                   "Create Sphere".
        board      name of the board; by default, the component whose name contains
                   "board" or "pcb".
        """
        self.components = list(components)
        if not self.components:
            raise ValueError("Chip needs at least one component")
        self.units = self.components[0].app.modeler.model_units
        self.gnd = Terminal(self.components, "GND", gnd)
        self.vcc = Terminal(self.components, "VCC", vcc)
        self.spheres = self._find_spheres(spheres)
        self.board = self._find_board(board)

    def _find_spheres(self, names):
        if names:
            spheres = [find_component(self.components, name, "sphere") for name in names]
        else:
            spheres = [c for c in self.components if safe(lambda: c.command) == "CreateSphere"]
        if len(spheres) != 2:
            raise LookupError(
                f"Expected 2 connection spheres, found {len(spheres)}: {[s.name for s in spheres]}. "
                "Pass spheres=[name1, name2] to pick them."
            )
        return spheres

    def _find_board(self, name):
        if name:
            return find_component(self.components, name, "board")
        candidates = [c for c in self.components if "board" in c.name.lower() or "pcb" in c.name.lower()]
        if len(candidates) != 1:
            raise LookupError(
                f"Expected one component named like a board, found {[c.name for c in candidates]}. "
                f"Pass board=name to pick it from {[c.name for c in self.components]}."
            )
        return candidates[0]

    def sphere_connections(self, sphere):
        """Names of the chip-model components the sphere touches (its conductor and the chip).

        Compares bounding boxes, which enclose the sphere, so a component that
        only comes close to the sphere can also be listed.
        """
        box = sphere.obj.bounding_box
        return [
            c.name
            for c in self.components
            if c is not sphere
            and c.obj.is_model
            and str(c.obj.material_name).lower() not in BACKGROUND_MATERIALS
            and _boxes_touch(box, c.obj.bounding_box)
        ]

    def info(self):
        board = self.board
        return {
            "units": self.units,
            "GND": self.gnd.info(),
            "VCC": self.vcc.info(),
            "spheres": {
                sphere.name: {
                    "center": sphere.center,
                    "radius": safe(lambda: max(sphere.obj.bounding_dimension) / 2),
                    "material": sphere.obj.material_name,
                    "connects": safe(lambda: self.sphere_connections(sphere)),
                }
                for sphere in self.spheres
            },
            "board": {
                "name": board.name,
                "material": board.obj.material_name,
                "center": board.center,
                "bounding box": board.obj.bounding_box,
                "dimensions (x, y, z)": board.obj.bounding_dimension,
            },
        }

    def __str__(self):
        """Each chip part with its chip-level fields, then its component's full information."""
        info = self.info()
        parts = [f"Chip  (units: {self.units})", str(self.gnd), str(self.vcc)]
        for sphere in self.spheres:
            details = {**info["spheres"][sphere.name], "component": sphere.info()}
            parts.append(f'Sphere "{sphere.name}"\n{format_info(details)}')
        details = {**info["board"], "component": self.board.info()}
        parts.append(f'Board "{self.board.name}"\n{format_info(details)}')
        return "\n\n".join(parts)

    def print(self):
        print(f"\n=== chip {'=' * 66}")
        print(self)
