from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from course_control import adapters
from course_control.contracts import Status
from course_control.paths import LessonPaths
from course_control.utils import MediaInfo

WORKSPACE = Path(__file__).resolve().parents[2]
FIXTURE = WORKSPACE / "CourseControl" / "tests" / "fixtures" / "lesson-manual"


def media() -> MediaInfo:
    return MediaInfo(
        duration=1.0,
        width=1920,
        height=1080,
        fps=30.0,
        codec="h264",
        pix_fmt="yuv420p",
        has_audio=False,
        audio_duration=None,
    )


class MotionCanvasHeadlessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.paths = LessonPaths.load(
            WORKSPACE, FIXTURE, build_root_override=Path(self.tmp.name)
        )
        self.target = (
            Path(self.tmp.name)
            / "animation"
            / "gui_vs_cli_paths.mp4"
        )

    def fake_success(self, command, cwd, timeout, log_path):
        target = Path(command[command.index("--out") + 1])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"rendered")
        return SimpleNamespace(exit_code=0, stdout="", stderr="")

    def test_auto_render_passes_without_manual_export(self):
        with patch.object(adapters.motion_canvas, "which_command", return_value=["node"]), \
             patch.object(adapters.motion_canvas, "run_command", side_effect=self.fake_success) as command, \
             patch.object(adapters.motion_canvas, "probe_media", return_value=media()):
            outcome = adapters.motion_canvas.run(self.paths)
        self.assertEqual(outcome.status, Status.PASS)
        self.assertEqual(len(outcome.outputs), 1)
        args = command.call_args.args[0]
        self.assertIn("scripts/render-headless.mjs", args)
        self.assertIn("gui-vs-cli-paths", args)

    def test_failure_retries_then_fails(self):
        with patch.object(adapters.motion_canvas, "which_command", return_value=["node"]), \
             patch.object(
                 adapters.motion_canvas,
                 "run_command",
                 return_value=SimpleNamespace(exit_code=1, stdout="", stderr="boom"),
             ) as command, \
             patch.object(adapters.motion_canvas, "probe_media", return_value=media()):
            outcome = adapters.motion_canvas.run(self.paths)
        self.assertEqual(outcome.status, Status.FAIL)
        self.assertEqual(command.call_count, 2)
        self.assertTrue(outcome.errors)

    def test_invalid_media_is_not_reported_as_pass(self):
        with patch.object(adapters.motion_canvas, "which_command", return_value=["node"]), \
             patch.object(adapters.motion_canvas, "run_command", side_effect=self.fake_success), \
             patch.object(adapters.motion_canvas, "probe_media", side_effect=ValueError("bad media")):
            outcome = adapters.motion_canvas.run(self.paths)
        self.assertEqual(outcome.status, Status.FAIL)
        self.assertTrue(any("bad media" in error for error in outcome.errors))

    def test_valid_existing_output_is_reused(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b"existing")
        with patch.object(adapters.motion_canvas, "run_command") as command, \
             patch.object(adapters.motion_canvas, "probe_media", return_value=media()):
            outcome = adapters.motion_canvas.run(self.paths)
        self.assertEqual(outcome.status, Status.PASS)
        command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
