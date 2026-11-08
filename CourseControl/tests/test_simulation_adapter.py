from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.adapters.code_video import materialize_simulation
from course_control.simulation import HexGrid, RPSRules, SimulationSpec, Species

SPECIES = [
    Species(id="rock", name="Rock", hex="#C75B55"),
    Species(id="paper", name="Paper", hex="#E3C84A"),
    Species(id="scissors", name="Scissors", hex="#4A82B8"),
]


def spec() -> SimulationSpec:
    return SimulationSpec(
        simulation_id="adapter-test",
        title="adapter",
        seed=5,
        grid=HexGrid(radius=2),
        species=SPECIES,
        rules=RPSRules(matrix=[[0.5, 0, 1], [1, 0.5, 0], [0, 1, 0.5]], mutation=0.001, updates_per_frame=2),
        frames=8,
        fps=30,
    )


class SimulationAdapterTest(unittest.TestCase):
    def test_materializes_data_into_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "spec").mkdir()
            (workspace / "project").mkdir()
            (workspace / "spec" / "sim.json").write_text(spec().model_dump_json(), encoding="utf-8")
            target = materialize_simulation(
                workspace,
                workspace / "project",
                {"simulation_spec": "spec/sim.json", "simulation_out": "simulation.json"},
            )
            self.assertIsNotNone(target)
            data = json.loads(Path(target).read_text(encoding="utf-8"))
            self.assertEqual(len(data["frames_species"]), 8)
            self.assertEqual(len(data["cells"]), 19)

    def test_no_inputs_is_a_noop(self):
        self.assertIsNone(materialize_simulation(Path("."), Path("."), None))

    def test_outside_workspace_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "inside"
            workspace.mkdir()
            with self.assertRaises(ValueError):
                materialize_simulation(workspace, workspace, {"simulation_spec": "../outside.json"})


if __name__ == "__main__":
    unittest.main()
