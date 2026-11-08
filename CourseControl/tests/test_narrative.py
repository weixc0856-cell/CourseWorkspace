from __future__ import annotations

import unittest

from course_control.contracts import LessonConfig
from course_control.narrative import NarrativePlan, validate_plan


def beat(beat_id: str, start: float, end: float) -> dict:
    return {
        "id": beat_id,
        "start_s": start,
        "end_s": end,
        "summary": f"{beat_id} summary",
        "evidence": "schematic",
    }


def long_plan(beats=None, **overrides) -> NarrativePlan:
    payload = {
        "schema_version": 1,
        "form": "long",
        "audience": "engineers",
        "promise": "explain the mechanism",
        "beats": beats
        or [
            beat("cold_open", 0, 20),
            beat("question", 20, 50),
            beat("intuition", 50, 120),
            beat("mechanism", 120, 240),
            beat("test", 240, 270),
            beat("connect", 270, 292),
        ],
        "payoff": "viewer can restate the mechanism",
    }
    payload.update(overrides)
    return NarrativePlan.model_validate(payload)


def lesson(target: float = 292) -> LessonConfig:
    return LessonConfig.model_validate(
        {
            "schema_version": 1,
            "lesson_id": "demo",
            "title_en": "Demo",
            "title_zh": "演示",
            "status": "draft",
            "content": {
                "slides": "slides.md",
                "notes": "notes.md",
                "outline": None,
                "storyboard": "storyboard.yaml",
                "assets": "assets/",
                "subtitles": None,
            },
            "outputs": {
                "fps": 30,
                "resolution": [1920, 1080],
                "slides_canvas": [1280, 720],
                "animation_canvas": [1920, 1080],
            },
            "engines": ["manim"],
            "compose": {"mode": "deck", "base_video": None, "renderer": "timeline"},
            "duration": {
                "profile": "standard",
                "target_seconds": target,
                "min_seconds": 60,
                "max_seconds": 360,
            },
        }
    )


class NarrativeTests(unittest.TestCase):
    def test_complete_long_plan_passes(self) -> None:
        self.assertEqual(validate_plan(long_plan(), lesson()), [])

    def test_missing_question_is_an_error(self) -> None:
        plan = long_plan(beats=[beat("cold_open", 0, 20), beat("connect", 20, 40)])
        issues = validate_plan(plan, lesson())
        self.assertTrue(any(i["rule"] == "N-11" and i["level"] == "error" for i in issues))

    def test_overlap_is_an_error(self) -> None:
        plan = long_plan(
            beats=[
                beat("cold_open", 0, 30),
                beat("question", 20, 50),
                beat("connect", 50, 60),
            ]
        )
        issues = validate_plan(plan, lesson(60))
        self.assertTrue(any(i["rule"] == "N-03" and i["level"] == "error" for i in issues))

    def test_short_form_over_ninety_seconds_is_an_error(self) -> None:
        plan = NarrativePlan.model_validate(
            {
                "schema_version": 1,
                "form": "short",
                "audience": "viewers",
                "promise": "one mechanism",
                "beats": [
                    beat("cold_open", 0, 10),
                    beat("question", 10, 20),
                    beat("mechanism", 20, 110),
                    beat("connect", 110, 120),
                ],
                "payoff": "a single conclusion",
                "short_form": {
                    "target_seconds": 90,
                    "aspect_ratio": "9:16",
                    "independent_script": True,
                    "hook": "hook",
                    "payoff": "payoff",
                },
            }
        )
        issues = validate_plan(plan, None)
        self.assertTrue(any(i["rule"] == "N-22" and i["level"] == "error" for i in issues))


if __name__ == "__main__":
    unittest.main()
