from __future__ import annotations

import unittest

from pydantic import ValidationError

from course_control.content.contracts import LessonConfig
from course_control.content.duration import (
    PROFILES,
    duplicate_authority_problem,
    frame_tolerance,
    planned_problems,
    resolve,
    window_problem,
)


def make_lesson(duration: dict | None = None, acceptance: dict | None = None) -> LessonConfig:
    payload = {
        "schema_version": 1,
        "lesson_id": "duration-fixture",
        "title_en": "Duration fixture",
        "title_zh": "时长夹具",
        "status": "draft",
        "content": {
            "slides": "slides.md",
            "notes": "lecture_notes.md",
            "storyboard": "storyboard.yaml",
            "assets": "assets/",
        },
        "outputs": {"fps": 30, "resolution": [1920, 1080]},
        "engines": ["manim"],
        "compose": {"mode": "deck"},
        "acceptance": acceptance or {},
    }
    if duration is not None:
        payload["duration"] = duration
    return LessonConfig.model_validate(payload)


class ProfileTest(unittest.TestCase):
    def test_standard_defaults(self):
        policy = resolve(make_lesson({"profile": "standard"}))
        self.assertIsNotNone(policy)
        self.assertEqual(policy.target, PROFILES["standard"]["target"])
        self.assertEqual(policy.minimum, PROFILES["standard"]["min"])
        self.assertEqual(policy.maximum, PROFILES["standard"]["max"])

    def test_short_defaults(self):
        policy = resolve(make_lesson({"profile": "short"}))
        self.assertEqual(policy.target, 720.0)
        self.assertEqual(policy.minimum, 600.0)

    def test_news_has_no_minimum(self):
        policy = resolve(make_lesson({"profile": "news"}))
        self.assertEqual(policy.minimum, 0.0)
        self.assertIsNone(window_problem(5.0, policy))

    def test_no_policy_returns_none(self):
        self.assertIsNone(resolve(make_lesson()))

    def test_explicit_override(self):
        policy = resolve(
            make_lesson(
                {
                    "profile": "standard",
                    "target_seconds": 600,
                    "min_seconds": 500,
                    "max_seconds": 700,
                    "page_tolerance_seconds": 2.5,
                }
            )
        )
        self.assertEqual(policy.target, 600.0)
        self.assertEqual(policy.minimum, 500.0)
        self.assertEqual(policy.maximum, 700.0)
        self.assertEqual(policy.page_tolerance, 2.5)


class WindowTest(unittest.TestCase):
    def test_below_minimum(self):
        policy = resolve(make_lesson({"profile": "standard"}))
        problem = window_problem(900.0, policy)
        self.assertIsNotNone(problem)
        self.assertEqual(problem.level, "error")
        self.assertIn("below minimum", problem.message)

    def test_above_maximum(self):
        policy = resolve(make_lesson({"profile": "standard"}))
        problem = window_problem(1500.0, policy)
        self.assertIsNotNone(problem)
        self.assertIn("exceeds maximum", problem.message)

    def test_inside_window(self):
        policy = resolve(make_lesson({"profile": "standard"}))
        self.assertIsNone(window_problem(1200.0, policy))

    def test_tolerance_is_one_sided(self):
        policy = resolve(make_lesson({"profile": "standard", "page_tolerance_seconds": 1.5}))
        self.assertIsNone(window_problem(1078.6, policy))
        self.assertIsNotNone(window_problem(1078.0, policy))

    def test_frame_tolerance(self):
        policy = resolve(make_lesson({"profile": "standard"}))
        self.assertAlmostEqual(frame_tolerance(policy, 30), 1 / 30)


class PlannedTest(unittest.TestCase):
    def test_planned_total_inside_window(self):
        policy = resolve(make_lesson({"profile": "standard"}))
        self.assertEqual(planned_problems(1200.0, policy), [])

    def test_planned_below_minimum_is_error(self):
        policy = resolve(make_lesson({"profile": "standard"}))
        problems = planned_problems(900.0, policy)
        self.assertTrue(any(problem.level == "error" for problem in problems))

    def test_planned_target_drift_is_warning(self):
        policy = resolve(make_lesson({"profile": "standard"}))
        problems = planned_problems(1150.0, policy)
        self.assertTrue(all(problem.level == "warning" for problem in problems))
        self.assertTrue(any("below" in problem.message for problem in problems))


class DuplicateAuthorityTest(unittest.TestCase):
    def test_matching_legacy_total_is_allowed(self):
        policy = resolve(make_lesson({"profile": "standard"}, {"notes_total_seconds": 1200}))
        self.assertIsNone(duplicate_authority_problem(make_lesson(
            {"profile": "standard"}, {"notes_total_seconds": 1200}
        ), policy))

    def test_conflicting_legacy_total_is_error(self):
        lesson = make_lesson({"profile": "standard"}, {"notes_total_seconds": 1870})
        policy = resolve(lesson)
        problem = duplicate_authority_problem(lesson, policy)
        self.assertIsNotNone(problem)
        self.assertEqual(problem.level, "error")


class ContractValidationTest(unittest.TestCase):
    def test_invalid_window_rejected(self):
        with self.assertRaises(ValidationError):
            make_lesson(
                {
                    "profile": "standard",
                    "target_seconds": 1200,
                    "min_seconds": 1300,
                }
            )

    def test_new_fields_are_optional_for_legacy_lessons(self):
        lesson = make_lesson()
        self.assertIsNone(lesson.duration)
        self.assertEqual(lesson.narration.timing, "planned")
        self.assertEqual(lesson.narration.mode, "reference_only")
        self.assertEqual(lesson.subtitles.render, "remotion")

    def test_unknown_key_still_rejected(self):
        with self.assertRaises(ValidationError):
            make_lesson({"profile": "standard", "unknown": 1})


if __name__ == "__main__":
    unittest.main()
