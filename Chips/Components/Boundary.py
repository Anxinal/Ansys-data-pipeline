from dataclasses import dataclass, field


@dataclass(frozen=True)
class Boundary:
    """A boundary or excitation of a design, as plain data (read by AnsysSession.DesignReader).

    faces     IDs of the faces it is assigned to
    objects   names of the objects it is assigned to as a whole
    center    average center of its faces in model units, None when it has no faces
    props     every AEDT property, for reports
    """

    name: str
    type: str
    faces: tuple = ()
    objects: tuple = ()
    center: tuple | None = None
    props: dict = field(default_factory=dict, compare=False, hash=False)
