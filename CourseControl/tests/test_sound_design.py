from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from course_control.content.contracts import (
    AudioPolicy,
    BgmCue,
    Compose,
    Content,
    LessonConfig,
)
from course_control.sound.checks import check_sound
from course_control.sound.planner import (
    ambience_cues,
    build_sound,
    delivery_for,
    music_cues,
    sfx_events,
    voice_cues,
)
from course_control.sound.schema import (
    AmbienceCue,
    MixPlan,
    MusicCue,
    SfxEvent,
    SoundDesign,
    VoiceCue,
)

WORKSPACE = Path(__file__).resolve().parents[2]


def lesson(kind: str = "formal_course", bgm: list[BgmCue] | None = None) -> LessonConfig:
    return LessonConfig(
        schema_version=1,
        lesson_id="01-transformer-demo",
        title_en="The Transformer",
        title_zh="Transformer",
        status="draft",
        content=Content(slides="slides.md", notes="notes.md", storyboard="storyboard.yaml", assets="assets/"),
        outputs={},
        engines=["manim"],
        compose=Compose(mode="deck"),
        audio=AudioPolicy(content_kind=kind, bgm=bgm or []),
    )


def segment(index: int, text: str, *, seconds: float = 10.0, style: str | None = None):
    return SimpleNamespace(
        id=f"seg_{index}",
        shot_id="shot_001",
        text=text,
        style=style,
        pause_after_ms=300,
        estimated_seconds=seconds,
        emphasis=[],
    )


def plan(*, narration=None, shots=None, chapters=None) -> SimpleNamespace:
    shots = shots or [SimpleNamespace(id="shot_001", start_s=0.0, end_s=120.0, purpose="explain")]
    chapters = chapters or [
        SimpleNamespace(start_s=0.0, end_s=40.0, target_seconds=40.0, shot_ids=["shot_001"]),
        SimpleNamespace(start_s=40.0, end_s=120.0, target_seconds=80.0, shot_ids=["shot_001"]),
    ]
    return SimpleNamespace(
        lesson_id="01-transformer-demo",
        shots=shots,
        narration=narration or [],
        chapters=chapters,
        duration=SimpleNamespace(planned_seconds=120.0),
    )


def visual(family: str = "engineering"):
    shot = SimpleNamespace(
        shot_id="shot_001",
        art_direction=SimpleNamespace(family=family, theme="editorial_science"),
        concept="airflow separates over the rear window",
        keyframe=lambda state: SimpleNamespace(at_s=30.0, id=state),
    )
    return SimpleNamespace(shots=[shot])


class DeliveryTest(unittest.TestCase):
    def test_a_question_mark_wins(self):
        delivery, _ = delivery_for(segment(1, "Why does the flow detach?"))
        self.assertEqual(delivery, "question")

    def test_script_markup_wins_over_phrasing(self):
        delivery, _ = delivery_for(segment(1, "The flow detaches.", style="example"))
        self.assertEqual(delivery, "example")

    def test_markers_use_word_boundaries(self):
        self.assertEqual(delivery_for(segment(1, "The iso surface is drawn."))[0], "calm_explanatory")
        self.assertEqual(delivery_for(segment(2, "So the pressure recovers."))[0], "conclusion")
        self.assertEqual(delivery_for(segment(3, "However, the wake widens."))[0], "contrast")


class VoiceTimingTest(unittest.TestCase):
    def test_segments_accumulate_inside_a_shot(self):
        cues = voice_cues(plan(narration=[segment(1, "One.", seconds=10), segment(2, "Two.", seconds=5)]))
        self.assertEqual([cue.at_s for cue in cues], [0.0, 10.0])


class MusicTest(unittest.TestCase):
    def test_a_lecture_is_silent_by_policy(self):
        cues = music_cues(lesson(), plan())
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0].action, "silence")
        self.assertIsNone(cues[0].track_id)

    def test_an_explainer_enters_and_ducks_by_section(self):
        cues = music_cues(lesson("popular_science"), plan())
        actions = [cue.action for cue in cues]
        self.assertEqual(actions[0], "enter")
        self.assertIn("duck", actions)

    def test_declared_cues_are_carried_through(self):
        declared = [BgmCue(track_id="bgm_serenity_guitar", start_s=0, end_s=120, license_status="cc_by")]
        cues = music_cues(lesson("popular_science", declared), plan())
        self.assertEqual(cues[0].track_id, "bgm_serenity_guitar")
        self.assertEqual(cues[0].license_status, "cc_by")


