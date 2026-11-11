from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from course_control.package import PackageError, build_package, verify_package
from course_control.paths import LessonPaths

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
  resolution: [64, 64]
  slides_canvas: [64, 64]
  animation_canvas: [64, 64]
engines: [manim]
compose:
  mode: deck
narration:
  enabled: true
  source: narration.wav
subtitles:
  enabled: true
  render: burn_in
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


class PackageTest(unittest.TestCase):
    def setUp(self) -> None:
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg is not available")
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        self.lesson_dir = self.workspace / "lessons" / "demo"
        (self.lesson_dir / "assets").mkdir(parents=True)
        (self.lesson_dir / "lesson.yaml").write_text(LESSON, encoding="utf-8")
        (self.lesson_dir / "slides.md").write_text("# Demo\n", encoding="utf-8")
        (self.lesson_dir / "notes.md").write_text("### Slide 1\n", encoding="utf-8")
        (self.lesson_dir / "storyboard.yaml").write_text(STORYBOARD, encoding="utf-8")
        (self.lesson_dir / "subtitles.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nHello\n你好\n", encoding="utf-8"
        )
        build = self.workspace / "build" / "demo"
        (build / "final").mkdir(parents=True)
        (build / "quality").mkdir(parents=True)
        (build / "narration").mkdir(parents=True)
        (build / "review").mkdir(parents=True)
        (build / "logs").mkdir(parents=True)
        (build / "narration" / "narration.wav").write_bytes(b"RIFF")
        (build / "narration" / "narration.meta.json").write_text("{}", encoding="utf-8")
        (build / "quality" / "media-qc.json").write_text('{"status": "PASS"}', encoding="utf-8")
        (build / "review" / "review.json").write_text('{"status": "completed"}', encoding="utf-8")
        (build / "logs" / "build.log").write_text("ok\n", encoding="utf-8")
        (build / "final" / "build-report.json").write_text(
            json.dumps({"verdict": "pass", "run_id": "run-1"}), encoding="utf-8"
        )
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=white:s=64x64:d=1:r=30",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(build / "final" / "course-video.mp4"),
            ],
            check=True,
        )
        self.paths = LessonPaths.load(self.workspace, self.lesson_dir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_package_collects_and_hashes(self) -> None:
        manifest, root = build_package(self.paths)
        self.assertEqual(root, self.workspace / "deliver" / "demo")
        self.assertEqual(manifest["run_id"], "run-1")
        self.assertEqual(manifest["verdict"], "pass")
        paths = {item["path"]: item for item in manifest["files"]}
        self.assertEqual(paths["final/master.mp4"]["status"], "present")
        self.assertEqual(paths["final/subtitles.srt"]["status"], "present")
        self.assertEqual(paths["review/review.json"]["status"], "present")
        self.assertTrue((root / "metadata.json").is_file())
        self.assertTrue((root / "delivery-checklist.md").is_file())
        self.assertEqual(verify_package(root), [])

    def test_missing_master_fails(self) -> None:
        (self.paths.build_root / "final" / "course-video.mp4").unlink()
        with self.assertRaises(PackageError):
            build_package(self.paths)

    def test_failed_rebuild_keeps_the_previous_package(self) -> None:
        manifest, root = build_package(self.paths)
        before = {item["path"]: item.get("sha256") for item in manifest["files"]}
        (self.paths.build_root / "final" / "course-video.mp4").unlink()
        with self.assertRaises(PackageError):
            build_package(self.paths)
        self.assertTrue((root / "manifest.json").is_file())
        self.assertEqual(verify_package(root), [])
        after = {
            item["path"]: item.get("sha256")
            for item in json.loads(
                (root / "manifest.json").read_text(encoding="utf-8")
            )["files"]
        }
        self.assertEqual(before["final/master.mp4"], after["final/master.mp4"])

    def test_tampered_package_is_detected(self) -> None:
        manifest, root = build_package(self.paths)
        target = root / "metadata.json"
        target.write_text("{}", encoding="utf-8")
        problems = verify_package(root)
        self.assertTrue(any("hash mismatch" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
