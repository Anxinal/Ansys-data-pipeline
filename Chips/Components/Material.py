from dataclasses import dataclass, field

from .utils import print_info


@dataclass(frozen=True)
class Material:
    """A material of the project, as plain data (read by AnsysSession.DesignReader).

    conductor    True when AEDT counts it as a conductor (conductivity above its threshold)
    properties   every physical property AEDT defines, as "value unit" strings
    """

    name: str
    conductor: bool = False
    properties: dict = field(default_factory=dict, compare=False, hash=False)

    def info(self):
        return dict(self.properties)

    def print(self, info=None, indent=2):
        info = self.info() if info is None else info
        print(f"{' ' * indent}-- Material \"{self.name}\"")
        print_info(info, indent + 2)
