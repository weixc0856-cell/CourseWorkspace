from __future__ import annotations

import tempfile
import unittest
import unittest.mock
from pathlib import Path

from course_control.code_video_qc import check_video
from course_control.utils import MediaInfo


class CodeVideoQCTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.video = self.root / "shot.mp4"
        self.video.write_bytes(b"fake")

    def tearDown(self):
        self._tmp.cleanup()

    def _check(self, media, black=None, freeze=None):
        with unittest.mock.patch(
            "course_control.code_video_qc.probe_media", return_value=media
        ), unittest.mock.patch(
            "course_control.code_video_qc.detect_black_freeze",
            return_value=(black or [], freeze or []),
        ):
            return check_video(
                self.video,
                width=1920,
                height=1080,
                fps=30,
                min_duration=30,
                max_duration=30,
                audio="0",
                workspace=self.root,
            )

    def test_valid_video_passes(self):
        media = MediaInfo(30.0, 1920, 1080, 30.0, "h264", "yuv420p", False, None)
        result = self._check(media)
        self.assertTrue(result["ok"])
        self.assertTrue(all(item["status"] == "pass" for item in result["checks"]))

    def test_wrong_fps_fails(self):
        media = MediaInfo(30.0, 1920, 1080, 25.0, "h264", "yuv420p", False, None)
        result = self._check(media)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["id"] == "fps" and item["status"] == "fail" for item in result["checks"]))

    def test_audio_rule_fails(self):
        media = MediaInfo(30.0, 1920, 1080, 30.0, "h264", "yuv420p", True, 30.0)
        result = self._check(media)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["id"] == "audio" and item["status"] == "fail" for item in result["checks"]))

    def test_black_and_freeze_are_warnings(self):
        media = MediaInfo(30.0, 1920, 1080, 30.0, "h264", "yuv420p", False, None)
        result = self._check(media, black=["0-1s"], freeze=["1-2s"])
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["warnings"]), 2)


if __name__ == "__main__":
    unittest.main()
