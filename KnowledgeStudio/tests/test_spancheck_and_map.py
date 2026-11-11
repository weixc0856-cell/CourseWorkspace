from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from knowledge_studio.bookmap import build as build_bookmap
from knowledge_studio.bookmap import write as write_bookmap
from knowledge_studio.extract import load_page_texts, sha256_text
from knowledge_studio.segment import build_units
from knowledge_studio.spancheck import check as check_spans
from knowledge_studio.spancheck import write as write_spancheck
from knowledge_studio.toc import resolve, save, write_page_map

from tests.test_knowledge_studio import make_book


def _citation(source_id: str, page: int, body: str) -> dict:
    return {
        "ref": f"{source_id}:p{page}",
        "source_id": source_id,
        "pdf_page": page,
        "printed_page": None,
        "page_sha256": sha256_text(body),
        "excerpt_sha256": sha256_text(body[:40]),
    }


class SpanCheckTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = make_book(Path(self._tmp.name))
        self.pages = load_page_texts(self.root)

    def _evidence(self, claims: list[dict]) -> Path:
        payload = {
            "schema_version": 1,
            "source_id": "demo-book",
            "retrieval": "retrieval/demo.json",
            "generated_at": "2026-11-10T00:00:00+00:00",
            "claims": claims,
            "citation_pool": [],
        }
        target = self.root / "evidence" / "demo.evidence.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding="utf-8")
        return target

    def test_present_quote_and_number_pass(self):
        body = self.pages[3]
        evidence = self._evidence(
            [
                {
                    "claim_id": "C1",
                    "statement": "Pressure and velocity are related.",
                    "quote": "The pressure field around a vehicle determines the velocity field.",
                    "citations": [_citation("demo-book", 3, body)],
                    "verification": "pending",
                }
            ]
        )
        report = check_spans(self.root, evidence)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["claims"][0]["status"], "ok")

    def test_missing_quote_blocks(self):
        body = self.pages[3]
        evidence = self._evidence(
            [
                {
                    "claim_id": "C1",
                    "statement": "A quote that is not on the page.",
                    "quote": "This sentence does not appear in the source.",
                    "citations": [_citation("demo-book", 3, body)],
                }
            ]
        )
        report = check_spans(self.root, evidence)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["claims"][0]["status"], "quote_missing")

    def test_missing_number_warns_and_can_be_strict(self):
        body = self.pages[3]
        evidence = self._evidence(
            [
                {
                    "claim_id": "C1",
                    "statement": "The drag coefficient is 0.31 in 1932.",
                    "quote": "The pressure field around a vehicle determines the velocity field.",
                    "citations": [_citation("demo-book", 3, body)],
                }
            ]
        )
        report = check_spans(self.root, evidence)
        self.assertEqual(report["status"], "warn")
        self.assertEqual(report["claims"][0]["status"], "numbers_missing")
        strict = check_spans(self.root, evidence, strict_numbers=True)
        self.assertEqual(strict["status"], "blocked")

    def test_changed_page_hash_blocks(self):
        body = self.pages[3]
        citation = _citation("demo-book", 3, body)
        citation["page_sha256"] = "0" * 64
        evidence = self._evidence(
            [
                {
                    "claim_id": "C1",
                    "statement": "Pressure and velocity are related.",
                    "quote": "The pressure field",
                    "citations": [citation],
                }
            ]
        )
        report = check_spans(self.root, evidence)
        self.assertEqual(report["status"], "blocked")
        self.assertIn("hash changed", report["claims"][0]["detail"])

    def test_writes_json_and_markdown(self):
        body = self.pages[3]
        evidence = self._evidence(
            [
                {
                    "claim_id": "C1",
                    "statement": "Pressure and velocity are related.",
                    "quote": "The pressure field",
                    "citations": [_citation("demo-book", 3, body)],
                }
            ]
        )
        report = check_spans(self.root, evidence)
        paths = write_spancheck(self.root, report, evidence)
        self.assertTrue(paths["json"].is_file())
        self.assertTrue(paths["markdown"].is_file())


class BookMapTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = make_book(Path(self._tmp.name))
        pages = load_page_texts(self.root)
        entries, info = resolve(pages)
        save(self.root, entries, info)
        write_page_map(self.root, offset=int(info.get("page_offset") or 0))
        build_units(self.root, entries)

    def test_map_reports_chapters_units_and_spans(self):
        report = build_bookmap(self.root)
        self.assertEqual(report["pdf_pages"], 12)
        titles = [row["title"] for row in report["chapters"]]
        self.assertEqual(titles, ["Fundamentals", "Drag", "Wind tunnel"])
        self.assertEqual(report["chapters"][0]["pdf_start"], 2)
        self.assertEqual(report["chapters"][1]["pdf_start"], 6)
        self.assertEqual(report["chapters"][2]["pdf_end"], 12)
        self.assertEqual(report["units_total"], 3)
        paths = write_bookmap(self.root, report)
        self.assertTrue(paths["json"].is_file())
        self.assertTrue(paths["markdown"].is_file())
