from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from course_control.content.contracts_v1 import (
    AssetRef,
    EvidenceManifestV1,
    LessonSpec,
    NarrationSpec,
    RationalFPS,
    RenderManifest,
    ShotSpecV1,
    TimelineSpec,
    V1_MODELS,
)

WORKSPACE = Path(__file__).resolve().parents[2]
EXAMPLES = WORKSPACE / "docs" / "contracts" / "examples"
SCHEMAS = WORKSPACE / "shared" / "schemas"


def example(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def asset(**overrides) -> dict:
    payload = {
        "path": "build/demo/a.mp4",
        "sha256": "a" * 64,
        "bytes": 10,
        "kind": "video",
        "origin": "rendered",
        "version": None,
    }
    payload.update(overrides)
    return payload


class RationalFPSTest(unittest.TestCase):
    def test_rational_rates(self):
        for num, den in [(24, 1), (25, 1), (30, 1), (30000, 1001), (60000, 1001)]:
            fps = RationalFPS(fps_num=num, fps_den=den)
            self.assertEqual(fps.frame_to_ms(0), 0)
            self.assertEqual(fps.ms_to_frame(0), 0)

    def test_invalid_rates_rejected(self):
        with self.assertRaises(ValidationError):
            RationalFPS(fps_num=0, fps_den=1)
        with self.assertRaises(ValidationError):
            RationalFPS(fps_num=30, fps_den=0)
        with self.assertRaises(ValidationError):
            RationalFPS(fps_num=-30, fps_den=1)

    def test_string_numbers_are_not_coerced(self):
        with self.assertRaises(ValidationError):
            RationalFPS(fps_num="30", fps_den=1)
        with self.assertRaises(ValidationError):
            AssetRef.model_validate(asset(bytes="10"))


class AssetRefTest(unittest.TestCase):
    def test_valid_asset(self):
        ref = AssetRef.model_validate(asset())
        self.assertEqual(ref.kind, "video")
        self.assertIsNone(ref.version)

    def test_rejects_absolute_and_traversal(self):
        for bad in ("/abs/a.mp4", "C:/abs/a.mp4", "../a.mp4", r"a\b.mp4"):
            with self.subTest(path=bad), self.assertRaises(ValidationError):
                AssetRef.model_validate(asset(path=bad))

    def test_external_absolute_path_allowed(self):
        ref = AssetRef.model_validate(
            asset(path="D:\voice\ref.wav", origin="external", kind="audio")
        )
        self.assertEqual(ref.origin, "external")

    def test_rejects_bad_hash_and_bytes(self):
        with self.assertRaises(ValidationError):
            AssetRef.model_validate(asset(sha256="NOT-A-HASH"))
        with self.assertRaises(ValidationError):
            AssetRef.model_validate(asset(bytes=-1))


class LessonSpecTest(unittest.TestCase):
    def test_example_validates(self):
        lesson = LessonSpec.model_validate(example("lesson.spec.json"))
        self.assertEqual(lesson.lesson_id, "e6-transformer-attention")
        self.assertEqual(lesson.output.fps.fps_num, 30)

    def test_duplicate_tracks_rejected(self):
        data = example("lesson.spec.json")
        data["tracks"] = ["manim", "manim"]
        with self.assertRaises(ValidationError):
            LessonSpec.model_validate(data)

    def test_enabled_narration_requires_spec(self):
        data = example("lesson.spec.json")
        data["narration"] = {"enabled": True, "spec": None}
        with self.assertRaises(ValidationError):
            LessonSpec.model_validate(data)

    def test_invalid_lesson_id_rejected(self):
        data = example("lesson.spec.json")
        data["lesson_id"] = "E6 Transformer"
        with self.assertRaises(ValidationError):
            LessonSpec.model_validate(data)


class ShotSpecTest(unittest.TestCase):
    def test_manim_example_uses_class_alias(self):
        shot = ShotSpecV1.model_validate(example("shot.spec.json"))
        self.assertEqual(shot.source.kind, "manim")
        self.assertEqual(shot.source.scene_class, "QKVScene")

    def test_session_example_validates(self):
        shot = ShotSpecV1.model_validate(example("shot.spec.session.json"))
        self.assertEqual(shot.track, "session")
        self.assertIsNone(shot.asset)

    def test_track_must_match_source(self):
        data = example("shot.spec.json")
        data["track"] = "session"
        with self.assertRaises(ValidationError):
            ShotSpecV1.model_validate(data)

    def test_asset_must_be_video_or_image(self):
        data = example("shot.spec.json")
        data["asset"] = asset(kind="audio")
        with self.assertRaises(ValidationError):
            ShotSpecV1.model_validate(data)

    def test_invalid_shot_id_rejected(self):
        data = example("shot.spec.json")
        data["shot_id"] = "S 2"
        with self.assertRaises(ValidationError):
            ShotSpecV1.model_validate(data)


class NarrationSpecTest(unittest.TestCase):
    def test_example_validates(self):
        spec = NarrationSpec.model_validate(example("narration.spec.json"))
        self.assertEqual(len(spec.segments), 4)
        self.assertEqual(spec.segments[0].duration_frames, 206)

    def test_duration_frames_must_match_ms(self):
        data = example("narration.spec.json")
        data["segments"][0]["duration_frames"] += 1
        with self.assertRaises(ValidationError):
            NarrationSpec.model_validate(data)

    def test_segments_must_be_ordered(self):
        data = example("narration.spec.json")
        data["segments"][0], data["segments"][1] = data["segments"][1], data["segments"][0]
        with self.assertRaises(ValidationError):
            NarrationSpec.model_validate(data)

    def test_overlap_rejected(self):
        data = example("narration.spec.json")
        data["segments"][1]["start_frame"] = 200
        with self.assertRaises(ValidationError):
            NarrationSpec.model_validate(data)

    def test_total_must_match_frames(self):
        data = example("narration.spec.json")
        data["total"]["duration_ms"] += 1
        with self.assertRaises(ValidationError):
            NarrationSpec.model_validate(data)


class TimelineSpecTest(unittest.TestCase):
    def test_example_validates(self):
        timeline = TimelineSpec.model_validate(example("timeline.spec.json"))
        self.assertEqual(timeline.total_frames, 993)
        self.assertEqual(timeline.duration_ms, 33100)

    def test_srt_text_uses_integer_frames(self):
        timeline = TimelineSpec.model_validate(example("timeline.spec.json"))
        text = timeline.srt_text()
        self.assertIn("00:00:00,500 --> 00:00:07,300", text)
        self.assertTrue(text.endswith("\n"))

    def test_gap_is_rejected(self):
        data = example("timeline.spec.json")
        data["sync"]["allow_gap_frames"] = 0
        data["video"][1]["start_frame"] = 241
        with self.assertRaises(ValidationError) as ctx:
            TimelineSpec.model_validate(data)
        self.assertIn("gap", str(ctx.exception))

    def test_overlap_is_rejected(self):
        data = example("timeline.spec.json")
        data["video"][1]["start_frame"] = 239
        with self.assertRaises(ValidationError) as ctx:
            TimelineSpec.model_validate(data)
        self.assertIn("overlap", str(ctx.exception))

    def test_overlay_outside_base_is_rejected(self):
        data = example("timeline.spec.json")
        data["video"].append(
            {
                "shot_id": "s5",
                "start_frame": 990,
                "duration_frames": 10,
                "role": "overlay",
                "z": 1,
                "asset": asset(),
            }
        )
        with self.assertRaises(ValidationError) as ctx:
            TimelineSpec.model_validate(data)
        self.assertIn("outside", str(ctx.exception))

    def test_audio_overflow_is_rejected(self):
        data = example("timeline.spec.json")
        data["audio"][-1]["start_frame"] = 900
        with self.assertRaises(ValidationError) as ctx:
            TimelineSpec.model_validate(data)
        self.assertIn("exceeds", str(ctx.exception))

    def test_subtitle_overlap_is_rejected(self):
        data = example("timeline.spec.json")
        data["subtitles"][1]["start_frame"] = 200
        with self.assertRaises(ValidationError) as ctx:
            TimelineSpec.model_validate(data)
        self.assertIn("overlap", str(ctx.exception))

    def test_total_must_match_base_end(self):
        data = example("timeline.spec.json")
        data["total_frames"] = 994
        with self.assertRaises(ValidationError) as ctx:
            TimelineSpec.model_validate(data)
        self.assertIn("expected 994", str(ctx.exception))

    def test_invalid_fps_rejected(self):
        data = example("timeline.spec.json")
        data["fps"]["fps_num"] = 0
        with self.assertRaises(ValidationError):
            TimelineSpec.model_validate(data)


class EvidenceManifestTest(unittest.TestCase):
    def test_example_validates(self):
        manifest = EvidenceManifestV1.model_validate(example("evidence.manifest.json"))
        self.assertEqual(manifest.run_id, "20261107T090000Z-1a2b3c4d")
        self.assertEqual(len(manifest.artifacts), 2)

    def test_bad_run_id_rejected(self):
        data = example("evidence.manifest.json")
        data["run_id"] = "yesterday"
        with self.assertRaises(ValidationError):
            EvidenceManifestV1.model_validate(data)

    def test_execution_result_must_be_json(self):
        data = example("evidence.manifest.json")
        data["execution_result"]["kind"] = "video"
        with self.assertRaises(ValidationError):
            EvidenceManifestV1.model_validate(data)

    def test_duplicate_artifact_path_rejected(self):
        data = example("evidence.manifest.json")
        data["artifacts"].append(copy.deepcopy(data["artifacts"][0]))
        with self.assertRaises(ValidationError):
            EvidenceManifestV1.model_validate(data)


class RenderManifestTest(unittest.TestCase):
    def test_examples_validate(self):
        for name in ("render.manifest.json", "e6.render.manifest.v1.json"):
            with self.subTest(name=name):
                manifest = RenderManifest.model_validate(example(name))
                self.assertEqual(manifest.output.total_frames, 993)

    def test_duration_must_match_frames(self):
        data = example("render.manifest.json")
        data["output"]["duration_ms"] += 1
        with self.assertRaises(ValidationError) as ctx:
            RenderManifest.model_validate(data)
        self.assertIn("duration_ms", str(ctx.exception))

    def test_shot_must_fit_output(self):
        data = example("render.manifest.json")
        data["shots"][-1]["duration_frames"] += 1
        with self.assertRaises(ValidationError) as ctx:
            RenderManifest.model_validate(data)
        self.assertIn("exceeds", str(ctx.exception))

    def test_duplicate_check_id_rejected(self):
        data = example("render.manifest.json")
        data["checks"].append(copy.deepcopy(data["checks"][0]))
        with self.assertRaises(ValidationError):
            RenderManifest.model_validate(data)

    def test_legacy_source_requires_v0_manifest(self):
        data = example("e6.render.manifest.v1.json")
        data["legacy"] = None
        with self.assertRaises(ValidationError) as ctx:
            RenderManifest.model_validate(data)
        self.assertIn("legacy.v0_manifest", str(ctx.exception))


class SchemaAndExampleTest(unittest.TestCase):
    def test_schema_files_match_models(self):
        for name, model in V1_MODELS.items():
            with self.subTest(name=name):
                path = SCHEMAS / f"{name}.schema.json"
                self.assertTrue(path.is_file(), f"missing schema: {path}")
                self.assertEqual(
                    json.loads(path.read_text(encoding="utf-8")),
                    model.model_json_schema(),
                )

    def test_all_examples_validate(self):
        mapping = {
            "lesson.spec.json": LessonSpec,
            "shot.spec.json": ShotSpecV1,
            "shot.spec.session.json": ShotSpecV1,
            "narration.spec.json": NarrationSpec,
            "timeline.spec.json": TimelineSpec,
            "evidence.manifest.json": EvidenceManifestV1,
            "render.manifest.json": RenderManifest,
            "e6.render.manifest.v1.json": RenderManifest,
        }
        for name, model in mapping.items():
            with self.subTest(name=name):
                model.model_validate(example(name))


if __name__ == "__main__":
    unittest.main()
