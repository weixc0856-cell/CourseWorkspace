from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.review_decisions import (
    DecisionError,
    load_decisions,
    record_decision,
    summarize,
)


def build_review(root: Path) -> None:
    (root / "review").mkdir(parents=True)
    (root / "review" / "review.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "findings": [
                    {"slide": 1, "claim": "A", "verdict": "unsupported"},
                    {"slide": 2, "claim": "B", "verdict": "supported"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "review" / "review_cross.json").write_text(
        json.dumps(
            {
                "claims": [
                    {"claim_id": "C-001", "claim_text": "A", "final_status": "disputed"}
                ]
            }
        ),
        encoding="utf-8",
    )


class ReviewDecisionsTest(unittest.TestCase):
    def test_findings_without_decisions_need_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_review(root)
            report = summarize(root)
            self.assertEqual(len(report["findings"]), 3)
            self.assertEqual(len(report["undecided"]), 3)
            self.assertTrue(report["needs_human_review"])

    def test_every_finding_decided_clears_the_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_review(root)
            report = summarize(root)
            for index, item in enumerate(report["findings"]):
                record_decision(
                    root,
                    "demo",
                    item["id"],
                    "fixed" if index % 2 == 0 else "rejected",
                    by="Wayne",
                    note="checked against source",
                )
            after = summarize(root)
            self.assertEqual(after["undecided"], [])
            self.assertTrue(after["clean"])
            self.assertFalse(after["needs_human_review"])

    def test_accepted_or_deferred_findings_stay_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_review(root)
            report = summarize(root)
            for item in report["findings"]:
                record_decision(root, "demo", item["id"], "accepted", by="Wayne")
            after = summarize(root)
            self.assertTrue(after["needs_human_review"])
            self.assertFalse(after["clean"])

    def test_rejection_requires_a_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_review(root)
            identifier = summarize(root)["findings"][0]["id"]
            with self.assertRaises(DecisionError):
                record_decision(root, "demo", identifier, "rejected", by="Wayne")
            record_decision(
                root, "demo", identifier, "rejected", by="Wayne", note="quote is correct"
            )
            self.assertEqual(
                load_decisions(root / "review" / "decisions.json")["decisions"][identifier][
                    "decision"
                ],
                "rejected",
            )

    def test_unknown_decision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_review(root)
            identifier = summarize(root)["findings"][0]["id"]
            with self.assertRaises(DecisionError):
                record_decision(root, "demo", identifier, "maybe", by="Wayne")


if __name__ == "__main__":
    unittest.main()
