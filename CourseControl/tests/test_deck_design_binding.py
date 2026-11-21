"""E6: deck design binding — plain pages must fail the check and the sign-off."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from course_control.authoring.llm import AuthoringError
from course_control.authoring.pipeline import sign_storyboard_page
from course_control.authoring.storyboard_page import build
from course_control.production.checks_deck_design import deck_design_problems

from tests.test_storyboard_page import StoryboardPageTest

PRODUCTION = {
    "lesson": "demo",
    "sequences": [
        {
            "id": "seq_01",
            "title": "What the smoke shows",
            "shots": [
                {
                    "id": "s01_01",
                    "visual_type": "book_figure_annotated",
                    "objects": ["assets/fig-a.png"],
                }
            ],
        },
        {"id": "seq_02", "title": "Takeaway", "shots": [{"id": "s02_01"}]},
    ],
}

COMPLIANT_DECK = """<div class="reveal"><div class="slides">
<section class="slide--annotated">
  <figure class="annotated-container"><img src="assets/fig-a.png" alt="smoke"></figure>
  <div class="slide-footer"><span class="source">Hucho, Fig. 1.4a, p. 12</span><span class="folio">1</span></div>
</section>
<section class="slide--editorial"><p class="headline">Takeaway</p>
  <div class="slide-footer"><span class="folio">2</span></div>
