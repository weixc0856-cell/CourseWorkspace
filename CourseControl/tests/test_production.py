from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml
from pydantic import ValidationError

from course_control.production import (
    ProductionPlan,
    load_production,
    normalize_source,
    shot_specs,
    synthetic_storyboard,
    timed_shots,
    validate_plan,
)

ROOT = Path(__file__).resolve().parents[2]

PLAN = {
    "schema_version": 1,
    "lesson": "demo",
    "sequences": [
        {
            "id": "seq-01",
            "title": "demo",
            "shots": [
                {
                    "id": "shot-001",
                    "duration_s": 3.0,
                    "purpose": "orient",
                    "visual_type": "kinetic_typography",
                    "grammar": "kinetic_edit",
                    "techniques": ["hard_cut"],
                    "renderer": "code_video",
                    "source": "CodeVideoStudio/shots/kinetic-cuts/SPEC.md",
                    "transition": {"in": "hard_cut", "out": "hard_cut"},
                },
                {
                    "id": "shot-002",
                    "duration_s": 6.0,
                    "purpose": "explain",
                    "visual_type": "geometric_transform",
                    "grammar": "long_take",
                    "renderer": "manim",
                    "source": "ManimSandbox/05-transformer-5min/attention_5min.py::Attention",
                    "camera": {"movement": "push_in", "motive": "follow the angle opening"},
                },
            ],
        }
    ],
}


class ProductionContractTest(unittest.TestCase):
    def test_load_and_timing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "production.yaml"
            path.write_text(yaml.safe_dump(PLAN, allow_unicode=True), encoding="utf-8")
            plan = load_production(path)
        self.assertEqual(plan.total_seconds, 9.0)
        rows = timed_shots(plan)
        self.assertEqual(rows[0][1:], (0.0, 3.0))
        self.assertEqual(rows[1][1:], (3.0, 9.0))
        self.assertEqual(plan.shots[0].transition.in_, "hard_cut")

    def test_duplicate_shot_ids_rejected(self) -> None:
        data = yaml.safe_load(yaml.safe_dump(PLAN))
        data["sequences"][0]["shots"][1]["id"] = "shot-001"
        with self.assertRaises(ValidationError):
            ProductionPlan.model_validate(data)

    def test_source_required_for_renderer(self) -> None:
        data = yaml.safe_load(yaml.safe_dump(PLAN))
        data["sequences"][0]["shots"][0]["source"] = None
        with self.assertRaises(ValidationError):
            ProductionPlan.model_validate(data)

    def test_camera_motive_required_when_moving(self) -> None:
        data = yaml.safe_load(yaml.safe_dump(PLAN))
        data["sequences"][0]["shots"][1]["camera"]["motive"] = ""
        with self.assertRaises(ValidationError):
            ProductionPlan.model_validate(data)

    def test_source_prefix_normalizes(self) -> None:
        self.assertEqual(
            normalize_source("code_video", "CodeVideoStudio/shots/x/SPEC.md"),
            "shots/x/SPEC.md",
        )
        self.assertEqual(normalize_source("manim", "05/x.py"), "05/x.py")

    def test_synthetic_storyboard_maps_shots(self) -> None:
        plan = ProductionPlan.model_validate(PLAN)
        specs = shot_specs(plan)
        self.assertEqual([spec.id for spec in specs], ["shot-001", "shot-002"])
        self.assertEqual(specs[0].scene, "shots/kinetic-cuts/SPEC.md")
        self.assertEqual(specs[1].engine, "manim")
        storyboard = synthetic_storyboard(plan)
        self.assertEqual(storyboard.lesson, "demo")
        self.assertEqual(len(storyboard.shots), 2)

    def test_validate_plan_reports_window_and_capability(self) -> None:
        from course_control.grammar import load_registry

        plan = ProductionPlan.model_validate(PLAN)
        registry = load_registry(ROOT)
        issues = validate_plan(plan, workspace=ROOT, registry=registry)
        # Manim cannot do a hard cut declared by kinetic_edit; shot 002 is long_take
        # and its 6 s duration is inside the window, so only source checks remain.
        self.assertFalse(any("shot-002" in issue and "window" in issue for issue in issues))

    def test_validate_plan_flags_unknown_grammar(self) -> None:
        from course_control.grammar import load_registry

        data = yaml.safe_load(yaml.safe_dump(PLAN))
        data["sequences"][0]["shots"][0]["grammar"] = "does_not_exist"
        plan = ProductionPlan.model_validate(data)
        issues = validate_plan(plan, registry=load_registry(ROOT))
        self.assertTrue(any("unknown grammar" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
