from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from course_control.release.build_manifest import (
    FINGERPRINT,
    MTIME_WEAK,
    BuildManifestError,
    check_freshness,
    write_manifest,
)


class EpisodeBuildManifestTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        lesson = root / "lessons" / "demo"
        build = root / "build" / "demo"
        (lesson / "authoring").mkdir(parents=True)
        (build / "narration").mkdir(parents=True)
        (build / "final").mkdir(parents=True)
        self.lesson = lesson
        self.build = build
        self.workspace = root
        self.paths = SimpleNamespace(
            slug="demo",
            workspace=root,
            lesson_dir=lesson,
            build_root=build,
            subtitles_path=lambda: lesson / "subtitles.srt",
        )
        self._write(lesson / "lesson.yaml", "lesson_id: demo\n")
        self._write(lesson / "authoring" / "episode.spec.yaml", "schema_version: 1\n")
        self._write(lesson / "authoring" / "quality.rubric.yaml", "schema_version: 1\n")
        self.timing = self._write(
            root / "RemotionStudio" / "src" / "episode" / "timing.json",
            '{"total_seconds": 10, "beats": []}\n',
        )
        self.meta = self._write(
            build / "narration" / "narration.resequenced.meta.json",
            '{"segments": []}\n',
        )
        self._write(lesson / "subtitles.srt", "1\n00:00:00,000 --> 00:00:01,000\nHi\n")
        self.video = self._write(build / "final" / "course-video.mp4", "rendered")

    def tearDown(self):
        self._tmp.cleanup()

    @staticmethod
    def _write(path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_manifest_records_every_input_and_the_film(self):
        payload = write_manifest(self.paths, self.workspace, self.video)
        names = [entry["name"] for entry in payload["inputs"]]
        self.assertEqual(
            names,
            ["lesson", "episode_spec", "quality_rubric", "timing", "narration_meta", "subtitles"],
        )
        self.assertEqual(len(payload["build_id"]), 12)
        self.assertEqual(len(payload["output"]["sha256"]), 64)
        manifest = json.loads(
            (self.build / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["build_id"], payload["build_id"])
        freshness = check_freshness(self.paths, self.video)
        self.assertTrue(freshness.fresh)
        self.assertEqual(freshness.stale_by, FINGERPRINT)
        self.assertEqual(freshness.build_id, payload["build_id"])

    def test_changed_input_without_render_is_stale(self):
        import os

        write_manifest(self.paths, self.workspace, self.video)
        # Same size, different content, older mtime: mtime would call this
        # fresh, so only the hash can catch it.
        spec = self._write(self.lesson / "authoring" / "episode.spec.yaml", "schema_version: 2\n")
        os.utime(spec, (1000, 1000))
        freshness = check_freshness(self.paths, self.video)
        self.assertFalse(freshness.fresh)
        self.assertEqual(freshness.stale_by, FINGERPRINT)
        self.assertIn("episode.spec.yaml", freshness.reason)

    def test_changed_timing_is_stale(self):
        write_manifest(self.paths, self.workspace, self.video)
        self._write(self.timing, '{"total_seconds": 11, "beats": []}\n')
        freshness = check_freshness(self.paths, self.video)
        self.assertFalse(freshness.fresh)
        self.assertIn("timing.json", freshness.reason)

    def test_missing_manifest_falls_back_to_mtime_and_says_weak(self):
        freshness = check_freshness(self.paths, self.video)
        self.assertFalse((self.build / "manifest.json").exists())
        self.assertTrue(freshness.fresh)
        self.assertEqual(freshness.stale_by, MTIME_WEAK)

    def test_mtime_fallback_still_fails_on_an_older_film(self):
        import os

        os.utime(self.video, (1000, 1000))
        spec = self.lesson / "authoring" / "episode.spec.yaml"
        os.utime(spec, (2000, 2000))
        freshness = check_freshness(self.paths, self.video)
        self.assertFalse(freshness.fresh)
        self.assertEqual(freshness.stale_by, MTIME_WEAK)

    def test_different_film_than_the_one_built_is_stale(self):
        write_manifest(self.paths, self.workspace, self.video)
        self._write(self.video, "another cut")
        freshness = check_freshness(self.paths, self.video)
        self.assertFalse(freshness.fresh)
        self.assertEqual(freshness.stale_by, FINGERPRINT)
        self.assertIn("output hash differs", freshness.reason)

    def test_missing_input_refuses_to_write_a_manifest(self):
        (self.lesson / "authoring" / "quality.rubric.yaml").unlink()
        with self.assertRaises(BuildManifestError):
            write_manifest(self.paths, self.workspace, self.video)
        self.assertFalse((self.build / "manifest.json").exists())

    def test_film_older_than_an_input_is_refused_unless_forced(self):
        import os

        os.utime(self.video, (1000, 1000))
        spec = self.lesson / "authoring" / "episode.spec.yaml"
        os.utime(spec, (2000, 2000))
        with self.assertRaises(BuildManifestError):
            write_manifest(self.paths, self.workspace, self.video)
        payload = write_manifest(self.paths, self.workspace, self.video, allow_older=True)
        self.assertEqual(len(payload["build_id"]), 12)


if __name__ == "__main__":
    unittest.main()
