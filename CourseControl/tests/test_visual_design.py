from __future__ import annotations

import unittest
from pathlib import Path
from xml.etree import ElementTree

from course_control.authoring.models import OutlinePage
from course_control.design.board import board_svg
from course_control.design.checks import check_design
from course_control.design.handoff import apply_themes, load_theme_map
from course_control.design.planner import (
    apply_override,
    derive_shot,
    nearest_theme,
    slug_id,
)
from course_control.design.schema import Keyframe, MotionPlan, ShotDesign, VisualDesign
from course_control.direction.schema import NarrationSegmentPlan, ShotPlan
from course_control.rendering.theme import load_theme

WORKSPACE = Path(__file__).resolve().parents[2]


def page(**updates) -> OutlinePage:
    data = dict(
        slide=3,
        title="Query, Key, Value",
        claim="Self-attention lets each word score itself against every other word.",
        target_seconds=120,
        visual="Three projection arrows fan out from one highlighted word.",
        visual_kind="diagram",
        animation="qkv_fanout",
        source_refs=["S2-1.4"],
    )
    data.update(updates)
    return OutlinePage(**data)


def shot(**updates) -> ShotPlan:
    data = dict(
        id="shot_003",
        chapter_id="c2",
        slide=3,
        title="Query, Key, Value",
        purpose="explain",
        engine="manim",
        engine_profile="manim",
        scene=None,
        readiness="planned",
        start_s=150.0,
        end_s=270.0,
        cue_seconds=0.0,
        target_seconds=120.0,
        transition="cut",
        layout_template="principle_diagram",
        layout_regions={
            "title": [0.06, 0.80, 0.88, 0.10],
            "main_visual": [0.06, 0.18, 0.58, 0.58],
            "explanation": [0.68, 0.28, 0.26, 0.40],
            "caption": [0.06, 0.09, 0.88, 0.05],
        },
        shot_size="medium",
        learning_intent="Self-attention lets each word score itself against every other word.",
        visual_metaphor="Three projection arrows fan out from one highlighted word.",
        composition="single claim per frame",
        camera="slow push in",
        motion=["animate qkv_fanout"],
        on_screen_text=["Query, Key, Value"],
    )
    data.update(updates)
    return ShotPlan(**data)


def design() -> ShotDesign:
    return derive_shot(shot(), page(), "editorial_science", None)


class DesignDerivationTest(unittest.TestCase):
    def test_focal_object_sits_in_the_main_visual_region(self):
        item = design()
        focal = next(
            obj for obj in item.keyframes[0].objects if obj.id == item.composition.focal_object
        )
        self.assertAlmostEqual(focal.rect.cx, 0.06 + 0.58 / 2, places=2)
        self.assertEqual(item.composition.hierarchy[0], item.composition.focal_object)

    def test_three_keyframes_in_order_and_focal_persists(self):
        item = design()
        self.assertEqual([frame.id for frame in item.keyframes], ["start", "turn", "end"])
        for frame in item.keyframes:
            ids = {obj.id for obj in frame.objects}
            self.assertIn(item.composition.focal_object, ids)
        self.assertEqual(item.authorship, "derived")

    def test_slug_ids_are_stable(self):
        self.assertEqual(slug_id("Query, Key, Value"), "query_key_value")
        self.assertEqual(slug_id("3D  Attention"), "object_3d_attention")
        self.assertTrue(slug_id("A").endswith("_o"))

    def test_theme_follows_the_page_colour(self):
        self.assertEqual(nearest_theme(WORKSPACE, "#FBFAF7"), "editorial_science")
        self.assertEqual(nearest_theme(WORKSPACE, "#0A0908"), "deep_space")

    def test_a_3d_shot_gets_depth(self):
        item = derive_shot(shot(engine="blender"), page(visual_kind="structure3d"), "editorial_science", None)
        roles = [layer.role for layer in item.composition.depth_layers]
        self.assertIn("midground", roles)
        self.assertEqual(item.art_direction.family, "engineering")


class DesignCheckTest(unittest.TestCase):
    def document(self, item: ShotDesign) -> VisualDesign:
        return VisualDesign(
            lesson_id="01-transformer-demo",
            theme_default="editorial_science",
            lesson_style_background="#FBFAF7",
            shots=[item],
            checks=[],
        )

    def test_clean_design_has_no_errors(self):
        checks = check_design(self.document(design()))
        self.assertFalse([check for check in checks if check.level == "error"])

    def test_entry_only_motion_is_a_warning(self):
        item = design()
        item = item.model_copy(
            update={
                "motion": MotionPlan(
                    primary="fade in", secondary="nothing", camera="slow push in", end_hold_s=1.5
                )
            }
        )
        ids = {check.id for check in check_design(self.document(item))}
        self.assertIn("design.entry_only", ids)

    def test_flat_depth_plus_entry_motion_reads_as_a_slide(self):
        item = design()
        layers = [item.composition.depth_layers[0]]
        item = item.model_copy(
            update={
                "composition": item.composition.model_copy(
                    update={"depth_layers": layers, "hierarchy": [item.composition.focal_object]}
                ),
                "motion": MotionPlan(
                    primary="fade in", secondary="nothing", camera="slow push in", end_hold_s=1.5
                ),
            }
        )
        checks = check_design(self.document(item))
        self.assertIn("design.reads_as_slide", {check.id for check in checks})
        self.assertTrue(any(check.level == "error" for check in checks))

    def test_a_keyframe_without_the_focal_object_is_an_error(self):
        item = design()
        frames = list(item.keyframes)
        frames[1] = Keyframe(
            id="turn",
            at_s=frames[1].at_s,
            purpose=frames[1].purpose,
            camera=frames[1].camera,
            change=frames[1].change,
            objects=[obj for obj in frames[1].objects if obj.id != item.composition.focal_object]
            or [frames[1].objects[0].model_copy(update={"id": "other"})],
        )
        item = item.model_copy(update={"keyframes": frames})
        checks = check_design(self.document(item))
        self.assertIn("design.focal_drifts", {check.id for check in checks})

    def test_derived_designs_are_marked_as_drafts(self):
        checks = check_design(self.document(design()))
        self.assertIn("design.derived", {check.id for check in checks})


