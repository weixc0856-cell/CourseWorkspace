from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from course_control.paths import LessonPaths
from course_control.timeouts import resolve_timeout

LESSON = """schema_version: 1
lesson_id: demo
title_en: Demo
title_zh: 演示
status: draft
content:
  slides: slides.md
  notes: notes.md
  storyboard: storyboard.yaml
  assets: assets/
outputs:
  fps: 30
  resolution: [1920, 1080]
engines: [manim]
compose:
  mode: deck
duration:
  target_seconds: 1200
"""

STORYBOARD = """schema_version: 1
lesson: demo
shots:
- id: s1
  slide: 1
  engine: manim
  scene: demo.py::Demo
  cue_seconds: 0
"""


def make_paths(tmp: Path) -> LessonPaths:
    lesson_dir = tmp / "lessons" / "demo"
    lesson_dir.mkdir(parents=True)
    (lesson_dir / "lesson.yaml").write_text(LESSON, encoding="utf-8")
    (lesson_dir / "storyboard.yaml").write_text(STORYBOARD, encoding="utf-8")
    (tmp / "config").mkdir()
    return LessonPaths.load(tmp, lesson_dir)


class TimeoutTest(unittest.TestCase):
    def test_long_lessons_scale_the_runtime_bound_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_paths(Path(tmp))
            self.assertEqual(resolve_timeout(paths, "compose"), 3600)
            self.assertEqual(resolve_timeout(paths, "burn_subtitles"), 1800)
            self.assertEqual(resolve_timeout(paths, "render:manim"), 1800)

    def test_tools_yaml_override_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_paths(Path(tmp))
            (Path(tmp) / "config" / "tools.yaml").write_text(
                "timeouts:\n  compose: 7200\n  render:blender: 3600\n",
                encoding="utf-8",
            )
            self.assertEqual(resolve_timeout(paths, "compose"), 7200)
            self.assertEqual(resolve_timeout(paths, "render:blender"), 3600)

    def test_unknown_stage_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = make_paths(Path(tmp))
            with self.assertRaises(KeyError):
                resolve_timeout(paths, "no_such_stage")


if __name__ == "__main__":
    unittest.main()
