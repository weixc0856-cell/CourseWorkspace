"""E1 display chain alignment: positive, incident negative, not_run, wiring."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml

from course_control.production.checks import EvalContext, run_checks
from course_control.production.checks_display import _display_chain, extract_numbers
from course_control.production.quality_rubric import QualityRubric


def _lesson(root: Path, *, screen_number: str = "ten million", spoken: str = "ten million",
            display_text: str | None = None, seq_title: str = "The regime",
            script_pages: int = 1, with_source: bool = False) -> Path:
    lesson = root / "lesson"
    (lesson / "authoring").mkdir(parents=True)
    source = (
        "\n<small>Source: Hucho, 5th ed., Fig. 1.4b, p. 26 · printed page = PDF page - 21</small>"
        if with_source else ""
    )
    (lesson / "slides.md").write_text(
        f"## 1. The regime\n\n- Reynolds number of order {screen_number}\n{source}\n",
        encoding="utf-8",
    )
    segment: dict = {"id": "s1a", "text": f"The Reynolds number is of order {spoken}."}
    if display_text is not None:
        segment["display_text"] = display_text
    pages = [
        {"slide": i + 1, "target_seconds": 30, "source_refs": [],
         "segments": [segment] if i == 0 else [{"id": f"s{i+1}a", "text": "Filler line."}]}
        for i in range(script_pages)
    ]
    (lesson / "authoring" / "narration.script.json").write_text(
        json.dumps({"schema_version": 1, "lesson": "lesson", "pages": pages}), encoding="utf-8"
    )
    (lesson / "authoring" / "production.yaml").write_text(
        yaml.safe_dump({"schema_version": 1, "lesson": "lesson",
                        "sequences": [{"id": "seq_01", "title": seq_title, "shots": []}]}),
        encoding="utf-8",
    )
    return lesson


def _run(lesson: Path):
    return _display_chain(EvalContext(spec=None, lesson_dir=lesson, build_root=lesson / "build"))


class ExtractorTests(unittest.TestCase):
    def test_word_and_literal_forms_agree(self):
        self.assertEqual(extract_numbers("ten million"), extract_numbers("1e7"))
        self.assertEqual(extract_numbers("10⁷"), {1e7})
        self.assertEqual(extract_numbers("10^7"), {1e7})
        self.assertEqual(extract_numbers("~32×"), extract_numbers("about thirty-two times"))
        self.assertEqual(extract_numbers("10-20 cm"), {10.0, 20.0})
        self.assertEqual(extract_numbers("50%"), extract_numbers("fifty percent"))
        self.assertEqual(extract_numbers("a third"), extract_numbers("one third"))

    def test_articles_are_not_numbers(self):
        self.assertEqual(extract_numbers("a car loses it at the rear"), set())


class DisplayChainTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_consistent_chain_passes(self):
        status, actual, _, _ = _run(_lesson(self.root))
        self.assertEqual(status, "pass")
        self.assertEqual(actual["pages"], 1)

    def test_incident_screen_one_million_voice_ten_million_fails(self):
        lesson = _lesson(self.root, screen_number="one million", spoken="ten million")
        status, actual, _, _ = _run(lesson)
        self.assertEqual(status, "fail")
        self.assertEqual(actual[0]["page"], 1)
        self.assertIn(1e6, actual[0]["screen_only_numbers"])

    def test_display_text_override_must_match_spoken(self):
        ok = _lesson(self.root, screen_number="thirty-two", spoken="thirty-two times",
                     display_text="~32×")
        self.assertEqual(_run(ok)[0], "pass")
        bad = _lesson(self.root / "bad", screen_number="thirty-two", spoken="thirty-two times",
                      display_text="~64×")
        status, actual, _, _ = _run(bad)
        self.assertEqual(status, "fail")
        self.assertIn(64.0, actual[0]["screen_only_numbers"])

    def test_source_line_numbers_are_not_claims(self):
        lesson = _lesson(self.root, with_source=True)
        self.assertEqual(_run(lesson)[0], "pass")

    def test_title_mismatch_fails(self):
        lesson = _lesson(self.root, seq_title="Something else")
        status, actual, _, _ = _run(lesson)
        self.assertEqual(status, "fail")
        self.assertEqual(actual[0]["issue"], "title mismatch")

    def test_page_count_mismatch_fails(self):
        lesson = _lesson(self.root, script_pages=2)
        status, actual, _, _ = _run(lesson)
        self.assertEqual(status, "fail")
        self.assertEqual(actual, {"slides": 1, "script": 2, "production": 1})

    def test_missing_script_is_not_run_not_pass(self):
        lesson = _lesson(self.root)
        (lesson / "authoring" / "narration.script.json").unlink()
        status, _, _, evidence = _run(lesson)
        self.assertEqual(status, "not_run")
        self.assertIn("narration.script.json", evidence)

    def test_wired_into_checks_and_exception_queue(self):
        lesson = _lesson(self.root, screen_number="one million", spoken="ten million")
        rubric = QualityRubric.model_validate({
            "dimensions": {"content": {"weight": 100, "checks": [
                {"id": "display_chain", "kind": "auto", "rule": "display_chain_alignment"}
            ]}},
            "hard_fails": ["display_chain"],
        })
        report = run_checks(SimpleNamespace(episode="t"), rubric, lesson, lesson / "build")
        self.assertEqual(report.results[0].status, "fail")
        self.assertEqual(len(report.auto_failed), 1)
        payload = report.as_dict("spec")
        self.assertEqual(payload["exceptions"][0]["id"], "display_chain")


if __name__ == "__main__":
    unittest.main()