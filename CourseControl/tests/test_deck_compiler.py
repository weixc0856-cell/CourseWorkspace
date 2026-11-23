"""The deck compiler must pour production.yaml data into EVDS archetypes.

Locks the contract the plain reveal.js shell never satisfied: archetype per
page driven by shot data, book figures bound 1:1 to production.yaml objects,
a non-empty source citation on every book-figure page, canonical colour
tokens (not the CSS file's drifted defaults), and no invented numbers.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.content.paths import LessonPaths
from course_control.rendering.deck_compiler import (
    ARCHETYPES,
    choose_archetype,
    compile_deck,
    parse_slides,
)


def _lesson_yaml(slug: str) -> str:
    return (
        f"schema_version: 1\nlesson_id: {slug}\ntitle_en: Demo\ntitle_zh: 演示\n"
        "status: draft\n"
        "content:\n  slides: slides.md\n  notes: lecture_notes.md\n"
        "  storyboard: storyboard.yaml\n  assets: assets/\n"
        "outputs:\n  fps: 30\n  resolution: [1920, 1080]\n"
        "  slides_canvas: [1920, 1080]\n  animation_canvas: [1920, 1080]\n"
        "engines: [motion_canvas]\ncompose:\n  mode: deck\n"
    )


def _shot(sid: str, purpose: str, visual_type: str, objects: list[str] | None = None, note: str = "") -> str:
    lines = [
        f"  - id: {sid}",
        "    duration_s: 8",
        f"    purpose: {purpose}",
        f"    visual_type: {visual_type}",
        "    grammar: long_take",
        "    renderer: motion_canvas",
        f"    source: demo/{sid}.tsx",
    ]
    if objects:
        lines.append("    objects:")
        lines.extend(f"    - assets/{o}" for o in objects)
    if note:
        lines.append("    actions:")
        lines.append("    - type: visual_event")
        lines.append(f"      note: {note}")
    return "\n".join(lines) + "\n"


class ParseSlidesTest(unittest.TestCase):
    def test_heading_bullets_and_source(self):
        text = (
            "## 1. Two bodies, one air\n\n- A wing keeps flow attached\n- A car loses it\n\n"
            "---\n\n## 2. What the smoke shows\n\n- Filaments stay ordered\n\n"
            "<small>Source: Hucho, Fig. 1.4a, p. 26</small>\n"
        )
        pages = parse_slides(text)
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0].heading, "Two bodies, one air")
        self.assertEqual(pages[0].bullets, ["A wing keeps flow attached", "A car loses it"])
        self.assertIsNone(pages[0].source)
        self.assertEqual(pages[1].source, "Source: Hucho, Fig. 1.4a, p. 26")


class ArchetypeTest(unittest.TestCase):
    def _seq(self, shots: str):
        import yaml

        data = yaml.safe_load(
            "schema_version: 1\nlesson: demo\nsequences:\n- id: seq_01\n  title: T\n  shots:\n" + shots
        )
        from course_control.content.production import ProductionPlan

        return ProductionPlan.model_validate(data).sequences[0]

    def test_book_figure_wins_over_purpose(self):
        seq = self._seq(_shot("s1", "compare", "book_figure_annotated", ["fig.png"]))
        self.assertEqual(choose_archetype(seq), "annotated")

    def test_all_data_chart_is_data(self):
        seq = self._seq(_shot("s1", "explain", "data_chart") + _shot("s2", "explain", "data_chart"))
        self.assertEqual(choose_archetype(seq), "data")

    def test_summarize_is_process(self):
        seq = self._seq(_shot("s1", "summarize", "diagram_animated"))
        self.assertEqual(choose_archetype(seq), "process")

    def test_compare_is_comparison(self):
        seq = self._seq(_shot("s1", "compare", "diagram_animated") + _shot("s2", "compare", "diagram_animated"))
        self.assertEqual(choose_archetype(seq), "comparison")

    def test_default_is_editorial(self):
        seq = self._seq(_shot("s1", "explain", "diagram_animated"))
        self.assertEqual(choose_archetype(seq), "editorial")


class CompileDeckTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.slug = "demo"
        self.lesson = self.ws / "lessons" / self.slug
        (self.lesson / "assets").mkdir(parents=True)
        (self.lesson / "authoring").mkdir(parents=True)
        (self.lesson / "lesson.yaml").write_text(_lesson_yaml(self.slug), encoding="utf-8")
        (self.lesson / "lecture_notes.md").write_text("notes\n", encoding="utf-8")
        (self.lesson / "storyboard.yaml").write_text(
            "schema_version: 1\nlesson: demo\nshots:\n"
            "  - id: s1\n    slide: 1\n    engine: motion_canvas\n"
            "    scene: demo/scene.tsx\n    cue_seconds: 0\n    expected_duration_s: 8\n",
            encoding="utf-8",
        )
        # A real 1x1 PNG so the asset-existence check passes without Pillow.
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000d49444154789c6360000002000100ffff03000006000557bfabd400"
            "00000049454e44ae426082"
        )
        (self.lesson / "assets" / "fig.png").write_bytes(png)
        self.slides_md = self.lesson / "slides.md"
        self.slides_md.write_text(
            "## 1. Compare\n\n- Wing attached\n- Car detached\n- Wake lives\n\n"
            "---\n\n## 2. Evidence\n\n- Filaments ordered\n- Let go at rear\n- Bubble hidden\n\n"
            "<small>Source: Hucho, Fig. 1.4a, p. 26</small>\n",
            encoding="utf-8",
        )
        self.production = self.lesson / "authoring" / "production.yaml"
        self.production.write_text(
            "schema_version: 1\nlesson: demo\nsequences:\n"
            "- id: seq_01\n  title: Compare\n  shots:\n"
            + _shot("s01_01", "compare", "diagram_animated", note="trace streamlines, hold attached")
            + _shot("s01_02", "compare", "diagram_animated", note="trace over car, detach at rear")
            + "- id: seq_02\n  title: Evidence\n  shots:\n"
            + _shot("s02_01", "demonstrate", "book_figure_annotated", ["fig.png"], note="spotlight the roof"),
            encoding="utf-8",
        )
        self.paths = LessonPaths.load(self.ws, self.lesson)

    def tearDown(self):
        self._tmp.cleanup()

    def test_manifest_pages_archetypes_and_assets(self):
        manifest = compile_deck(self.paths, font="default")
        self.assertEqual(manifest["pages"], 2)
        self.assertEqual([p["archetype"] for p in manifest["archetypes"]], ["hero", "annotated"])
        self.assertEqual(manifest["assets_used"], ["assets/fig.png"])
        for page in manifest["archetypes"]:
            self.assertIn(page["archetype"], ARCHETYPES)

    def test_book_figure_page_has_nonempty_source(self):
        compile_deck(self.paths, font="default")
        html = (self.paths.build_root / "deck" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Source · Hucho, Fig. 1.4a, p. 26", html)
        self.assertIn('src="/lessons/demo/assets/fig.png"', html)

    def test_schematic_page_has_no_fabricated_source(self):
        compile_deck(self.paths, font="default")
        html = (self.paths.build_root / "deck" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Schematic · no external source", html)

    def test_canonical_palette_overrides_drifted_css(self):
        compile_deck(self.paths, font="default")
        html = (self.paths.build_root / "deck" / "index.html").read_text(encoding="utf-8")
        self.assertIn("#E8733B", html)  # canonical orange, not the CSS file's #A8422B
        self.assertIn("#FBFAF7", html)  # canonical paper, not #F4EFEA
        self.assertIn("#EDE7DA", html)  # book-figure panel stays the mandated warm white

    def test_missing_local_font_fails_loud(self):
        # No silent fallback: a declared local OFL face that is absent must raise.
        with self.assertRaises(FileNotFoundError):
            compile_deck(self.paths, font="inter")

    def test_local_font_copied_and_face_emitted(self):
        fonts = self.ws / "references" / "fonts" / "inter"
        fonts.mkdir(parents=True)
        (fonts / "Inter-var.ttf").write_bytes(b"\x00\x01\x00\x00dummy")
        (fonts / "OFL.txt").write_text("SIL Open Font License", encoding="utf-8")
        manifest = compile_deck(self.paths, font="inter")
        deck = self.paths.build_root / "deck"
        self.assertTrue((deck / "fonts" / "Inter-var.ttf").is_file())
        self.assertTrue((deck / "fonts" / "OFL.txt").is_file())
        html = (deck / "index.html").read_text(encoding="utf-8")
        self.assertIn("@font-face", html)
        self.assertIn("fonts/Inter-var.ttf", html)  # relative, no absolute path / CDN
        self.assertEqual(manifest["font"], "inter")

    def test_source_single_line_and_mapping_note_off_screen(self):
        slides = self.paths.content_path(self.paths.lesson.content.slides)
        text = slides.read_text(encoding="utf-8")
        slides.write_text(
            text.replace(
                "<small>Source: Hucho, Fig. 1.4a, p. 26</small>",
                "<small>Source: Hucho, Fig. 1.4a, p. 26 · printed page = PDF page - 21</small>",
            ),
            encoding="utf-8",
        )
        compile_deck(self.paths, font="default")
        deck = self.paths.build_root / "deck"
        html = (deck / "index.html").read_text(encoding="utf-8")
        self.assertIn("white-space: nowrap", html)
        self.assertNotIn("printed page", html)  # mapping note is evidence, not screen text
        prov = json.loads((deck / "citation-provenance.json").read_text(encoding="utf-8"))
        full = [c["full"] for c in prov["citations"]]
        self.assertTrue(any("printed page = PDF page - 21" in f for f in full))

    def test_manifest_binds_current_input_hashes(self):
        import hashlib

        manifest = compile_deck(self.paths, font="default")
        self.assertEqual(
            manifest["slides_sha256"], hashlib.sha256(self.slides_md.read_bytes()).hexdigest()
        )
        self.assertEqual(
            manifest["production_sha256"], hashlib.sha256(self.production.read_bytes()).hexdigest()
        )

    def test_missing_asset_is_loud(self):
        (self.lesson / "assets" / "fig.png").unlink()
        with self.assertRaises(FileNotFoundError):
            compile_deck(self.paths, font="default")

    def test_page_count_mismatch_is_loud(self):
        self.slides_md.write_text("## 1. Only one page\n\n- bullet\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            compile_deck(self.paths, font="default")


if __name__ == "__main__":
    unittest.main()