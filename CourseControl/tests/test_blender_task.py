from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.rendering.blender_task import BlenderTaskError, load_blender_task


def write_task(workspace: Path, relative: str, payload: dict) -> Path:
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def v1(lesson: str = "demo") -> dict:
    return {
        "schema_version": 1,
        "lesson": lesson,
        "scene": "stack_explode",
        "engine": "BLENDER_EEVEE",
        "resolution": [1920, 1080],
        "fps": 30,
        "frames": 750,
        "samples": 16,
        "format": "mp4",
        "output": f"build/{lesson}/blender/stack_explode.mp4",
        "blend": f"BlenderStudio/scenes/{lesson}/stack_explode.blend",
    }


class BlenderTaskTest(unittest.TestCase):
    def test_v1_task_is_validated_and_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            path = write_task(workspace, "BlenderStudio/tasks/demo/stack.json", v1())
            ref = load_blender_task(path, workspace)
            self.assertEqual(ref.version, 1)
            self.assertEqual(
                ref.output, (workspace / "build/demo/blender/stack_explode.mp4").resolve()
            )
            self.assertEqual(
                ref.blend,
                (workspace / "BlenderStudio/scenes/demo/stack_explode.blend").resolve(),
            )

    def test_unknown_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            payload = v1()
            payload["render_style"] = "cinematic"
            path = write_task(workspace, "BlenderStudio/tasks/demo/stack.json", payload)
            with self.assertRaises(BlenderTaskError):
                load_blender_task(path, workspace)

    def test_output_must_stay_under_the_lesson_build_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            payload = v1()
            payload["output"] = "build/other/blender/stack_explode.mp4"
            path = write_task(workspace, "BlenderStudio/tasks/demo/stack.json", payload)
            with self.assertRaises(BlenderTaskError):
                load_blender_task(path, workspace)

    def test_lesson_must_match_the_task_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            path = write_task(
                workspace, "BlenderStudio/tasks/demo/stack.json", v1(lesson="other")
            )
            with self.assertRaises(BlenderTaskError):
                load_blender_task(path, workspace)

    def test_unknown_schema_version_names_the_supported_ones(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            payload = {"schema_version": 9, "lesson": "demo"}
            path = write_task(workspace, "BlenderStudio/tasks/demo/stack.json", payload)
            with self.assertRaises(BlenderTaskError) as context:
                load_blender_task(path, workspace)
            self.assertIn("schema_version=9", str(context.exception))


if __name__ == "__main__":
    unittest.main()
