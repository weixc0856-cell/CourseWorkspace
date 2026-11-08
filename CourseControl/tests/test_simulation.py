from __future__ import annotations

import unittest

from pydantic import ValidationError

from course_control.simulation import (
    HexGrid,
    RPSRules,
    SimulationSpec,
    Species,
    run_simulation,
)

SPECIES = [
    Species(id="rock", name="Rock", hex="#C75B55"),
    Species(id="paper", name="Paper", hex="#E3C84A"),
    Species(id="scissors", name="Scissors", hex="#4A82B8"),
]
MATRIX = [[0.5, 0.0, 1.0], [1.0, 0.5, 0.0], [0.0, 1.0, 0.5]]


def spec(**overrides) -> SimulationSpec:
    payload = dict(
        simulation_id="test-rps",
        title="test",
        seed=3,
        grid=HexGrid(radius=2),
        species=SPECIES,
        rules=RPSRules(matrix=MATRIX, mutation=0.001, updates_per_frame=4),
        frames=12,
        fps=30,
    )
    payload.update(overrides)
    return SimulationSpec(**payload)


class SimulationContractTest(unittest.TestCase):
    def test_grid_cell_count(self):
        data = run_simulation(spec())
        self.assertEqual(len(data.cells), 19)
        self.assertEqual(len(data.frames_species), 12)
        self.assertEqual(len(data.fractions), 12)

    def test_same_seed_is_deterministic(self):
        first = run_simulation(spec())
        second = run_simulation(spec())
        self.assertEqual(first.frames_species, second.frames_species)
        self.assertEqual(first.fractions, second.fractions)

    def test_different_seed_changes_run(self):
        first = run_simulation(spec(seed=1))
        second = run_simulation(spec(seed=2))
        self.assertNotEqual(first.frames_species, second.frames_species)

    def test_fractions_sum_to_one(self):
        data = run_simulation(spec())
        for frame in data.fractions:
            self.assertAlmostEqual(sum(frame), 1.0, places=5)

    def test_invalid_matrix_is_rejected(self):
        with self.assertRaises(ValidationError):
            spec(rules=RPSRules(matrix=[[1.0, 0.0], [0.0, 1.0]]))

    def test_duplicate_species_is_rejected(self):
        with self.assertRaises(ValidationError):
            spec(species=[SPECIES[0], SPECIES[0], SPECIES[2]])


if __name__ == "__main__":
    unittest.main()
