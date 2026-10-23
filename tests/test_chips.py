"""Tests of the chip layer on plain data; no AEDT needed.

Run from the project root:  .venv/bin/python -m unittest discover tests
"""

import sys
import unittest

from Chips import (Board, Chip, ChipSection, CopyRecord, DesignSnapshot, NumericalPositionFixed, Position, PositionSampler, Terminal,
                   TerminalPositionPair)
from Chips.Components import Boundary, Component, SolidComponent


def solid(name, box, faces=6, material="copper", boundaries=()):
    return Component.create(name, "Solid", bounding_box=box, face_ids=list(range(faces)),
                            material_name=material, boundaries=boundaries)


def chip_components(gnd_excitation=None, second_board=False):
    pad_boundaries = (gnd_excitation,) if gnd_excitation else ()
    extra = [solid("Board2", [20, 0, 0, 30, 10, 1], material="fr4_epoxy")] if second_board else []
    return extra + [
        solid("ChipBoard", [0, 0, 0, 10, 10, 1], material="fr4_epoxy"),
        solid("VCC", [0, 4, 1, 1, 5, 1.2]),
        solid("GND" if gnd_excitation is None else "Pad", [9, 4, 1, 10, 5, 1.2], boundaries=pad_boundaries),
        solid("Sphere1", [2.8, 4.3, 1.2, 3.2, 4.7, 1.6], faces=1),
        solid("Sphere2", [6.8, 4.3, 1.2, 7.2, 4.7, 1.6], faces=1),
        solid("Die", [2.5, 4, 1.6, 7.5, 5, 2.0]),
        solid("Region", [-5, -5, -5, 15, 15, 6], material="vacuum"),
    ]


class ComponentTests(unittest.TestCase):
    def test_create_picks_subtype(self):
        self.assertIsInstance(solid("A", [0, 0, 0, 1, 1, 1]), SolidComponent)
        self.assertIs(type(Component.create("B", "Unclassified")), Component)

    def test_geometry_and_position(self):
        c = solid("A", [0, 0, 0, 0.6, 0.3, 0.2])
        self.assertEqual(c.center, [0.3, 0.15, 0.1])
        self.assertIsInstance(c.position, Position)
        self.assertEqual((c.position.i, c.position.j), (10, 5))
        self.assertEqual(c.position_on(step=0.1, origin=(0.1, 0)).i, 2)

    def test_sphere_shape(self):
        self.assertTrue(solid("S", [0, 0, 0, 1, 1, 1], faces=1).looks_like_sphere())
        self.assertFalse(solid("Box", [0, 0, 0, 1, 1, 1], faces=6).looks_like_sphere())
        self.assertFalse(solid("Ellipsoid", [0, 0, 0, 1, 2, 1], faces=1).looks_like_sphere())


class ChipTests(unittest.TestCase):
    def test_finds_parts(self):
        chip = ChipSection(chip_components(), units="mm")
        self.assertEqual(chip.board.name, "ChipBoard")
        self.assertEqual(sorted(s.name for s in chip.spheres), ["Sphere1", "Sphere2"])
        self.assertEqual([t.name for t in chip.get_terminals()], ["VCC", "GND"])
        self.assertIsInstance(chip.vcc, Terminal)
        self.assertIsInstance(chip.vcc, Component)

    def test_spheres_paired_by_distance_to_vcc(self):
        near_vcc, near_gnd = Chip(chip_components()).get_spheres()
        self.assertEqual((near_vcc.name, near_gnd.name), ("Sphere1", "Sphere2"))

    def test_terminal_by_excitation(self):
        excitation = Boundary("GND_in", "Current", faces=(0,), center=(10.0, 4.5, 1.1))
        chip = Chip(chip_components(gnd_excitation=excitation), gnd="gnd_in")
        self.assertEqual(chip.gnd.name, "Pad")
        self.assertEqual(chip.gnd.boundary.name, "GND_in")
        self.assertEqual(chip.gnd.point, [10.0, 4.5, 1.1])

    def test_sphere_connections_ignore_background(self):
        chip = Chip(chip_components())
        sphere = next(s for s in chip.spheres if s.name == "Sphere1")
        self.assertEqual(chip.sphere_connections(sphere), ["Die"])

    def test_unknown_names(self):
        with self.assertRaises(LookupError):
            Chip(chip_components(), gnd="nope")
        with self.assertRaises(LookupError):
            Chip(chip_components(), boards=["nope"])
        with self.assertRaises(LookupError):
            ChipSection(chip_components(), board="nope")

    def test_several_boards_and_sections(self):
        excitation = Boundary("GND_in", "Current", faces=(0,), center=(10.0, 4.5, 1.1))
        chip = Chip(chip_components(gnd_excitation=excitation, second_board=True), gnd="gnd_in")
        self.assertEqual([b.name for b in chip.boards], ["Board2", "ChipBoard"])
        self.assertTrue(all(isinstance(b, Board) for b in chip.boards))
        with self.assertRaises(LookupError):
            ChipSection(chip_components(second_board=True))
        section = chip.section(chip.boards[0])
        self.assertIsInstance(section, ChipSection)
        self.assertEqual(section.board.name, "Board2")
        self.assertEqual(chip.section("chipboard").board.name, "ChipBoard")
        self.assertEqual(section.gnd.boundary.name, "GND_in")  # same terminal lookup as the chip
        self.assertEqual(sorted(s.name for s in section.spheres), ["Sphere1", "Sphere2"])
        with self.assertRaises(LookupError):
            chip.section("Die")

    def test_extraction_positions_put_spheres_on_terminals(self):
        chip = ChipSection(chip_components())
        PositionSampler.reset()
        positions = chip.extraction_positions(step=0.5, sampler=PositionSampler())
        self.assertEqual(set(positions), {"VCC", "GND", "Sphere1", "Sphere2"})
        self.assertEqual(positions["Sphere1"], positions["VCC"])
        self.assertEqual(positions["Sphere2"], positions["GND"])
        self.assertTrue(all(p.z is None for p in positions.values()))


