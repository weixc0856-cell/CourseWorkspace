from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from course_control.authoring.digest import build_digest
from course_control.authoring.ingest import IngestError, ingest


class IngestTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        self.lesson = self.workspace / "lessons" / "test-lesson"
        self.lesson.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_markdown_ingest_and_digest(self):
        source = self.workspace / "note.md"
        source.write_text(
            "# Attention\n\nScaled dot-product attention uses Q, K and V.\n\n## Scaling\n\nDivide by sqrt(d_k).\n",
            encoding="utf-8",
        )
        entry = ingest(
            self.workspace, self.lesson, str(source), kind="markdown", source_id="S1"
        )
        self.assertEqual(entry.id, "S1")
        self.assertEqual(entry.kind, "markdown")
        self.assertTrue((self.lesson / entry.local_path).is_file())
        self.assertTrue((self.lesson / "authoring" / "sources.yaml").is_file())

        digest = build_digest(self.lesson)
        refs = {section.ref for section in digest.sections}
        self.assertIn("S1-1", refs)
        self.assertIn("S1-1.1", refs)
        self.assertTrue((self.lesson / "authoring" / "source-digest.json").is_file())
        self.assertTrue((self.lesson / "authoring" / "source-digest.md").is_file())

    def test_second_source_gets_next_id(self):
        first = self.workspace / "a.md"
        first.write_text("# A\n\nalpha\n", encoding="utf-8")
        second = self.workspace / "b.md"
        second.write_text("# B\n\nbeta\n", encoding="utf-8")
        ingest(self.workspace, self.lesson, str(first), kind="markdown")
        entry = ingest(self.workspace, self.lesson, str(second), kind="markdown")
        self.assertEqual(entry.id, "S2")

    def test_empty_source_fails(self):
        source = self.workspace / "empty.md"
        source.write_text("   \n", encoding="utf-8")
        with self.assertRaises(IngestError):
            ingest(self.workspace, self.lesson, str(source), kind="markdown")

    def test_unreadable_url_fails(self):
        with self.assertRaises(IngestError):
            ingest(
                self.workspace,
                self.lesson,
                "http://127.0.0.1:9/never",
                kind="url",
            )

    def test_digest_detects_tampering(self):
        source = self.workspace / "note.md"
        source.write_text("# A\n\nalpha\n", encoding="utf-8")
        entry = ingest(self.workspace, self.lesson, str(source), kind="markdown", source_id="S1")
        body = self.lesson / entry.local_path
        body.write_text("# A\n\nchanged\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            build_digest(self.lesson)


class IngestHtmlTest(unittest.TestCase):
    def test_extractor_skips_scripts_and_nav(self):
        from course_control.authoring.ingest import html_to_markdown

        title, markdown = html_to_markdown(
            "<html><head><title>Doc</title><style>x{}</style></head>"
            "<body><nav>menu</nav><article><h1>Heading</h1>"
            "<p>First paragraph.</p><script>bad()</script>"
            "<h2>Sub</h2><p>Second paragraph.</p></article>"
            "<footer>foot</footer></body></html>"
        )
        self.assertEqual(title, "Doc")
        self.assertIn("# Heading", markdown)
        self.assertIn("First paragraph.", markdown)
        self.assertIn("## Sub", markdown)
        self.assertNotIn("menu", markdown)
        self.assertNotIn("bad()", markdown)
        self.assertNotIn("foot", markdown)


if __name__ == "__main__":
    unittest.main()
