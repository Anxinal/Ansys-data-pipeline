from Chips import ChipSection, TerminalPositionPair

from ..ModelEditor import AedtError
from .Action import AnsysAction


class SetTerminalPositions(AnsysAction):
    """Set VCC's position value from pair.a and GND's from pair.b; in AEDT that shifts them and their spheres.

    ``pair`` holds NumericalPositionFixed positions. The values go through
    ModelEditor.set_position_value; the board's value is left unset.
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
                editor.set_position_value(terminal.name, terminal.position_value)
            except AedtError as e:
                self.error = f"{e} ({terminal.label} at {position})"
                return self.FAILURE
        return self.SUCCESS
