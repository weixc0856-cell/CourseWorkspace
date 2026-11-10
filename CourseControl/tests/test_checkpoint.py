from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from course_control.adapters.base import StageOutcome
from course_control.checkpoint import CheckpointStore, run_stage
from course_control.contracts import Status


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
