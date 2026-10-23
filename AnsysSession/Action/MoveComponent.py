from Chips.Components import Component
from Chips.Positions import Position

from ..ModelEditor import AedtError
from .Action import AnsysAction


class MoveComponent(AnsysAction):
    """Move ``component`` so its center lands on ``to_position`` (z=None keeps its height)."""

    def __init__(self, app, component: Component, to_position: Position):
        super().__init__(app, "Move Component")
        self.component = component
        self.to_position = to_position

    def act(self) -> int:
        """Move a component within the current design app"""
        center = self.component.center
        target = self.to_position.coordinates(z=center[2])
        vector = [t - c for t, c in zip(target, center)]
        try:
            self.editor.move(self.component.name, vector)
        except AedtError as e:
            self.error = f"{e} (target {self.to_position})"
            return self.FAILURE
        return self.SUCCESS
