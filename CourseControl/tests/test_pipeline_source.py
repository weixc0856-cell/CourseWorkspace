from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from course_control.content.paths import ContractError
from course_control.pipeline import BuildOptions, _validate_resume_from, storyboard_override


class StoryboardSourceTest(unittest.TestCase):
    def test_director_source_points_at_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            lesson_dir = workspace / "lessons" / "demo"
            lesson_dir.mkdir(parents=True)
            override = storyboard_override(
                workspace, lesson_dir, BuildOptions(storyboard_source="director")
            )
            self.assertEqual(
                override,
                workspace / "build" / "demo" / "director" / "storyboard.director.yaml",
            )

    def test_explicit_storyboard_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            lesson_dir = workspace / "lessons" / "demo"
            lesson_dir.mkdir(parents=True)
            explicit = lesson_dir / "custom.yaml"
            override = storyboard_override(
                workspace,
                lesson_dir,
                BuildOptions(storyboard=explicit, storyboard_source="director"),
            )
            self.assertEqual(override, explicit)

    def test_default_is_lesson_storyboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            lesson_dir = workspace / "lessons" / "demo"
            lesson_dir.mkdir(parents=True)
            self.assertIsNone(storyboard_override(workspace, lesson_dir, BuildOptions()))

    def test_resume_from_rejects_unknown_stage(self) -> None:
        with self.assertRaises(ContractError):
            _validate_resume_from("no-such-stage")
        _validate_resume_from("compose")
        _validate_resume_from(None)


if __name__ == "__main__":
    unittest.main()
