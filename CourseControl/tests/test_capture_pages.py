"""The capture stage must reject a deck that is not this lesson's deck.

A server that misses ``/lessons/<slug>/slides.md`` falls back to a one-page
placeholder.  The capture script happily reports ``1/1`` for it, so the page
count has to be checked against ``slides.md`` before the stage can pass.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from course_control.content.paths import LessonPaths
from course_control.rendering.adapters import slides


class CapturePageCountTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.lesson = self.ws / "lessons" / "demo"
        (self.lesson / "assets").mkdir(parents=True)
        (self.lesson / "lesson.yaml").write_text(
            "schema_version: 1\nlesson_id: demo\ntitle_en: Demo\ntitle_zh: 演示\n"
            "status: draft\n"
            "content:\n  slides: slides.md\n  notes: lecture_notes.md\n"
            "  storyboard: storyboard.yaml\n  assets: assets/\n"
            "outputs:\n  fps: 30\n  resolution: [1920, 1080]\n"
            "  slides_canvas: [1280, 720]\n  animation_canvas: [1920, 1080]\n"
            "engines: [manim]\ncompose:\n  mode: deck\n",
            encoding="utf-8",
        )
        self.slides_md = self.lesson / "slides.md"
        self.slides_md.write_text("<h1>One</h1>\n---\n<h2>Two</h2>\n", encoding="utf-8")
        (self.lesson / "lecture_notes.md").write_text("notes\n", encoding="utf-8")
        (self.lesson / "storyboard.yaml").write_text(
            "schema_version: 1\nlesson: demo\nshots:\n"
            "  - id: s1\n    slide: 1\n    engine: manim\n"
            "    scene: demo/scene.py::Demo\n    cue_seconds: 0\n"
            "    expected_duration_s: 8\n",
            encoding="utf-8",
        )
        self.paths = LessonPaths.load(self.ws, self.lesson)
        self.manifest = self.paths.build_root / "slides" / "capture-manifest.json"
        self.manifest.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _capture(self, total: int, captured: int):
        import hashlib

        self.manifest.write_text(
            json.dumps(
                {
                    "lesson": "demo",
                    "slides_sha256": hashlib.sha256(
                        self.slides_md.read_bytes()
                    ).hexdigest(),
                    "total_slides": total,
                    "captured": captured,
                    "pages": [],
                }
            ),
            encoding="utf-8",
        )
        with mock.patch.object(slides, "_server_ready", return_value=True), mock.patch.object(
            slides, "run_command", return_value=SimpleNamespace(exit_code=0, stderr="", stdout="")
        ):
            return slides.capture_slides(self.paths)

    def test_a_fallback_deck_is_a_failure(self):
        outcome = self._capture(total=1, captured=1)
        self.assertEqual(outcome.status.value, "fail")
        joined = " ".join(outcome.errors)
        self.assertIn("fallback", joined)
        self.assertIn("declares 2", joined)

    def test_a_matching_count_passes(self):
        outcome = self._capture(total=2, captured=2)
        self.assertEqual(outcome.status.value, "pass")

    def test_missing_slides_md_is_a_failure(self):
        self.slides_md.unlink()
        self.manifest.write_text(
            json.dumps({"lesson": "demo", "total_slides": 2, "captured": 2, "pages": []}),
            encoding="utf-8",
        )
        with mock.patch.object(slides, "_server_ready", return_value=True), mock.patch.object(
            slides, "run_command", return_value=SimpleNamespace(exit_code=0, stderr="", stdout="")
        ):
            outcome = slides.capture_slides(self.paths)
        self.assertEqual(outcome.status.value, "fail")
        self.assertTrue(outcome.errors)


if __name__ == "__main__":
    unittest.main()
