from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from content_qa.claims import (
    Claim,
    ClaimType,
    ReviewStatus,
    infer_type,
    registry_from_report,
)
from content_qa.cross_review import align_claims, decide, run_cross_review


def claim(
    claim_id: str,
    text: str,
    *,
    slide: int = 1,
    refs=None,
    status: ReviewStatus = ReviewStatus.supported,
) -> Claim:
    return Claim(
        claim_id=claim_id,
        claim_text=text,
        slide_id=slide,
        source_refs=refs or [],
        review_status=status,
    )


class ClaimTests(unittest.TestCase):
    def test_type_inference(self) -> None:
        self.assertEqual(infer_type("I think this tool is better"), ClaimType.opinion)
        self.assertEqual(infer_type("Think of attention like a filter"), ClaimType.analogy)
        self.assertEqual(infer_type("The current version supports X"), ClaimType.time_sensitive)
        self.assertEqual(infer_type("The formula derives from softmax"), ClaimType.derivation)
        self.assertEqual(infer_type("Self-attention computes pairwise scores"), ClaimType.mechanism)

    def test_registry_risk_uses_evidence(self) -> None:
        report = {
            "lesson": "demo",
            "findings": [
                {"slide": 1, "claim": "A supported claim", "verdict": "supported", "source_refs": ["S1"]},
                {"slide": 1, "claim": "An unsourced claim", "verdict": "supported", "source_refs": []},
                {"slide": 2, "claim": "A disputed claim", "verdict": "disputed", "source_refs": ["S2"]},
            ],
        }
        registry = registry_from_report(report, source_ids={"S1", "S2"})
        self.assertEqual(registry.claims[0].risk_level.value, "low")
        self.assertEqual(registry.claims[1].risk_level.value, "high")
        self.assertEqual(registry.claims[2].risk_level.value, "high")


class CrossReviewTests(unittest.TestCase):
    def test_alignment_matches_same_claim(self) -> None:
        a = [claim("C-001", "Self-attention compares every word with every other word", refs=["S1"])]
        b = [claim("C-001", "Self attention compares every word with every other word", refs=["S1"])]
        pairs = align_claims(a, b)
        self.assertEqual(len(pairs), 1)
        self.assertIsNotNone(pairs[0][1])
        self.assertGreater(pairs[0][2], 0.8)

    def test_decision_matrix(self) -> None:
        self.assertEqual(
            decide(ReviewStatus.supported, ReviewStatus.supported, [])[0],
            ReviewStatus.supported,
        )
        self.assertEqual(
            decide(ReviewStatus.supported, ReviewStatus.supported, ["no source_refs"])[0],
            ReviewStatus.needs_human_review,
        )
        self.assertEqual(
            decide(ReviewStatus.supported, ReviewStatus.unsupported, [])[0],
            ReviewStatus.disputed,
        )
        self.assertEqual(
            decide(ReviewStatus.unsupported, ReviewStatus.unsupported, [])[0],
            ReviewStatus.unsupported,
        )
        self.assertEqual(
            decide(ReviewStatus.not_checked, ReviewStatus.supported, [])[0],
            ReviewStatus.needs_human_review,
        )

    def test_cross_review_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            lesson = workspace / "lessons" / "demo"
            lesson.mkdir(parents=True)
            (lesson / "sources.yaml").write_text(
                "sources:\n- id: S1\n  title: Source\n", encoding="utf-8"
            )
            a = {
                "lesson": "demo",
                "status": "completed",
                "findings": [
                    {"slide": 1, "claim": "Claim one", "verdict": "supported", "source_refs": ["S1"]},
                    {"slide": 1, "claim": "Claim two", "verdict": "supported", "source_refs": []},
                ],
            }
            b = {
                "lesson": "demo",
                "status": "completed",
                "findings": [
                    {"slide": 1, "claim": "Claim one", "verdict": "supported", "source_refs": ["S1"]},
                    {"slide": 1, "claim": "Claim two", "verdict": "unsupported", "source_refs": []},
                ],
            }
            a_path = workspace / "a.json"
            b_path = workspace / "b.json"
            a_path.write_text(json.dumps(a), encoding="utf-8")
            b_path.write_text(json.dumps(b), encoding="utf-8")
            out = workspace / "out"
            paths = run_cross_review(lesson, a_path, b_path, out_dir=out)
            for path in paths.values():
                self.assertTrue(path.is_file())
            cross = json.loads(paths["cross"].read_text(encoding="utf-8"))
            self.assertEqual(cross["summary"]["claims"], 2)
            self.assertEqual(cross["summary"]["disputed"], 1)
            self.assertEqual(cross["summary"]["missing_evidence"], 1)


if __name__ == "__main__":
    unittest.main()
