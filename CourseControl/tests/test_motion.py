from __future__ import annotations

import unittest
from pathlib import Path

from course_control.content.contracts import MotionPolicy
from course_control.rendering.motion import slide_motion
from course_control.content.paths import LessonPaths
from course_control.platform.workspace_layout import lessons_root

WORKSPACE = Path(__file__).resolve().parents[2]
LESSON = lessons_root(WORKSPACE) / "01-transformer-demo"


@unittest.skipUnless(LESSON.is_dir(), "local lesson 01-transformer-demo not present")
class SlideMotionTest(unittest.TestCase):
    def test_static_policy_returns_none(self):
        self.assertIsNone(slide_motion(1, MotionPolicy(slides="static")))

    def test_ken_burns_is_deterministic_and_bounded(self):
        policy = MotionPolicy()
        first = slide_motion(3, policy)
        second = slide_motion(3, policy)
        self.assertEqual(first, second)
        self.assertEqual(first["kind"], "ken_burns")
        self.assertGreaterEqual(min(first["scale_from"], first["scale_to"]), 1.0)
        self.assertLessEqual(max(first["scale_from"], first["scale_to"]), 1.12)
        for key in ("pan_x_from", "pan_x_to", "pan_y_from", "pan_y_to"):
            self.assertLessEqual(abs(first[key]), policy.pan_percent)

    def test_patterns_vary_between_slides(self):
        policy = MotionPolicy()
        specs = [slide_motion(index, policy) for index in range(1, 5)]
        self.assertGreaterEqual(len({spec["scale_from"] for spec in specs}), 2)
        self.assertEqual(len({tuple(spec.items()) for spec in specs}), 4)

    def test_lesson_opts_into_ken_burns(self):
        paths = LessonPaths.load(WORKSPACE, LESSON)
        self.assertEqual(paths.lesson.motion.slides, "ken_burns")
        self.assertEqual(paths.lesson.motion.scale, 1.06)


if __name__ == "__main__":
    unittest.main()
