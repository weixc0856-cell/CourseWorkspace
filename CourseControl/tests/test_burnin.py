from __future__ import annotations

import tempfile
import unittest
import unittest.mock
from pathlib import Path
from types import SimpleNamespace

from course_control.rendering.adapters import burn
from course_control.platform.utils import CommandResult, MediaInfo


def result(code: int) -> CommandResult:
    return CommandResult(["fake"], code, "", "", 1)


class BurnTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.build = self.root / "build" / "test-lesson"
        (self.build / "final").mkdir(parents=True)
        (self.build / "logs").mkdir()
        (self.build / "final" / "course-video.mp4").write_bytes(b"clean")
        (self.build / "subtitles.ass").write_text("[Events]\n", encoding="utf-8")
        self.paths = SimpleNamespace(
            slug="test-lesson",
            build_root=self.build,
            workspace=self.root,
        )
        self.clean = MediaInfo(6.0, 1920, 1080, 30.0, "h264", "yuv420p", True, 6.0)
        self.captioned = MediaInfo(6.0, 1920, 1080, 30.0, "h264", "yuv420p", True, 6.0)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, codes):
        output = self.build / "final" / "course-video-captioned.mp4"

        def fake_run(command, cwd, **kwargs):
            code = codes.pop(0)
            if code == 0:
                output.write_bytes(b"captioned")
            return result(code)

        def fake_probe(path):
            return self.clean if Path(path).name == "course-video.mp4" else self.captioned

        with unittest.mock.patch.object(burn, "run_command", side_effect=fake_run), unittest.mock.patch.object(
            burn, "probe_media", side_effect=fake_probe
        ):
            return burn.burn_subtitles(self.paths)

    def test_qsv_success(self):
        outcome = self._run([0])
        self.assertEqual(outcome.status.value, "pass")
        self.assertTrue((self.build / "final" / "burn.json").is_file())

    def test_qsv_falls_back_to_libx264(self):
        outcome = self._run([1, 0])
        self.assertEqual(outcome.status.value, "pass")
        record = (self.build / "final" / "burn.json").read_text(encoding="utf-8")
        self.assertIn('"encoder": "libx264"', record)
        self.assertIn('"encoder_fallback": true', record)

    def test_both_encoders_fail(self):
        outcome = self._run([1, 1])
        self.assertEqual(outcome.status.value, "fail")
        self.assertIn("all encoders failed", " ".join(outcome.errors))

    def test_missing_ass_fails(self):
        (self.build / "subtitles.ass").unlink()
        outcome = burn.burn_subtitles(self.paths)
        self.assertEqual(outcome.status.value, "fail")
        self.assertEqual(outcome.reason, "missing_ass")


if __name__ == "__main__":
    unittest.main()
