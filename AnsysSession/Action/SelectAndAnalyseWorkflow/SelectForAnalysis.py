from typing import TYPE_CHECKING

from Chips.Components import Component
from configs import DEFAULT_GND, DEFAULT_VCC, DEFAULT_SPEHRE

from ..Action import AnsysAction

if TYPE_CHECKING:  # only for the annotation: importing Session at run time would load pyaedt
    from ...Session import Session


class BoardSelect(AnsysAction):
    """Make ``components`` (Components) active; ``names`` holds their names."""

    def __init__(self, session: "Session", components, label="Board_Select"):
        super().__init__(session, label)
        self.set_components(components)

    def set_components(self, components):
        wrong = [c for c in components if not isinstance(c, Component)]
        if wrong:
            raise TypeError(f"{type(self).__name__} needs Components, got {wrong}")
        self.names = [c.name for c in components]

    def act(self):
        for name in self.names:
            self.session.select_for_analysis(name)
        return self.SUCCESS


class DeselectAll(AnsysAction):
    """Disable objects except ``preserve``, recording their original state in ``state_file``."""

    def __init__(self, session, selected, state_file, preserve=()):
        super().__init__(session, "Deselect_All")
        self.selected = selected
        self.state_file = state_file
        self.preserve = preserve

    def act(self):
        self.result = self.session.deselect_all_for_analysis(self.selected, self.state_file, self.preserve)
        return self.SUCCESS

class SelectNecessaryComponents(AnsysAction):
    """Select GND VCC and the spheres once and for all """
    def __init__(self, session, label="Select_first"):
        super().__init__(session, label)

    def act(self):
        names = [DEFAULT_GND, DEFAULT_VCC] + DEFAULT_SPEHRE
        for name in names:
            self.session.select_for_analysis(name)
        return self.SUCCESS


class BoardUpdate(AnsysAction):
    """Deselect one board and then select another board, with the critical components unchanged"""
    def __init__(self, session, component_deact: Component, component_act: Component, label="Board_Update"):
        super().__init__(session, label)
        self.deactive = component_deact
        self.active = component_act

    def act(self):
        self.session.deselect_for_analysis(self.deactive.name)
        self.session.select_for_analysis(self.active.name)
        return self.SUCCESS

