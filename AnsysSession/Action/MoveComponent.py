from Chips.Components import Component
from Chips.Positions import Position

from ..ModelEditor import AedtError
from .Action import AnsysAction


class MoveComponent(AnsysAction):
    """Move ``component`` so its center lands on ``to_position`` (z=None keeps its height)."""

    def __init__(self, session, component: Component, to_position: Position):
        super().__init__(session, "Move Component")
        self.component = component
        self.to_position = to_position

    def act(self) -> int:
        """Move a component within the active design"""
        try:
            self.session.move_to(self.component.name, self.to_position)
        except AedtError as e:
            self.error = f"{e} (target {self.to_position})"
            return self.FAILURE
        return self.SUCCESS
