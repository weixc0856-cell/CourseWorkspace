from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

from course_control import separation, workspace_layout
from course_control.separation import audit

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
        self._lesson("01-transformer-demo")
        fixture = self.workspace / "BlenderStudio" / "tasks" / "01-transformer-demo"
        fixture.mkdir(parents=True)
        allowed = {"BlenderStudio/tasks/01-transformer-demo": "check.ps1 fixture"}
        with patch.dict(separation.ALLOWED, allowed, clear=True):
            report = audit(self.workspace)
        self.assertEqual(report["problems"], [])
        entry = report["entries"][0]
        self.assertTrue(entry["allowed"])
        self.assertEqual(entry["reason"], "check.ps1 fixture")

    def test_an_empty_allowlist_makes_every_lesson_directory_a_problem(self) -> None:
        self._lesson("01-transformer-demo")
        (self.workspace / "BlenderStudio" / "tasks" / "01-transformer-demo").mkdir(parents=True)
        self.assertEqual(audit(self.workspace)["problems"], ["BlenderStudio/tasks/01-transformer-demo"])

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


if __name__ == "__main__":
    unittest.main()
