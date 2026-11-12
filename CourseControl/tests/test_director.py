from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from course_control.direction.animation_direction import AnimationDirection
from course_control.content.contracts import Storyboard
from course_control.direction import build, validate_file
from course_control.direction.inputs import load_inputs
from course_control.direction.planners import plan_all
from course_control.direction.schema import ApprovalState
from course_control.direction.validator import validate
from course_control.platform.workspace_layout import lessons_root

WORKSPACE = Path(__file__).resolve().parents[2]
LESSON = lessons_root(WORKSPACE) / "01-transformer-demo"


@unittest.skipUnless(LESSON.is_dir(), "local lesson 01-transformer-demo not present")
class DirectorPlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "director"
        cls.plan, cls.paths = build(WORKSPACE, LESSON, cls.out)
        cls.inputs = load_inputs(WORKSPACE, LESSON)
        cls.chapters, cls.shots, cls.narration, cls.decisions = plan_all(cls.inputs)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def reload(self, **updates):
        data = self.plan.model_dump(mode="json")
        data.update(updates)
        from course_control.direction.schema import DirectorPlan

        return DirectorPlan.model_validate(data)

    def test_golden_plan_is_contiguous_and_within_budget(self):
        self.assertEqual(self.plan.duration.planned_seconds, 1200.0)
        self.assertEqual(len(self.plan.shots), 12)
        self.assertEqual(len(self.plan.chapters), 5)
        self.assertEqual(self.plan.summary.errors, 0)
        self.assertEqual(self.plan.status, "ready")
        self.assertEqual(self.plan.summary.ready_shots, 12)
        self.assertEqual(self.plan.summary.planned_shots, 0)
        self.assertTrue(self.paths["plan"].is_file())
        rules = {check.rule for check in self.plan.checks}
        self.assertNotIn("style.background_mismatch", rules)
        cursor = 0.0
        for shot in self.plan.shots:
            self.assertAlmostEqual(shot.start_s, cursor)
            cursor = shot.end_s
        self.assertAlmostEqual(cursor, self.plan.duration.planned_seconds)
        self.assertAlmostEqual(sum(c.target_seconds for c in self.plan.chapters), 1200.0)

    def test_routing_readiness_and_narration_cover(self):
        by_id = {shot.id: shot for shot in self.plan.shots}
        self.assertEqual(by_id["shot_002"].engine, "blender")
        self.assertEqual(by_id["shot_002"].readiness, "ready")
        self.assertEqual(by_id["shot_003"].engine, "manim")
        self.assertEqual(by_id["shot_003"].readiness, "ready")
        self.assertIn("qkv_fanout.py", by_id["shot_003"].scene)
        self.assertEqual(by_id["shot_007"].readiness, "ready")
        self.assertIn("ResidualBypassScene", by_id["shot_007"].scene)
        self.assertIn("CrossAttentionFlowScene", by_id["shot_008"].scene)
        self.assertIn("LossBackpropScene", by_id["shot_010"].scene)
        self.assertEqual(by_id["shot_009"].engine, "remotion")
        self.assertEqual(by_id["shot_001"].layout_template, "title_intro")
        self.assertEqual(by_id["shot_007"].layout_template, "process_flow")
        self.assertEqual(by_id["shot_009"].layout_template, "data_chart")
        self.assertEqual(len(self.plan.narration), 54)
        segment_ids = {segment.id for segment in self.plan.narration}
        for shot in self.plan.shots:
            self.assertTrue(set(shot.narration_ids) <= segment_ids, shot.id)

    def test_chapter_objectives_follow_the_brief(self):
        by_id = {chapter.id: chapter for chapter in self.plan.chapters}
        self.assertIn("architectural", by_id["c1"].learning_objective)
        self.assertIn("self-attention", by_id["c2"].learning_objective.lower())
        self.assertIn("positional encoding", by_id["c3"].learning_objective.lower())
        self.assertIn("training process", by_id["c4"].learning_objective.lower())
        self.assertIn("mental model", by_id["c5"].learning_objective.lower())

    def test_storyboard_and_directions_are_valid_contracts(self):
        payload = yaml.safe_load(self.paths["storyboard"].read_text(encoding="utf-8"))
        storyboard = Storyboard.model_validate(payload)
        self.assertEqual(len(storyboard.shots), 8)
        self.assertTrue(all(shot.engine != "remotion" for shot in storyboard.shots))
        direction = AnimationDirection.model_validate_json(
            (self.paths["directions"] / "shot_003.json").read_text(encoding="utf-8")
        )
        self.assertEqual(direction.problems(), [])
        self.assertTrue((self.paths["shot_specs"] / "shot_003.json").is_file())
        by_id = {shot.id: shot for shot in storyboard.shots}
        # cue_seconds is page-relative; collect.py adds the page start.
        self.assertEqual(by_id["shot_003"].cue_seconds, 30.0)
        self.assertEqual(by_id["shot_007"].cue_seconds, 30.0)

    def test_validate_file_round_trip(self):
        parsed = validate_file(self.paths["plan"])
        self.assertEqual(parsed.summary.errors, 0)

    def test_duration_drift_is_rejected(self):
        plan = self.reload()
        plan.duration.planned_seconds = 1210.0
        rules = {check.rule for check in validate(plan)}
        self.assertIn("duration.target", rules)
        self.assertIn("duration.chapter_sum", rules)

    def test_cue_outside_page_is_rejected(self):
        plan = self.reload()
        plan.shots[2].cue_seconds = plan.shots[2].target_seconds + 1
        rules = {check.rule for check in validate(plan)}
        self.assertIn("cue.out_of_page", rules)

    def test_timeline_gap_is_rejected(self):
        plan = self.reload()
        plan.shots[3].start_s += 5
        rules = {check.rule for check in validate(plan)}
        self.assertIn("timeline.contiguous", rules)

    def test_unknown_narration_id_is_rejected(self):
        plan = self.reload()
        plan.shots[0].narration_ids = ["does-not-exist"]
        rules = {check.rule for check in validate(plan)}
        self.assertIn("narration.missing_segment", rules)

    def test_3d_page_cannot_route_to_manim_without_override(self):
        plan = self.reload()
        plan.shots[1].engine = "manim"
        rules = {check.rule for check in validate(plan, self.inputs, self.decisions)}
        self.assertIn("engine.3d_route", rules)

    def test_unknown_layout_template_is_rejected(self):
        plan = self.reload()
        plan.shots[0].layout_template = "nope"
        rules = {check.rule for check in validate(plan, self.inputs, self.decisions)}
        self.assertIn("layout.unknown_template", rules)

    def test_missing_scene_class_is_rejected(self):
        plan = self.reload()
        plan.shots[6].scene = "01-transformer-demo/residual_bypass.py::NotAScene"
        rules = {check.rule for check in validate(plan, self.inputs, self.decisions)}
        self.assertIn("scene.class_missing", rules)

    def test_missing_scene_is_rejected(self):
        plan = self.reload()
        plan.shots[2].scene = "01-transformer-demo/not_there.py::Missing"
        rules = {check.rule for check in validate(plan, self.inputs, self.decisions)}
        self.assertIn("scene.exists", rules)

    def test_unapproved_inputs_become_a_warning(self):
        plan = self.reload()
        plan.approval = ApprovalState(approved=False, artifacts=[])
        checks = validate(plan, self.inputs, self.decisions)
        self.assertTrue(any(check.rule == "source.approval" and check.level == "warning" for check in checks))


if __name__ == "__main__":
    unittest.main()
