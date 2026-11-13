"""Convert pin pools to numerical positions and delegate sampling in batches."""
from ..Positions import NumericalPositionFixed, Position, TerminalPositionPair
from .SectionCandidate import SectionCandidate


def numerical_position(text, origin, z):
    if not text:
        raise ValueError("missing candidate pin")
    if text.isdigit():
        return NumericalPositionFixed.from_number(int(text), origin=origin, z=z)
    return NumericalPositionFixed.from_string(text, origin=origin, z=z)


def sample_candidates(chip, row, sampler, count=-1):
    def cell(key):
        return (row.get(key) or "").strip() or None

    spheres = [cell("sphere_vcc"), cell("sphere_gnd")]
    if any(spheres) and not all(spheres):
        raise ValueError("give both sphere_vcc and sphere_gnd, or neither")
    section = chip.section(cell("board") or "", gnd=cell("gnd"), vcc=cell("vcc"),
                           spheres=spheres if all(spheres) else None)
    origin = Position.board_origin(section.board)
    pins = cell("sphere_positions")
    pins = pins.split() if pins else [cell("vcc_pin"), cell("gnd_pin")]
    positions = {p.value:p for p in (numerical_position(pin, origin, section.vcc.center[2]) for pin in pins)}
    pairs = sampler.sample_pair_batch(list(positions.values()), count)
    candidates = []
    for pair in pairs:
        gnd = NumericalPositionFixed.from_number(pair.b.value, step=pair.b.step,
                                                origin=pair.b.origin, z=section.gnd.center[2])
        candidates.append(SectionCandidate(section, TerminalPositionPair(pair.a, gnd)))
    return candidates
