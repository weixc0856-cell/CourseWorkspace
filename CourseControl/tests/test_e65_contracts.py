from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from course_control.contracts_v1 import NarrationSpec, RenderManifest, TimelineSpec
from course_control.e65 import E65Error, adapt_e65

WORKSPACE = Path(__file__).resolve().parents[2]
E65 = WORKSPACE / "build" / "manim-multi-head" / "e6.5"
REQUIRED = [
    E65 / "manifest.json",
    E65 / "final.mp4",
    E65 / "narration.wav",
    E65 / "subtitles.srt",
    E65 / "narration" / "segments" / "e65-b1.wav",
    E65 / "narration" / "segments" / "e65-b2.wav",
    E65 / "narration" / "segments" / "e65-b3.wav",
    E65 / "narration" / "segments" / "e65-b4.wav",
    E65 / "narration" / "segments" / "e65-b5.wav",
]


@unittest.skipUnless(all(path.is_file() for path in REQUIRED), "E6.5 build artifacts not present")
class E65AdapterTest(unittest.TestCase):
    def test_generates_valid_v1_contracts(self):
        with tempfile.TemporaryDirectory(dir=WORKSPACE / "build") as temp:
            output = Path(temp) / "contracts"
            result = adapt_e65(
                E65 / "manifest.json",
                workspace=WORKSPACE,
                output_dir=output,
                voice_ref=E65 / "narration" / "segments" / "e65-b1.wav",
                run_id="20261107T130000Z-deadbeef",
                now=datetime(2026, 11, 7, 13, 0, 0, tzinfo=timezone.utc),
            )
            render = result["manifest"]
            self.assertIsInstance(render, RenderManifest)
            self.assertIsNotNone(render.source)
            self.assertIsNone(render.source.lesson_spec)
            self.assertIsNotNone(render.source.timeline)
            self.assertIsNotNone(render.source.narration)
            self.assertEqual(render.output.total_frames, 2608)
            self.assertEqual(render.output.duration_ms, 86933)
            self.assertEqual(len(render.shots), 5)
            self.assertEqual(len(render.narration.segments), 5)
            self.assertEqual(len(render.checks), 14)
            self.assertTrue(all(check.status == "pass" for check in render.checks))
            self.assertEqual(render.legacy["checks_are_automatic"], True)

            narration = NarrationSpec.model_validate(
                result["narration"].model_dump()
            )
            timeline = TimelineSpec.model_validate(result["timeline"].model_dump())
            self.assertEqual(narration.total.total_frames, 2608)
            self.assertEqual(timeline.total_frames, 2608)
            self.assertEqual(timeline.video[-1].start_frame, 2024)
            self.assertEqual(timeline.video[-1].duration_frames, 584)
            self.assertEqual(len(timeline.subtitles), 10)
            for path in result["paths"]["shots"]:
                self.assertTrue(path.is_file())
            self.assertTrue(result["paths"]["render"].is_file())

    def test_missing_voice_reference_fails(self):
        with tempfile.TemporaryDirectory(dir=WORKSPACE / "build") as temp:
            with self.assertRaises(E65Error):
                adapt_e65(
                    E65 / "manifest.json",
                    workspace=WORKSPACE,
                    output_dir=Path(temp) / "contracts",
                    voice_ref=Path(temp) / "missing.wav",
                )


if __name__ == "__main__":
    unittest.main()