class SfxTest(unittest.TestCase):
    def test_effects_are_placed_on_the_visual_turn(self):
        events = sfx_events(plan(), visual("engineering"))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].at_s, 30.0)
        self.assertEqual(events[0].visual_ref, "shot_001:turn")

    def test_no_effects_without_a_visual_design(self):
        self.assertEqual(sfx_events(plan(), None), [])

    def test_geometric_and_editorial_shots_stay_silent(self):
        self.assertEqual(sfx_events(plan(), visual("geometric")), [])
        self.assertEqual(sfx_events(plan(), visual("editorial")), [])

    def test_ambience_only_for_physical_spaces(self):
        self.assertEqual(len(ambience_cues(plan(), visual("engineering"))), 1)
        self.assertEqual(ambience_cues(plan(), visual("geometric")), [])


def sound(**updates) -> SoundDesign:
    data = dict(
        lesson_id="01-transformer-demo",
        content_kind="formal_course",
        style="lecture",
        voice=[VoiceCue(segment_id="seg_1", shot_id="shot_001", at_s=0.0, delivery="calm_explanatory", reason="r")],
        music=[
            MusicCue(
                start_s=0,
                end_s=120,
                action="silence",
                mood="room tone",
                reason="lecture",
            )
        ],
        sfx=[],
        ambience=[],
        mix=MixPlan(),
        checks=[],
    )
    data.update(updates)
    return SoundDesign(**data)


class SoundCheckTest(unittest.TestCase):
    def run_checks(self, design, **kwargs):
        options = dict(has_visual_design=True, has_narration=True)
        options.update(kwargs)
        return {check.id: check.level for check in check_sound(design, **options)}

    def test_a_clean_lecture_has_no_errors(self):
        levels = self.run_checks(sound())
        self.assertFalse([item for item in levels.values() if item == "error"])

    def test_music_in_a_lecture_is_a_creative_choice(self):
        design = sound(
            music=[MusicCue(start_s=0, end_s=120, action="hold", mood="bed", track_id="x", reason="r")]
        )
        levels = self.run_checks(design)
        self.assertNotIn("sound.bgm_policy", levels)
        self.assertFalse([item for item in levels.values() if item == "error"])

    def test_unknown_licence_is_an_error(self):
        design = sound(
            content_kind="popular_science",
            style="explainer",
            music=[
                MusicCue(
                    start_s=0,
                    end_s=120,
                    action="hold",
                    mood="bed",
                    track_id="bgm_x",
                    license_status="unknown",
                    reason="r",
                )
            ],
        )
        self.assertEqual(self.run_checks(design).get("sound.licence_unknown"), "error")

    def test_an_effect_without_a_visual_event_is_an_error(self):
        design = sound(
            content_kind="popular_science",
            style="explainer",
            sfx=[
                SfxEvent(
                    id="sfx_shot_001",
                    at_s=10,
                    event="whoosh",
                    source="air_soft",
                    trigger="visual_event",
                    reason="r",
                )
            ],
        )
        self.assertEqual(self.run_checks(design).get("sound.sfx_unmotivated"), "error")

    def test_effect_density_is_a_warning(self):
        events = [
            SfxEvent(
                id=f"sfx_shot_{index:03d}",
                at_s=float(index),
                event="tick",
                source="tick",
                trigger="visual_event",
                visual_ref="shot_001:turn",
                reason="r",
            )
            for index in range(6)
        ]
        design = sound(content_kind="popular_science", style="explainer", sfx=events)
        self.assertEqual(self.run_checks(design).get("sound.sfx_density"), "warning")

    def test_missing_voice_is_an_error_when_narration_exists(self):
        self.assertEqual(self.run_checks(sound(voice=[])).get("sound.voice_missing"), "error")

    def test_loudness_outside_the_target_is_a_warning(self):
        design = sound(mix=MixPlan(loudness_lufs=-12.0))
        self.assertEqual(self.run_checks(design).get("sound.loudness_target"), "warning")

    def test_ambience_in_a_lecture_asks_for_confirmation(self):
        design = sound(
            ambience=[AmbienceCue(start_s=0, end_s=30, source="wind tunnel room", reason="scene")]
        )
        self.assertEqual(self.run_checks(design).get("sound.ambience_in_lecture"), "warning")


class BuildSoundTest(unittest.TestCase):
    def test_build_wires_all_five_tracks(self):
        design = build_sound(lesson(), plan(narration=[segment(1, "One.")]), visual("engineering"))
        self.assertEqual(len(design.voice), 1)
        self.assertEqual(len(design.sfx), 1)
        self.assertEqual(len(design.ambience), 1)
        self.assertEqual(design.content_kind, "formal_course")
        self.assertEqual(design.mix.loudness_lufs, -16.0)


if __name__ == "__main__":
    unittest.main()
