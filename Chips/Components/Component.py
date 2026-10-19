from .Material import Material
from .utils import print_info, safe


class Component:
    """One object of the design's 3D modeler, read and edited through the AEDT API.

    Use Component.from_object() or Component.all() rather than the constructor:
    they return the subclass matching the object's type (SolidComponent,
    SheetComponent, LineComponent), falling back to Component itself.
    """

    object_type = None  # AEDT object type a subclass handles: "Solid", "Sheet", "Line"
    _subtypes = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.object_type:
            Component._subtypes[cls.object_type] = cls

    def __init__(self, app, obj):
        self.app = app
        self.obj = obj  # the PyAEDT Object3d

    @classmethod
    def from_object(cls, app, obj):
        return cls._subtypes.get(obj.object_type, Component)(app, obj)

    @classmethod
    def all(cls, app):
        modeler = app.modeler
        return [cls.from_object(app, modeler.get_object_from_name(name)) for name in modeler.object_names]

    @property
    def name(self):
        return self.obj.name

    @property
    def center(self):
        """Center of the bounding box, in model units."""
        box = self.obj.bounding_box
        return [(box[i] + box[i + 3]) / 2 for i in range(3)]

    @property
    def command(self):
        """The AEDT command that created the object, e.g. "CreateSphere" or "CreateBox"."""
        history = self.obj.history()
        return history.command if history else ""

    @property
    def material(self):
        """The object's Material, or None for objects without one (e.g. non-model sheets)."""
        return Material.from_name(self.app, self.obj.material_name)

    def info(self):
        """Information every object type has; subclasses extend it."""
        obj = self.obj
        return {
            "type": obj.object_type,
            "id": obj.id,
            "material": obj.material_name,
            "solve inside": obj.solve_inside,
            "model": obj.is_model,
            "group": safe(lambda: obj.group_name),
            "coordinate system": safe(lambda: obj.part_coordinate_system),
            "bounding box": safe(lambda: obj.bounding_box),
            "dimensions (x, y, z)": safe(lambda: obj.bounding_dimension),
            "faces / edges / vertices": f"{len(obj.faces)} / {len(obj.edges)} / {len(obj.vertices)}",
            "boundaries": safe(self.boundaries),
        }

    def boundaries(self):
        """Names of the boundaries and excitations assigned to this object or its faces."""
        face_ids = {face.id for face in self.obj.faces}
        return [
            b.name
            for b in self.app.boundaries
            if self.name in b.props.get("Objects", []) or face_ids & set(b.props.get("Faces", []))
        ]

    def print(self, info=None, indent=2):
        info = self.info() if info is None else info
        print(f"{' ' * indent}-- {self.obj.object_type} \"{self.name}\"")
        print_info(info, indent + 2)

    def edit(self, **changes):
        """Set editable object properties (material_name, solve_inside, name, color, ...).

        Returns the edited values as read back from the session.
        """
        for key, value in changes.items():
            prop = getattr(type(self.obj), key, None)
            if not (isinstance(prop, property) and prop.fset):
                raise KeyError(f"{key!r} is not an editable property of {self.obj.object_type} objects")
            setattr(self.obj, key, value)
        return {key: getattr(self.obj, key) for key in changes}
