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


if __name__ == "__main__":
    unittest.main()
