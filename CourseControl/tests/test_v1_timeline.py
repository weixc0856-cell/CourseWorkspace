from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.content.contracts import (
    LegendAnnotation,
    Shot,
    ShotsFile,
    TextAnnotation,
    Timeline,
)
from course_control.content.contracts_v1 import TimelineSpec
from course_control.content.v1_timeline import (
    V1TimelineError,
    shots_from_timeline,
    timeline_from_shots,
    write_timeline_contract,
)


class _Paths:
    def __init__(self, workspace: Path, slug: str):
        self.workspace = workspace
        self.build_root = workspace / "build" / slug
        self.slug = slug


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class V1TimelineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.slug = "lesson-x"
        self.build = self.workspace / "build" / self.slug
        _write(self.build / "slides" / "slide-001.png")
        _write(self.build / "slides" / "slide-002.png")
        _write(self.build / "animation" / "overlay.mp4")
        _write(self.build / "narration.wav")
        _write(
            self.build / "subtitles.srt",
            "1\n00:00:00,000 --> 00:00:01,000\nfirst\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\nsecond\n",
        )
        self.shots = ShotsFile(
            lesson=self.slug,
            generated_at="2026-11-07T00:00:00+00:00",
            timeline=Timeline(fps=30, resolution=(1920, 1080), total_duration_s=2.0),
            shots=[
                Shot(
                    id="slide_001",
                    kind="slide",
                    slide=1,
                    source="slides/slide-001.png",
                    start_s=0.0,
                    duration_s=1.0,
                    timeline_role="base",
                ),
                Shot(
                    id="slide_002",
                    kind="slide",
                    slide=2,
                    source="slides/slide-002.png",
                    start_s=1.0,
                    duration_s=1.0,
                    timeline_role="base",
                ),
                Shot(
                    id="overlay_001",
                    kind="animation",
                    slide=1,
                    engine="manim",
                    source="animation/overlay.mp4",
                    start_s=0.5,
                    duration_s=0.5,
                    timeline_role="overlay",
                    presentation="cutaway",
                ),
            ],
            annotations=[
                TextAnnotation(
                    id="caption",
                    kind="text",
                    text="caption",
                    start_s=0.2,
                    duration_s=0.4,
                    position=(0.5, 0.1),
                    size=36,
                    align="center",
                    color="text",
                    background=False,
                ),
                LegendAnnotation(
                    id="legend",
                    kind="legend",
                    start_s=1.2,
                    duration_s=0.4,
                    position=(0.9, 0.5),
                    colormap="viridis",
                    min_value=0,
                    max_value=1,
                    units="Pa",
                    stops=[(0.0, (0.0, 0.0, 0.0)), (1.0, (1.0, 1.0, 1.0))],
                    bar_height=240,
                    bar_width=28,
                    label_size=24,
                ),
            ],
            narration={"path": "narration.wav", "duration_s": 2.0},
            subtitles={"path": "subtitles.srt", "cues": 2},
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_timeline_from_shots(self):
        timeline = timeline_from_shots(self.shots, self.workspace, self.build)
        self.assertEqual(timeline.lesson_id, self.slug)
        self.assertEqual(timeline.total_frames, 60)
        self.assertEqual(len(timeline.video), 3)
        self.assertEqual([item.track for item in timeline.video], ["slide", "slide", "manim"])
        self.assertEqual(timeline.video[2].start_frame, 15)
        self.assertEqual(timeline.video[2].duration_frames, 15)
        self.assertEqual(len(timeline.audio), 1)
        self.assertEqual(timeline.audio[0].duration_frames, 60)
        self.assertEqual([(cue.start_frame, cue.end_frame) for cue in timeline.subtitles], [(0, 30), (30, 60)])
        self.assertEqual(len(timeline.metadata["legacy_annotations"]), 2)
        # The object must survive its own Schema contract.
        TimelineSpec.model_validate(timeline.model_dump())

    def test_round_trip_to_shots(self):
        timeline = timeline_from_shots(self.shots, self.workspace, self.build)
        restored = shots_from_timeline(timeline, self.workspace, self.build)
        self.assertEqual(restored.lesson, self.slug)
        self.assertEqual(len(restored.shots), 3)
        self.assertEqual([shot.kind for shot in restored.shots], ["slide", "slide", "animation"])
        self.assertEqual(restored.shots[2].engine, "manim")
        self.assertEqual(restored.shots[2].timeline_role, "overlay")
        self.assertEqual(len(restored.annotations), 2)
        self.assertEqual(restored.narration["path"], "narration.wav")
        self.assertEqual(restored.subtitles["cues"], 2)
        self.assertTrue((self.build / "subtitles.srt").is_file())
        self.assertEqual(restored.timeline.total_duration_s, 2.0)

    def test_write_timeline_contract(self):
        paths = _Paths(self.workspace, self.slug)
        target, timeline = write_timeline_contract(self.shots, paths)
        self.assertTrue(target.is_file())
        payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["kind"], "timeline_spec")
        self.assertEqual(payload["total_frames"], 60)
        self.assertEqual(payload["lesson_id"], self.slug)
        self.assertEqual(timeline.total_frames, 60)

    def test_narration_overflow_rejected(self):
        bad = self.shots.model_copy(
            update={"narration": {"path": "narration.wav", "duration_s": 3.0}}
        )
        with self.assertRaises(V1TimelineError):
            timeline_from_shots(bad, self.workspace, self.build)


if __name__ == "__main__":
    unittest.main()
