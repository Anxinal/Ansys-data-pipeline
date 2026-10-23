from configs import DEFAULT_GRID_STEP

from ..Positions.Position import Position
from .utils import print_info


class Component:
    """One object of a design's 3D modeler, as plain data.

    Holds no AEDT handle: AnsysSession.DesignReader reads every object once into
    a DesignSnapshot. After the design changes, read a new snapshot
    (Session.refresh()); changes themselves go through AnsysSession.ModelEditor.

    Use Component.create() rather than the constructor: it returns the subclass
    matching the object's type (SolidComponent, SheetComponent, LineComponent),
    falling back to Component itself.
    """

    object_type = None  # AEDT object type a subclass handles: "Solid", "Sheet", "Line"
    _subtypes = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.object_type:
            Component._subtypes[cls.object_type] = cls

    def __init__(self, name, type="Unclassified", bounding_box=(0.0,) * 6, face_ids=(), material_name="",
                 is_model=True, boundaries=()):
        self.name = name
        self.type = type  # "Solid", "Sheet", "Line" or "Unclassified"
        self.bounding_box = list(bounding_box)  # [xmin, ymin, zmin, xmax, ymax, zmax] in model units
        self.face_ids = list(face_ids)
        self.material_name = material_name  # "" for objects without one
        self.is_model = is_model
        self.boundaries = tuple(boundaries)  # the Boundary objects assigned to it or its faces

    @classmethod
    def create(cls, name, type, **fields):
        return cls._subtypes.get(type, Component)(name, type, **fields)

    @property
    def dimensions(self):
        box = self.bounding_box
        return [box[i + 3] - box[i] for i in range(3)]

    @property
    def center(self):
        """Center of the bounding box, in model units."""
        box = self.bounding_box
        return [(box[i] + box[i + 3]) / 2 for i in range(3)]

    @property
    def point(self):
        """The exact (x, y, z) the component's position refers to: its bounding-box center."""
        return self.center

    def position_on(self, step=DEFAULT_GRID_STEP, origin=(0.0, 0.0)):
        """The component's Position on a grid with this step and origin, keeping its height."""
        x, y, z = self.point
        return Position.from_point(x, y, step, origin, z)

    @property
    def position(self):
        """The component's Position on the default grid (configs.DEFAULT_GRID_STEP, origin (0, 0))."""
        return self.position_on()

    def looks_like_sphere(self, tolerance=1e-6):
        """True for a solid with a single face and equal x, y and z extents."""
        if self.type != "Solid":
            return False
        dx, dy, dz = self.dimensions
        if max(dx, dy, dz) - min(dx, dy, dz) > tolerance * max(dx, dy, dz, 1e-30):
            return False
        return len(self.face_ids) == 1

    def boundary_names(self):
        return [boundary.name for boundary in self.boundaries]

    def info(self):
        """What the snapshot knows about the object; DesignReader.details() adds the rest."""
        return {
            "type": self.type,
            "material": self.material_name,
            "model": self.is_model,
            "position": str(self.position),
            "bounding box": self.bounding_box,
            "dimensions (x, y, z)": self.dimensions,
            "faces": len(self.face_ids),
            "boundaries": self.boundary_names(),
        }

    def print(self, info=None, indent=2):
        info = self.info() if info is None else info
        print(f"{' ' * indent}-- {self.type} \"{self.name}\"")
        print_info(info, indent + 2)
