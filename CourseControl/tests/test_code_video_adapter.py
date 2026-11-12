from __future__ import annotations

import os
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path
from types import SimpleNamespace

from course_control.adapters import code_video
from course_control.utils import CommandResult


def result(code: int) -> CommandResult:
    return CommandResult(["node"], code, "", "", 1)


class CodeVideoAdapterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.project = self.root / "CodeVideoStudio" / "shots" / "attention-flow"
        self.project.mkdir(parents=True)
        self.spec = self.project / "SPEC.md"
        self.spec.write_text("# SPEC\n", encoding="utf-8")
        self.verify = self.project / "VERIFY.md"
        self.verify.write_text("| 1 | must have | pass |\n", encoding="utf-8")
        skill = self.root / "CodeVideoStudio" / "skills" / "code-video" / "scripts" / "capture.mjs"
        skill.parent.mkdir(parents=True)
        skill.write_text("// capture\n", encoding="utf-8")
        self.build = self.root / "build" / "lesson-code-video"
        self.shot = SimpleNamespace(
            id="shot_001",
            engine="code_video",
            scene="shots/attention-flow/SPEC.md",
            expected_duration_s=None,
        )
        self.paths = SimpleNamespace(
            storyboard=SimpleNamespace(shots=[self.shot]),
            build_root=self.build,
            workspace=self.root,
            lesson=SimpleNamespace(outputs=SimpleNamespace(fps=30, resolution=(1920, 1080))),
            scene_path=lambda shot: (self.spec, None),
            engine_root=lambda engine: self.root / "CodeVideoStudio",
            engine_home=lambda engine: self.root / "CodeVideoStudio",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self):
        output_box = {}

        def fake_run(command, cwd, **kwargs):
            out_index = command.index("--out") + 1
            output = Path(command[out_index])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"fake")
            output_box["out"] = output
            output_box["command"] = list(command)
            return result(0)

        def fake_qc(*args, **kwargs):
            return {"ok": True, "checks": [], "warnings": [], "media": {}}

        def fake_contact(video, out, **kwargs):
            Path(out).write_bytes(b"jpg")
            return Path(out)

        with unittest.mock.patch.object(code_video, "run_command", side_effect=fake_run), unittest.mock.patch.object(
            code_video, "check_video", side_effect=fake_qc
        ), unittest.mock.patch.object(
            code_video, "contact_sheet", side_effect=fake_contact
        ), unittest.mock.patch.object(code_video, "which_command", return_value=["node"]):
            outcome = code_video.run(self.paths)
        self.command = output_box.get("command", [])
        return outcome

    def test_render_pass_copies_to_animation(self):
        outcome = self._run()
        self.assertEqual(outcome.status.value, "pass")
        target = self.build / "animation" / "attention-flow.mp4"
        self.assertTrue(target.is_file())

    def test_qc_failure_fails(self):
        def fake_qc(*args, **kwargs):
            return {
                "ok": False,
                "checks": [{"id": "fps", "status": "fail", "expected": "30", "actual": "25"}],
                "warnings": [],
                "media": {},
            }

        def fake_contact(video, out, **kwargs):
            Path(out).write_bytes(b"jpg")
            return Path(out)

        def fake_run(command, cwd, **kwargs):
            output = Path(command[command.index("--out") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"fake")
            return result(0)

        with unittest.mock.patch.object(code_video, "run_command", side_effect=fake_run), unittest.mock.patch.object(
            code_video, "check_video", side_effect=fake_qc
        ), unittest.mock.patch.object(
            code_video, "contact_sheet", side_effect=fake_contact
        ), unittest.mock.patch.object(code_video, "which_command", return_value=["node"]):
            outcome = code_video.run(self.paths)
        self.assertEqual(outcome.status.value, "fail")
        self.assertIn("QC fps", " ".join(outcome.errors))

    def test_missing_verify_fails(self):
        self.verify.unlink()
        outcome = self._run()
        self.assertEqual(outcome.status.value, "fail")
        self.assertIn("VERIFY.md", " ".join(outcome.errors))

    def test_failing_verify_fails(self):
        self.verify.write_text("| 1 | must have | fail |\n", encoding="utf-8")
        outcome = self._run()
        self.assertEqual(outcome.status.value, "fail")
        self.assertIn("failing must-have", " ".join(outcome.errors))



    def test_capture_config_forwards_switches(self):
        (self.project / "capture.json").write_text('{"gpu": true, "jpeg": true}', encoding="utf-8")
        outcome = self._run()
        self.assertEqual(outcome.status.value, "pass")
        self.assertIn("--gpu", self.command)
        self.assertIn("--jpeg", self.command)

    def test_unknown_capture_switch_fails(self):
        (self.project / "capture.json").write_text('{"turbo": true}', encoding="utf-8")
        outcome = self._run()
        self.assertEqual(outcome.status.value, "fail")
        self.assertIn("unknown keys", " ".join(outcome.errors))

    def test_cached_capture_reused_until_a_source_changes(self):
        self._run()
        self.assertIn("--out", self.command)
        self._run()
        self.assertEqual(self.command, [], "unchanged shot should reuse the cached capture")
        skill = self.root / "CodeVideoStudio" / "skills" / "code-video" / "scripts" / "capture.mjs"
        later = time.time() + 10
        os.utime(skill, (later, later))
        self._run()
        self.assertIn("--out", self.command, "capture script change must invalidate the cache")


class CaptureFlagsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_absent_config_means_no_flags(self):
        self.assertEqual(code_video.capture_flags(self.project), [])

    def test_switches_follow_config(self):
        (self.project / "capture.json").write_text('{"gpu": true, "jpeg": false, "note": "x"}', encoding="utf-8")
        self.assertEqual(code_video.capture_flags(self.project), ["--gpu"])

    def test_unknown_key_rejected(self):
        (self.project / "capture.json").write_text('{"turbo": true}', encoding="utf-8")
        with self.assertRaises(ValueError):
            code_video.capture_flags(self.project)


if __name__ == "__main__":
    unittest.main()
