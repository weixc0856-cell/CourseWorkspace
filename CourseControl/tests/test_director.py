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
from ._local_lesson import LOCAL, REASON

WORKSPACE = Path(__file__).resolve().parents[2]
LESSON = LOCAL.path if LOCAL is not None else None


@unittest.skipUnless(LOCAL is not None, REASON)
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

    def reload(self, *, need: int = 1, **updates):
        if len(self.plan.shots) < need:
            self.skipTest(f"local lesson has fewer than {need} shots")
        data = self.plan.model_dump(mode="json")
        data.update(updates)
        from course_control.direction.schema import DirectorPlan

        return DirectorPlan.model_validate(data)

    def test_plan_is_contiguous_and_within_budget(self):
        self.assertEqual(
            self.plan.duration.planned_seconds, self.plan.duration.target_seconds
        )
        self.assertGreater(len(self.plan.shots), 0)
        self.assertGreater(len(self.plan.chapters), 0)
        self.assertEqual(self.plan.summary.errors, 0)
        self.assertEqual(self.plan.status, "ready")
        self.assertEqual(self.plan.summary.ready_shots, len(self.plan.shots))
        self.assertEqual(self.plan.summary.planned_shots, 0)
        self.assertTrue(self.paths["plan"].is_file())
        rules = {check.rule for check in self.plan.checks}
        self.assertNotIn("style.background_mismatch", rules)
        cursor = 0.0
        for shot in self.plan.shots:
            self.assertAlmostEqual(shot.start_s, cursor)
            cursor = shot.end_s
        self.assertAlmostEqual(cursor, self.plan.duration.planned_seconds)
        self.assertAlmostEqual(
            sum(c.target_seconds for c in self.plan.chapters),
            self.plan.duration.planned_seconds,
        )

    def test_every_shot_routes_and_covers_narration(self):
        engines = {"blender", "manim", "motion_canvas", "code_video", "remotion"}
        segment_ids = {segment.id for segment in self.plan.narration}
        self.assertGreater(len(segment_ids), 0)
        for shot in self.plan.shots:
            self.assertIn(shot.engine, engines)
            self.assertIn(shot.readiness, {"ready", "planned"})
            self.assertTrue(set(shot.narration_ids) <= segment_ids, shot.id)

    def test_chapters_have_objectives_and_cover_the_plan(self):
        objectives = [chapter.learning_objective for chapter in self.plan.chapters]
        self.assertTrue(all(objective.strip() for objective in objectives))
        self.assertEqual(
            len({chapter.id for chapter in self.plan.chapters}), len(self.plan.chapters)
        )
        self.assertAlmostEqual(
            sum(chapter.target_seconds for chapter in self.plan.chapters),
            self.plan.duration.planned_seconds,
        )

    def test_storyboard_and_directions_are_valid_contracts(self):
        payload = yaml.safe_load(self.paths["storyboard"].read_text(encoding="utf-8"))
        storyboard = Storyboard.model_validate(payload)
        self.assertGreater(len(storyboard.shots), 0)
        self.assertTrue(all(shot.engine != "remotion" for shot in storyboard.shots))
        for shot in storyboard.shots[:2]:
            direction = AnimationDirection.model_validate_json(
                (self.paths["directions"] / f"{shot.id}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(direction.problems(), [])
            self.assertTrue((self.paths["shot_specs"] / f"{shot.id}.json").is_file())
            # cue_seconds is page-relative; collect.py adds the page start.
            self.assertGreaterEqual(shot.cue_seconds, 0.0)

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
        plan = self.reload(need=3)
        plan.shots[2].cue_seconds = plan.shots[2].target_seconds + 1
        rules = {check.rule for check in validate(plan)}
        self.assertIn("cue.out_of_page", rules)

    def test_timeline_gap_is_rejected(self):
        plan = self.reload(need=4)
        plan.shots[3].start_s += 5
        rules = {check.rule for check in validate(plan)}
        self.assertIn("timeline.contiguous", rules)

    def test_unknown_narration_id_is_rejected(self):
        plan = self.reload()
        plan.shots[0].narration_ids = ["does-not-exist"]
        rules = {check.rule for check in validate(plan)}
        self.assertIn("narration.missing_segment", rules)

    def test_3d_page_cannot_route_to_manim_without_override(self):
        plan = self.reload(need=2)
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
        target = next(
            (shot for shot in plan.shots if shot.engine == "manim" and "::" in shot.scene),
            None,
        )
        if target is None:
            self.skipTest("local lesson has no manim shot with a class")
        file_part = target.scene.split("::", 1)[0]
        target.scene = f"{file_part}::NotAScene"
        rules = {check.rule for check in validate(plan, self.inputs, self.decisions)}
        self.assertIn("scene.class_missing", rules)

    def test_missing_scene_is_rejected(self):
        plan = self.reload(need=3)
        plan.shots[2].scene = "lesson-scene/not_there.py::Missing"
        rules = {check.rule for check in validate(plan, self.inputs, self.decisions)}
        self.assertIn("scene.exists", rules)

    def test_unapproved_inputs_become_a_warning(self):
        plan = self.reload()
        plan.approval = ApprovalState(approved=False, artifacts=[])
        checks = validate(plan, self.inputs, self.decisions)
        self.assertTrue(any(check.rule == "source.approval" and check.level == "warning" for check in checks))


if __name__ == "__main__":
    unittest.main()
