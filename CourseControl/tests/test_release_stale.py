from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from course_control.release.check import _stale_reason


class StaleFinalTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.paths = SimpleNamespace(
            lesson_dir=root / "lesson",
            build_root=root / "build",
        )
        (self.paths.lesson_dir / "authoring").mkdir(parents=True)
        (self.paths.build_root / "final").mkdir(parents=True)
        self.spec = self.paths.lesson_dir / "authoring" / "episode.spec.yaml"
        self.spec.write_text("schema_version: 1\n", encoding="utf-8")
        self.video = self.paths.build_root / "final" / "course-video.mp4"
        self.video.write_bytes(b"mp4")

    def tearDown(self):
        self._tmp.cleanup()

    def _touch(self, path, when):
        os.utime(path, (when, when))

    def test_older_video_is_stale_and_names_both_files(self):
        self._touch(self.video, 1000)
        self._touch(self.spec, 2000)
        reason = _stale_reason(self.paths, self.video)
        self.assertIsNotNone(reason)
        self.assertIn("stale", reason)
        self.assertIn(str(self.video), reason)
        self.assertIn(str(self.spec), reason)

    def test_newer_video_is_current(self):
        self._touch(self.spec, 1000)
        self._touch(self.video, 2000)
        self.assertIsNone(_stale_reason(self.paths, self.video))


if __name__ == "__main__":
    unittest.main()
