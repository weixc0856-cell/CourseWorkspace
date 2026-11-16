from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import typer

from course_control.cli.producer import release_approve_command

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

PASS_CHECK = {
    "status": "pass",
    "steps": [{"id": "media_qc", "status": "pass", "detail": "ok"}],
    "approval_problems": [],
}


class ReleaseApproveTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        self.lesson_parent = self.workspace / "lessons"
        self.lesson_dir = self.lesson_parent / "demo"
        (self.lesson_dir / "assets").mkdir(parents=True)
        (self.lesson_dir / "authoring").mkdir()
        (self.lesson_dir / "lesson.yaml").write_text(LESSON, encoding="utf-8")
        (self.lesson_dir / "slides.md").write_text("# Demo\n", encoding="utf-8")
        (self.lesson_dir / "notes.md").write_text("### Slide 1\n", encoding="utf-8")
        (self.lesson_dir / "storyboard.yaml").write_text(STORYBOARD, encoding="utf-8")
        (self.lesson_dir / "subtitles.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nHello\n你好\n", encoding="utf-8"
        )
        (self.lesson_dir / "authoring" / "approval.json").write_text(
            "{}", encoding="utf-8"
        )
        build = self.workspace / "build" / "demo"
        (build / "final").mkdir(parents=True)
        (build / "quality").mkdir(parents=True)
        (build / "narration").mkdir(parents=True)
        (build / "narration" / "narration.wav").write_bytes(b"RIFF")
        (build / "quality" / "media-qc.json").write_text(
            '{"status": "PASS"}', encoding="utf-8"
        )
        (build / "final" / "build-report.json").write_text(
            '{"verdict": "pass"}', encoding="utf-8"
        )
        (build / "final" / "course-video.mp4").write_bytes(b"film")
        self.build = build
        self._env = patch.dict(
            os.environ,
            {
                "COURSEWORKSPACE_MODE": "production",
                "COURSEWORKSPACE_CONTENT_ROOT": str(self.workspace),
            },
            clear=False,
        )
        self._env.start()
        self.addCleanup(self._env.stop)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, **overrides):
        kwargs = dict(
            lesson="demo",
            project=None,
            lesson_dir=self.lesson_parent,
            workspace=self.workspace,
            stage="review",
            approved_by="alice",
            decision="approved",
            note="",
        )
        kwargs.update(overrides)
        with patch(
            "course_control.authoring.pipeline.assert_storyboard_signed"
        ):
            try:
                release_approve_command(**kwargs)
            except typer.Exit as exc:
                return exc.exit_code
        return None

    def _approval(self, stage: str) -> dict:
        path = self.build / "quality" / f"{stage}-approval.json"
        self.assertTrue(path.is_file(), path)
        return json.loads(path.read_text(encoding="utf-8"))

    def _content_sha(self) -> str:
        report = json.loads(
            (self.build / "quality" / "quality-report.json").read_text("utf-8")
        )
        return report["content_sha256"]

    def test_review_then_release_then_content_hash_is_stable(self) -> None:
        with patch(
            "course_control.release.check.run_release_check",
            return_value=PASS_CHECK,
        ) as check:
            self.assertEqual(self._run(stage="review"), 0)
            self.assertEqual(check.call_count, 1)
            self.assertEqual(check.call_args.kwargs["paths"].slug, "demo")
            review = self._approval("review")
            self.assertEqual(review["lesson"], "demo")
            self.assertEqual(review["stage"], "review")
            self.assertEqual(review["approved_by"], "alice")
            first_sha = self._content_sha()

            self.assertEqual(self._run(stage="release", approved_by="bob"), 0)
            release = self._approval("release")
            self.assertEqual(release["stage"], "release")
            self.assertEqual(release["approved_by"], "bob")
            self.assertEqual(self._content_sha(), first_sha)

    def test_refuses_when_the_full_chain_is_incomplete(self) -> None:
        with patch(
            "course_control.release.check.run_release_check",
            return_value={
                "status": "incomplete",
                "steps": [
                    {"id": "media_qc", "status": "incomplete", "detail": "missing"}
                ],
            },
        ):
            self.assertEqual(self._run(stage="review"), 2)
        self.assertFalse((self.build / "quality" / "review-approval.json").exists())

    def test_release_needs_a_valid_named_review(self) -> None:
        with patch(
            "course_control.release.check.run_release_check",
            return_value=PASS_CHECK,
        ):
            self.assertEqual(self._run(stage="release"), 2)
        self.assertFalse((self.build / "quality" / "release-approval.json").exists())

    def test_review_signed_by_a_machine_does_not_release(self) -> None:
        with patch(
            "course_control.release.check.run_release_check",
            return_value=PASS_CHECK,
        ):
            self.assertEqual(self._run(stage="review"), 0)
            payload = json.loads(
                (self.build / "quality" / "review-approval.json").read_text("utf-8")
            )
            payload["approved_by"] = "human"
            (self.build / "quality" / "review-approval.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            self.assertEqual(self._run(stage="release"), 2)
        self.assertFalse((self.build / "quality" / "release-approval.json").exists())

    def test_machine_approver_is_refused_before_the_chain(self) -> None:
        with patch(
            "course_control.release.check.run_release_check",
            return_value=PASS_CHECK,
        ) as check:
            self.assertEqual(self._run(stage="review", approved_by="owner"), 1)
        self.assertEqual(check.call_count, 0)
        self.assertFalse((self.build / "quality" / "review-approval.json").exists())

    def test_rejection_is_recorded_without_running_the_chain(self) -> None:
        with patch(
            "course_control.release.check.run_release_check",
            return_value=PASS_CHECK,
        ) as check:
            self.assertEqual(
                self._run(stage="review", decision="rejected", approved_by="alice"), 0
            )
        self.assertEqual(check.call_count, 0)
        record = self._approval("review")
        self.assertEqual(record["decision"], "rejected")


if __name__ == "__main__":
    unittest.main()
