from __future__ import annotations

import unittest

from pydantic import ValidationError

from course_control.beats import Beat, BeatSheet, BeatShot, CameraMove, validate_sheet

SEGMENTS = [(0.0, 10.0), (10.0, 12.0)]


def shot(
    shot_id: str,
    segment: int,
    start: float,
    end: float,
    beats: tuple[float, ...] = (0.1, 0.5, 0.9),
    long_lived: tuple[str, ...] = ("sentence",),
) -> BeatShot:
    return BeatShot(
        id=shot_id,
        segment=segment,
        start=start,
        end=end,
        engine="manim",
        long_lived=list(long_lived),
        beats=[Beat(at=value, kind="reveal", action="visual change") for value in beats],
    )


def sheet(shots: list[BeatShot]) -> BeatSheet:
    return BeatSheet(lesson="demo", palette="editorial", subtitle_safe_below=-2.2, shots=shots)


VALID = [
    shot("a", 1, 0.0, 0.5),
    shot("b", 1, 0.5, 1.0),
    shot("c", 2, 0.0, 1.0, beats=(0.1, 0.4, 0.7, 0.95)),
]


class BeatValidationTest(unittest.TestCase):
    def test_valid_sheet_has_no_issues(self) -> None:
        self.assertEqual(validate_sheet(sheet(VALID), SEGMENTS), [])

    def test_gap_between_shots(self) -> None:
        shots = [shot("a", 1, 0.0, 0.4), shot("b", 1, 0.5, 1.0), shot("c", 2, 0.0, 1.0)]
        issues = validate_sheet(sheet(shots), SEGMENTS)
        self.assertTrue(any("gap/overlap" in issue for issue in issues))

    def test_missing_segment(self) -> None:
        issues = validate_sheet(sheet([shot("a", 1, 0.0, 1.0)]), SEGMENTS)
        self.assertTrue(any("segment 2" in issue for issue in issues))

    def test_short_shot(self) -> None:
        shots = [shot("a", 1, 0.0, 0.2), shot("b", 1, 0.2, 1.0), shot("c", 2, 0.0, 1.0)]
        issues = validate_sheet(sheet(shots), SEGMENTS)
        self.assertTrue(any("shorter than" in issue for issue in issues))

    def test_long_shot(self) -> None:
        segments = [(0.0, 20.0), (20.0, 12.0)]
        shots = [
            shot("a", 1, 0.0, 1.0, beats=(0.05, 0.2, 0.35, 0.5, 0.65, 0.8)),
            shot("c", 2, 0.0, 1.0, beats=(0.1, 0.4, 0.7, 0.95)),
        ]
        issues = validate_sheet(sheet(shots), segments)
        self.assertTrue(any("longer than" in issue for issue in issues))

    def test_first_beat_too_late(self) -> None:
        shots = [shot("a", 1, 0.0, 1.0, beats=(0.5, 0.7, 0.9)), shot("c", 2, 0.0, 1.0, beats=(0.1, 0.4, 0.7, 0.95))]
        issues = validate_sheet(sheet(shots), SEGMENTS)
        self.assertTrue(any("first beat" in issue for issue in issues))

    def test_dead_zone_between_beats(self) -> None:
        shots = [shot("a", 1, 0.0, 1.0, beats=(0.1, 0.4)), shot("c", 2, 0.0, 1.0, beats=(0.1, 0.4, 0.7, 0.95))]
        issues = validate_sheet(sheet(shots), SEGMENTS)
        self.assertTrue(any("without a beat" in issue for issue in issues))

    def test_low_long_lived_ratio(self) -> None:
        shots = [
            shot("a", 1, 0.0, 0.5, long_lived=("sentence",)),
            shot("b", 1, 0.5, 1.0, long_lived=()),
            shot("c", 2, 0.0, 1.0, long_lived=()),
        ]
        issues = validate_sheet(sheet(shots), SEGMENTS)
        self.assertTrue(any("continuity" in issue for issue in issues))

    def test_palette_gate(self) -> None:
        issues = validate_sheet(sheet(VALID), SEGMENTS, palette_ok=False)
        self.assertTrue(any("palette" in issue for issue in issues))

    def test_camera_move_requires_motive(self) -> None:
        with self.assertRaises(ValidationError):
            CameraMove(at=0.5, width=12.0, motive="zoom")

    def test_subtitle_band_must_be_reserved(self) -> None:
        with self.assertRaises(ValidationError):
            BeatSheet(
                lesson="demo",
                palette="editorial",
                subtitle_safe_below=-1.0,
                shots=VALID,
            )


if __name__ == "__main__":
    unittest.main()
