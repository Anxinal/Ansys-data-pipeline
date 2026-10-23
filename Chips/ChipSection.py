from dataclasses import replace

from configs import DEFAULT_GND, DEFAULT_GRID_STEP, DEFAULT_VCC

from .Chip import Chip
from .Positions import Position, PositionSampler


class ChipSection(Chip):
    """A chip with exactly one board: the section that is copied and analysed.

    Made by Chip.section(board) from a main chip with several boards, or directly
    (e.g. for a copy's analysis design, where only one board remains).
    """

    def __init__(self, components, gnd=DEFAULT_GND, vcc=DEFAULT_VCC, spheres=None, board=None, units=""):
        """As Chip, with ``board`` the name of the one board; by default, the only component named like a board."""
        super().__init__(components, gnd, vcc, spheres, [board] if board else None, units)
        if len(self.boards) != 1:
            raise LookupError(
                f"Expected one component named like a board, found {[b.name for b in self.boards]}. "
                f"Pass board=name to pick one."
            )

    @property
    def board(self):
        return self.boards[0]

    def feasible_positions(self, step=DEFAULT_GRID_STEP, origin=None):
        """PLACEHOLDER: the grid Positions GND/VCC may be moved to.

        Replace this with the real feasible positions. For now they are the
        current GND and VCC cells. ``origin`` defaults to the board's minimum
        corner, so the cells line up with the Bz image pixels.
        """
        origin = Position.board_origin(self.board) if origin is None else origin
        # z=None: whatever moves onto these cells keeps its own height.
        return [replace(t.position_on(step, origin), z=None) for t in (self.vcc, self.gnd)]

    def terminal_positions(self, step=DEFAULT_GRID_STEP, origin=None, sampler=None):
        """Where the VCC and GND copies go, as {"VCC": Position, "GND": Position}.

        A pair sampled from feasible_positions() by ``sampler`` (default: the
        run-wide PositionSampler).
        """
        sampler = PositionSampler() if sampler is None else sampler
        return sampler.sample_pair(self.feasible_positions(step, origin)).as_dict()

    def extraction_positions(self, step=DEFAULT_GRID_STEP, origin=None, sampler=None):
        """{component name: Position} for ExtractCopy.

        VCC and GND get terminal_positions(); the two spheres sit at those same XY
        positions (the sphere nearest VCC goes to VCC's), each keeping its own
        height. The board gets no position: it is never moved.
        """
        targets = self.terminal_positions(step, origin, sampler)
        positions = {}
        for terminal in (self.vcc, self.gnd):
            positions[terminal.name] = targets[terminal.label]
        near_vcc, near_gnd = self.get_spheres()
        positions[near_vcc.name] = targets["VCC"]
        positions[near_gnd.name] = targets["GND"]
        return positions
