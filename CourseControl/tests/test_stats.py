from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.paths import LessonPaths
from course_control.stats import lesson_stats

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
  subtitles: subtitles.srt
outputs:
  fps: 30
  resolution: [1920, 1080]
engines: [manim]
compose:
  mode: deck
narration:
  enabled: true
subtitles:
  enabled: true
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

SRT = """1
00:00:00,000 --> 00:00:02,000
Hello
你好

2
00:00:02,100 --> 00:00:04,000
World
世界
"""


class StatsTest(unittest.TestCase):
    def test_counts_come_from_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            lesson_dir = workspace / "lessons" / "demo"
            build = workspace / "build" / "demo"
            lesson_dir.mkdir(parents=True)
            (build / "narration").mkdir(parents=True)
            (build / "quality").mkdir(parents=True)
            (lesson_dir / "lesson.yaml").write_text(LESSON, encoding="utf-8")
            (lesson_dir / "storyboard.yaml").write_text(STORYBOARD, encoding="utf-8")
            (lesson_dir / "slides.md").write_text(
                "## One\n\n---\n\n## Two\n\n---\n\n## Three\n", encoding="utf-8"
            )
            (lesson_dir / "notes.md").write_text("### Slide 1\n", encoding="utf-8")
            (lesson_dir / "subtitles.srt").write_text(SRT, encoding="utf-8")
            (build / "narration" / "narration.meta.json").write_text(
                json.dumps(
                    {
                        "pages": [{"end_s": 4.0}],
                        "segments": [{"end_s": 2.0}, {"end_s": 4.0}],
                    }
                ),
                encoding="utf-8",
            )
            (build / "quality" / "media-qc.json").write_text(
                '{"status": "WARN"}', encoding="utf-8"
            )
            paths = LessonPaths.load(workspace, lesson_dir)
            report = lesson_stats(paths)
            self.assertEqual(report["counts"]["pages"], 3)
            self.assertEqual(report["counts"]["storyboard_shots"], 1)
            self.assertEqual(report["counts"]["audio_assets"], 2)
            self.assertEqual(report["counts"]["subtitle_cues"], 2)
            self.assertEqual(report["duration_seconds"], 4.0)
            self.assertEqual(report["status"]["media_qc"], "WARN")


if __name__ == "__main__":
    unittest.main()
