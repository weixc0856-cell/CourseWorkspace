from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from knowledge_studio import index as index_mod
from knowledge_studio.evidence import EvidenceError, attach
from knowledge_studio.extract import extract_pdf, extract_text, load_page_texts, write_pages
from knowledge_studio.models import SourceMeta
from knowledge_studio.qa import verify
from knowledge_studio.retrieve import export_lesson, retrieve, write
from knowledge_studio.segment import build_units, load_units
from knowledge_studio.toc import resolve, save, write_page_map

BOOK_PAGES = [
    "Vehicle Aerodynamics Handbook\nContents\n"
    "1 Fundamentals .......... 6\n"
    "1.1 Pressure and velocity .. 7\n"
    "2 Drag ................... 10\n"
    "3 Wind tunnel ........... 13",
    "1 Fundamentals\nThis chapter introduces the fundamentals of vehicle aerodynamics.",
    "1.1 Pressure and velocity\nThe pressure field around a vehicle determines the velocity field.",
    "The boundary layer grows along the body and separates near the rear.",
    "Flow around a vehicle is governed by the Navier-Stokes equations.",
    "2 Drag\nDrag is the resistance force acting opposite to the direction of motion.",
    "2.1 Drag mechanisms\nThe drag coefficient combines pressure drag and friction drag. "
    "气动阻力 由压差阻力和摩擦阻力组成。气动阻力 与 车身造型 有关。",
    "Flow separation increases pressure drag at the rear of the vehicle.",
    "3 Wind tunnel\nWind tunnel testing measures drag and lift. 风洞 实验 测量 气动阻力。",
    "Wind tunnel balance sensors record forces on the model.",
    "The wind tunnel test section has a uniform velocity profile.",
    "Corrections for blockage are applied to wind tunnel results.",
]


def build_pdf(page_texts: list[str]) -> bytes:
    """Minimal multi-page PDF with text, used to exercise the pypdf backend."""

    count = len(page_texts)
    kids = " ".join(f"{3 + index * 2} 0 R" for index in range(count))
    font_object = 3 + 2 * count
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {count} >>",
    ]
    for index, text in enumerate(page_texts):
        content_object = 4 + 2 * index
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_object} 0 R >> >> "
            f"/Contents {content_object} 0 R >>"
        )
        escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        stream = f"BT /F1 14 Tf 72 720 Td ({escaped}) Tj ET"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    output = "%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output += f"{number} 0 obj\n{body}\nendobj\n"
    xref = len(output)
    output += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for offset in offsets:
        output += f"{offset:010d} 00000 n \n"
    output += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    )
    return output.encode("latin-1")