def segment(index: int, text: str, seconds: float = 10.0) -> NarrationSegmentPlan:
    return NarrationSegmentPlan(
        id=f"seg_{index}",
        shot_id="shot_003",
        page=3,
        text=text,
        estimated_seconds=seconds,
        pause_after_ms=300,
    )


class BeatTest(unittest.TestCase):
    def document(self, item: ShotDesign) -> VisualDesign:
        return VisualDesign(
            lesson_id="01-transformer-demo",
            theme_default="editorial_science",
            lesson_style_background="#FBFAF7",
            shots=[item],
            checks=[],
        )

    def test_beats_follow_the_narration_in_order(self):
        item = derive_shot(
            shot(),
            page(),
            "editorial_science",
            None,
            [segment(1, "So the weights change."), segment(2, "But the values stay.", 8.0)],
        )
        self.assertEqual([beat.at_s for beat in item.beats], [0.0, 10.0])
        self.assertEqual([beat.kind for beat in item.beats], ["highlight", "compare"])

    def test_an_unwritten_page_still_gets_a_cadence(self):
        item = design()
        self.assertGreaterEqual(len(item.beats), 2)
        self.assertEqual(item.beats[0].at_s, 0.0)

    def test_a_long_page_without_beats_is_an_error(self):
        item = design().model_copy(update={"beats": []})
        checks = check_design(self.document(item))
        self.assertIn("design.no_beats", {check.id for check in checks})

    def test_pages_longer_than_the_shot_contract_raise_one_document_warning(self):
        checks = check_design(self.document(design()))
        matches = [check for check in checks if check.id == "design.page_not_shot"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].level, "warning")

    def test_the_board_draws_the_change_schedule(self):
        svg = board_svg(design(), load_theme(WORKSPACE, "editorial_science"))
        self.assertIn("beats", svg)
        self.assertIn("0s", svg)
        self.assertIn("transform", svg)


class DesignHandoffTest(unittest.TestCase):
    def board(self, themes: dict[str, str] | None = None):
        from course_control.content.contracts import ShotSpec, Storyboard

        spec = ShotSpec(
            id="shot_003",
            slide=3,
            engine="manim",
            scene="scenes/qkv.py",
            cue_seconds=0.0,
            theme=(themes or {}).get("own"),
        )
        return Storyboard(schema_version=1, lesson="01-transformer-demo", shots=[spec])

    def test_a_design_theme_reaches_a_shot_that_has_none(self):
        board, changed = apply_themes(self.board(), {"shot_003": "deep_space"})
        self.assertEqual(changed, ["shot_003"])
        self.assertEqual(board.shots[0].theme, "deep_space")

    def test_a_shot_keeps_its_own_theme(self):
        board, changed = apply_themes(
            self.board({"own": "engineering_studio"}), {"shot_003": "deep_space"}
        )
        self.assertEqual(changed, [])
        self.assertEqual(board.shots[0].theme, "engineering_studio")

    def test_an_unknown_shot_is_ignored(self):
        board, changed = apply_themes(self.board(), {"shot_999": "deep_space"})
        self.assertEqual(changed, [])
        self.assertIsNone(board.shots[0].theme)

    def test_theme_map_reads_the_design_file(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            design = Path(tmp) / "design"
            design.mkdir()
            (design / "visual_design.json").write_text(
                json.dumps(
                    {
                        "shots": [
                            {"shot_id": "shot_003", "art_direction": {"theme": "deep_space"}},
                            {"shot_id": "shot_004", "art_direction": {}},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(load_theme_map(Path(tmp)), {"shot_003": "deep_space"})
            self.assertEqual(load_theme_map(Path(tmp) / "missing"), {})


class DesignOverrideTest(unittest.TestCase):
    def test_override_replaces_decisions_and_keeps_the_shot(self):
        item = apply_override(
            design(),
            {
                "concept": "attention weights are visible as area",
                "art_direction": {
                    "theme": "deep_space",
                    "family": "cinematic",
                    "atmosphere": "dark, inertial",
                    "contrast": "dramatic",
                    "note": "authored",
                },
            },
        )
        self.assertEqual(item.authorship, "authored")
        self.assertEqual(item.art_direction.theme, "deep_space")
        self.assertEqual(item.shot_id, "shot_003")
        self.assertEqual(item.duration_s, 120.0)
        self.assertEqual(item.concept, "attention weights are visible as area")


class DesignBoardTest(unittest.TestCase):
    def test_board_renders_three_panels_and_escapes_text(self):
        svg = board_svg(design(), load_theme(WORKSPACE, "editorial_science"))
        root = ElementTree.fromstring(svg)
        groups = {
            element.get("id")
            for element in root.iter()
            if element.tag.endswith("}g") or element.tag == "g"
        }
        self.assertEqual(groups, {"panel-start", "panel-turn", "panel-end"})
        self.assertIn("Query, Key, Value", svg)
        self.assertNotIn("<script", svg)


if __name__ == "__main__":
    unittest.main()
