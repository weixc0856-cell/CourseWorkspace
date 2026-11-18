from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from course_control.content.contracts import (
    Authoring,
    Compose,
    Content,
    DurationPolicy,
    LessonConfig,
)
from course_control.production.product import (
    TIERS,
    aspect_of,
    check_product,
    policy_for,
    write_product_record,
)
from course_control.release.check import INCOMPLETE, PASS, _product_steps


def lesson(
    tier: str | None = "short_explainer",
    *,
    width: int = 1920,
    height: int = 1080,
    target: float = 120,
    minimum: float = 100,
    maximum: float = 145,
    narrative: str | None = "authoring/narrative-plan.json",
) -> LessonConfig:
    return LessonConfig(
        schema_version=1,
        lesson_id="product-fixture",
        title_en="Product fixture",
        title_zh="产品夹具",
        status="draft",
        content=Content(
            slides="slides.md",
            notes="lecture_notes.md",
            storyboard="storyboard.yaml",
            assets="assets/",
        ),
        outputs={"resolution": [width, height]},
        engines=["manim"],
        compose=Compose(mode="deck"),
        product_tier=tier,
        duration=DurationPolicy(
            profile="standard",
            target_seconds=target,
            min_seconds=minimum,
            max_seconds=maximum,
        ),
        authoring=Authoring(narrative=narrative),
    )


def write_plan(root: Path, beats: list[str]) -> None:
    target = root / "authoring" / "narrative-plan.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "form": "short",
                "audience": "engineers",
                "promise": "one point",
                "beats": [{"id": beat, "start_s": index, "end_s": index + 1, "summary": beat} for index, beat in enumerate(beats)],
                "payoff": "done",
            }
        ),
        encoding="utf-8",
    )


class ProductTierTest(unittest.TestCase):
    def test_windows_are_disjoint_and_ordered(self):
        self.assertEqual(TIERS["micro_explainer"].max_s, 90)
        self.assertEqual(TIERS["short_explainer"].min_s, 90)
        self.assertEqual(TIERS["research_brief"].min_s, 180)
        self.assertEqual(TIERS["deep_lecture"].min_s, 600)
        self.assertLessEqual(TIERS["course_series"].min_s, TIERS["course_series"].max_s)

    def test_unknown_tier_is_an_error(self):
        with self.assertRaises(ValueError):
            policy_for("webinar")

    def test_aspect_of(self):
        self.assertEqual(aspect_of(1920, 1080), "16:9")
        self.assertEqual(aspect_of(1080, 1920), "9:16")
        self.assertEqual(aspect_of(1080, 1080), "1:1")

    def test_short_passes_with_required_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_plan(root, ["cold_open", "mechanism", "test", "connect"])
            result = check_product(lesson(), root)
        self.assertEqual(result.status, "PASS", result.errors)
        self.assertEqual(result.aspect, "16:9")
        self.assertIn("hook", result.modules_found)

    def test_target_outside_window_fails(self):
        result = check_product(lesson(target=240, minimum=200, maximum=300), None)
        self.assertEqual(result.status, "FAIL")
        self.assertTrue(any("outside" in error for error in result.errors))

    def test_vertical_research_brief_fails(self):
        result = check_product(
            lesson("research_brief", width=1080, height=1920, target=240, minimum=200, maximum=300),
            None,
        )
        self.assertEqual(result.status, "FAIL")
        self.assertTrue(any("aspect 9:16" in error for error in result.errors))

    def test_missing_narrative_is_incomplete_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = check_product(lesson(), Path(tmp))
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertTrue(result.warnings)

    def test_undeclared_tier_is_not_a_pass(self):
        result = check_product(lesson(None), None)
        self.assertEqual(result.status, "NOT_DECLARED")

    def test_missing_module_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_plan(root, ["cold_open"])
            result = check_product(lesson(), root)
        self.assertEqual(result.status, "FAIL")
        self.assertTrue(any("missing module" in error for error in result.errors))

    def test_release_steps_are_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = SimpleNamespace(
                lesson=lesson(None),
                lesson_dir=root,
                build_root=root / "build",
            )
            self.assertEqual(_product_steps(paths), [])

    def test_declared_tier_without_plan_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_plan(root, ["cold_open", "mechanism", "test", "connect"])
            paths = SimpleNamespace(
                lesson=lesson(),
                lesson_dir=root,
                build_root=root / "build",
            )
            steps = {step.id: step.status for step in _product_steps(paths)}
        self.assertEqual(steps["product_tier"], PASS)
        self.assertEqual(steps["visual_events"], INCOMPLETE)

    def test_record_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_plan(root, ["cold_open", "mechanism", "test", "connect"])
            result = check_product(lesson(), root)
            target = write_product_record(result, root / "build" / "product.json")
            payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["policy"]["id"], "short_explainer")


if __name__ == "__main__":
    unittest.main()
