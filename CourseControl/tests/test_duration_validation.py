from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from course_control.content.paths import LessonPaths
from course_control.content.validators import validate

WORKSPACE = Path(__file__).resolve().parents[2]
FIXTURE = WORKSPACE / "CourseControl" / "tests" / "fixtures" / "lesson-authoring"


class DurationValidationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.lesson = self.root / "lessons" / "lesson-authoring"
        shutil.copytree(FIXTURE, self.lesson)
        scene = self.root / "ManimSandbox" / "lesson-authoring" / "scene.py"
        scene.parent.mkdir(parents=True)
        scene.write_text("from manim import Scene\n\n\nclass AuthoringScene(Scene):\n    pass\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _validate(self):
        paths = LessonPaths.load(self.root, self.lesson)
        return validate(paths)

    def test_planned_total_inside_window_passes(self):
        result = self._validate()
        self.assertFalse([issue for issue in result.issues if issue.rule == "V-26"])

    def test_planned_total_below_minimum_fails(self):
        notes = self.lesson / "lecture_notes.md"
        notes.write_text(
            notes.read_text(encoding="utf-8").replace("3 秒", "1 秒"),
            encoding="utf-8",
        )
        result = self._validate()
        problems = [issue for issue in result.issues if issue.rule == "V-26"]
        self.assertTrue(problems)
        self.assertTrue(any(issue.level == "error" for issue in problems))

    def test_conflicting_legacy_total_fails(self):
        lesson = self.lesson / "lesson.yaml"
        lesson.write_text(
            lesson.read_text(encoding="utf-8").replace(
                "notes_total_seconds: null",
                "notes_total_seconds: 60",
            ),
            encoding="utf-8",
        )
        result = self._validate()
        problems = [issue for issue in result.issues if issue.rule == "V-26"]
        self.assertTrue(any("contradicts" in issue.message for issue in problems))

    def test_measured_without_meta_warns(self):
        lesson = self.lesson / "lesson.yaml"
        lesson.write_text(
            lesson.read_text(encoding="utf-8").replace(
                "  enabled: false\n  source: null",
                "  enabled: true\n  source: narration.wav\n  timing: measured",
            ),
            encoding="utf-8",
        )
        result = self._validate()
        problems = [issue for issue in result.issues if issue.rule == "V-26"]
        self.assertTrue(any(issue.level == "warning" for issue in problems))


if __name__ == "__main__":
    unittest.main()
