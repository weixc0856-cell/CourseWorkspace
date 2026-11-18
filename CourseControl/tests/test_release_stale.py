from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from unittest.mock import patch

from course_control.release.build_manifest import check_freshness
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
        (self.paths.build_root / "episode").mkdir(parents=True)
        (self.paths.build_root / "episode" / "timing.json").write_text(
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
            self.paths.build_root / "episode" / "timing.json",
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

    def test_mtime_fallback_is_stale_when_inputs_cannot_be_enumerated(self) -> None:
        # The old fallback list is present and older than the film.  A rename
        # or a moved input must still read as stale, not fresh.
        for relative in (
            "contracts/timeline.spec.json",
            "narration/narration.meta.json",
            "subtitles.srt",
        ):
            path = self.paths.build_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
            self._touch(path, 1000)
        self._touch(self.video, 2000)
        with patch(
            "course_control.release.build_manifest.declared_inputs",
            side_effect=AttributeError("unreadable input set"),
        ):
            freshness = check_freshness(self.paths, self.video)
        self.assertFalse(freshness.fresh)
        self.assertIn("cannot evaluate", freshness.reason or "")
        self.assertIn("unreadable input set", freshness.reason or "")

    def test_newer_video_is_current(self):
        self._touch(self.spec, 1000)
        self._touch(self.video, 2000)
        self.assertIsNone(_stale_reason(self.paths, self.video))


if __name__ == "__main__":
    unittest.main()
