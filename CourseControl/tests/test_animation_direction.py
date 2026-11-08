from __future__ import annotations

import unittest

from course_control.animation_direction import AnimationDirection, ShotDirection


def shot(sid: str, start: float, end: float) -> ShotDirection:
    return ShotDirection(
        shot_id=sid,
        start_s=start,
        end_s=end,
        learning_intent="understand the move",
        visual_metaphor="arrow displacement",
        composition="left-weighted with negative space",
        focus="current arrow",
        camera="slow push in",
        motion=["draw arrow", "trace component"],
        continuity="same origin and grid",
        reference="3Blue1Brown vector intuition",
        acceptance=["no text overlap", "arrow tip readable"],
    )


class AnimationDirectionTest(unittest.TestCase):
    def test_contiguous_direction_is_valid(self):
        direction = AnimationDirection(
            lesson_id="vector-slice",
            title="Vectors",
            total_seconds=30,
            shots=[shot("s1", 0, 10), shot("s2", 10, 30)],
        )
        self.assertEqual(direction.problems(), [])

    def test_gap_and_total_mismatch_are_reported(self):
        direction = AnimationDirection(
            lesson_id="vector-slice",
            title="Vectors",
            total_seconds=40,
            shots=[shot("s1", 0, 10), shot("s2", 12, 30)],
        )
        problems = direction.problems()
        self.assertTrue(any("expected 10" in item for item in problems))
        self.assertTrue(any("total_seconds" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
