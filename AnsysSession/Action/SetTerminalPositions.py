from Chips import ChipSection, TerminalPositionPair
from configs import PIN_COUNT_VARIABLES

from ..ModelEditor import AedtError
from .Action import AnsysAction


class SetTerminalPositions(AnsysAction):
    """Put VCC on pair.a and GND on pair.b by setting their pin-count design variables.

    ``pair`` holds NumericalPositionFixed positions; each terminal's
    position_value becomes its pin count, which goes to the variable named in
    configs.PIN_COUNT_VARIABLES ("PinCount", "PinCountGND"). AEDT then moves
    each terminal together with its sphere (sphere_VCC, sphere_GND) through the
    design's expressions, so the spheres are not moved here. The board is not
    moved and its position value is left unset.
    """

    def __init__(self, app, section: ChipSection, pair: TerminalPositionPair):
        super().__init__(app, "Set_Terminal_Positions")
        self.section = section
        self.pair = pair

    def act(self):
        editor = self.editor
        for terminal, position in ((self.section.vcc, self.pair.a), (self.section.gnd, self.pair.b)):
            terminal.place_at(position)
            try:
                editor.set_pin_count(PIN_COUNT_VARIABLES[terminal.label], terminal.position_value)
            except AedtError as e:
                self.error = f"{e} ({terminal.label} at {position})"
                return self.FAILURE
        return self.SUCCESS