class PositionTests(unittest.TestCase):
    def test_from_string(self):
        p = NumericalPositionFixed.from_string("B3", z=1.0)
        self.assertEqual((p.i, p.j), (2, 1))
        with self.assertRaises(ValueError):
            NumericalPositionFixed.from_string("A0", z=1.0)

    def test_numerical_position_keeps_its_height(self):
        p = NumericalPositionFixed.from_number(23, z=1.5)
        self.assertEqual((p.i, p.j, p.num), (3, 1, 23))
        q = p.with_number(5)
        self.assertEqual((q.i, q.j, q.z), (5, 0, 1.5))
        self.assertIsInstance(q, NumericalPositionFixed)
        with self.assertRaises(ValueError):
            NumericalPositionFixed(0, 0)
        with self.assertRaises(ValueError):
            NumericalPositionFixed.from_number(-1, z=1.5)

    def test_place_at_sets_value_without_moving(self):
        chip = ChipSection(chip_components())
        self.assertIsInstance(chip.board, Board)
        box = list(chip.vcc.bounding_box)
        position = NumericalPositionFixed.from_string("B3", z=1.2)
        for part in (chip.vcc, chip.gnd, chip.board):
            self.assertIsNone(part.position_value)
            part.place_at(position)
            self.assertEqual(part.position_value, position.value)
        self.assertEqual(chip.vcc.bounding_box, box)
        self.assertFalse(hasattr(chip.spheres[0], "place_at"))
        with self.assertRaises(TypeError):
            chip.board.place_at(Position(0, 0, z=1.2))

    def test_sampler_is_a_seeded_singleton(self):
        PositionSampler.reset()
        cells = [Position(i, 0) for i in range(5)]
        first = PositionSampler().sample_pair_batch(cells, 3)
        self.assertIs(PositionSampler(), PositionSampler())
        PositionSampler.reset()
        self.assertEqual(PositionSampler().sample_pair_batch(cells, 3), first)
        self.assertIsInstance(first[0], TerminalPositionPair)


class SnapshotAndRecordTests(unittest.TestCase):
    def test_snapshot_lookups(self):
        snapshot = DesignSnapshot("D1", "mm", tuple(chip_components()), groups={"BOARD_1": ("BOARD_1_VCC",)})
        self.assertEqual(snapshot.get_component("chipboard").name, "ChipBoard")
        self.assertEqual(snapshot.group("board_1"), "BOARD_1")
        self.assertEqual(snapshot.members("board_1"), ["BOARD_1_VCC"])
        self.assertEqual(snapshot.members("nope"), [])

    def test_copy_record_round_trip(self):
        record = CopyRecord("BOARD_1", "D1", roles={"sphere_vcc": "a", "sphere_gnd": "b"}, copies={"S1": "a"})
        self.assertEqual(CopyRecord.from_dict(record.to_dict()), record)
        self.assertEqual(record.spheres, ["a", "b"])

    def test_chip_layer_does_not_load_pyaedt(self):
        self.assertFalse(any(name.startswith("ansys") for name in sys.modules))


if __name__ == "__main__":
    unittest.main()
