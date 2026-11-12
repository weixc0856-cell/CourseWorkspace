from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.platform.config_resolve import (
    blocking_conflicts,
    resolve_config,
    write_snapshot,
)
from course_control.content.paths import LessonPaths

LESSON = """schema_version: 1
lesson_id: demo
title_en: Demo
title_zh: 演示
status: draft
content:
  slides: slides.md
  notes: notes.md
  outline: null
  storyboard: storyboard.yaml
  assets: assets/
  subtitles: subtitles.srt
outputs:
  fps: 30
  resolution: [1920, 1080]
engines: [manim]
compose:
  mode: scene
narration:
  enabled: true
  timing: measured
subtitles:
  enabled: true
  bilingual: true
audio:
  content_kind: formal_course
duration:
  target_seconds: 10
  min_seconds: 5
  max_seconds: 30
"""

STORYBOARD = """schema_version: 1
lesson: demo
shots:
  - id: s1
    slide: 1
    engine: manim
    scene: scenes/demo.py
    cue_seconds: 0
"""


def make_workspace(tmp: str, *, lesson_extra: str = "", srt: str | None = None) -> tuple[Path, LessonPaths]:
    workspace = Path(tmp)
    lesson_dir = workspace / "lessons" / "demo"
    lesson_dir.mkdir(parents=True)
    (lesson_dir / "lesson.yaml").write_text(LESSON + lesson_extra, encoding="utf-8")
    (lesson_dir / "storyboard.yaml").write_text(STORYBOARD, encoding="utf-8")
    (lesson_dir / "slides.md").write_text("# Slides\n", encoding="utf-8")
    (lesson_dir / "notes.md").write_text("### Slide 1\n时长预算：10 秒\n", encoding="utf-8")
    if srt is not None:
        (lesson_dir / "subtitles.srt").write_text(srt, encoding="utf-8")
    config = workspace / "config"
    config.mkdir()
    (config / "model-routing.yaml").write_text(
        "remote:\n  enabled: true\n  provider: deepseek\n  model: deepseek-flash\n",
        encoding="utf-8",
    )
    paths = LessonPaths.load(workspace, lesson_dir)
    return workspace, paths


class ConfigResolveTest(unittest.TestCase):
    def test_values_record_their_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, paths = make_workspace(tmp)
            report = resolve_config(workspace, paths)
            values = {item["key"]: item for item in report["values"]}
            self.assertEqual(values["compose.mode"]["value"], "scene")
            self.assertEqual(
                values["compose.mode"]["source"], "lessons/demo/lesson.yaml"
            )
            self.assertEqual(
                values["model-routing.remote"]["value"]["provider"], "deepseek"
            )
            self.assertTrue(report["fingerprint"])
            self.assertEqual(blocking_conflicts(report), [])

    def test_fingerprint_changes_when_lesson_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, paths = make_workspace(tmp)
            first = resolve_config(workspace, paths)
            lesson = paths.lesson_dir / "lesson.yaml"
            lesson.write_text(
                lesson.read_text(encoding="utf-8").replace("target_seconds: 10", "target_seconds: 11"),
                encoding="utf-8",
            )
            paths = LessonPaths.load(workspace, paths.lesson_dir)
            second = resolve_config(workspace, paths)
            self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_bilingual_declaration_must_match_srt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            srt = "1\n00:00:00,000 --> 00:00:02,000\n只有中文\n"
            workspace, paths = make_workspace(tmp, srt=srt)
            report = resolve_config(workspace, paths)
            codes = {item["code"] for item in blocking_conflicts(report)}
            self.assertIn("subtitle_language_mismatch", codes)

    def test_formal_course_must_not_declare_bgm(self) -> None:
        extra = """
audio:
  content_kind: formal_course
  bgm:
    - track_id: bgm_demo
      start_s: 0
      end_s: 5
      license_status: public_domain
      commercial_allowed: true
"""
        with tempfile.TemporaryDirectory() as tmp:
            workspace, paths = make_workspace(tmp, lesson_extra=extra)
            report = resolve_config(workspace, paths)
            codes = {item["code"] for item in blocking_conflicts(report)}
            self.assertIn("bgm_policy_violation", codes)

    def test_deepseek_pro_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, paths = make_workspace(tmp)
            (workspace / "config" / "model-routing.yaml").write_text(
                "remote:\n  enabled: true\n  provider: deepseek\n  model: deepseek-v4-pro\n",
                encoding="utf-8",
            )
            report = resolve_config(workspace, paths)
            codes = {item["code"] for item in blocking_conflicts(report)}
            self.assertIn("deepseek_model_pinned", codes)

    def test_snapshot_is_written_under_build_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace, paths = make_workspace(tmp)
            report = resolve_config(workspace, paths)
            path = write_snapshot(paths, report)
            self.assertTrue(path.is_file())
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8"))["fingerprint"],
                report["fingerprint"],
            )
            self.assertEqual(path.parent, paths.build_root / "logs")


if __name__ == "__main__":
    unittest.main()
