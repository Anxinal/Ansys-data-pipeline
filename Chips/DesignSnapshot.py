from dataclasses import dataclass, field

from .Components.utils import find_component


@dataclass(frozen=True)
class DesignSnapshot:
    """Everything the chip layer knows about one design, read from AEDT at one moment.

    Made by AnsysSession.DesignReader.snapshot(). It never changes: after the
    design is edited, read a new one.
    """

    design: str
    units: str
    components: tuple = ()
    boundaries: tuple = ()
    groups: dict = field(default_factory=dict, compare=False, hash=False)  # group -> member names

    def get_component(self, name):
        """The component called ``name`` (case-insensitive), or a LookupError naming the options."""
        return find_component(self.components, name, f'design "{self.design}"')

    def group(self, name):
        """The group called ``name`` as spelled in AEDT (case-insensitive), or None."""
        return next((group for group in self.groups if group.lower() == name.lower()), None)

    def members(self, group):
        """Names of the objects in a group (case-insensitive group name); empty if there is none."""
        spelled = self.group(group)
        return list(self.groups[spelled]) if spelled else []
