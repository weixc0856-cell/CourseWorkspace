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
            workspace=root,
            lesson_dir=root / "lesson",
            build_root=root / "build",
            lesson=SimpleNamespace(content=SimpleNamespace(slides="slides.md")),
            subtitles_path=lambda: None,
        )
        (self.paths.lesson_dir / "authoring").mkdir(parents=True)
        (self.paths.build_root / "final").mkdir(parents=True)
        self.spec = self.paths.lesson_dir / "authoring" / "episode.spec.yaml"
        self.spec.write_text("schema_version: 1\n", encoding="utf-8")
        (self.paths.lesson_dir / "lesson.yaml").write_text(
            "lesson_id: demo\n", encoding="utf-8"
        )
        (self.paths.lesson_dir / "authoring" / "quality.rubric.yaml").write_text(
            "schema_version: 1\n", encoding="utf-8"
        )
        (self.paths.lesson_dir / "slides.md").write_text("# demo\n", encoding="utf-8")
        (root / "RemotionStudio" / "src" / "episode").mkdir(parents=True)
        (root / "RemotionStudio" / "src" / "episode" / "timing.json").write_text(
            "{}", encoding="utf-8"
        )
        (self.paths.build_root / "narration").mkdir(parents=True)
        (
            self.paths.build_root / "narration" / "narration.resequenced.meta.json"
        ).write_text("{}", encoding="utf-8")
        self.video = self.paths.build_root / "final" / "course-video.mp4"
        self.video.write_bytes(b"mp4")
        for item in (
            self.paths.lesson_dir / "lesson.yaml",
            self.paths.lesson_dir / "authoring" / "quality.rubric.yaml",
            self.paths.lesson_dir / "slides.md",
            root / "RemotionStudio" / "src" / "episode" / "timing.json",
            self.paths.build_root / "narration" / "narration.resequenced.meta.json",
            self.spec,
            self.video,
        ):
            self._touch(item, 1000)

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
