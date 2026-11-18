from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.content.contracts import ShotSpec, Storyboard
from course_control.production.episode_spec import load_episode_spec
from course_control.production.visual_events import (
    VisualEvent,
    VisualEventPlan,
    compile_plan,
    validate_plan,
)

SPEC = """\
schema_version: 1
episode: E1
title: Visual event fixture
core_question: Does the plan bind claims to pictures?
target_seconds: 30
min_seconds: 20
max_seconds: 40
claims:
- id: C01
  text: The first claim.
  source: {chapter: '1', section: '1.1'}
- id: C02
  text: The second claim.
  source: {chapter: '1', figure: '1.2'}
- id: C03
  text: The shot-level claim.
  source: {chapter: '1', figure: '1.3'}
beats:
- {id: B1, type: question, seconds: 5, claims: [C01], visual: 'page:1'}
- {id: B2, type: case, seconds: 5, claims: [C01], visual: 'page:2'}
- {id: B3, type: mechanism, seconds: 5, claims: [C03], visual: 'shot:anim_001'}
- {id: B4, type: derivation, seconds: 5, claims: [C02], visual: 'page:3'}
- {id: B5, type: evidence, seconds: 5, claims: [C02], visual: 'page:3'}
- {id: B6, type: conclusion, seconds: 5, claims: [C01, C02], visual: 'page:1-3'}
cut_list: [nothing]
"""


def shots(total: float = 30) -> dict:
    return {
        "schema_version": 1,
        "lesson": "ve-fixture",
        "timeline": {"fps": 30, "resolution": [1920, 1080], "total_duration_s": total},
        "shots": [
            {
                "id": "slide_001",
                "kind": "slide",
                "slide": 1,
                "engine": None,
                "source": "slides/slide-001.png",
                "start_s": 0.0,
                "duration_s": 10.0,
                "timeline_role": "base",
            },
            {
                "id": "slide_002",
                "kind": "slide",
                "slide": 2,
                "engine": None,
                "source": "slides/slide-002.png",
                "start_s": 10.0,
                "duration_s": 10.0,
                "timeline_role": "base",
            },
            {
                "id": "anim_001",
                "kind": "animation",
                "slide": 2,
                "engine": "manim",
                "source": "animation/anim.mp4",
                "start_s": 12.0,
                "duration_s": 3.0,
                "timeline_role": "overlay",
            },
            {
                "id": "slide_003",
                "kind": "slide",
                "slide": 3,
                "engine": None,
                "source": "slides/slide-003.png",
                "start_s": 20.0,
                "duration_s": 10.0,
                "timeline_role": "base",
            },
        ],
        "narration": {"path": "narration/narration.wav", "duration_s": total},
    }


def storyboard() -> Storyboard:
    return Storyboard(
        schema_version=2,
        lesson="ve-fixture",
        shots=[
            ShotSpec(
                id="anim_001",
                slide=2,
                engine="manim",
                scene="anim.py::Anim",
                cue_seconds=12.0,
                expected_duration_s=3.0,
                purpose="demonstrate",
                visual_action="the layer splits in two",
                evidence_refs=["C02"],
            )
        ],
    )


class VisualEventTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in ("slide-001.png", "slide-002.png", "slide-003.png"):
            (self.root / "slides").mkdir(parents=True, exist_ok=True)
            (self.root / "slides" / name).write_bytes(b"png")
        (self.root / "animation").mkdir()
        (self.root / "animation" / "anim.mp4").write_bytes(b"mp4")
        self.shots_path = self.root / "shots.json"
        self.shots_path.write_text(json.dumps(shots()), encoding="utf-8")
        self.spec = load_episode_spec(self._spec_file())

    def tearDown(self):
        self.tmp.cleanup()

    def _spec_file(self) -> Path:
        path = self.root / "episode.spec.yaml"
        path.write_text(SPEC, encoding="utf-8")
        return path

    def plan(self) -> VisualEventPlan:
        return compile_plan(
            lesson="ve-fixture",
            shots_path=self.shots_path,
            storyboard=storyboard(),
            episode=self.spec,
        )

    def test_compile_binds_pages_to_claims(self):
        plan = self.plan()
        self.assertEqual(len(plan.events), 4)
        first = plan.events[0]
        self.assertIn("C01", first.evidence_refs)
        self.assertEqual(first.visual_type, "static_image")
        self.assertEqual(first.renderer, "remotion")
        self.assertIsNotNone(first.narration_ref)
        overlay = [event for event in plan.events if event.metadata["kind"] == "animation"][0]
        self.assertEqual(overlay.visual_type, "manim_scene")
        self.assertEqual(overlay.renderer, "manim")
        self.assertEqual(overlay.purpose, "demonstrate")
        self.assertIn("C02", overlay.evidence_refs)
        self.assertIn("C03", overlay.evidence_refs)

    def test_valid_plan_passes(self):
        report = validate_plan(self.plan(), build_root=self.root, episode=self.spec)
        self.assertEqual(report.status, "PASS", report.errors)

    def test_missing_episode_is_incomplete(self):
        plan = compile_plan(
            lesson="ve-fixture",
            shots_path=self.shots_path,
            storyboard=storyboard(),
            episode=None,
        )
        report = validate_plan(plan, build_root=self.root, episode=None)
        self.assertEqual(report.status, "INCOMPLETE")

    def test_gap_in_base_events_fails(self):
        plan = self.plan()
        plan.events = [event for event in plan.events if event.metadata.get("shot_id") != "slide_002"]
        report = validate_plan(plan, build_root=self.root, episode=self.spec)
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(any("timeline gap" in error for error in report.errors))

    def test_unknown_renderer_fails(self):
        plan = self.plan()
        plan.events[0].renderer = "whisper"
        report = validate_plan(plan, build_root=self.root, episode=self.spec)
        self.assertTrue(any("not registered" in error for error in report.errors))

    def test_missing_asset_fails(self):
        plan = self.plan()
        plan.events[0].asset_refs = ["slides/missing.png"]
        report = validate_plan(plan, build_root=self.root, episode=self.spec)
        self.assertTrue(any("asset not found" in error for error in report.errors))

    def test_unknown_claim_fails(self):
        plan = self.plan()
        plan.events[0].evidence_refs.append("K-999")
        report = validate_plan(plan, build_root=self.root, episode=self.spec)
        self.assertTrue(any("not in the episode spec" in error for error in report.errors))

    def test_unbound_must_teach_claim_fails(self):
        plan = self.plan()
        for event in plan.events:
            event.evidence_refs = [ref for ref in event.evidence_refs if ref != "C02"]
        report = validate_plan(plan, build_root=self.root, episode=self.spec)
        self.assertTrue(any("not bound to any visual event" in error for error in report.errors))

    def test_evidence_type_without_refs_fails(self):
        plan = self.plan()
        plan.events[0].visual_type = "chart"
        plan.events[0].evidence_refs = []
        report = validate_plan(plan, build_root=self.root, episode=self.spec)
        self.assertTrue(any("needs at least one evidence ref" in error for error in report.errors))

    def test_event_id_pattern(self):
        with self.assertRaises(ValueError):
            VisualEvent(
                event_id="event-1",
                start_s=0,
                duration_s=1,
                purpose="explain",
                visual_type="text",
                renderer="remotion",
            )


if __name__ == "__main__":
    unittest.main()
