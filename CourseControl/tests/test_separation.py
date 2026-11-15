from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

from course_control.platform import separation, workspace_layout
from course_control.platform.separation import audit

ENV = workspace_layout.ENV_VAR


class SeparationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.workspace = base / "Program"
        self.content = base / "CourseContent"
        self.workspace.mkdir()
        self.content.mkdir()
        (self.content / "lessons").mkdir()
        self._previous = os.environ.get(ENV)
        os.environ[ENV] = str(self.content)
        workspace_layout.reset_cache()

    def tearDown(self) -> None:
        if self._previous is None:
            os.environ.pop(ENV, None)
        else:
            os.environ[ENV] = self._previous
        workspace_layout.reset_cache()
        self._tmp.cleanup()

    def _lesson(self, slug: str) -> None:
        (self.content / "lessons" / slug).mkdir(parents=True)

    def test_without_a_content_root_the_check_is_off(self) -> None:
        os.environ.pop(ENV, None)
        workspace_layout.reset_cache()
        report = audit(self.workspace)
        self.assertFalse(report["configured"])
        self.assertEqual(report["entries"], [])

    def test_lesson_directory_inside_the_workspace_is_reported(self) -> None:
        self._lesson("lesson-x")
        (self.workspace / "ManimSandbox" / "lesson-x").mkdir(parents=True)
        report = audit(self.workspace)
        self.assertEqual(report["problems"], ["ManimSandbox/lesson-x"])

    def test_declared_fixture_is_allowed_with_its_reason(self) -> None:
        self._lesson("demo-lesson")
        fixture = self.workspace / "BlenderStudio" / "tasks" / "demo-lesson"
        fixture.mkdir(parents=True)
        allowed = {"BlenderStudio/tasks/demo-lesson": "a fixture with a lesson-shaped name"}
        with patch.dict(separation.ALLOWED, allowed, clear=True):
            report = audit(self.workspace)
        self.assertEqual(report["problems"], [])
        entry = report["entries"][0]
        self.assertTrue(entry["allowed"])
        self.assertEqual(entry["reason"], "a fixture with a lesson-shaped name")

    def test_an_empty_allowlist_makes_every_lesson_directory_a_problem(self) -> None:
        self._lesson("demo-lesson")
        (self.workspace / "BlenderStudio" / "tasks" / "demo-lesson").mkdir(parents=True)
        self.assertEqual(audit(self.workspace)["problems"], ["BlenderStudio/tasks/demo-lesson"])

    def test_lessons_in_the_content_root_are_not_reported(self) -> None:
        self._lesson("lesson-x")
        report = audit(self.workspace)
        self.assertEqual(report["entries"], [])
        self.assertEqual(report["lessons"], 1)

    def test_docs_only_carries_prose_and_contracts(self) -> None:
        docs = self.workspace / "docs"
        (docs / "contracts").mkdir(parents=True)
        (docs / "note.md").write_text("prose", encoding="utf-8")
        (docs / "audit.yaml").write_text("k: v", encoding="utf-8")
        (docs / "contracts" / "x.schema.json").write_text("{}", encoding="utf-8")
        self.assertEqual(audit(self.workspace)["docs_data"], [])
        (docs / "reference.json").write_text("{}", encoding="utf-8")
        self.assertEqual(audit(self.workspace)["docs_data"], ["docs/reference.json"])

    def test_junction_is_skipped_because_the_bytes_are_elsewhere(self) -> None:
        self._lesson("lesson-x")
        target = self.content / "engines" / "motion_canvas" / "scenes" / "lesson-x"
        target.mkdir(parents=True)
        link = self.workspace / "MotionStudio" / "src" / "scenes" / "lesson-x"
        link.parent.mkdir(parents=True)
        made = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        if made.returncode != 0:
            self.skipTest("junctions are not available here")
        try:
            report = audit(self.workspace)
            self.assertEqual(report["entries"], [])
        finally:
            link.rmdir()


    def test_media_file_in_the_workspace_is_reported(self) -> None:
        self._lesson("lesson-x")
        media = self.workspace / "RemotionStudio" / "public" / "chapter"
        media.mkdir(parents=True)
        (media / "x.png").write_bytes(b"png")
        report = audit(self.workspace)
        self.assertIn("RemotionStudio/public/chapter/x.png", report["media_problems"])
        self.assertIn("RemotionStudio/public/chapter/x.png", report["problems"])

    def test_render_output_directory_with_media_is_reported(self) -> None:
        self._lesson("lesson-x")
        target = self.workspace / "RemotionStudio" / "out" / "frames"
        target.mkdir(parents=True)
        (target / "1.png").write_bytes(b"png")
        report = audit(self.workspace)
        self.assertIn("RemotionStudio/out", report["output_dir_problems"])
        self.assertIn("RemotionStudio/out", report["problems"])

    def test_gitignore_does_not_whitelist_media(self) -> None:
        self._lesson("lesson-x")
        (self.workspace / ".gitignore").write_text("RemotionStudio/public/chapter/" + chr(10), encoding="utf-8")
        media = self.workspace / "RemotionStudio" / "public" / "chapter"
        media.mkdir(parents=True)
        (media / "x.png").write_bytes(b"png")
        self.assertIn("RemotionStudio/public/chapter/x.png", audit(self.workspace)["media_problems"])

    def test_declared_media_is_allowed_with_its_reason(self) -> None:
        self._lesson("lesson-x")
        fixture = self.workspace / "CourseControl" / "tests" / "fixtures"
        fixture.mkdir(parents=True)
        (fixture / "frame.png").write_bytes(b"png")
        allowed = {"CourseControl/tests/fixtures": "test fixtures"}
        with patch.dict(separation.MEDIA_ALLOWED, allowed, clear=True):
            report = audit(self.workspace)
        self.assertEqual(report["media_problems"], [])
        entry = next(item for item in report["media"] if item["path"].endswith("frame.png"))
        self.assertTrue(entry["allowed"])
        self.assertEqual(entry["reason"], "test fixtures")

    def test_staging_area_is_allowed_by_default(self) -> None:
        self._lesson("lesson-x")
        staged = self.workspace / "RemotionStudio" / "public" / "staging" / "lesson-x"
        staged.mkdir(parents=True)
        (staged / "clip.mp4").write_bytes(b"mp4")
        report = audit(self.workspace)
        self.assertEqual(report["media_problems"], [])
        self.assertEqual(report["problems"], [])


if __name__ == "__main__":
    unittest.main()
