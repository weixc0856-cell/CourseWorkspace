from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.quality.certificate import issue


class QualityCertificateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.build = Path(self._tmp.name)
        (self.build / "quality").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, name: str, payload: dict) -> None:
        (self.build / "quality" / name).write_text(json.dumps(payload), encoding="utf-8")

    def test_missing_defects_report_is_incomplete(self) -> None:
        certificate = issue(self.build, "demo")
        self.assertEqual(certificate.verdict, "incomplete")
        self.assertIn("defects.json", certificate.reason or "")

    def test_open_defect_fails_the_certificate(self) -> None:
        self._write("defects.json", {"defects": [{"id": "DEF-1", "status": "open"}]})
        self._write("gate.json", {"verification_status": "pass"})
        certificate = issue(self.build, "demo")
        self.assertEqual(certificate.verdict, "fail")
        self.assertEqual(certificate.open_defects, ["DEF-1"])

    def test_passing_gate_without_defects_passes(self) -> None:
        self._write("defects.json", {"defects": []})
        self._write("gate.json", {"verification_status": "pass"})
        self._write(
            "quality-report.json",
            {"dimensions": [{"id": "Q1", "status": "PASS"}]},
        )
        certificate = issue(self.build, "demo")
        self.assertEqual(certificate.verdict, "pass")
        self.assertEqual(certificate.dimensions, {"Q1": "PASS"})
        self.assertIsNotNone(certificate.quality_report_sha256)

    def test_incomplete_gate_is_incomplete(self) -> None:
        self._write("defects.json", {"defects": []})
        self._write("gate.json", {"verification_status": "incomplete"})
        certificate = issue(self.build, "demo")
        self.assertEqual(certificate.verdict, "incomplete")
