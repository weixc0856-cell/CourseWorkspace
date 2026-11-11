from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from course_control.adapters.base import verify_media
from course_control.utils import NO_CONSOLE


class MediaContractTest(unittest.TestCase):
    def setUp(self) -> None:
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg is not available")
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.video = self.root / "clip.mp4"
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=white:s=64x64:d=1:r=30",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(self.video),
            ],
            check=True,
            creationflags=NO_CONSOLE,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_matching_media_passes(self) -> None:
        info, warnings = verify_media(
            self.video, width=64, height=64, fps=30, expected_duration_s=1.0
        )
        self.assertEqual((info.width, info.height), (64, 64))
        self.assertEqual(warnings, [])

    def test_wrong_resolution_fails(self) -> None:
        with self.assertRaises(ValueError):
            verify_media(self.video, width=1280, height=720, fps=30)

    def test_duration_outside_tolerance_fails(self) -> None:
        with self.assertRaises(ValueError):
            verify_media(self.video, width=64, height=64, fps=30, expected_duration_s=3.0)


if __name__ == "__main__":
    unittest.main()
