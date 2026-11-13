from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from course_control.animatic import AnimaticError, resolve_build
from course_control.animatic.builder import _segment_key
from course_control.animatic.report import _checks
from course_control.animatic.timeline import Timeline, Unit


class AnimaticTimelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.build = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _touch(self, relative: str, data: bytes = b"x") -> Path:
        path = self.build / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def _write_json(self, relative: str, payload: dict) -> None:
        path = self.build / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_page_plan_prefers_rendered_clip(self) -> None:
        self._write_json(
            "timeline/page-plan.json",
            {
                "pages": [
                    {"slide": 1, "start_s": 0.0, "duration_s": 10.0},
                    {"slide": 2, "start_s": 10.0, "duration_s": 5.0},
                ]
            },
        )
        self._touch("scenes/pages/page-001.mp4")
        self._touch("slides/slide-002.png")

        timeline = resolve_build(self.build, slug="demo")

        self.assertEqual(timeline.mode, "pages")
        self.assertEqual([unit.kind for unit in timeline.units], ["clip", "still"])
        self.assertEqual([unit.id for unit in timeline.units], ["page-001", "page-002"])
        self.assertEqual(timeline.duration_s, 15.0)
        self.assertEqual(timeline.warnings, [])

    def test_page_without_any_picture_becomes_placeholder(self) -> None:
        self._write_json(
            "timeline/page-plan.json",
            {"pages": [{"slide": 1, "start_s": 0.0, "duration_s": 4.0}]},
        )

        timeline = resolve_build(self.build, slug="demo")

        self.assertEqual(timeline.units[0].kind, "placeholder")
        self.assertIsNone(timeline.units[0].source)
        self.assertTrue(any("no page clip and no slide still" in item for item in timeline.warnings))

    def test_shots_skip_overlays_and_keep_base_order(self) -> None:
        self._write_json(
            "shots.json",
            {
                "shots": [
                    {
                        "id": "b2",
                        "kind": "slide",
                        "slide": 2,
                        "source": "slides/slide-002.png",
                        "start_s": 10.0,
                        "duration_s": 5.0,
                        "timeline_role": "base",
                    },
                    {
                        "id": "over",
                        "kind": "animation",
                        "source": "animation/x.mp4",
                        "start_s": 11.0,
                        "duration_s": 2.0,
                        "timeline_role": "overlay",
                    },
                    {
                        "id": "b1",
                        "kind": "slide",
                        "slide": 1,
                        "source": "slides/slide-001.png",
                        "start_s": 0.0,
                        "duration_s": 10.0,
                        "timeline_role": "base",
                    },
                ]
            },
        )
        self._touch("slides/slide-001.png")
        self._touch("slides/slide-002.png")

        timeline = resolve_build(self.build, slug="demo")

        self.assertEqual(timeline.mode, "shots")
        self.assertEqual([unit.id for unit in timeline.units], ["b1", "b2"])
        self.assertTrue(any("overlay shot(s) not composited" in item for item in timeline.warnings))

    def test_missing_shot_source_falls_back_to_slide(self) -> None:
        self._write_json(
            "shots.json",
            {
                "shots": [
                    {
                        "id": "anim",
                        "kind": "animation",
                        "slide": 3,
                        "source": "animation/gone.mp4",
                        "start_s": 0.0,
                        "duration_s": 6.0,
                        "timeline_role": "base",
                    }
                ]
            },
        )
        self._touch("slides/slide-003.png")

        timeline = resolve_build(self.build, slug="demo")

        self.assertEqual(timeline.units[0].kind, "still")
        self.assertTrue(any("using still" in item for item in timeline.warnings))

    def test_gap_becomes_a_placeholder_unit(self) -> None:
        self._write_json(
            "timeline/page-plan.json",
            {
                "pages": [
                    {"slide": 1, "start_s": 2.0, "duration_s": 3.0},
                    {"slide": 2, "start_s": 5.0, "duration_s": 3.0},
                ]
            },
        )
        self._touch("slides/slide-001.png")
        self._touch("slides/slide-002.png")

        timeline = resolve_build(self.build, slug="demo")

        self.assertEqual([unit.id for unit in timeline.units], ["gap-001", "page-001", "page-002"])
        self.assertEqual(timeline.units[0].duration_s, 2.0)
        self.assertEqual(timeline.units[0].kind, "placeholder")
        self.assertTrue(any("gap 2.00s" in item for item in timeline.warnings))

    def test_scenes_manifest_is_used_when_no_page_plan(self) -> None:
        self._write_json(
            "scenes/manifest.json",
            {
                "pages": [
                    {"file": "scenes/pages/page-001.mp4", "slide": 1, "duration_s": 4.0},
                    {"file": "scenes/pages/page-002.mp4", "slide": 2, "duration_s": 6.0},
                ]
            },
        )
        self._touch("scenes/pages/page-001.mp4")
        self._touch("scenes/pages/page-002.mp4")

        timeline = resolve_build(self.build, slug="demo")

        self.assertEqual(timeline.mode, "scenes")
        self.assertEqual([unit.start_s for unit in timeline.units], [0.0, 4.0])
        self.assertEqual(timeline.duration_s, 10.0)

    def test_no_timeline_raises_with_the_places_it_looked(self) -> None:
        with self.assertRaises(AnimaticError) as caught:
            resolve_build(self.build, slug="demo")
        self.assertIn("page-plan.json", str(caught.exception))

    def test_frame_grid_covers_the_timeline_exactly(self) -> None:
        timeline = Timeline(
            mode="test",
            units=[
                Unit("a", "still", None, "", 0.0, 4.192, "A"),
                Unit("b", "still", None, "", 4.192, 6.999, "B"),
                Unit("c", "still", None, "", 11.191, 0.5, "C"),
            ],
        )
        counts = timeline.frames()
        self.assertEqual(sum(counts), round(timeline.duration_s * timeline.fps))
        self.assertTrue(all(count >= 1 for count in counts))


class AnimaticCacheKeyTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.label = self.root / "label.png"
        self.label.write_bytes(b"label")
        self.timeline = Timeline(mode="test", units=[Unit("a", "still", None, "", 0.0, 2.0, "A")])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_key_is_stable_for_the_same_inputs(self) -> None:
        source = self.root / "slide.png"
        source.write_bytes(b"one")
        unit = Unit("a", "still", source, "slide.png", 0.0, 2.0, "A")
        first = _segment_key(unit, 60, self.label, self.timeline)
        second = _segment_key(unit, 60, self.label, self.timeline)
        self.assertEqual(first, second)

    def test_key_changes_when_the_picture_changes(self) -> None:
        source = self.root / "slide.png"
        source.write_bytes(b"one")
        unit = Unit("a", "still", source, "slide.png", 0.0, 2.0, "A")
        before = _segment_key(unit, 60, self.label, self.timeline)
        source.write_bytes(b"two")
        after = _segment_key(unit, 60, self.label, self.timeline)
        self.assertNotEqual(before, after)

    def test_key_changes_when_the_slot_length_changes(self) -> None:
        unit = Unit("a", "still", None, "", 0.0, 2.0, "A")
        self.assertNotEqual(
            _segment_key(unit, 60, self.label, self.timeline),
            _segment_key(unit, 61, self.label, self.timeline),
        )


if __name__ == "__main__":
    unittest.main()


class AnimaticAcceptanceTest(unittest.TestCase):
    def _checks_for(self, duration: float, audio_duration: float) -> dict:
        timeline = SimpleNamespace(duration_s=duration)
        checks = _checks(timeline, [], {"duration": duration}, {"duration_s": audio_duration})
        return {item["id"]: item for item in checks}

    def test_drift_beyond_acceptance_is_flagged_while_preview_passes(self) -> None:
        checks = self._checks_for(1260.0, 1260.5)
        self.assertEqual(checks["audio_sync"]["status"], "pass")
        self.assertEqual(checks["audio_sync_acceptance"]["status"], "warn")

    def test_small_drift_passes_both(self) -> None:
        checks = self._checks_for(1260.0, 1260.05)
        self.assertEqual(checks["audio_sync"]["status"], "pass")
        self.assertEqual(checks["audio_sync_acceptance"]["status"], "pass")
