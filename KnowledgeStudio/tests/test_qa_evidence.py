from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from knowledge_studio.qa import _evidence_problems


def citation(ref: str, page: int = 7) -> dict:
    return {
        "ref": ref,
        "source_id": "book",
        "pdf_page": page,
        "page_sha256": "a" * 64,
        "excerpt_sha256": "b" * 64,
    }


def evidence_file(*refs: str) -> dict:
    return {
        "schema_version": 1,
        "source_id": "book",
        "retrieval": "retrieval/query.json",
        "generated_at": "2026-11-13T00:00:00+08:00",
        "claims": [
            {
                "claim_id": "c1",
                "statement": "a claim",
                "citations": [citation(refs[0])],
            }
        ],
        "citation_pool": [citation(item) for item in refs],
    }


class EvidenceFileSelectionTest(unittest.TestCase):
    def test_spancheck_report_is_not_read_as_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "evidence"
            folder.mkdir()
            (folder / "good.evidence.json").write_text(
                json.dumps(evidence_file("p7")), encoding="utf-8"
            )
            (folder / "good.spancheck.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source_id": "book",
                        "status": "pass",
                        "counts": {"claims": 1, "ok": 1},
                        "note": "presence only",
                        "claims": [
                            {
                                "claim_id": "c1",
                                "cited_pages": [7],
                                "numbers": [],
                                "missing_numbers": [],
                                "status": "ok",
                                "detail": "quote found",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(_evidence_problems(root), [])

    def test_evidence_citation_outside_the_pool_still_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "evidence"
            folder.mkdir()
            payload = evidence_file("p7", "p8")
            payload["claims"] = [
                {
                    "claim_id": "c1",
                    "statement": "a claim",
                    "citations": [citation("p9")],
                }
            ]
            (folder / "bad.evidence.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            problems = _evidence_problems(root)
            self.assertTrue(any("not in citation pool" in item for item in problems))
