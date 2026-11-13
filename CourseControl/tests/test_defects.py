from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.quality.defect import Defect, DefectReport, collect, defect_id
from course_control.quality.regression import compare
from course_control.quality.repair import MAX_ATTEMPTS, plan, plan_for


class DefectCollectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.build = Path(self._tmp.name)
        (self.build / "final").mkdir(parents=True)
        (self.build / "quality").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, relative: str, payload: dict) -> None:
        (self.build / relative).write_text(json.dumps(payload), encoding="utf-8")

    def test_collects_failures_from_each_report(self) -> None:
        self._write(
            "final/build-report.json",
            {"checks": [{"id": "V-27", "status": "fail", "detail": "too long"}]},
        )
        self._write(
            "quality/media-qc.json",
            {"checks": [{"id": "media.loudness", "status": "fail", "detail": "-9 LUFS"}]},
        )
        self._write(
            "quality/subtitles-qc.json",
            {"status": "FAIL", "errors": ["cue 5 overlaps"]},
        )
        self._write(
            "quality/quality-report.json",
            {
                "dimensions": [
                    {"id": "Q1", "status": "INCOMPLETE", "reason": "no evidence"},
                    {"id": "Q2", "status": "PASS"},
                ]
            },
        )
        report = collect(self.build, "demo")
        dimensions = sorted(item.dimension for item in report.defects)
        self.assertEqual(dimensions, ["K", "T", "V", "V"])
        self.assertTrue(all(item.severity == "blocking" for item in report.defects))
        self.assertEqual(len({item.id for item in report.defects}), 4)

    def test_missing_subtitles_qc_is_a_defect(self) -> None:
        report = collect(self.build, "demo")
        self.assertEqual(len(report.defects), 1)
        self.assertEqual(report.defects[0].symptom, "subtitles-qc: no report")

    def test_ids_are_stable_for_the_same_symptom(self) -> None:
        self.assertEqual(defect_id("V-27: too long", "T"), defect_id("V-27: too long", "T"))
        self.assertNotEqual(defect_id("V-27: too long", "T"), defect_id("V-27: too long", "V"))


class RepairPlanTest(unittest.TestCase):
    def _defect(self, cause: str) -> Defect:
        return Defect(
            id="DEF-00000001",
            dimension="T",
            symptom="x",
            root_cause_hint=cause,
        )

    def test_script_length_replans_authoring_downstream(self) -> None:
        item = plan_for(self._defect("script_length"), project_id="demo")
        self.assertEqual(item.strategy, "reauthor_segment")
        self.assertIn("author", item.rebuild_scope)
        self.assertIn("deliver", item.rebuild_scope)
        self.assertFalse(item.blocked)

    def test_audio_timing_reruns_production(self) -> None:
        item = plan_for(self._defect("audio_timing"), project_id="demo")
        self.assertEqual(item.strategy, "rerun_stage")
        self.assertEqual(item.rebuild_scope, ["produce", "verify", "deliver"])

    def test_unknown_cause_stops_instead_of_guessing(self) -> None:
        item = plan_for(self._defect("unknown"), project_id="demo")
        self.assertEqual(item.strategy, "stop")
        self.assertTrue(item.blocked)

    def test_attempt_limit_blocks(self) -> None:
        item = plan_for(self._defect("script_length"), attempt=MAX_ATTEMPTS + 1, project_id="demo")
        self.assertTrue(item.blocked)
        self.assertIn("exceeds limit", item.reason or "")

    def test_plan_covers_every_defect(self) -> None:
        report = DefectReport(
            project_id="demo",
            generated_at="2026-11-13T00:00:00+08:00",
            defects=[self._defect("script_length"), self._defect("unknown")],
        )
        plans = plan(report)
        self.assertEqual(len(plans.plans), 2)
        self.assertEqual({item.defect_ids[0] for item in plans.plans}, {"DEF-00000001"})


class RegressionTest(unittest.TestCase):
    def _report(self, *ids: str) -> DefectReport:
        return DefectReport(
            project_id="demo",
            generated_at="2026-11-13T00:00:00+08:00",
            defects=[
                Defect(id=item, dimension="T", symptom=item) for item in ids
            ],
        )

    def test_compare_separates_fixed_open_and_introduced(self) -> None:
        result = compare(self._report("A", "B"), self._report("B", "C"))
        self.assertEqual(result.fixed, ["A"])
        self.assertEqual(result.still_open, ["B"])
        self.assertEqual(result.introduced, ["C"])
        self.assertTrue(result.regressed)

    def test_no_new_defect_is_not_a_regression(self) -> None:
        result = compare(self._report("A", "B"), self._report("B"))
        self.assertFalse(result.regressed)
        self.assertEqual(result.fixed, ["A"])
