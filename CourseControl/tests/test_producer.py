from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from pydantic import ValidationError

from course_control.director.inputs import load_inputs
from course_control.producer import affected, run, status
from course_control.producer.order import OrderOverrides, default_order, load_order, order_path, save_order
from course_control.producer.orchestrator import execute_rebuild, plan_rebuild
from course_control.contracts import Status
from course_control.paths import ContractError
from course_control.producer.state import load_state, save_state, state_path
from course_control.producer.rebuild import diff_fingerprints
from course_control.producer.schema import DeliveryItem, DeliveryManifest, ShotFingerprint
from course_control.workspace_layout import lessons_root

WORKSPACE = Path(__file__).resolve().parents[2]
LESSON = lessons_root(WORKSPACE) / "01-transformer-demo"


@unittest.skipUnless(LESSON.is_dir(), "local lesson 01-transformer-demo not present")
class ProducerRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.result = run(WORKSPACE, LESSON, build_root=cls.root)
        cls.inputs = load_inputs(WORKSPACE, LESSON)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_order_defaults_follow_brief_and_lesson(self):
        order = default_order(self.inputs)
        self.assertEqual(order.lesson_id, "01-transformer-demo")
        self.assertEqual(order.target_seconds, 1200.0)
        self.assertEqual(order.language, "en")
        self.assertEqual(len(order.must_cover), len(self.inputs.brief.objectives))
        self.assertIsNone(order.approved_by)
        self.assertFalse(order.authorizations.allow_network)
        round_trip = type(order).model_validate_json(order.model_dump_json())
        self.assertEqual(round_trip.order_id, order.order_id)

    def test_order_file_round_trip(self):
        path = order_path(self.root)
        self.assertTrue(path.is_file())
        loaded = load_order(path)
        self.assertEqual(loaded.order_id, self.result.order.order_id)

    def test_state_records_fingerprints_and_blocked_status(self):
        self.assertEqual(self.result.state.status, "blocked")
        self.assertEqual(len(self.result.state.shots), 12)
        self.assertEqual(self.result.state.stages["director"], "ready")
        self.assertEqual(self.result.state.stages["render"], "missing")
        self.assertEqual(self.result.state.stages["audio"], "missing")
        self.assertEqual(self.result.state.stages["audio_policy"], "ready")
        self.assertTrue(self.result.paths["audio_plan"].is_file())
        self.assertGreater(self.result.state.usage.wall_seconds, 0)
        self.assertGreaterEqual(self.result.state.usage.disk_gb, 0)

    def test_delivery_reports_missing_artifacts_honestly(self):
        self.assertTrue((self.root / "producer" / "manifest.json").is_file())
        manifest = self.result.manifest
        self.assertEqual(manifest.status, "blocked")
        by_id = {item.id: item for item in manifest.items}
        self.assertEqual(by_id["02_script"].status, "present")
        self.assertEqual(by_id["03_storyboard"].status, "present")
        self.assertEqual(by_id["04_assets"].status, "present")
        self.assertEqual(by_id["05_audio"].status, "partial")
        self.assertTrue(any("course-video.mp4" in entry for entry in manifest.missing))
        self.assertFalse(any("shot_007" in entry for entry in manifest.missing))
        self.assertEqual(len(manifest.missing), 3)

    def test_order_language_mismatch_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(WORKSPACE, LESSON, build_root=Path(tmp), overrides=OrderOverrides(language="zh"))
            self.assertTrue(any("language zh" in note for note in result.state.notes))

    def test_status_and_affected_are_consistent(self):
        data = status(WORKSPACE, LESSON, build_root=self.root)
        self.assertEqual(data["state"].status, "blocked")
        self.assertIsNotNone(data["manifest"])
        self.assertEqual(affected(WORKSPACE, LESSON, build_root=self.root), [])

    def test_limit_violation_blocks_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(
                WORKSPACE,
                LESSON,
                build_root=Path(tmp),
                overrides=OrderOverrides(max_wall_seconds=1e-6),
            )
            self.assertTrue(result.limits)
            self.assertEqual(result.state.status, "blocked")

    def test_approval_is_recorded_thanks_to_delivery_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(WORKSPACE, LESSON, build_root=Path(tmp), approve_by="reviewer")
            self.assertEqual(result.order.approved_by, "reviewer")
            self.assertIsNotNone(result.order.approved_at)
            # Missing artifacts still block delivery even when the order is approved.
            self.assertEqual(result.manifest.status, "blocked")


