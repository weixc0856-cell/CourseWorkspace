from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

from course_control.blender_scene import (
    BlenderSceneTask,
    SceneContractError,
    task_summary,
    validate_scene_task,
)

WORKSPACE = Path(__file__).resolve().parents[2]
TASKS = WORKSPACE / "BlenderStudio" / "tasks" / "scene-system"
SCHEMA = WORKSPACE / "shared" / "schemas" / "blender-scene-task.schema.json"


def load_task(name: str) -> dict:
    return json.loads((TASKS / name).read_text(encoding="utf-8"))


def load_blender_validator():
    path = WORKSPACE / "BlenderStudio" / "scripts" / "scene_system" / "task_schema.py"
    spec = importlib.util.spec_from_file_location("blender_task_schema", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SceneContractTest(unittest.TestCase):
    def test_demo_task_passes(self):
        task = validate_scene_task(load_task("demo-scene.json"), WORKSPACE)
        summary = task_summary(task)
        self.assertEqual(summary["objects"], 6)
        self.assertEqual(summary["materials"], 5)
        self.assertEqual(summary["cameras"], 1)
        self.assertEqual(summary["lights"], 3)

    def test_text_curve_ortho_task_passes(self):
        task = validate_scene_task(load_task("demo-text-curve.json"), WORKSPACE)
        summary = task_summary(task)
        self.assertEqual(summary["objects"], 7)
        self.assertEqual(summary["text_objects"], 4)
        self.assertEqual(summary["curve_objects"], 3)
        self.assertEqual(summary["ortho_cameras"], 1)
        self.assertEqual(task.cameras[0].projection, "ORTHO")
        self.assertEqual(task.cameras[0].ortho_scale, 6.0)
        self.assertEqual(task.objects[3].text.body, "x")

    def test_text_and_curve_fields_are_type_scoped(self):
        data = load_task("demo-scene.json")
        data["objects"][0]["text"] = {"body": "x"}
        with self.assertRaises(SceneContractError) as raised:
            validate_scene_task(data, WORKSPACE)
        self.assertIn("text is only valid for TEXT objects", "\n".join(raised.exception.messages))

        data = load_task("demo-text-curve.json")
        text = next(obj for obj in data["objects"] if obj["type"] == "TEXT")
        text["curve"] = {"points": [[0, 0, 0], [1, 0, 0]]}
        with self.assertRaises(SceneContractError) as raised:
            validate_scene_task(data, WORKSPACE)
        self.assertIn("curve is only valid for CURVE objects", "\n".join(raised.exception.messages))

    def test_geometry_nodes_and_animation_tasks_pass(self):
        gn = validate_scene_task(load_task("demo-geometry-nodes.json"), WORKSPACE)
        self.assertEqual(task_summary(gn)["geometry_nodes"], 2)
        animated = validate_scene_task(load_task("demo-animation-scene.json"), WORKSPACE)
        self.assertEqual(task_summary(animated)["animations"], 5)

    def test_invalid_fixtures_rejected(self):
        expected = {
            "invalid-collection-root.json": "collection",
            "invalid-duplicate-id.json": "unique",
            "invalid-material-ref.json": "unknown material",
            "invalid-no-camera.json": "camera",
            "invalid-output-outside.json": "build/blender-scene-acceptance/blender/",
            "invalid-primitive.json": "primitive",
            "invalid-text-empty.json": "at least 1 character",
            "invalid-text-primitive.json": "primitive is only valid",
            "invalid-curve-points.json": "at least 2 items",
            "invalid-curve-bevel.json": "greater than or equal to 0.0001",
            "invalid-camera-projection.json": "'PERSPECTIVE' or 'ORTHO'",
        }
        for name, needle in expected.items():
            with self.subTest(name=name), self.assertRaises(SceneContractError) as raised:
                validate_scene_task(load_task(name), WORKSPACE)
            self.assertIn(needle, "\n".join(raised.exception.messages))

    def test_unknown_geometry_node_asset_rejected(self):
        data = load_task("demo-geometry-nodes.json")
        data["objects"][0]["geometry_nodes"][0]["asset"] = "gn.missing"
        with self.assertRaises(SceneContractError) as raised:
            validate_scene_task(data, WORKSPACE)
        self.assertIn("unknown geometry node asset", "\n".join(raised.exception.messages))

    def test_geometry_node_param_range_rejected(self):
        data = load_task("demo-geometry-nodes.json")
        data["objects"][0]["geometry_nodes"][0]["params"]["Strength"] = -1.0
        with self.assertRaises(SceneContractError) as raised:
            validate_scene_task(data, WORKSPACE)
        self.assertIn("Strength", "\n".join(raised.exception.messages))

    def test_animation_outside_frame_range_rejected(self):
        data = load_task("demo-animation-scene.json")
        data["animations"][0]["channels"][0]["keyframes"][1]["frame"] = 999
        with self.assertRaises(SceneContractError) as raised:
            validate_scene_task(data, WORKSPACE)
        self.assertIn("outside the scene frame range", "\n".join(raised.exception.messages))

    def test_schema_matches_pydantic_model(self):
        payload = json.dumps(BlenderSceneTask.model_json_schema(), ensure_ascii=False, indent=2)
        committed = SCHEMA.read_text(encoding="utf-8").rstrip("\n")
        self.assertEqual(payload, committed)

    def test_external_and_blender_validators_agree(self):
        blender = load_blender_validator()
        for path in sorted(TASKS.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            external_ok = True
            try:
                validate_scene_task(data, WORKSPACE)
            except SceneContractError:
                external_ok = False
            blender_ok = True
            try:
                blender.validate_task(data, cwd=str(WORKSPACE))
            except blender.TaskError:
                blender_ok = False
            self.assertEqual(
                external_ok,
                blender_ok,
                f"validators disagree on {path.name}: external={external_ok} blender={blender_ok}",
            )

    def test_validators_agree_without_generated_artifacts(self):
        """Contract validation must not depend on build/ artifacts existing."""
        blender = load_blender_validator()
        data = load_task("demo-modify.json")
        data["base_blend"] = "build/blender-scene-acceptance/blender/not-generated-yet.blend"
        validate_scene_task(data, WORKSPACE)
        blender.validate_task(data, cwd=str(WORKSPACE))


if __name__ == "__main__":
    unittest.main()