</section>
</div></div>"""

PLAIN_DECK = """<div class="reveal"><div class="slides">
<section><h2>What the smoke shows</h2><ul><li>bullet</li></ul></section>
<section><h2>Takeaway</h2><ul><li>bullet</li></ul></section>
</div></div>"""


class DeckDesignCheckTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.lesson = self.root / "lessons" / "demo"
        (self.lesson / "authoring").mkdir(parents=True)
        (self.lesson / "lesson.yaml").write_text(
            "schema_version: 1\nlesson_id: demo\ncompose:\n  mode: deck\n",
            encoding="utf-8",
        )
        (self.lesson / "authoring" / "production.yaml").write_text(
            yaml.safe_dump(PRODUCTION, sort_keys=False), encoding="utf-8"
        )
        self.build_root = self.root / "build" / "demo"
        (self.build_root / "deck").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _deck(self, html: str) -> None:
        (self.build_root / "deck" / "index.html").write_text(html, encoding="utf-8")

    def _check(self):
        return deck_design_problems(self.lesson, self.build_root)

    def test_compliant_deck_passes(self):
        self._deck(COMPLIANT_DECK)
        status, findings, stats = self._check()
        self.assertEqual(status, "pass", findings)
        self.assertEqual(stats, {"pages": 2, "sequences": 2})

    def test_plain_reveal_shell_fails(self):
        self._deck(PLAIN_DECK)
        status, findings, _ = self._check()
        self.assertEqual(status, "fail")
        self.assertTrue(any("archetype" in f for f in findings))

    def test_process_archetype_accepted_summary_rejected(self):
        # 版式系统 §3.1 canonical six include process, not summary.
        self._deck(COMPLIANT_DECK.replace("slide--editorial", "slide--process"))
        status, findings, _ = self._check()
        self.assertEqual(status, "pass", findings)
        self._deck(COMPLIANT_DECK.replace("slide--editorial", "slide--summary"))
        status, findings, _ = self._check()
        self.assertEqual(status, "fail")
        self.assertTrue(any("archetype" in f for f in findings))

    def test_instruction_leak_fails(self):
        self._deck(COMPLIANT_DECK.replace(
            '<figure class="annotated-container">',
            '<figure class="annotated-container">'
            '<div class="callout-badge">spotlight sweep along original smoke…</div>',
        ))
        status, findings, _ = self._check()
        self.assertEqual(status, "fail")
        self.assertTrue(any("instruction leaked" in f for f in findings))

    def test_truncated_badge_alone_fails(self):
        self._deck(COMPLIANT_DECK.replace(
            '<figure class="annotated-container">',
            '<figure class="annotated-container">'
            '<div class="callout-badge">pin labels on the closed recirculation…</div>',
        ))
        status, findings, _ = self._check()
        self.assertEqual(status, "fail")
        self.assertTrue(any("instruction leaked" in f for f in findings))

    def test_physical_labels_pass(self):
        self._deck(COMPLIANT_DECK.replace(
            '<figure class="annotated-container">',
            '<figure class="annotated-container">'
            '<div class="callout-badge">separation line</div>'
            '<div class="callout-badge">closed recirculation bubble</div>',
        ))
        status, findings, _ = self._check()
        self.assertEqual(status, "pass", findings)

    def test_placeholder_mechanism_fails(self):
        svg = ('<svg viewBox="0 0 400 300"><rect x="70" y="130" width="260" '
               'height="70" rx="30" fill="#E3E0D7"/></svg>')
        self._deck(COMPLIANT_DECK.replace(
            '<p class="headline">Takeaway</p>',
            '<p class="headline">Takeaway</p>' + svg,
        ))
        status, findings, _ = self._check()
        self.assertEqual(status, "fail")
        self.assertTrue(any("placeholder mechanism" in f for f in findings))

    def test_book_figure_page_with_svg_exempt(self):
        svg = ('<svg viewBox="0 0 400 300"><rect x="70" y="130" width="260" '
               'height="70" rx="30" fill="#E3E0D7"/></svg>')
        self._deck(COMPLIANT_DECK.replace(
            '<figure class="annotated-container">',
            '<figure class="annotated-container">' + svg,
        ))
        status, findings, _ = self._check()
        self.assertEqual(status, "pass", findings)

    def test_data_page_without_numbers_fails(self):
        body = ('<svg viewBox="0 0 400 300"><text x="200" y="30">schematic — not measured</text>'
                '<rect x="120" y="60" width="260" height="30" rx="3"/>'
                '<text x="20" y="82">lost</text><text x="20" y="172">recovered</text></svg>')
        self._deck(COMPLIANT_DECK.replace(
            '<section class="slide--editorial"><p class="headline">Takeaway</p>',
            '<section class="slide--data"><p class="headline">Takeaway</p>' + body,
        ))
        status, findings, _ = self._check()
        self.assertEqual(status, "fail")
        self.assertTrue(any("no real numbers" in f for f in findings))
        self.assertFalse(any("placeholder mechanism" in f for f in findings))

    def test_data_page_with_percentages_passes(self):
        body = ('<svg viewBox="0 0 400 300"><text x="100" y="80">70-80%</text>'
                '<text x="250" y="80">10-15%</text><text x="330" y="80">8-12%</text>'
                '<text x="20" y="280">0%</text><text x="100" y="280">25%</text>'
                '<text x="180" y="280">50%</text><text x="260" y="280">75%</text>'
                '<text x="340" y="280">100%</text>'
                '<rect x="20" y="60" width="260" height="30" rx="3"/></svg>')
        self._deck(COMPLIANT_DECK.replace(
            '<section class="slide--editorial"><p class="headline">Takeaway</p>',
            '<section class="slide--data"><p class="headline">Takeaway</p>' + body,
        ))
        status, findings, _ = self._check()
        self.assertEqual(status, "pass", findings)

    def test_folio_and_kicker_numbers_do_not_count(self):
        body = ('<svg viewBox="0 0 400 300"><text x="200" y="30">schematic — not measured</text>'
                '<rect x="120" y="60" width="260" height="30" rx="3"/></svg>')
        self._deck(COMPLIANT_DECK.replace(
            '<section class="slide--editorial"><p class="headline">Takeaway</p>',
            '<section class="slide--data"><p class="headline">Takeaway</p>' + body,
        ))
        status, findings, _ = self._check()
        self.assertEqual(status, "fail")
        self.assertTrue(any("page 2" in f and "no real numbers" in f for f in findings))

    def test_folio_alone_is_not_a_citation(self):
        self._deck(COMPLIANT_DECK.replace(
            '<span class="source">Hucho, Fig. 1.4a, p. 12</span>', ""))
        status, findings, _ = self._check()
        self.assertEqual(status, "fail")
        self.assertTrue(any("page 1" in f and "citation" in f for f in findings))

    def test_source_outside_footer_does_not_count(self):
        self._deck(COMPLIANT_DECK.replace(
            '<div class="slide-footer"><span class="source">Hucho, Fig. 1.4a, p. 12</span>',
            '<span class="source">Hucho, Fig. 1.4a, p. 12</span><div class="slide-footer">'))
        status, findings, _ = self._check()
        self.assertEqual(status, "fail")
        self.assertTrue(any("citation" in f for f in findings))

    def test_missing_figure_binding_fails(self):
        self._deck(COMPLIANT_DECK.replace('src="assets/fig-a.png"', 'src="assets/other.png"'))
        status, findings, _ = self._check()
        self.assertEqual(status, "fail")
        self.assertTrue(any("fig-a.png" in f for f in findings))

    def test_data_asset_src_binding_counts(self):
        self._deck(COMPLIANT_DECK.replace(
            'src="assets/fig-a.png"', 'data-asset-src="assets/fig-a.png"'))
        status, findings, _ = self._check()
        self.assertEqual(status, "pass", findings)

    def test_page_count_mismatch_fails(self):
        self._deck(COMPLIANT_DECK.replace(
            '<section class="slide--editorial"><p class="headline">Takeaway</p>\n'
            '  <div class="slide-footer"><span class="folio">2</span></div>\n</section>', ""))
        status, findings, _ = self._check()
        self.assertEqual(status, "fail")
        self.assertTrue(any("page count" in f for f in findings))

    def test_missing_deck_html_is_not_run(self):
        status, findings, _ = self._check()
        self.assertEqual(status, "not_run")
        self.assertTrue(any("deck HTML missing" in f for f in findings))

    def test_shots_mode_not_applicable(self):
        (self.lesson / "lesson.yaml").write_text(
            "schema_version: 1\nlesson_id: demo\ncompose:\n  mode: shots\n",
            encoding="utf-8",
        )
        self._deck(COMPLIANT_DECK)
        status, _, _ = self._check()
        self.assertEqual(status, "not_run")


class DeckSignoffGateTest(StoryboardPageTest):
    def _write_production(self):
        (self.lesson / "authoring").mkdir(exist_ok=True)
        (self.lesson / "authoring" / "production.yaml").write_text(
            yaml.safe_dump(PRODUCTION, sort_keys=False), encoding="utf-8"
        )

    def _deck(self, html: str):
        (self.build_root / "deck").mkdir(parents=True, exist_ok=True)
        (self.build_root / "deck" / "index.html").write_text(html, encoding="utf-8")

    def _prepared(self):
        self._write_production()
        build("demo", self.lesson, self.build_root)
        self._approve_all()

    def test_missing_deck_html_blocks_signoff(self):
        self._prepared()
        with self.assertRaisesRegex(AuthoringError, "deck design binding"):
            sign_storyboard_page(self.root, self.lesson, "Wei Chen")

    def test_plain_deck_blocks_signoff(self):
        self._prepared()
        self._deck(PLAIN_DECK)
        with self.assertRaisesRegex(AuthoringError, "deck design binding"):
            sign_storyboard_page(self.root, self.lesson, "Wei Chen")

    def test_compliant_deck_signs(self):
        self._prepared()
        self._deck(COMPLIANT_DECK)
        sign_storyboard_page(self.root, self.lesson, "Wei Chen")


if __name__ == "__main__":
    unittest.main()