from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from course_control.contracts import Storyboard
from course_control.director import build as build_director
from course_control.paths import ContractError, LessonPaths
from course_control.pipeline import BuildOptions, run_build
from course_control.workspace_layout import lessons_root

WORKSPACE = Path(__file__).resolve().parents[2]
LESSON = lessons_root(WORKSPACE) / "01-transformer-demo"


@unittest.skipUnless(LESSON.is_dir(), "local lesson 01-transformer-demo not present")
class StoryboardOverrideTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        _, cls.paths = build_director(WORKSPACE, LESSON, root / "director")
        cls.override = cls.paths["storyboard"]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_override_loads_director_storyboard(self):
        paths = LessonPaths.load(WORKSPACE, LESSON, self.override)
        self.assertEqual(len(paths.storyboard.shots), 8)
        self.assertEqual(paths.storyboard_source, self.override.resolve())
        self.assertTrue(paths.selects("shot_003"))
        paths.selected_shot_ids = {"shot_003"}
        self.assertTrue(paths.selects("shot_003"))
        self.assertFalse(paths.selects("shot_004"))

    def test_override_must_match_lesson_id(self):
        payload = yaml.safe_load(self.override.read_text(encoding="utf-8"))
        Storyboard.model_validate(payload)
        payload["lesson"] = "another-lesson"
        bad = Path(self.tmp.name) / "bad-storyboard.yaml"
        bad.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        with self.assertRaises(ContractError):
            LessonPaths.load(WORKSPACE, LESSON, bad)

    def test_build_accepts_override_and_shot_filter(self):
        report, _ = run_build(
            WORKSPACE,
            LESSON,
            BuildOptions(
                skip_render=True,
                skip_compose=True,
                storyboard=self.override,
                shots=["shot_003"],
                build_root=Path(self.tmp.name) / "artifacts",
            ),
        )
        self.assertNotEqual(report.verdict, "pass")

    def test_unknown_shot_is_rejected(self):
        with self.assertRaises(ContractError):
            run_build(
                WORKSPACE,
                LESSON,
                BuildOptions(
                    skip_render=True,
                    skip_compose=True,
                    storyboard=self.override,
                    shots=["shot_999"],
                    build_root=Path(self.tmp.name) / "artifacts",
                ),
            )


if __name__ == "__main__":
    unittest.main()
