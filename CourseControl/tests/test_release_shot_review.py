from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.release.check import (
    EXEMPT,
    FAIL,
    INCOMPLETE,
    PASS,
    PASS_WITH_EXEMPTION,
    _overall,
    _shot_review_steps,
)


class ReleaseShotReviewTests(unittest.TestCase):
    def _package(self, root: Path, shot: str = "a1", status: str = "PASS") -> Path:
        package = root / shot
        package.mkdir(parents=True)
        (package / "qc.json").write_text(
            json.dumps({"shot": shot, "status": status, "checks": []}), encoding="utf-8"
        )
        return package

    def _exemption(self, package: Path) -> None:
        package.mkdir(parents=True, exist_ok=True)
        (package / "exemption.json").write_text(json.dumps({
            "object": "a1 review package",
            "reason": "shot is a technical blockout; no review package generated",
            "operator": "owner",
            "time": "2026-11-14T23:00:00+08:00",
            "missing_checks": ["shot_review"],
            "delivery_version": "p2-blockout",
        }), encoding="utf-8")

    def test_pass_and_warn_are_not_blocking(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._package(root, "a1", "PASS")
            self._package(root, "a4", "WARN")
            steps = _shot_review_steps(root, root)
            self.assertEqual(steps[0].status, PASS)
            self.assertEqual(len(steps[0].data["shots"]), 2)

    def test_fail_is_blocking(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._package(root, "a1", "FAIL")
            steps = _shot_review_steps(root, root)
            self.assertEqual(steps[0].status, FAIL)
            self.assertEqual(_overall(steps), FAIL)

    def test_missing_directory_is_incomplete(self):
        with tempfile.TemporaryDirectory() as raw:
            steps = _shot_review_steps(Path(raw), Path(raw) / "missing")
            self.assertEqual(steps[0].status, INCOMPLETE)

    def test_valid_exemption_is_distinct_from_pass(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._exemption(root / "a1")
            steps = _shot_review_steps(root, root)
            self.assertEqual(steps[0].status, EXEMPT)
            self.assertEqual(_overall(steps), PASS_WITH_EXEMPTION)

    def test_invalid_exemption_is_incomplete(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            package = root / "a1"
            package.mkdir()
            (package / "exemption.json").write_text('{"reason": "because"}', encoding="utf-8")
            steps = _shot_review_steps(root, root)
            self.assertEqual(steps[0].status, INCOMPLETE)


if __name__ == "__main__":
    unittest.main()
