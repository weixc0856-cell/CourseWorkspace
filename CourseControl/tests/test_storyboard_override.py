from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from course_control.content.contracts import Storyboard
from course_control.direction import build as build_director
from course_control.content.paths import ContractError, LessonPaths
from course_control.pipeline import BuildOptions, run_build
from ._local_lesson import LOCAL, REASON

WORKSPACE = Path(__file__).resolve().parents[2]
LESSON = LOCAL.path if LOCAL is not None else None


@unittest.skipUnless(LOCAL is not None, REASON)
class StoryboardOverrideTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        _, cls.paths = build_director(WORKSPACE, LESSON, root / "director")
        cls.override = cls.paths["storyboard"]
        cls.shot_ids = [
            shot.id
            for shot in LessonPaths.load(WORKSPACE, LESSON, cls.override).storyboard.shots
        ]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_override_loads_director_storyboard(self):
        paths = LessonPaths.load(WORKSPACE, LESSON, self.override)
        self.assertGreater(len(paths.storyboard.shots), 0)
        self.assertEqual(paths.storyboard_source, self.override.resolve())
        first, other = self.shot_ids[0], self.shot_ids[1]
        self.assertTrue(paths.selects(first))
        paths.selected_shot_ids = {first}
        self.assertTrue(paths.selects(first))
        self.assertFalse(paths.selects(other))

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
                shots=[self.shot_ids[0]],
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
