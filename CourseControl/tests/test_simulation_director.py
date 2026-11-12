from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from course_control.direction import build
from course_control.direction.inputs import load_inputs
from course_control.direction.planners import plan_visual

WORKSPACE = Path(__file__).resolve().parents[2]
FIXTURE = WORKSPACE / "CourseControl" / "tests" / "fixtures" / "lesson-simulation"


class SimulationDirectorTest(unittest.TestCase):
    def test_director_plan_routes_simulation_to_code_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, _ = build(WORKSPACE, FIXTURE, Path(tmp))
        self.assertEqual(plan.status, "ready")
        self.assertEqual(len(plan.shots), 1)
        shot = plan.shots[0]
        self.assertEqual(shot.engine, "code_video")
        self.assertEqual(shot.layout_template, "process_flow")
        self.assertEqual(shot.scene, "shots/primer-rps/SPEC.md")
        self.assertEqual(
            shot.inputs["simulation_spec"],
            "BlenderStudio/scenes/primer-poc/simulation.spec.json",
        )
        self.assertEqual(shot.narration_ids, [])
        self.assertEqual(plan.narration, [])

    def test_inputs_are_inferred_from_shot_spec(self):
        inputs = load_inputs(WORKSPACE, FIXTURE)
        page = inputs.outline.pages[0]
        decision = plan_visual(inputs.paths, page, {})
        self.assertEqual(decision.engine, "code_video")
        self.assertEqual(
            decision.inputs["simulation_spec"],
            "BlenderStudio/scenes/primer-poc/simulation.spec.json",
        )


if __name__ == "__main__":
    unittest.main()
