"""Copy the chip's parts into a new model (a group) in the same design.

Each extraction makes one copy of the board, the two spheres and the GND/VCC
objects, in its own model-tree group numbered from the prefix (BOARD_1,
BOARD_2, ...). Copies are named "<group>_<original>", e.g. BOARD_1_Sphere1.
The board copy keeps the board's position; only the spheres and GND/VCC are
moved, to the grid Positions given for them. Excitations on the moved parts
are duplicated with them. The originals are not changed. A CopyRecord of which
copy plays which role is saved with the project (CopyStore).
"""

from Chips import ChipSection, CopyRecord, DesignSnapshot
from Chips.Components.utils import find_component
from configs import DEFAULT_PREFIX

from ..CopyStore import CopyStore
from .Action import AnsysAction


def _unique_name(name, taken):
    candidate, n = name, 1
    while candidate.lower() in taken:
        candidate, n = f"{name}_{n}", n + 1
    return candidate


def copy_groups(snapshot: DesignSnapshot, prefix=DEFAULT_PREFIX):
    """Names of the model-tree groups that hold extracted copies."""
    return [group for group in snapshot.groups if group.lower().startswith(prefix.lower())]


def original_components(snapshot: DesignSnapshot, prefix=DEFAULT_PREFIX):
    """The snapshot's components that are not part of an extracted copy."""
    copied = {name.lower() for group in copy_groups(snapshot, prefix) for name in snapshot.members(group)}
    return [c for c in snapshot.components if c.name.lower() not in copied]


def next_group_name(snapshot: DesignSnapshot, prefix=DEFAULT_PREFIX):
    taken = {group.lower() for group in snapshot.groups}
    n = 1
    while f"{prefix}{n}".lower() in taken:
        n += 1
    return f"{prefix}{n}"


class ExtractCopy(AnsysAction):
    """Copy ``chip``'s board, spheres and GND/VCC into a new group; ``result`` is its CopyRecord.

    chip        the ChipSection to copy (one board), e.g. Chip.section(board)
    snapshot    the DesignSnapshot ``chip`` was built from
    positions   {component name: Position} for the spheres and GND/VCC, e.g.
                chip.extraction_positions(). A part without a position is copied in
                place. Positions for any other part (e.g. the board) are rejected.
    names       components to copy; default: board, two spheres, GND and VCC
    group_name  name of the new group; default: the next free "<prefix><n>"
    """

    def __init__(self, app, snapshot: DesignSnapshot, chip: ChipSection, positions, names=None, group_name=None,
                 prefix=DEFAULT_PREFIX):
        super().__init__(app, "Extract_Copy")
        self.snapshot = snapshot
        self.chip = chip
        self.sources = ([find_component(snapshot.components, name, "extract") for name in names] if names
                        else [chip.board, *self.movable_parts()])
        self.group_name = group_name or next_group_name(snapshot, prefix)
        if snapshot.group(self.group_name):
            raise ValueError(f'Group "{self.group_name}" already exists; pick a new group name')

        self.targets = {name.lower(): position for name, position in positions.items()}
        unused = set(self.targets) - {source.name.lower() for source in self.sources}
        if unused:
            raise KeyError(f"Positions given for components that are not copied: {sorted(unused)}")
        fixed = [name for name in positions if name.lower() not in self._movable_names()]
        if fixed:
            raise ValueError(f"Only the spheres and GND/VCC can be moved; {sorted(fixed)} keep their position")
        self.result = None

    def movable_parts(self):
        """The parts that may move: the two spheres and the GND/VCC objects."""
        return [*self.chip.spheres, self.chip.gnd, self.chip.vcc]

    def _movable_names(self):
        return {part.name.lower() for part in self.movable_parts()}

    def act(self):
        editor = self.editor
        taken = {c.name.lower() for c in self.snapshot.components}
        copies = {}
        for source in self.sources:
            if source.name.lower() in self._movable_names():
                position = self.targets.get(source.name.lower())
                center = source.center
                vector = [0.0, 0.0, 0.0] if position is None else [
                    target - current for target, current in zip(position.coordinates(z=center[2]), center)]
                new_name = editor.duplicate(source.name, vector)
            else:
                new_name = editor.copy_in_place(source.name)
            new_name = editor.rename(new_name, _unique_name(f"{self.group_name}_{source.name}", taken))
            taken.add(new_name.lower())
            copies[source.name] = new_name

        group = editor.create_group(list(copies.values()), self.group_name)
        near_vcc, near_gnd = self.chip.get_spheres()
        roles = {"board": self.chip.board.name, "vcc": self.chip.vcc.name, "gnd": self.chip.gnd.name,
                 "sphere_vcc": near_vcc.name, "sphere_gnd": near_gnd.name}
        self.result = CopyRecord(group, self.snapshot.design,
                                 roles={role: copies[name] for role, name in roles.items() if name in copies},
                                 copies=copies)
        CopyStore(self.app).save(self.result)
        return self.SUCCESS
