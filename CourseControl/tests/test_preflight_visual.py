"""Every beat must say what the viewer is looking at, and the budgets must add up.

These rules exist because a beat list and a slide deck can both be internally
valid while describing different videos: nothing compared the measured beat
total with the planned page budgets, and nothing required a beat to name a page
or a shot.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from course_control.production.episode_spec import Beat, Claim, EpisodeSpec, SourceRef
from course_control.production.preflight import run_preflight, visual_problems

SPEC_HEAD = """schema_version: 1
episode: demo
title: Demo
core_question: Why?
claims:
  - id: C01
    text: A claim.
    source: {chapter: "1", section: "1.1"}
beats:
  - {id: B1, type: question, seconds: 10, claims: [C01], visual: "@VISUAL@"}
  - {id: B2, type: case, seconds: 10, claims: [C01], visual: "page:1; static, reason: x"}
  - {id: B3, type: mechanism, seconds: 10, claims: [C01], visual: "page:1; static, reason: x"}
  - {id: B4, type: derivation, seconds: 10, claims: [C01], visual: "page:1; static, reason: x"}
  - {id: B5, type: evidence, seconds: 10, claims: [C01], visual: "page:1; static, reason: x"}
  - {id: B6, type: conclusion, seconds: 10, claims: [C01], visual: "page:1; static, reason: x"}
target_seconds: 720
min_seconds: 600
max_seconds: 900
cut_list: ["nothing cut"]
voice: {status: local}
rights: {figures_checked: true}
"""


def _spec(visual: str) -> EpisodeSpec:
    return EpisodeSpec(
        episode="demo",
        title="Demo",
        core_question="Why?",
        claims=[Claim(id="C01", text="A claim.", source=SourceRef(chapter="1", section="1.1"))],
        cut_list=["nothing cut"],
        beats=[
            Beat(id="B1", type="question", seconds=10, claims=["C01"], visual=visual),
            Beat(id="B2", type="case", seconds=10, claims=["C01"], visual="page:1; static, reason: x"),
            Beat(id="B3", type="mechanism", seconds=10, claims=["C01"], visual="page:1; static, reason: x"),
            Beat(id="B4", type="derivation", seconds=10, claims=["C01"], visual="page:1; static, reason: x"),
            Beat(id="B5", type="evidence", seconds=10, claims=["C01"], visual="page:1; static, reason: x"),
            Beat(id="B6", type="conclusion", seconds=10, claims=["C01"], visual="page:1; static, reason: x"),
        ],
    )


class VisualMappingTest(unittest.TestCase):
    def test_a_beat_without_visual_is_rejected(self):
        problems = visual_problems(_spec(""), page_count=5, shot_ids=set())
        self.assertTrue(any("beat.visual is required" in p for p in problems))

    def test_a_page_range_beyond_the_deck_is_rejected(self):
        problems = visual_problems(_spec("page:3-9"), page_count=5, shot_ids=set())
        self.assertTrue(any("exceeds the deck" in p for p in problems))

    def test_an_unknown_shot_is_rejected(self):
        problems = visual_problems(_spec("page:1; shot:ghost"), page_count=5, shot_ids={"real"})
        self.assertTrue(any("not in storyboard.yaml" in p for p in problems))

    def test_a_static_beat_needs_a_reason(self):
        problems = visual_problems(_spec("page:1-2"), page_count=5, shot_ids=set())
        self.assertTrue(any("static, reason" in p for p in problems))

    def test_beat_with_both_shot_and_static_is_rejected(self):
        problems = visual_problems(
            _spec("page:1; shot:real; static, reason: conflict"),
            page_count=5,
            shot_ids={"real"},
        )
        self.assertTrue(any("conflicting visual contract" in p for p in problems))

    def test_unreferenced_storyboard_shot_is_rejected(self):
        problems = visual_problems(
            _spec("page:1; shot:real"),
            page_count=5,
            shot_ids={"real", "orphaned_shot"},
        )
        self.assertTrue(any("orphaned_shot" in p for p in problems))

    def test_a_complete_mapping_passes(self):
        self.assertEqual(
            visual_problems(_spec("page:1-2; static, reason: cover"), page_count=5, shot_ids=set()),
            [],
        )
        self.assertEqual(
            visual_problems(
                _spec("page:3; shot:real"), page_count=5, shot_ids={"real"}
            ),
            [],
        )


class BudgetMismatchTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.lesson = Path(self._tmp.name) / "demo"
        (self.lesson / "authoring").mkdir(parents=True)
        (self.lesson / "slides.md").write_text("<h1>One</h1>\n", encoding="utf-8")
        (self.lesson / "storyboard.yaml").write_text(
            "schema_version: 1\nlesson: demo\nshots:\n"
            "  - {id: s1, slide: 1, engine: manim, scene: demo/x.py::X, cue_seconds: 0}\n",
            encoding="utf-8",
        )
        (self.lesson / "authoring" / "quality.rubric.yaml").write_text(
            "schema_version: 1\ndimensions:\n  content:\n    weight: 100\n    checks: []\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, spec_visual: str, budgets: list[float]) -> None:
        (self.lesson / "authoring" / "episode.spec.yaml").write_text(
            SPEC_HEAD.replace("@VISUAL@", spec_visual), encoding="utf-8"
        )
        notes = []
        for index, value in enumerate(budgets, 1):
            notes.append(
                f"### Slide {index}: Page {index}\n\n- **时长预算**：{value:g} 秒\n"
                "- **动画切入**：无\n- **技术核查**：-\n- **逐字口播**：\n\ntext\n"
            )
        (self.lesson / "lecture_notes.md").write_text("\n\n".join(notes), encoding="utf-8")

    def test_a_budget_total_that_disagrees_with_the_beats_fails(self):
        self._write("page:1; static, reason: only page", budgets=[10.0])
        report = run_preflight(self.lesson)
        joined = " ".join(report.errors)
        self.assertIn("page budgets total 10.000s", joined)
        self.assertIn("60.000s", joined)

    def test_matching_totals_pass_the_budget_check(self):
        self._write("page:1; static, reason: only page", budgets=[60.0])
        report = run_preflight(self.lesson)
        self.assertFalse(any("page budgets total" in error for error in report.errors))


if __name__ == "__main__":
    unittest.main()
