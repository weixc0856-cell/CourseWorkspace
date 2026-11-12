from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from course_control.voice.audio_plan import build_audio_plan, write_audio_plan
from course_control.content.contracts import AudioPolicy, BgmCue
from course_control.content.paths import LessonPaths

WORKSPACE = Path(__file__).resolve().parents[2]
FIXTURE = WORKSPACE / "CourseControl" / "tests" / "fixtures" / "lesson-authoring"


class AudioPlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.paths = LessonPaths.load(
            WORKSPACE, FIXTURE, build_root_override=Path(cls.tmp.name)
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def with_audio(self, policy: AudioPolicy):
        return self.paths.lesson.model_copy(update={"audio": policy})

    def test_default_is_formal_course_without_bgm(self):
        plan = build_audio_plan(self.paths.lesson)
        self.assertEqual(plan.content_kind, "formal_course")
        self.assertFalse(plan.bgm_allowed)
        self.assertEqual(plan.cues, [])
        self.assertEqual(plan.status, "ready")

    def test_formal_course_rejects_bgm(self):
        cue = BgmCue(track_id="bgm_x", start_s=0, end_s=30, license_status="public_domain")
        plan = build_audio_plan(
            self.with_audio(AudioPolicy(content_kind="formal_course", bgm=[cue]))
        )
        self.assertEqual(plan.status, "blocked")
        self.assertTrue(any("does not allow BGM" in error for error in plan.errors))

    def test_popular_science_needs_attribution_for_cc_by(self):
        cue = BgmCue(track_id="bgm_x", start_s=0, end_s=30, license_status="cc_by")
        plan = build_audio_plan(
            self.with_audio(AudioPolicy(content_kind="popular_science", bgm=[cue]))
        )
        self.assertEqual(plan.status, "blocked")
        self.assertTrue(any("attribution" in error for error in plan.errors))

    def test_popular_science_ready_with_attribution(self):
        cue = BgmCue(
            track_id="bgm_serenity_guitar",
            start_s=3,
            end_s=90,
            gain_db=-25,
            license_status="cc_by",
            attribution="SERENITY by Jason Shaw (audionautix.com), CC BY 3.0 US",
        )
        plan = build_audio_plan(
            self.with_audio(AudioPolicy(content_kind="popular_science", bgm=[cue]))
        )
        self.assertEqual(plan.status, "ready")
        self.assertTrue(plan.bgm_allowed)
        self.assertFalse(plan.errors)

    def test_unverified_owner_authorization_cannot_be_commercial(self):
        cue = BgmCue(
            track_id="bgm_commons_we_never",
            start_s=0,
            end_s=30,
            license_status="owner_authorized_unverified",
            commercial_allowed=True,
        )
        plan = build_audio_plan(
            self.with_audio(AudioPolicy(content_kind="popular_science", bgm=[cue]))
        )
        self.assertEqual(plan.status, "blocked")
        self.assertTrue(any("commercial_allowed" in error for error in plan.errors))

    def test_writer_creates_artifact(self):
        plan, target = write_audio_plan(Path(self.tmp.name), self.paths.lesson)
        self.assertEqual(plan.status, "ready")
        self.assertTrue(target.is_file())
        self.assertEqual(target.parent.name, "audio")


if __name__ == "__main__":
    unittest.main()
