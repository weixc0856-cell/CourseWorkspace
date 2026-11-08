from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.audio_mix import bgm_source, mix_lesson
from course_control.contracts import Status
from course_control.media_qc import INCOMPLETE, _parse_srt, run_media_qc
from course_control.paths import LessonPaths
from course_control.quality import BLOCKED, INCOMPLETE as Q_INCOMPLETE, PASS, build_quality_report


LESSON_YAML = """schema_version: 1
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
  slides_canvas: [1280, 720]
  animation_canvas: [1920, 1080]
engines: [manim]
compose:
  mode: deck
  base_video: null
  renderer: timeline
subtitles:
  enabled: true
  render: burn_in
  top_language: en
  bottom_language: zh-Hans
authoring:
  script: authoring/narration.script.json
  approval: authoring/approval.json
duration:
  profile: standard
  target_seconds: 10
  min_seconds: 5
  max_seconds: 20
"""


class DemoCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        self.lesson_dir = self.workspace / "lessons" / "demo"
        (self.lesson_dir / "assets").mkdir(parents=True)
        (self.lesson_dir / "authoring").mkdir(parents=True)
        (self.lesson_dir / "lesson.yaml").write_text(LESSON_YAML, encoding="utf-8")
        for name in ("slides.md", "notes.md", "subtitles.srt"):
            (self.lesson_dir / name).write_text("", encoding="utf-8")
        (self.lesson_dir / "storyboard.yaml").write_text(
            """schema_version: 1
lesson: demo
shots:
- id: shot_001
  slide: 1
  engine: manim
  scene: demo.py::DemoScene
  cue_seconds: 5.0
""",
            encoding="utf-8",
        )
        (self.lesson_dir / "authoring" / "narration.script.json").write_text("{}", encoding="utf-8")
        (self.lesson_dir / "authoring" / "approval.json").write_text("{}", encoding="utf-8")
        self.paths = LessonPaths.load(self.workspace, self.lesson_dir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_bgm_source_uses_local_root(self) -> None:
        config = self.workspace / "config"
        config.mkdir()
        root = self.workspace / "music"
        root.mkdir()
        (root / "track.wav").write_bytes(b"RIFF")
        (config / "local-paths.yaml").write_text(f"bgm_root: {root.as_posix()}\n", encoding="utf-8")
        self.assertEqual(bgm_source(self.workspace, "bgm_track"), root / "track.wav")
        self.assertIsNone(bgm_source(self.workspace, "bgm_missing"))

    def test_mix_is_skipped_without_final_video(self) -> None:
        result = mix_lesson(self.workspace, self.paths)
        self.assertEqual(result.status, Status.SKIPPED)
        self.assertTrue(result.report_path.is_file())

    def test_media_qc_is_incomplete_without_video(self) -> None:
        report, target = run_media_qc(self.workspace, self.paths)
        self.assertEqual(report["status"], INCOMPLETE)
        self.assertTrue(target.is_file())

    def test_srt_parser_reads_cues(self) -> None:
        text = "1\n00:00:00,000 --> 00:00:01,500\nhello\n你好\n\n2\n00:00:02,000 --> 00:00:03,000\nworld\n世界\n"
        cues = _parse_srt(text)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0]["end_ms"], 1500)
        self.assertEqual(cues[1]["text"], "world\n世界")


class QualityReportTests(DemoCase):
    def _write(self, relative: str, payload: dict) -> None:
        path = self.paths.build_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_missing_reports_are_incomplete_not_pass(self) -> None:
        report, target = build_quality_report(self.workspace, self.paths)
        statuses = {item["id"]: item["status"] for item in report["dimensions"]}
        self.assertEqual(statuses["Q1"], Q_INCOMPLETE)
        self.assertEqual(statuses["Q2"], Q_INCOMPLETE)
        self.assertEqual(statuses["Q3"], Q_INCOMPLETE)
        self.assertEqual(statuses["Q4"], Q_INCOMPLETE)
        self.assertEqual(statuses["Q5"], BLOCKED)
        self.assertFalse(report["states"]["BUILD_PASS"])
        self.assertTrue(target.is_file())

    def test_build_pass_still_not_quality_pass(self) -> None:
        self._write("final/build-report.json", {"verdict": "pass", "stages": [{"name": "compose", "status": "pass"}]})
        self._write("quality/media-qc.json", {"status": PASS})
        final = self.paths.build_root / "final" / "course-video.mp4"
        final.write_bytes(b"fake")
        narration = self.paths.build_root / "narration" / "narration.wav"
        narration.parent.mkdir(parents=True, exist_ok=True)
        narration.write_bytes(b"fake")
        report, _ = build_quality_report(self.workspace, self.paths)
        self.assertEqual(report["dimensions"][3]["status"], PASS)
        self.assertTrue(report["states"]["BUILD_PASS"])
        self.assertFalse(report["states"]["QUALITY_PASS"])
        self.assertFalse(report["states"]["RELEASE_APPROVED"])


if __name__ == "__main__":
    unittest.main()
