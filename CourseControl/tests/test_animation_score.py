from __future__ import annotations

import unittest

from course_control.animation_score import WEIGHTS, score
from course_control.beats import Beat, BeatSheet, BeatShot, CameraMove

SEGMENTS = [(0.0, 16.0), (16.0, 12.0)]


def demo_sheet() -> BeatSheet:
    shots = [
        BeatShot(
            id="a",
            segment=1,
            start=0.0,
            end=0.5,
            engine="manim",
            long_lived=["sentence"],
            beats=[Beat(at=0.1, kind="reveal", action="first change"), Beat(at=0.5, kind="highlight", action="second change")],
        ),
        BeatShot(
            id="b",
            segment=1,
            start=0.5,
            end=1.0,
            engine="manim",
            long_lived=["sentence"],
            beats=[Beat(at=0.1, kind="reveal", action="first change"), Beat(at=0.5, kind="highlight", action="second change")],
        ),
        BeatShot(
            id="c",
            segment=2,
            start=0.0,
            end=1.0,
            engine="manim",
            long_lived=["matrix"],
            beats=[
                Beat(at=0.1, kind="reveal", action="first change"),
                Beat(at=0.4, kind="highlight", action="second change"),
                Beat(at=0.7, kind="highlight", action="third change"),
                Beat(at=0.95, kind="annotation", action="fourth change"),
            ],
        ),
    ]
    return BeatSheet(lesson="demo", palette="editorial", subtitle_safe_below=-2.2, shots=shots)


class AnimationScoreTest(unittest.TestCase):
    def test_perfect_inputs_without_camera_do_not_score_full(self) -> None:
        result = score(demo_sheet(), SEGMENTS, media_qc={"freeze_intervals": []}, build_verdict="pass")
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["components"]["gates"], WEIGHTS["gates"])
        self.assertEqual(result["components"]["freeze"], WEIGHTS["freeze"])
        self.assertEqual(result["components"]["camera"], 0.0)
        self.assertEqual(result["score"], 90.0)
        self.assertEqual(result["metrics"]["long_lived_ratio"], 1.0)

    def test_camera_evidence_unlocks_the_camera_component(self) -> None:
        sheet = demo_sheet()
        sheet.shots[0].camera = [CameraMove(at=0.5, width=12.0, motive="push in on the matrix")]
        result = score(sheet, SEGMENTS, media_qc={"freeze_intervals": []}, build_verdict="pass")
        self.assertEqual(result["components"]["camera"], WEIGHTS["camera"])
        self.assertEqual(result["score"], 100.0)

    def test_freeze_intervals_reduce_the_score(self) -> None:
        clean = score(demo_sheet(), SEGMENTS, media_qc={"freeze_intervals": []}, build_verdict="pass")
        frozen = score(
            demo_sheet(),
            SEGMENTS,
            media_qc={"freeze_intervals": [f"{i}" for i in range(80)]},
            build_verdict="pass",
        )
        self.assertLess(frozen["components"]["freeze"], clean["components"]["freeze"])
        self.assertLess(frozen["score"], clean["score"])

    def test_failed_build_zeroes_the_gate(self) -> None:
        result = score(demo_sheet(), SEGMENTS, media_qc={"freeze_intervals": []}, build_verdict="fail")
        self.assertEqual(result["components"]["gates"], 0.0)
        self.assertEqual(result["verdict"], "fail")

    def test_creative_threshold_is_a_warning_not_a_gate(self) -> None:
        # D-071: long-lived objects are a diagnostic.  The structural gate stays.
        sheet = demo_sheet()
        sheet.shots[0].long_lived = []
        sheet.shots[1].long_lived = []
        sheet.shots[2].long_lived = []
        result = score(sheet, SEGMENTS, media_qc={"freeze_intervals": []}, build_verdict="pass")
        self.assertTrue(any("continuity" in issue for issue in result["issues"]))
        self.assertEqual(result["components"]["gates"], WEIGHTS["gates"])
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual(result["score"], 70.0)

    def test_components_sum_to_score(self) -> None:
        result = score(demo_sheet(), SEGMENTS, media_qc={"freeze_intervals": ["1", "2"]}, build_verdict="pass")
        self.assertAlmostEqual(result["score"], sum(result["components"].values()), places=1)


if __name__ == "__main__":
    unittest.main()
