from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml

from course_control.adapters import brand as brand_stage
from course_control.branding import (
    BrandError,
    first_sound_s,
    video_timing_from_pts,
    build_plan,
    choose_master,
    delivery_path,
    load_spec,
    resolve_preset_id,
    segment_key,
)
from course_control.contracts import Branding, BrandSegment, LessonConfig
from tests._process import NO_CONSOLE

WORKSPACE = Path(__file__).resolve().parents[2]
FIXTURE = WORKSPACE / "CourseControl" / "tests" / "fixtures" / "lesson-smoke" / "lesson.yaml"


def _lesson() -> LessonConfig:
    data = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    return LessonConfig.model_validate(data)


def _workspace(root: Path) -> SimpleNamespace:
    build = root / "build" / "lesson-smoke"
    (build / "final").mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        workspace=WORKSPACE,
        build_root=build,
        slug="lesson-smoke",
        lesson=_lesson(),
        outputs=None,
    )


def _paths(root: Path, **branding) -> SimpleNamespace:
    paths = _workspace(root)
    lesson = paths.lesson.model_copy(
        update={"branding": Branding.model_validate(branding)}
    )
    paths.lesson = lesson
    return paths


class BrandSpecTest(unittest.TestCase):
    def test_spec_content_kinds_reference_existing_presets(self):
        spec = load_spec(WORKSPACE)
        for kind, meta in spec["content_kinds"].items():
            for segment in ("intro", "outro"):
                preset = meta.get(segment)
                if preset is not None:
                    self.assertIn(preset, spec["presets"], f"{kind}.{segment}")

    def test_presets_have_bounds_and_composition(self):
        spec = load_spec(WORKSPACE)
        for preset_id, preset in spec["presets"].items():
            self.assertTrue(preset["composition"].startswith("Brand"), preset_id)
            self.assertLessEqual(preset["min_s"], preset["duration_s"])
            self.assertLessEqual(preset["duration_s"], preset["max_s"])

    def test_missing_spec_is_an_explicit_error(self):
        with self.assertRaises(BrandError):
            load_spec(WORKSPACE / "does-not-exist")


