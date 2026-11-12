from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.quality.reference import (
    ReferenceRecord,
    compare,
    load_reference,
    resolve_reference,
)

ROOT = Path(__file__).resolve().parents[2]

RECORD = {
    "schema_version": 1,
    "id": "demo",
    "title": "Demo",
    "duration_s": 60,
    "sample_interval_s": 5,
    "metrics": {
        "shot_seconds_min": 3,
        "shot_seconds_max": 8,
        "beats_per_10s_min": 4,
        "cut_rate_per_10s_min": 1.0,
        "camera_required": False,
    },
}


class ReferenceTest(unittest.TestCase):
    def test_load_reference_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.json"
            path.write_text(json.dumps(RECORD), encoding="utf-8")
            record = load_reference(path)
        self.assertEqual(record.id, "demo")

    def test_compare_passes_measurable_dimensions(self) -> None:
        record = ReferenceRecord.model_validate(RECORD)
        report = compare(
            {"average_shot_seconds": 4.0, "beats_per_10s": 5.0, "cut_rate_per_10s": 2.0, "camera_moves": 0},
            record,
        )
        self.assertEqual(report["dimensions"]["timing"]["status"], "pass")
        self.assertEqual(report["dimensions"]["motion_quality"]["status"], "pass")
        for name in ("composition", "visual_hierarchy", "typography"):
            self.assertEqual(report["dimensions"][name]["status"], "human_review")
        self.assertEqual(report["overall"], "ready_for_human_review")
        self.assertTrue(report["human_review_required"])

    def test_compare_reports_required_improvements(self) -> None:
        record = ReferenceRecord.model_validate(RECORD)
        report = compare(
            {"average_shot_seconds": 12.0, "beats_per_10s": 1.0, "cut_rate_per_10s": 0.2, "camera_moves": 0},
            record,
        )
        self.assertEqual(report["overall"], "not_ready")
        self.assertTrue(any("average shot" in item for item in report["required_improvements"]))
        self.assertTrue(any("action density" in item for item in report["required_improvements"]))

    def test_resolve_workspace_reference(self) -> None:
        path = resolve_reference(ROOT, "yari-ai-voiceover")
        self.assertTrue(path.is_file())

    def test_reference_chapters_are_accepted(self) -> None:
        record = load_reference(resolve_reference(ROOT, "3b1b-attention"))
        self.assertGreaterEqual(len(record.chapters), 5)


if __name__ == "__main__":
    unittest.main()
