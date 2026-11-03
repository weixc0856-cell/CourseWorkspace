from __future__ import annotations

import unittest

from pydantic import ValidationError

import json
from pathlib import Path

from modeling_studio.contracts import ModelPlan, Revision, ValidationReport, VisualAnalysis
from modeling_studio.model_planner import ground_plan, normalize_plan

MINIMAL_ANALYSIS = {
    "object": "bracket",
    "parts": [{"name": "plate", "geometry": "cuboid", "confidence": 0.9}],
}

MINIMAL_PLAN = {
    "object_name": "bracket",
    "parts": [
        {
            "id": "plate",
            "name": "plate",
            "geometry": "cuboid",
            "size": [0.2, 0.1, 0.02],
            "location": [0.0, 0.0, -0.01],
        }
    ],
}


class ContractTest(unittest.TestCase):
    def test_visual_analysis_minimal(self):
        analysis = VisualAnalysis.model_validate(MINIMAL_ANALYSIS)
        self.assertEqual(analysis.parts[0].geometry, "cuboid")

    def test_model_plan_minimal(self):
        plan = ModelPlan.model_validate(MINIMAL_PLAN)
        self.assertEqual(plan.units, "METRIC")

    def test_plan_rejects_unknown_material(self):
        data = {**MINIMAL_PLAN}
        data["parts"] = [{**MINIMAL_PLAN["parts"][0], "material_id": "missing"}]
        with self.assertRaises(ValidationError):
            ModelPlan.model_validate(data)

    def test_normalize_cylinder_axes(self):
        plan = ModelPlan.model_validate(
            {
                "object_name": "pin",
                "parts": [
                    {
                        "id": "pin",
                        "name": "pin",
                        "geometry": "cylinder",
                        "size": [0.03, 0.25, 0.03],
                        "location": [0, 0, 0.125],
                    }
                ],
            }
        )
        plan = normalize_plan(plan)
        self.assertEqual(plan.parts[0].size, (0.03, 0.03, 0.25))

    def test_committed_schemas_match_models(self):
        schema_dir = Path(__file__).resolve().parents[1] / "schemas"
        models = {
            "visual_analysis": VisualAnalysis,
            "model_plan": ModelPlan,
            "validation": ValidationReport,
            "revision": Revision,
        }
        for name, model in models.items():
            expected = json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + chr(10)
            actual = (schema_dir / f"{name}.schema.json").read_text(encoding="utf-8")
            self.assertEqual(expected, actual, f"schema drift: {name}")

    def test_color_components_are_normalized(self):
        plan = ModelPlan.model_validate(
            {
                "object_name": "colors",
                "parts": [
                    {"id": "p", "name": "p", "geometry": "cuboid", "size": [0.1, 0.1, 0.1], "material_id": "m"}
                ],
                "materials": [{"id": "m", "base_color": [0.5, 0.4, 0.3]}],
                "lights": [{"type": "AREA", "color": [1.0, 0.9, 0.8, 1.0]}],
            }
        )
        self.assertEqual(plan.materials[0].base_color, (0.5, 0.4, 0.3, 1.0))
        self.assertEqual(plan.lights[0].color, (1.0, 0.9, 0.8))

    def test_ground_plan(self):
        plan = ModelPlan.model_validate(MINIMAL_PLAN)
        plan = ground_plan(plan)
        self.assertAlmostEqual(plan.parts[0].location[2], 0.01)
        self.assertIn("shifted up", plan.assumptions[-1])


if __name__ == "__main__":
    unittest.main()
