from __future__ import annotations

import unittest
from pathlib import Path

from course_control.direction.animation_score import score
from course_control.direction.beats import Beat, BeatSheet, BeatShot, CameraMove
from course_control.rendering.grammar import load_registry
from course_control.quality.quality_gates import decide

ROOT = Path(__file__).resolve().parents[2]
SEGMENTS = [(0.0, 6.0), (6.0, 6.0)]


def kinetic_sheet() -> BeatSheet:
    shots = []
    for segment in (1, 2):
        for index, start in enumerate((0.0, 0.5)):
            shots.append(
                BeatShot(
                    id=f"s{segment}{index}",
                    segment=segment,
                    grammar="kinetic_edit",
                    start=start,
                    end=start + 0.5,
                    engine="code_video",
                    beats=[
                        Beat(at=0.1, kind="reveal", action="first change"),
                        Beat(at=0.6, kind="highlight", action="second change"),
                    ],
                    camera=(
                        [CameraMove(at=0.5, width=12.0, motive="follow the cut")]
                        if segment == 1 and index == 0
                        else []
                    ),
                )
            )
    return BeatSheet(
        lesson="demo",
        grammar="kinetic_edit",
        subtitle_safe_below=-2.2,
        shots=shots,
    )


class QualityGateTest(unittest.TestCase):
    def test_decide_separates_hard_and_grammar(self) -> None:
        report = decide(
            hard=[{"source": "build-report", "id": "V-10", "detail": "missing"}],
            grammar=["shot-001: 3.0s is shorter than 5.00s (long_take)"],
        )
        self.assertFalse(report["hard_ok"])
        self.assertFalse(report["grammar_ok"])
        self.assertFalse(report["releasable"])
        self.assertTrue(report["human_review_required"])

    def test_waiver_removes_grammar_failure_only(self) -> None:
        report = decide(
            hard=[],
            grammar=["shot-001: 3.0s is shorter than 5.00s (long_take)"],
            waivers=["shot-001"],
        )
        self.assertTrue(report["hard_ok"])
        self.assertTrue(report["grammar_ok"])
        self.assertTrue(report["releasable"])

    def test_incomplete_check_blocks_release(self) -> None:
        report = decide(
            hard=[],
            grammar=[],
            incomplete=[{"source": "media-qc", "id": "media.speech_match"}],
        )
        self.assertEqual(report["verification_status"], "incomplete")
        self.assertFalse(report["releasable"])

    def test_grammar_warnings_do_not_block_release(self) -> None:
        report = decide(
            hard=[],
            grammar=[],
            grammar_warnings=["shot-001: 3.0s is shorter than 5.00s (long_take)"],        )
        self.assertEqual(report["verification_status"], "pass")
        self.assertTrue(report["releasable"])
        self.assertTrue(report["grammar_warnings"])

    def test_kinetic_profile_scores_full_and_is_metric_only(self) -> None:
        result = score(
            kinetic_sheet(),
            SEGMENTS,
            media_qc={"freeze_intervals": []},
            registry=load_registry(ROOT),
        )
        self.assertEqual(result["score"], 100.0)
        self.assertEqual(result["release_gate"], "metric_only")
        self.assertEqual(result["verdict"], "pass")

    def test_mixed_grammar_motion_is_judged_per_shot(self) -> None:
        sheet = BeatSheet(
            lesson="mixed",
            subtitle_safe_below=-2.2,
            shots=[
                BeatShot(
                    id="kinetic",
                    segment=1,
                    grammar="kinetic_edit",
                    start=0.0,
                    end=1.0,
                    engine="code_video",
                    beats=[
                        Beat(at=0.1, kind="reveal", action="change one"),
                        Beat(at=0.3, kind="transform", action="change two"),
                        Beat(at=0.5, kind="highlight", action="change three"),
                        Beat(at=0.7, kind="flow", action="change four"),
                        Beat(at=0.9, kind="reveal", action="change five"),
                    ],
                ),
                BeatShot(
                    id="long",
                    segment=2,
                    grammar="long_take",
                    start=0.0,
                    end=1.0,
                    engine="manim",
                    long_lived=["sentence"],
                    beats=[
                        Beat(at=0.2, kind="reveal", action="build the object"),
                        Beat(at=0.7, kind="transform", action="move the object"),
                    ],
                ),
            ],
        )
        result = score(sheet, [(0.0, 8.0), (8.0, 8.0)], registry=load_registry(ROOT))
        self.assertEqual(result["components"]["motion"], 25.0)

    def test_legacy_score_has_no_release_gate_marker(self) -> None:
        result = score(kinetic_sheet(), SEGMENTS)
        self.assertNotIn("release_gate", result)

    def test_blocking_warnings_stop_a_release(self) -> None:
        report = decide(
            hard=[],
            grammar=[],
            blocking_warnings=["Q5 最终交付: release sign-off pending"],
        )
        self.assertEqual(report["verification_status"], "incomplete")
        self.assertFalse(report["releasable"])
        self.assertEqual(len(report["blocking_warnings"]), 1)

    def test_human_review_warnings_are_not_automatic_vetoes(self) -> None:
        report = decide(
            hard=[],
            grammar=[],
            human_review_items=["Q3 视听体验: frozen intervals"],
        )
        self.assertEqual(report["verification_status"], "pass")
        self.assertTrue(report["needs_human_review"])
        self.assertTrue(report["releasable"])


if __name__ == "__main__":
    unittest.main()
