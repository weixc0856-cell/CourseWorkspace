from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.paths import LessonPaths
from course_control.plan_audit import audit_plan

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
  slides_canvas: [1280, 720]
  animation_canvas: [1920, 1080]
engines: [manim]
compose:
  mode: deck
"""

STORYBOARD = """schema_version: 1
lesson: demo
shots:
- id: shot_001
  slide: 1
  engine: manim
  scene: demo.py::DemoScene
  cue_seconds: 0.0
"""

BEATS = """schema_version: 1
lesson: demo
palette: editorial
subtitle_safe_below: -2.2
shots:
- id: a
  segment: 1
  start: 0.0
  end: 0.5
  engine: manim
  beats:
  - {at: 0.1, kind: reveal, action: first change}
  - {at: 0.5, kind: reveal, action: second change}
- id: b
  segment: 1
  start: 0.5
  end: 1.0
  engine: manim
  beats:
  - {at: 0.1, kind: reveal, action: first change}
  - {at: 0.5, kind: reveal, action: second change}
"""


class PlanAuditTest(unittest.TestCase):
    def test_reports_counts_and_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            lesson_dir = workspace / "lessons" / "demo"
            (lesson_dir / "assets").mkdir(parents=True)
            (lesson_dir / "authoring").mkdir(parents=True)
            (lesson_dir / "lesson.yaml").write_text(LESSON, encoding="utf-8")
            (lesson_dir / "slides.md").write_text("", encoding="utf-8")
            (lesson_dir / "notes.md").write_text("", encoding="utf-8")
            (lesson_dir / "storyboard.yaml").write_text(STORYBOARD, encoding="utf-8")
            (lesson_dir / "authoring" / "beats.yaml").write_text(BEATS, encoding="utf-8")
            director = workspace / "build" / "demo" / "director"
            director.mkdir(parents=True)
            (director / "director_plan.json").write_text(
                json.dumps({"shots": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}),
                encoding="utf-8",
            )
            paths = LessonPaths.load(workspace, lesson_dir)
            report = audit_plan(paths)
        self.assertEqual(report["authority"], "storyboard.yaml")
        self.assertEqual(report["counts"]["storyboard"], 1)
        self.assertEqual(report["counts"]["beats"], 2)
        self.assertEqual(report["counts"]["director"], 3)
        self.assertIn("beats", report["mismatches"])
        self.assertIn("director", report["mismatches"])


if __name__ == "__main__":
    unittest.main()
