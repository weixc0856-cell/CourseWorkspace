"""The production content audit reports on the real tree; it never writes it."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from course_control.platform.content_audit import run_audit

WORKSPACE = Path(__file__).resolve().parents[2]


class ContentAuditTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "lessons").mkdir()
        (self.root / "build" / "_shared").mkdir(parents=True)
        (self.root / "deliver").mkdir()
        self._env = mock.patch.dict(
            os.environ,
            {
                # check.ps1 runs this suite in dev mode, where the dev root
                # wins over COURSEWORKSPACE_CONTENT_ROOT. The audit is a
                # production command; the test names its own root.
                "COURSEWORKSPACE_MODE": "",
                "COURSEWORKSPACE_CONTENT_ROOT": str(self.root),
            },
        )
        self._env.start()
        self.addCleanup(self._env.stop)

    def _audit(self, strict: bool = False):
        return run_audit(WORKSPACE, strict=strict)

    def _status(self, result, area: str) -> list[str]:
        return [item.status for item in result.findings if item.area == area]

    def test_clean_layout_passes(self):
        result = self._audit()
        self.assertIn("pass", self._status(result, "layout"))
        self.assertFalse(result.errors)

    def test_stray_build_directory_fails(self):
        (self.root / "build" / "tmp_preview").mkdir()
        result = self._audit()
        self.assertTrue(result.errors)
        self.assertTrue(
            any("tmp_preview" in item.detail for item in result.errors),
            [item.detail for item in result.errors],
        )

    def test_lesson_with_missing_content_fails(self):
        lesson = self.root / "lessons" / "demo"
        lesson.mkdir()
        (lesson / "lesson.yaml").write_text(
            "schema_version: 1\nlesson_id: demo\ntitle_en: Demo\ntitle_zh: 演示\n"
            "status: draft\n"
            "content:\n  slides: slides.md\n  notes: lecture_notes.md\n"
            "  storyboard: storyboard.yaml\n  assets: assets/\n"
            "outputs:\n  fps: 30\n  resolution: [1920, 1080]\n"
            "  slides_canvas: [1280, 720]\n  animation_canvas: [1920, 1080]\n"
            "engines: [manim]\ncompose:\n  mode: deck\n",
            encoding="utf-8",
        )
        result = self._audit()
        self.assertTrue(
            any("demo" in item.detail for item in result.errors),
            [item.detail for item in result.findings],
        )

    def test_leftover_deliver_directory_is_a_warning(self):
        (self.root / "deliver" / "demo.tmp").mkdir()
        result = self._audit()
        self.assertEqual(result.status(), "incomplete")
        self.assertTrue(any(".tmp" in item.detail for item in result.warnings))
        strict = self._audit(strict=True)
        self.assertEqual(strict.status(strict=True), "fail")

    def test_unclassified_delivery_is_reported(self):
        package = self.root / "deliver" / "old"
        package.mkdir()
        (package / "manifest.json").write_text(
            json.dumps({"schema_version": 1, "verdict": "pass"}), encoding="utf-8"
        )
        result = self._audit()
        self.assertTrue(
            any("schema 1" in item.detail for item in result.findings),
            [item.detail for item in result.findings],
        )
        (package / "manifest.json").unlink()
        result = self._audit()
        self.assertTrue(
            any("no manifest.json" in item.detail for item in result.warnings)
        )


if __name__ == "__main__":
    unittest.main()
