"""The storyboard gate must not lock out the capture that feeds it.

``capture_slides`` renders slides.md so the storyboard page has images to
review.  Before this rule the gate blocked it: the page needed captures to be
reviewable, and the build that produces captures needed a signed page.

``--capture-only`` is the single exception.  These tests pin that it (a) works
before sign-off, (b) does not manufacture approval evidence, (c) runs nothing
but the capture, and (d) cannot be mixed with flags that would blur what it
does.
"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import typer
import yaml

from course_control.authoring.llm import AuthoringError
from course_control.cli.lesson import build_command
from course_control.content.paths import LessonPaths
from course_control.content.validators import validate
from course_control.pipeline import BuildOptions, run_build
from course_control.rendering import adapters

SIGNOFF = Path("authoring/storyboard-review.json")


class CaptureOnlyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.ws = self.root / "ws"
        self.lesson = self.ws / "lessons" / "demo"
        (self.lesson / "assets").mkdir(parents=True)
        (self.lesson / "lesson.yaml").write_text(
            "schema_version: 1\nlesson_id: demo\ntitle_en: Demo\ntitle_zh: 演示\n"
            "status: draft\n"
            "content:\n  slides: slides.md\n  notes: lecture_notes.md\n"
            "  storyboard: storyboard.yaml\n  assets: assets/\n"
            "outputs:\n  fps: 30\n  resolution: [1920, 1080]\n"
            "  slides_canvas: [1280, 720]\n  animation_canvas: [1920, 1080]\n"
            "engines: [manim]\ncompose:\n  mode: deck\n"
            "duration:\n  profile: short\n  target_seconds: 720\n"
            "  min_seconds: 600\n  max_seconds: 900\n",
            encoding="utf-8",
        )
        (self.lesson / "slides.md").write_text(
            "<h1>Opening</h1>\n---\n<h2>Second page</h2>\n", encoding="utf-8"
        )
        (self.lesson / "lecture_notes.md").write_text(
            "### Slide 1: Opening\n\n- **时长预算**：60 秒\n- **动画切入**：无\n"
            "- **技术核查**：占位\n- **逐字口播**：\n\nplaceholder\n\n"
            "### Slide 2: Second page\n\n- **时长预算**：60 秒\n- **动画切入**：无\n"
            "- **技术核查**：占位\n- **逐字口播**：\n\nplaceholder\n",
            encoding="utf-8",
        )
        (self.lesson / "storyboard.yaml").write_text(
            "schema_version: 1\nlesson: demo\nshots:\n"
            "  - id: s1\n    slide: 1\n    engine: manim\n"
            "    scene: demo/scene.py::Demo\n    cue_seconds: 0\n"
            "    expected_duration_s: 8\n",
            encoding="utf-8",
        )
        scene = self.ws / "ManimSandbox" / "demo" / "scene.py"
        scene.parent.mkdir(parents=True)
        scene.write_text("class Demo:\n    pass\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _build(self, **kwargs):
        calls: list[Path] = []

        def fake_capture(paths):
            calls.append(paths.lesson_dir)
            from course_control.rendering.adapters.base import StageOutcome
            from course_control.content.contracts import Status

            return StageOutcome("capture_slides", Status.PASS)

        with mock.patch.object(adapters.slides, "capture_slides", fake_capture):
            report, _path = run_build(self.ws, self.lesson, BuildOptions(**kwargs))
        return report, calls

    def test_capture_only_runs_before_sign_off(self):
        report, calls = self._build(capture_only=True)
        stages = {stage.name: stage for stage in report.stages}
        self.assertEqual(len(calls), 1, "capture must run exactly once")
        self.assertEqual(stages["capture_slides"].status.value, "pass")
        self.assertFalse(
            (self.lesson / SIGNOFF).exists(),
            "capture must not create approval evidence of any kind",
        )

    def test_capture_only_defers_scene_and_duration_gates(self):
        (self.ws / "ManimSandbox" / "demo" / "scene.py").unlink()
        paths = LessonPaths.load(self.ws, self.lesson)

        full = validate(paths)
        self.assertTrue(any(issue.rule == "V-08" for issue in full.errors))
        self.assertTrue(any(issue.rule == "V-26" for issue in full.errors))

        static = validate(paths, capture_only=True)
        self.assertFalse(any(issue.rule == "V-08" for issue in static.errors))
        self.assertFalse(any(issue.rule == "V-26" for issue in static.errors))
        self.assertTrue(any("episode-duration gate" in issue.message for issue in static.warnings))

    def test_capture_only_still_rejects_missing_slide_assets(self):
        (self.lesson / "slides.md").write_text(
            '<img src="/lessons/demo/assets/missing.png">\n', encoding="utf-8"
        )
        paths = LessonPaths.load(self.ws, self.lesson)
        static = validate(paths, capture_only=True)
        self.assertTrue(any(issue.rule == "V-05" for issue in static.errors))

    def test_plain_build_is_still_blocked_without_a_signature(self):
        with self.assertRaises(AuthoringError):
            self._build()

    def test_capture_only_runs_nothing_else(self):
        report, _ = self._build(capture_only=True)
        stages = {stage.name: stage for stage in report.stages}
        self.assertIn("validate", stages)
        self.assertIn("capture_slides", stages)
        for later in (
            "render:motion_canvas",
            "render:manim",
            "render:blender",
            "render:code_video",
            "collect",
            "compose",
            "verify",
        ):
            self.assertIn(later, stages, f"{later} must be reported, not omitted")
            self.assertNotEqual(
                stages[later].status.value,
                "pass",
                f"{later} must not run under --capture-only",
            )
        self.assertEqual(stages["render:manim"].reason, "capture_only")

    def test_bound_lesson_without_plan_fails_before_capture(self):
        lesson_path = self.lesson / "lesson.yaml"
        lesson = yaml.safe_load(lesson_path.read_text(encoding="utf-8"))
        lesson["course_id"] = "demo-course"
        lesson["episode_id"] = "T1-01"
        lesson_path.write_text(
            yaml.safe_dump(lesson, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        config = self.root / "course-chain.yaml"
        config.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 2,
                    "courses": {
                        "demo-course": {
                            "expected_episode_count": 80,
                            "plan": "runtime/course-content/demo-course/COURSE_MAP-80.md",
                            "cards_dir": "runtime/course-content/demo-course/episodes",
                            "lessons_root": "lessons",
                            "forbidden_lesson_slugs": {},
                            "forbidden_slide_terms": [],
                        }
                    },
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        with mock.patch.dict(
            os.environ, {"COURSEWORKSPACE_CHAIN_CONFIG": str(config)}
        ):
            report, calls = self._build(capture_only=True)
        stages = {stage.name: stage for stage in report.stages}
        self.assertEqual(calls, [])
        self.assertEqual(stages["validate"].status.value, "not_run")
        self.assertEqual(stages["capture_slides"].status.value, "not_run")
        self.assertTrue(
            any(
                item.id == "V-48"
                and item.status.value == "fail"
                and "no 80-episode plan" in (item.actual or "")
                for item in report.checks
            )
        )

    def test_capture_only_rejects_conflicting_flags(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            with self.assertRaises(typer.Exit) as caught:
                build_command(
                    lesson="demo",
                    lesson_dir=self.lesson,
                    workspace=self.ws,
                    storyboard_source=None,
                    capture_only=True,
                    skip_compose=True,
                )
        self.assertEqual(caught.exception.exit_code, 2)
        self.assertIn("--capture-only runs capture_slides", err.getvalue())
        self.assertIn("--skip-compose", err.getvalue())


if __name__ == "__main__":
    unittest.main()
