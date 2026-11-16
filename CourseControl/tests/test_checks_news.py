from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml

from course_control.production.checks_news import NEWS_RULES, timeline_components_resolve

WORKSPACE = Path(__file__).resolve().parents[2]


def make_ctx(root: Path, entries: list[dict] | None) -> SimpleNamespace:
    lesson = root / "lessons" / "demo"
    (lesson / "authoring").mkdir(parents=True, exist_ok=True)
    if entries is not None:
        payload = {
            "schema_version": 1,
            "product": "demo",
            "fps": 30,
            "duration_s": 10,
            "entries": entries,
        }
        (lesson / "authoring" / "timeline.yaml").write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
    return SimpleNamespace(
        lesson_dir=lesson,
        build_root=root / "build" / "demo",
        workspace=WORKSPACE,
    )


def entry(item_id: str, renderer: str, start: float) -> dict:
    return {"id": item_id, "kind": "card", "start_s": start, "duration_s": 5, "renderer": renderer}


class TimelineComponentsResolveTests(unittest.TestCase):
    def test_known_components_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            status, actual, expected, _ = timeline_components_resolve(
                make_ctx(Path(tmp), [entry("a", "Statement", 0)])
            )
        self.assertEqual(status, "pass")
        self.assertEqual(actual, ["Statement"])
        self.assertIn("Statement", expected)

    def test_unknown_component_fails_and_is_named(self) -> None:
        """A typo used to pass every gate: the contract only checked for a string."""
        with tempfile.TemporaryDirectory() as tmp:
            status, actual, _, _ = timeline_components_resolve(
                make_ctx(Path(tmp), [entry("ok", "Statement", 0), entry("typo", "NotAComponent", 5)])
            )
        self.assertEqual(status, "fail")
        self.assertEqual(actual, ["typo→NotAComponent"])

    def test_internal_helper_is_not_resolvable(self) -> None:
        """DesignMotion / MotionImage / Formula are wrappers, not full screens."""
        with tempfile.TemporaryDirectory() as tmp:
            status, actual, _, _ = timeline_components_resolve(
                make_ctx(Path(tmp), [entry("x", "DesignMotion", 0)])
            )
        self.assertEqual(status, "fail")
        self.assertEqual(actual, ["x→DesignMotion"])

    def test_missing_timeline_is_not_run_not_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            status, _, _, _ = timeline_components_resolve(make_ctx(Path(tmp), None))
        self.assertEqual(status, "not_run")

    def test_rule_is_exported_for_the_executor(self) -> None:
        self.assertIs(NEWS_RULES["timeline_components_resolve"], timeline_components_resolve)


if __name__ == "__main__":
    unittest.main()
