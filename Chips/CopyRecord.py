from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class CopyRecord:
    """Which objects of an extracted copy play which role, so the copy can be found again.

    group          the copy's model-tree group, e.g. BOARD_1
    source_design  the design the copy was made in
    roles          role -> copy name: "board", "vcc", "gnd", "sphere_vcc", "sphere_gnd"
    copies         original name -> copy name, for every copied object
    """

    group: str
    source_design: str
    roles: dict = field(default_factory=dict)
    copies: dict = field(default_factory=dict)

    @property
    def spheres(self):
        return [self.roles["sphere_vcc"], self.roles["sphere_gnd"]]

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)
