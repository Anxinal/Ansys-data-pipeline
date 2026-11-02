from Chips import Chip
from Chips.Positions import TerminalPositionPair

from .Action import AnsysProcedure
from .MoveComponent import MoveComponent


class MoveCurrentConnectors(AnsysProcedure):
    """Move the terminals, then the spheres onto the same positions, as one procedure."""

    def __init__(self, session, pair: TerminalPositionPair, chip: Chip):
        super().__init__([MoveTerminals(session, pair, chip), MoveSpheres(session, pair, chip)], session, "Move_Current_Connectors")


class MoveTerminals(AnsysProcedure):
    """Move the chip's VCC object onto pair.a and its GND object onto pair.b."""

    def __init__(self, session, pair: TerminalPositionPair, chip: Chip):
        vcc, gnd = chip.get_terminals()
        moves = [MoveComponent(session, vcc, pair.a), MoveComponent(session, gnd, pair.b)]
        super().__init__(moves, session, "MoveTerminals")


class MoveSpheres(AnsysProcedure):
    """Move the sphere nearest VCC onto pair.a and the other onto pair.b, each keeping its height."""

    def __init__(self, session, pair: TerminalPositionPair, chip: Chip):
        near_vcc, near_gnd = chip.get_spheres()
        moves = [MoveComponent(session, near_vcc, pair.a), MoveComponent(session, near_gnd, pair.b)]
        super().__init__(moves, session, "MoveSpheres")
