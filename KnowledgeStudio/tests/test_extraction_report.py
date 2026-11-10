from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from knowledge_studio.report import analyse, parse_pages, render_markdown, write


def _write_source(root: Path, pages: int) -> None:
    original = root / "original" / "book.pdf"
    original.parent.mkdir(parents=True, exist_ok=True)
    payload = b"%PDF-1.4 extraction report fixture\n"
    original.write_bytes(payload)
    source = {
        "schema_version": 1,
        "source_id": "fixture",
        "title": "Fixture Book",
        "original": "original/book.pdf",
        "original_sha256": hashlib.sha256(payload).hexdigest(),
        "pdf_pages": pages,
        "extractor": "fixture",
        "extracted_at": "2026-11-10T00:00:00+00:00",
    }
    (root / "source.yaml").write_text(
        yaml.safe_dump(source, allow_unicode=True), encoding="utf-8"
    )


def make_root(tmp: str, texts: dict[int, str], total: int | None = None) -> Path:
    root = Path(tmp)
    root.mkdir(parents=True, exist_ok=True)
    _write_source(root, total if total is not None else max(texts))
    (root / "pages").mkdir(exist_ok=True)
    for number, text in texts.items():
        (root / "pages" / f"p{number:04d}.md").write_text(
            f"<!-- ks:page pdf={number} -->\n\n{text}\n", encoding="utf-8"
        )
    page_map = {
        "schema_version": 1,
        "page_offset": 0,
        "pages": [
            {"pdf_page": number, "printed_page": number} for number in sorted(texts)
        ],
    }
    (root / "metadata").mkdir(exist_ok=True)
    (root / "metadata" / "page_map.json").write_text(
        json.dumps(page_map), encoding="utf-8"
    )
    return root


def body(marker: str) -> str:
    return (
        f"{marker}\n"
        "The drag coefficient combines pressure drag and friction drag over the body. "
        "Wind tunnel testing measures the forces acting on the vehicle at speed.\n"
    )


class ExtractionReportTest(unittest.TestCase):
    def test_parse_pages_accepts_lists_and_ranges(self):
        self.assertEqual(parse_pages("12,13-15,20"), {12, 13, 14, 15, 20})
        self.assertEqual(parse_pages(""), set())

    def test_empty_page_blocks_the_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(tmp, {1: body("Drag"), 2: "", 3: body("Lift")})
            report = analyse(root)
            self.assertEqual(report["status"], "blocked")
            self.assertEqual(report["pages"]["empty"], [2])
            self.assertTrue(any("no text" in item for item in report["fatal"]))

    def test_allow_listed_empty_page_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(tmp, {1: body("Drag"), 2: "", 3: body("Lift")})
            report = analyse(root, allow_empty={2})
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["pages"]["allow_empty"], [2])
            self.assertEqual(report["pages"]["empty"], [])

    def test_missing_page_file_is_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(tmp, {1: body("Drag"), 3: body("Lift")}, total=3)
            report = analyse(root)
            self.assertEqual(report["status"], "blocked")
            self.assertEqual(report["pages"]["missing"], [2])

    def test_hyphenation_and_replacement_characters_are_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(
                tmp,
                {
                    1: "Vehicle aero-\ndynamics is the study of air flow around bodies.\n",
                    2: "The drag � coefficient is dimensionless and depends on shape.\n",
                },
            )
            report = analyse(root)
            self.assertEqual(report["pages"]["hyphenated"], [1])
            self.assertEqual(report["pages"]["replacement"], [2])
            self.assertEqual(len(report["serious"]), 2)

    def test_repeated_header_is_reported(self):
        header = "Aerodynamics of Road Vehicles"
        texts = {number: f"{header}\n{body('Chapter')}" for number in range(1, 7)}
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(tmp, texts)
            report = analyse(root)
            lines = [item["line"] for item in report["repeated_lines"]]
            self.assertIn(header.lower(), lines)

    def test_toc_entry_missing_from_its_page_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(tmp, {1: body("Drag")})
            toc = {
                "schema_version": 1,
                "method": "dotted",
                "entries": [
                    {"level": 1, "title": "Aerodynamic Forces", "pdf_page": 1},
                ],
            }
            (root / "metadata" / "toc.json").write_text(
                json.dumps(toc), encoding="utf-8"
            )
            report = analyse(root)
            self.assertEqual(len(report["toc"]["anchor_misses"]), 1)
            self.assertEqual(report["toc"]["anchor_misses"][0]["pdf_page"], 1)

    def test_report_is_written_in_both_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(tmp, {1: body("Drag")})
            report = analyse(root)
            paths = write(root, report)
            self.assertTrue(paths["json"].is_file())
            markdown = paths["markdown"].read_text(encoding="utf-8")
            self.assertIn("# Extraction report — fixture", markdown)
            self.assertIn("必须处理", markdown)
            self.assertEqual(json.loads(paths["json"].read_text(encoding="utf-8"))["status"], "pass")
            self.assertIn("status:", render_markdown(report))


if __name__ == "__main__":
    unittest.main()