def make_book(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    source = root / "book.txt"
    source.write_text("".join(BOOK_PAGES), encoding="utf-8")
    extraction = extract_text(source)
    records = write_pages(root, extraction)
    (root / "original").mkdir(exist_ok=True)
    original = root / "original" / "book.txt"
    shutil.copy2(source, original)
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    meta = SourceMeta(
        source_id="demo-book",
        title="Demo Aerodynamics",
        authors=["A. Author"],
        original="original/book.txt",
        original_sha256=digest,
        pdf_pages=len(records),
        extractor=extraction.extractor,
        extracted_at="2026-11-09T00:00:00+00:00",
    )
    (root / "source.yaml").write_text(
        yaml.safe_dump(meta.model_dump(mode="json"), allow_unicode=True), encoding="utf-8"
    )
    write_page_map(root, records)
    return root


class ExtractTest(unittest.TestCase):
    def test_text_pages_split_on_form_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "book.txt"
            path.write_text("one" + chr(12) + "two" + chr(12) + "three", encoding="utf-8")
            extraction = extract_text(path)
            self.assertEqual(len(extraction.pages), 3)
            self.assertEqual(extraction.pages[1].text, "two")
            self.assertEqual(extraction.pages[2].text, "three")

    def test_text_markers_must_be_sequential(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "book.txt"
            path.write_text(
                "<!-- ks:page pdf=2 -->\ntwo\n<!-- ks:page pdf=1 -->\none", encoding="utf-8"
            )
            with self.assertRaises(Exception):
                extract_text(path)

    def test_pdf_backend_extracts_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "small.pdf"
            path.write_bytes(build_pdf(["Chapter 1 Drag", "Chapter 2 Lift"]))
            extraction = extract_pdf(path)
            self.assertEqual(len(extraction.pages), 2)
            self.assertIn("Drag", extraction.pages[0].text)
            self.assertIn("Lift", extraction.pages[1].text)
            self.assertTrue(extraction.extractor.startswith("pypdf"))


class KnowledgePipelineTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = make_book(Path(self._tmp.name))

    def _toc(self):
        pages = load_page_texts(self.root)
        entries, info = resolve(pages)
        save(self.root, entries, info)
        write_page_map(self.root, offset=int(info.get("page_offset") or 0))
        return entries, info

    def test_toc_parses_and_calibrates_page_offset(self):
        entries, info = self._toc()
        self.assertEqual(info["method"], "toc")
        self.assertEqual(info["page_offset"], -4)
        by_title = {entry.title: entry for entry in entries}
        self.assertEqual(by_title["Fundamentals"].pdf_page, 2)
        self.assertEqual(by_title["Drag"].pdf_page, 6)
        self.assertEqual(by_title["Wind tunnel"].pdf_page, 9)
        self.assertEqual(by_title["Pressure and velocity"].pdf_page, 3)

    def test_units_follow_chapters_and_cover_pages_once(self):
        entries, _ = self._toc()
        units = build_units(self.root, entries)
        self.assertEqual(len(units), 3)
        self.assertEqual(units[0].pdf_pages, (2, 5))
        self.assertEqual(units[1].pdf_pages, (6, 8))
        self.assertEqual(units[2].pdf_pages, (9, 12))
        self.assertEqual(units[1].keywords != [], True)
        self.assertEqual(units[1].figure_count, 0)
        self.assertTrue(any("pages_" in name for name in units[0].files))

    def test_index_and_english_retrieval_respects_the_page_budget(self):
        entries, _ = self._toc()
        build_units(self.root, entries)
        index_mod.build(self.root, "demo-book")
        result = retrieve(self.root, "drag coefficient", max_pages=3)
        self.assertLessEqual(result.pages_read, 3)
        self.assertGreater(result.pages_read, 0)
        self.assertLess(result.pages_read, result.total_pages)
        self.assertEqual(result.units, ["U02"])
        for excerpt in result.excerpts:
            self.assertGreaterEqual(excerpt.pdf_page, 5)
            self.assertLessEqual(excerpt.pdf_page, 8)
        self.assertTrue(all(citation.page_sha256 for citation in result.citations))

    def test_chinese_query_matches_page_text(self):
        entries, _ = self._toc()
        build_units(self.root, entries)
        index_mod.build(self.root, "demo-book")
        result = retrieve(self.root, "气动阻力", max_pages=4)
        pages = {excerpt.pdf_page for excerpt in result.excerpts}
        self.assertIn(7, pages)
        self.assertTrue(
            all(
                "气动阻力" in excerpt.text
                for excerpt in result.excerpts
                if excerpt.pdf_page == 7
            )
        )

    def test_retrieval_without_terms_is_an_error(self):
        entries, _ = self._toc()
        build_units(self.root, entries)
        index_mod.build(self.root, "demo-book")
        with self.assertRaises(Exception):
            retrieve(self.root, "!!!", max_pages=3)

    def test_retrieval_is_written_and_verified(self):
        entries, _ = self._toc()
        build_units(self.root, entries)
        index_mod.build(self.root, "demo-book")
        result = retrieve(self.root, "drag coefficient", max_pages=4)
        paths = write(self.root, result)
        self.assertTrue(paths["json"].is_file())
        self.assertTrue(paths["markdown"].is_file())
        report = verify(self.root)
        self.assertEqual(report["status"], "pass", report["checks"])
        self.assertEqual(report["counts"]["retrievals"], 1)

    def test_evidence_must_cite_retrieved_pages(self):
        entries, _ = self._toc()
        build_units(self.root, entries)
        index_mod.build(self.root, "demo-book")
        result = retrieve(self.root, "drag coefficient", max_pages=4)
        paths = write(self.root, result)
        claims = Path(self._tmp.name) / "claims.json"
        claims.write_text(
            json.dumps([{"claim_id": "C001", "statement": "Drag has two components", "pages": [6]}]),
            encoding="utf-8",
        )
        target = attach(self.root, paths["json"], claims)
        self.assertTrue(target.is_file())
        evidence = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(evidence["claims"][0]["verification"], "pending")
        self.assertEqual(evidence["claims"][0]["citations"][0]["pdf_page"], 6)

        bad = Path(self._tmp.name) / "bad.json"
        bad.write_text(
            json.dumps([{"claim_id": "C002", "statement": "Lift", "pages": [11]}]),
            encoding="utf-8",
        )
        with self.assertRaises(EvidenceError):
            attach(self.root, paths["json"], bad)

    def test_export_writes_a_lesson_source_and_fragment(self):
        entries, _ = self._toc()
        build_units(self.root, entries)
        index_mod.build(self.root, "demo-book")
        result = retrieve(self.root, "wind tunnel", max_pages=4)
        lesson = Path(self._tmp.name) / "lessons" / "demo-lesson"
        lesson.mkdir(parents=True)
        exported = export_lesson(self.root, result, lesson)
        self.assertTrue(exported["source"].is_file())
        fragment = yaml.safe_load(exported["fragment"].read_text(encoding="utf-8"))
        entry = fragment["sources"][0]
        self.assertEqual(entry["id"], "S1")
        self.assertEqual(entry["kind"], "markdown")
        self.assertEqual(len(entry["sha256"]), 64)
        self.assertTrue(exported["source"].read_text(encoding="utf-8").startswith("# demo-book"))

    def test_verify_blocks_when_a_page_hash_changes(self):
        entries, _ = self._toc()
        build_units(self.root, entries)
        index_mod.build(self.root, "demo-book")
        page = self.root / "pages" / "p0006.md"
        page.write_text(page.read_text(encoding="utf-8") + "\ntampered\n", encoding="utf-8")
        report = verify(self.root)
        self.assertEqual(report["status"], "blocked")
        self.assertIn("KS-03", [check["id"] for check in report["checks"] if check["status"] == "blocked"])


class FallbackTocTest(unittest.TestCase):
    def test_chapter_headings_are_used_when_toc_does_not_parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "book.txt"
            path.write_text(
                "Preface\nNo contents page here.\f"
                "Chapter 1 Flow\nText about flow.\f"
                "Chapter 2 Drag\nText about drag.",
                encoding="utf-8",
            )
            extraction = extract_text(path)
            write_pages(Path(tmp), extraction)
            entries, info = resolve(load_page_texts(Path(tmp)))
            self.assertEqual(info["method"], "headings")
            self.assertEqual([entry.pdf_page for entry in entries], [2, 3])


if __name__ == "__main__":
    unittest.main()