class BrandPlanTest(unittest.TestCase):
    def test_formal_course_auto_gets_intro_and_outro(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(Path(tmp), intro={}, outro={})
            plan = build_plan(paths)
            kinds = [segment["kind"] for segment in plan.segments]
            self.assertEqual(kinds, ["intro", "outro"])
            self.assertEqual(plan.segments[0]["preset"], "course_intro")
            self.assertEqual(plan.segments[0]["duration_frames"], 90)  # 3.0 s @ 30
            self.assertEqual(plan.segments[1]["preset"], "course_outro")
            self.assertEqual(plan.brand_duration_s, 15.0)

    def test_news_never_gets_an_intro(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(Path(tmp), intro={}, outro={})
            lesson = paths.lesson.model_copy(
                update={
                    "audio": paths.lesson.audio.model_copy(
                        update={"content_kind": "news"}
                    )
                }
            )
            paths.lesson = lesson
            plan = build_plan(paths)
            self.assertEqual([s["kind"] for s in plan.segments], ["outro"])
            self.assertEqual(plan.segments[0]["preset"], "news_outro")
            self.assertEqual(plan.segments[0]["props"]["category"], "INDUSTRY BRIEFING")

    def test_news_rejects_an_explicit_intro(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(Path(tmp), intro={"preset": "course_intro"}, outro={})
            paths.lesson = paths.lesson.model_copy(
                update={
                    "audio": paths.lesson.audio.model_copy(
                        update={"content_kind": "news"}
                    )
                }
            )
            with self.assertRaises(BrandError):
                build_plan(paths)

    def test_short_uses_a_signature_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(Path(tmp), intro={}, outro={})
            paths.lesson = paths.lesson.model_copy(update={"video_form": "short"})
            with self.assertRaises(BrandError):
                # The fixture renders 1920x1080; a signature needs 1080x1920.
                build_plan(paths)

    def test_short_signature_rejected_for_long_form(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(Path(tmp), outro={"preset": "short_signature"})
            with self.assertRaises(BrandError):
                build_plan(paths)

    def test_duration_override_is_applied_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(Path(tmp), intro={"duration_s": 4.0}, outro={"enabled": False})
            plan = build_plan(paths)
            self.assertEqual(plan.segments[0]["duration_s"], 4.0)
            self.assertEqual(plan.segments[0]["duration_frames"], 120)
            self.assertEqual(plan.brand_duration_s, 4.0)

            paths = _paths(Path(tmp), intro={"duration_s": 9.0}, outro={"enabled": False})
            with self.assertRaises(BrandError) as caught:
                build_plan(paths)
            self.assertIn("outside", str(caught.exception))

    def test_unknown_preset_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(Path(tmp), intro={"preset": "fancy-logo"})
            with self.assertRaises(BrandError) as caught:
                build_plan(paths)
            self.assertIn("unknown brand preset", str(caught.exception))

    def test_resolution_must_match_the_preset(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(Path(tmp), intro={}, outro={"enabled": False})
            outputs = paths.lesson.outputs.model_copy(update={"resolution": (2560, 1440)})
            paths.lesson = paths.lesson.model_copy(update={"outputs": outputs})
            with self.assertRaises(BrandError) as caught:
                build_plan(paths)
            self.assertIn("1920x1080", str(caught.exception))

    def test_plan_is_deterministic_and_json_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(Path(tmp), intro={}, outro={})
            first = build_plan(paths).as_dict()
            second = build_plan(paths).as_dict()
            self.assertEqual(first, second)
            self.assertEqual(json.loads(json.dumps(first)), first)

    def test_props_carry_no_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(Path(tmp), intro={}, outro={})
            plan = build_plan(paths)
            for segment in plan.segments:
                self.assertEqual(
                    set(segment["props"]),
                    {
                        "durationInSeconds",
                        "title",
                        "category",
                        "date",
                        "showReservedArea",
                    },
                )
                self.assertEqual(segment["props"]["title"], paths.lesson.title_en)
                self.assertNotIn("五分钟", str(segment["props"]))

    def test_segment_key_tracks_props(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(Path(tmp), intro={}, outro={})
            plan = build_plan(paths)
            key = segment_key(plan, plan.segments[0])
            moved = dict(plan.segments[0])
            moved["props"] = {**moved["props"], "title": "Another lesson"}
            self.assertNotEqual(key, segment_key(plan, moved))

    def test_rendering_resolution_and_master(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(Path(tmp), intro={})
            plan = build_plan(paths)
            self.assertEqual((plan.width, plan.height), (1920, 1080))
            self.assertEqual(plan.fps, 30)
            self.assertIsNone(plan.master)
            self.assertEqual(delivery_path(paths).name, "course-video-delivery.mp4")


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
class AudioAlignmentTest(unittest.TestCase):
    def _ffmpeg(self, *args: str) -> None:
        result = subprocess.run(
            [shutil.which("ffmpeg"), "-y", *args],
            capture_output=True,
            text=True,
            creationflags=NO_CONSOLE,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-600:])

    def test_first_sound_after_silence(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "delayed.wav"
            self._ffmpeg(
                "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                "-filter_complex",
                "[1:a]atrim=duration=1[s0];[s0][0:a]concat=n=2:v=0:a=1[a]",
                "-map", "[a]", str(target),
            )
            value = first_sound_s(target, limit=3.0)
            self.assertIsNotNone(value)
            self.assertAlmostEqual(value, 1.0, delta=0.25)

    def test_sound_from_the_first_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "tone.wav"
            self._ffmpeg(
                "-f", "lavfi", "-i", "sine=frequency=440:duration=1", str(target)
            )
            self.assertEqual(first_sound_s(target, limit=1.0), 0.0)


class VideoTimingTest(unittest.TestCase):
    def test_normal_frame_spacing_passes(self):
        pts = [index / 30 for index in range(90)]
        result = video_timing_from_pts(pts, 30, 3.0)
        self.assertEqual(result["status"], "pass", result)

    def test_collapsed_timestamps_fail(self):
        # The observed failure: hundreds of body frames 11 microseconds apart.
        pts = [2.921 + index * 0.000011 for index in range(400)]
        result = video_timing_from_pts(pts, 30, 13.0)
        self.assertEqual(result["status"], "fail")
        self.assertGreater(result["clustered_intervals"], 2)

    def test_missing_frames_fail(self):
        pts = [index / 30 for index in range(10)]
        result = video_timing_from_pts(pts, 30, 10.0)
        self.assertEqual(result["status"], "fail")


class MasterSelectionTest(unittest.TestCase):
    def test_mixed_then_captioned_then_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "build" / "lesson"
            final = root / "final"
            final.mkdir(parents=True)
            self.assertIsNone(choose_master(root))
            (final / "course-video.mp4").write_bytes(b"")
            self.assertEqual(choose_master(root), "course-video.mp4")
            (final / "course-video-captioned.mp4").write_bytes(b"")
            self.assertEqual(choose_master(root), "course-video-captioned.mp4")
            (final / "course-video-mixed.mp4").write_bytes(b"")
            self.assertEqual(choose_master(root), "course-video-mixed.mp4")


class BrandingContractTest(unittest.TestCase):
    def test_branding_is_disabled_by_default(self):
        lesson = _lesson()
        self.assertFalse(lesson.branding.enabled)
        self.assertIsNone(lesson.branding.intro)

    def test_branding_parses_from_lesson_yaml(self):
        data = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
        data["branding"] = {
            "intro": {},
            "outro": {"duration_s": 12},
            "date": "2026-11-09",
        }
        lesson = LessonConfig.model_validate(data)
        self.assertTrue(lesson.branding.enabled)
        self.assertEqual(lesson.branding.intro.preset, "auto")
        self.assertEqual(lesson.branding.outro.duration_s, 12)

    def test_branding_rejects_course_metadata_fields(self):
        # Field permissions: series / next episode / translations are not part
        # of the brand frames and must fail loudly instead of being rendered.
        for field in ("series", "next_title", "episode"):
            with self.assertRaises(Exception):
                Branding.model_validate({field: "x"})
        with self.assertRaises(Exception):
            BrandSegment(preset="course_intro", subtitle="五分钟看懂 Transformer")

    def test_branding_rejects_unknown_fields(self):
        data = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
        data["branding"] = {"logo": "wayne.svg"}
        with self.assertRaises(Exception):
            LessonConfig.model_validate(data)

    def test_segment_duration_bounds_are_enforced_at_parse_time(self):
        with self.assertRaises(Exception):
            BrandSegment(preset="course_intro", duration_s=60)


class BrandStageTest(unittest.TestCase):
    def test_disabled_branding_is_not_applicable(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _workspace(Path(tmp))
            outcome = brand_stage.run(paths)
            self.assertEqual(outcome.status.value, "not_applicable")
            self.assertEqual(outcome.reason, "branding_disabled")

    def test_enabled_without_a_master_fails_before_rendering(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(Path(tmp), intro={})
            outcome = brand_stage.run(paths)
            self.assertEqual(outcome.status.value, "fail")
            self.assertIn("no viewing master", " ".join(outcome.errors))


class ResolvePresetTest(unittest.TestCase):
    def test_auto_maps_to_content_kind(self):
        spec = load_spec(WORKSPACE)
        lesson = _lesson()
        segment = BrandSegment(preset="auto")
        self.assertEqual(
            resolve_preset_id(lesson, "intro", segment, spec), "course_intro"
        )
        self.assertEqual(
            resolve_preset_id(lesson, "outro", segment, spec), "course_outro"
        )


if __name__ == "__main__":
    unittest.main()