@unittest.skipUnless(LESSON.is_dir(), "local lesson 01-transformer-demo not present")
class DeliveryPolicyTest(unittest.TestCase):
    def test_delivered_requires_every_item_present(self):
        with self.assertRaises(ValidationError):
            DeliveryManifest(
                lesson_id="demo",
                order_id="demo-v1",
                generated_at="2026-11-08T00:00:00+00:00",
                status="delivered",
                items=[DeliveryItem(id="01_final_video", title="video", status="blocked")],
                missing=[],
            )


@unittest.skipUnless(LESSON.is_dir(), "local lesson 01-transformer-demo not present")
class IncrementalDiffTest(unittest.TestCase):
    def base(self, **updates) -> ShotFingerprint:
        payload = dict(
            shot_id="shot_001",
            slide=1,
            engine="manim",
            scene="demo/a.py::A",
            fingerprint="a" * 64,
            content_sha256="b" * 64,
            narration_sha256="c" * 64,
        )
        payload.update(updates)
        return ShotFingerprint(**payload)

    def test_narration_change_is_re_narrate(self):
        delta = diff_fingerprints(
            [self.base()], [self.base(narration_sha256="d" * 64, fingerprint="e" * 64)]
        )[0]
        self.assertEqual(delta.change, "re-narrate")

    def test_scene_change_is_re_render(self):
        delta = diff_fingerprints(
            [self.base()], [self.base(scene_sha256="f" * 64, fingerprint="e" * 64)]
        )[0]
        self.assertEqual(delta.change, "re-render")

    def test_content_change_is_redesign_and_wins(self):
        delta = diff_fingerprints(
            [self.base()],
            [self.base(content_sha256="1" * 64, scene_sha256="f" * 64, fingerprint="e" * 64)],
        )[0]
        self.assertEqual(delta.change, "redesign")
        self.assertIn("rewrite direction", delta.actions)

    def test_new_shot_is_redesign(self):
        delta = diff_fingerprints([], [self.base()])[0]
        self.assertEqual(delta.change, "redesign")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(LESSON.is_dir(), "local lesson 01-transformer-demo not present")
class RebuildPlanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        run(WORKSPACE, LESSON, build_root=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_state_has_nothing_to_rebuild(self):
        plan = plan_rebuild(WORKSPACE, LESSON, build_root=self.root)
        self.assertEqual(plan.shot_ids, [])
        self.assertEqual(plan.command, [])

    def test_changed_state_produces_shots_command(self):
        state_file = state_path(self.root)
        state = load_state(state_file)
        target = next(item for item in state.shots if item.shot_id == "shot_003")
        target.content_sha256 = "0" * 64
        target.fingerprint = "0" * 64
        save_state(state, state_file)
        plan = plan_rebuild(WORKSPACE, LESSON, build_root=self.root)
        self.assertEqual(plan.shot_ids, ["shot_003"])
        self.assertIn("--storyboard-source", plan.command)
        self.assertIn("--shots", plan.command)
        self.assertIn("--skip-compose", plan.command)
        self.assertTrue(plan.authorized)

    def test_render_authorization_is_honoured(self):
        order_file = order_path(self.root)
        order = load_order(order_file)
        order.authorizations.allow_render = False
        save_order(order, order_file)
        plan = plan_rebuild(WORKSPACE, LESSON, build_root=self.root)
        self.assertFalse(plan.authorized)

    def test_execute_refreshes_only_rebuilt_shots(self):
        state_file = state_path(self.root)
        state = load_state(state_file)
        target = next(item for item in state.shots if item.shot_id == "shot_003")
        target.content_sha256 = "0" * 64
        target.fingerprint = "0" * 64
        save_state(state, state_file)
        plan = plan_rebuild(WORKSPACE, LESSON, build_root=self.root)
        report = SimpleNamespace(
            verdict="incomplete",
            stages=[SimpleNamespace(name="render:manim", status=Status.PASS)],
        )
        with patch(
            "course_control.producer.orchestrator.run_build",
            return_value=(report, Path("unused.json")),
        ):
            result = execute_rebuild(plan, WORKSPACE, LESSON, build_root=self.root)
        self.assertFalse(result["failed"])
        self.assertIsNotNone(result["state"])
        refreshed = load_state(state_file)
        shot = next(item for item in refreshed.shots if item.shot_id == "shot_003")
        self.assertNotEqual(shot.fingerprint, "0" * 64)

    def test_execute_refuses_without_render_authorization(self):
        order_file = order_path(self.root)
        order = load_order(order_file)
        order.authorizations.allow_render = False
        save_order(order, order_file)
        plan = plan_rebuild(WORKSPACE, LESSON, build_root=self.root)
        with self.assertRaises(ContractError):
            execute_rebuild(plan, WORKSPACE, LESSON, build_root=self.root)
