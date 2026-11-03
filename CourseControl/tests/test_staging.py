from __future__ import annotations

import shutil
import unittest
import unittest.mock
from pathlib import Path

from course_control.adapters import remotion
from course_control.paths import LessonPaths
from course_control.utils import CommandResult, MediaInfo

WORKSPACE = Path(__file__).resolve().parents[2]
FIXTURE = WORKSPACE / "CourseControl" / "tests" / "fixtures" / "lesson-smoke"


class StagingLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.paths = LessonPaths.load(WORKSPACE, FIXTURE)
        self.staging = WORKSPACE / "RemotionStudio" / "public" / "staging" / self.paths.slug
        shutil.rmtree(self.staging, ignore_errors=True)
        self.staging.mkdir(parents=True)
        (self.staging / "marker.txt").write_text("staged", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.staging, ignore_errors=True)

    @staticmethod
    def _result(code: int) -> CommandResult:
        return CommandResult(["fake"], code, "", "", 1)

    def test_render_failure_preserves_staging(self):
        with unittest.mock.patch.object(
            remotion, "run_command", side_effect=[self._result(0), self._result(1)]
        ):
            outcome = remotion.compose(self.paths)
        self.assertEqual(outcome.status.value, "fail")
        self.assertTrue((self.staging / "marker.txt").is_file())

    def test_render_success_cleans_staging(self):
        output = self.paths.build_root / "final" / "course-video.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake")
        self.addCleanup(lambda: output.unlink(missing_ok=True))
        media = MediaInfo(6.0, 1920, 1080, 30.0, "h264", "yuv420p", True, 6.0)
        with unittest.mock.patch.object(
            remotion, "run_command", side_effect=[self._result(0), self._result(0)]
        ), unittest.mock.patch.object(remotion, "probe_media", return_value=media):
            outcome = remotion.compose(self.paths)
        self.assertEqual(outcome.status.value, "pass")
        self.assertFalse(self.staging.exists())


if __name__ == "__main__":
    unittest.main()
