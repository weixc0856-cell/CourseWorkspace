from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from course_control.direction.animation_score import score
from course_control.direction.beats import Beat, BeatSheet, BeatShot, CameraMove
from course_control.rendering.grammar import load_registry
from course_control.quality.quality_gates import (
    decide,
    freshness_problems,
    subtitles_qc_result,
)

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


class ReportFreshnessTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, relative: str, payload: dict) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_build_report_is_stale_when_a_delivered_file_changed(self) -> None:
        video = self.root / "final" / "final.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"one")
        digest = hashlib.sha256(b"one").hexdigest()
        self._write(
            "final/build-report.json",
            {"artifacts": [{"path": "final/final.mp4", "sha256": digest}]},
        )
        self.assertEqual(freshness_problems(self.root), [])

        video.write_bytes(b"two")
        problems = freshness_problems(self.root)
        self.assertTrue(any(item["id"] == "freshness.build" for item in problems))

    def test_missing_subtitles_qc_blocks_only_when_enabled(self) -> None:
        enabled = SimpleNamespace(
            build_root=self.root,
            lesson=SimpleNamespace(subtitles=SimpleNamespace(enabled=True)),
        )
        hard, incomplete = subtitles_qc_result(enabled)
        self.assertEqual(hard, [])
        self.assertTrue(any(item["id"] == "subtitles.qc" for item in incomplete))

        disabled = SimpleNamespace(
            build_root=self.root,
            lesson=SimpleNamespace(subtitles=SimpleNamespace(enabled=False)),
        )
        self.assertEqual(subtitles_qc_result(disabled), ([], []))

    def test_failed_subtitles_qc_is_a_hard_failure(self) -> None:
        self._write(
            "quality/subtitles-qc.json",
            {"status": "FAIL", "errors": ["cue 5 overlaps the previous cue"]},
        )
        paths = SimpleNamespace(
            build_root=self.root,
            lesson=SimpleNamespace(subtitles=SimpleNamespace(enabled=True)),
        )
        hard, incomplete = subtitles_qc_result(paths)
        self.assertTrue(any(item["id"] == "subtitles.qc" for item in hard))
        self.assertEqual(incomplete, [])

    def test_passing_subtitles_qc_with_matching_source_is_clean(self) -> None:
        srt = self.root / "subtitles.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nhello\n", encoding="utf-8")
        digest = hashlib.sha256(srt.read_bytes()).hexdigest()
        self._write(
            "quality/subtitles-qc.json",
            {"status": "PASS", "source": {"path": str(srt), "sha256": digest}},
        )
        paths = SimpleNamespace(
            build_root=self.root,
            lesson=SimpleNamespace(subtitles=SimpleNamespace(enabled=True)),
        )
        self.assertEqual(subtitles_qc_result(paths), ([], []))
        self.assertEqual(freshness_problems(self.root), [])

        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nchanged\n", encoding="utf-8")
        problems = freshness_problems(self.root)
        self.assertTrue(any(item["id"] == "freshness.subtitles" for item in problems))

    def test_new_subtitle_report_does_not_stale_the_quality_report(self) -> None:
        self._write("quality/quality-report.json", {"dimensions": []})
        self._write("quality/subtitles-qc.json", {"status": "PASS"})
        self.assertEqual(freshness_problems(self.root), [])

    def test_new_build_report_does_stale_the_quality_report(self) -> None:
        self._write("quality/quality-report.json", {"dimensions": []})
        build_report = self._write("final/build-report.json", {"verdict": "pass"})
        future = time.time() + 5
        os.utime(build_report, (future, future))
        problems = freshness_problems(self.root)
        self.assertTrue(any(item["id"] == "freshness.quality" for item in problems))
