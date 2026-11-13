from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from course_control.rendering.adapters.base import StageOutcome
from course_control.platform.checkpoint import CheckpointStore, run_stage, stage_inputs
from course_control.content.paths import LessonPaths
from course_control.content.contracts import Status


def outcome(name: str, output: Path, status: Status = Status.PASS) -> StageOutcome:
    return StageOutcome(name, status, outputs=[output], warnings=["rendered"])


class CheckpointStoreTest(unittest.TestCase):
    def test_pass_checkpoint_is_reused_only_while_inputs_and_outputs_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            output = build / "animation" / "shot.mp4"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"first")
            store = CheckpointStore(build, "fingerprint")
            inputs = {"lesson.yaml": "abc"}

            store.save(outcome("render:manim", output), inputs, "run-1")
            valid, reasons = store.check("render:manim", inputs)
            self.assertTrue(valid, reasons)

            output.write_bytes(b"changed")
            valid, reasons = store.check("render:manim", inputs)
            self.assertFalse(valid)
            self.assertTrue(any("hash changed" in item for item in reasons))

    def test_input_change_and_fingerprint_change_invalidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            output = build / "animation" / "shot.mp4"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"video")
            store = CheckpointStore(build, "fingerprint")
            store.save(outcome("render:manim", output), {"a": "1"}, "run-1")

            valid, reasons = store.check("render:manim", {"a": "2"})
            self.assertFalse(valid)
            self.assertTrue(any("inputs changed" in item for item in reasons))

            other = CheckpointStore(build, "another")
            valid, reasons = other.check("render:manim", {"a": "1"})
            self.assertFalse(valid)
            self.assertIn("configuration fingerprint changed", reasons)

    def test_non_pass_checkpoint_is_not_reused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            output = build / "animation" / "shot.mp4"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"video")
            store = CheckpointStore(build, "fingerprint")
            store.save(outcome("render:manim", output, Status.FAIL), {}, "run-1")
            valid, _ = store.check("render:manim", {})
            self.assertFalse(valid)


    def test_subtitles_only_invalidate_consuming_stages(self) -> None:
        workspace = Path(__file__).resolve().parents[2]
        fixture = workspace / "CourseControl" / "tests" / "fixtures" / "lesson-smoke"
        paths = LessonPaths.load(workspace, fixture)
        subtitle_key = "CourseControl/tests/fixtures/lesson-smoke/subtitles.srt"
        self.assertNotIn(subtitle_key, stage_inputs(paths, "capture_slides"))
        self.assertNotIn(subtitle_key, stage_inputs(paths, "render:blender"))
        self.assertIn(subtitle_key, stage_inputs(paths, "collect"))

    def test_run_stage_skips_the_action_when_checkpoint_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            output = build / "animation" / "shot.mp4"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"video")
            store = CheckpointStore(build, "fingerprint")
            inputs = {"lesson.yaml": "abc"}
            calls = []

            def action():
                calls.append(1)
                return outcome("render:manim", output)

            first, reused, _ = run_stage(
                "render:manim", inputs, action, store, resume=True, run_id="run-1"
            )
            self.assertFalse(reused)
            self.assertEqual(first.status, Status.PASS)
            second, reused, reasons = run_stage(
                "render:manim", inputs, action, store, resume=True, run_id="run-2"
            )
            self.assertTrue(reused)
            self.assertEqual(second.reason, "resumed_from_checkpoint")
            self.assertEqual(len(calls), 1)

    def test_force_reruns_even_when_checkpoint_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            output = build / "animation" / "shot.mp4"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"video")
            store = CheckpointStore(build, "fingerprint")
            calls = []

            def action():
                calls.append(1)
                return outcome("render:manim", output)

            run_stage("render:manim", {}, action, store, resume=True, run_id="run-1")
            run_stage(
                "render:manim",
                {},
                action,
                store,
                resume=True,
                run_id="run-2",
                force=True,
            )
            self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()


class StageDagTest(unittest.TestCase):
    def test_dependencies_are_declared_in_topological_order(self) -> None:
        from course_control.platform.checkpoint import STAGE_DEPS, STAGE_ORDER

        self.assertEqual(set(STAGE_DEPS), set(STAGE_ORDER))
        for name, deps in STAGE_DEPS.items():
            for dependency in deps:
                self.assertIn(dependency, STAGE_ORDER)
                self.assertLess(STAGE_ORDER.index(dependency), STAGE_ORDER.index(name))

    def test_a_render_change_does_not_touch_its_siblings(self) -> None:
        from course_control.platform.checkpoint import affected_by, downstream

        affected = downstream("render:manim")
        self.assertIn("collect", affected)
        self.assertIn("verify", affected)
        self.assertNotIn("render:blender", affected)
        self.assertNotIn("render:code_video", affected)
        self.assertNotIn("capture_slides", affected)
        self.assertEqual(affected_by("verify"), {"verify"})
        self.assertEqual(affected_by("capture_slides"), set(STAGE_ORDER_ALL))

    def test_invalidate_from_keeps_sibling_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(Path(tmp), "fingerprint")
            store.root.mkdir(parents=True)
            for stage in STAGE_ORDER_ALL:
                (store.root / (stage.replace(":", "-") + ".json")).write_text("{}", encoding="utf-8")
            store.invalidate_from("render:manim")
            remaining = {path.stem for path in store.root.glob("*.json")}
            self.assertIn("render-blender", remaining)
            self.assertIn("render-code_video", remaining)
            self.assertIn("capture_slides", remaining)
            self.assertNotIn("render-manim", remaining)
            self.assertNotIn("collect", remaining)
            self.assertNotIn("verify", remaining)


STAGE_ORDER_ALL = [
    "capture_slides",
    "render:motion_canvas",
    "render:manim",
    "render:blender",
    "render:code_video",
    "collect",
    "compose",
    "burn_subtitles",
    "brand",
    "verify",
]
