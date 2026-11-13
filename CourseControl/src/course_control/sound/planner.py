"""Derive a sound design from the lesson, the director plan and the visual design."""
from __future__ import annotations

import json
import re
from pathlib import Path

from course_control.content.contracts import BgmCue, LessonConfig
from course_control.design.schema import VisualDesign
from course_control.direction.schema import DirectorPlan, NarrationSegmentPlan
from course_control.sound.schema import (
    AmbienceCue,
    MixPlan,
    MusicCue,
    SfxEvent,
    SoundDesign,
    VoiceCue,
)

DELIVERY_HINTS: tuple[tuple[str, str], ...] = (
    (r"\b(why|how does|what if)\b", "question"),
    (r"\b(so|therefore|that means|the point is|in the end)\b", "conclusion"),
    (r"\b(but|however|unlike|instead|by contrast)\b", "contrast"),
    (r"\b(for example|imagine|consider)\b", "example"),
    (r"\b(next|now let|let me move|turn to)\b", "transition"),
)

# Editorial and geometric shots stay silent: a tick on every data change turns a
# documentary into a game UI.  Only shots that show a physical event get one.
SFX_BY_FAMILY = {
    "engineering": ("mechanical_motion", "mech_soft"),
    "cinematic": ("field_shift", "air_soft"),
}

AMBIENCE_BY_FAMILY = {
    "engineering": "studio room tone",
    "cinematic": "low field hum",
}

STYLE_BY_KIND = {
    "popular_science": "explainer",
    "formal_course": "lecture",
    "news": "news",
}


def delivery_for(segment: NarrationSegmentPlan) -> tuple[str, str]:
    """Infer a delivery from the script's own mark-up, then from its phrasing."""
    style = (segment.style or "").strip().lower()
    if style in {
        "calm_explanatory",
        "question",
        "conclusion",
        "contrast",
        "example",
        "transition",
    }:
        return style, f"the script marks this segment as {style}"
    text = segment.text.lower()
    if "?" in text:
        return "question", "the segment asks a question; let it hang before the answer"
    for pattern, delivery in DELIVERY_HINTS:
        if re.search(pattern, text):
            return delivery, f"phrasing suggests {delivery}"
    return "calm_explanatory", "unmarked segment; keep it even"


def voice_cues(plan: DirectorPlan) -> list[VoiceCue]:
    by_shot = {shot.id: shot.start_s for shot in plan.shots}
    cursor: dict[str, float] = {}
    cues: list[VoiceCue] = []
    for segment in plan.narration:
        delivery, reason = delivery_for(segment)
        start = cursor.get(segment.shot_id, by_shot.get(segment.shot_id, 0.0))
        cursor[segment.shot_id] = start + segment.estimated_seconds
        cues.append(
            VoiceCue(
                segment_id=segment.id,
                shot_id=segment.shot_id,
                at_s=round(start, 3),
                delivery=delivery,  # type: ignore[arg-type]
                emphasis=list(segment.emphasis),
                pause_after_ms=segment.pause_after_ms,
                reason=reason,
            )
        )
    return cues


def _from_lesson_cues(cues: list[BgmCue]) -> list[MusicCue]:
    return [
        MusicCue(
            start_s=cue.start_s,
            end_s=cue.end_s,
            action="hold",
            mood="declared in lesson.yaml audio.bgm",
            track_id=cue.track_id,
            gain_db=cue.gain_db,
            license_status=cue.license_status,
            reason="lesson declares a music bed; review whether every second of it earns its place",
        )
        for cue in cues
    ]


def music_cues(lesson: LessonConfig, plan: DirectorPlan) -> list[MusicCue]:
    declared = _from_lesson_cues(lesson.audio.bgm)
    if declared:
        return declared
    end = plan.duration.planned_seconds

    if lesson.audio.content_kind in {"formal_course", "news"}:
        return [
            MusicCue(
                start_s=0.0,
                end_s=round(end, 3),
                action="silence",
                mood="lecture room tone",
                reason=f"{lesson.audio.content_kind} carries no music bed; silence is the design",
            )
        ]

    # An explainer earns music in sections, not as a single bed.
    chapters = plan.chapters
    cues: list[MusicCue] = []
    longest = max(chapters, key=lambda chapter: chapter.target_seconds) if chapters else None
    for index, chapter in enumerate(chapters):
        actions = {shot.id: shot for shot in plan.shots if shot.id in chapter.shot_ids}
        purposes = {shot.purpose for shot in actions.values()}
        if index == 0:
            action, mood, reason = "enter", "a short, recognisable theme", "open the question"
        elif "summarize" in purposes or "recap" in purposes:
            action, mood, reason = "lift", "the theme returns", "close the argument"
        elif chapter is longest:
            action, mood, reason = "duck", "restrained, almost absent", "keep the reasoning bare"
        else:
            action, mood, reason = "hold", "light, unobtrusive", "support without competing"
        cues.append(
            MusicCue(
                start_s=round(chapter.start_s, 3),
                end_s=round(chapter.end_s, 3),
                action=action,  # type: ignore[arg-type]
                mood=mood,
                gain_db=-25.0 if action != "lift" else -20.0,
                reason=reason,
            )
        )
    return cues


def sfx_events(plan: DirectorPlan, design: VisualDesign | None) -> list[SfxEvent]:
    """Effects are placed on visual events, never on a fixed interval."""
    if design is None:
        return []
    events: list[SfxEvent] = []
    for item in design.shots:
        pair = SFX_BY_FAMILY.get(item.art_direction.family)
        if pair is None:
            continue
        event, source = pair
        turn = item.keyframe("turn")
        shot_start = next((shot.start_s for shot in plan.shots if shot.id == item.shot_id), 0.0)
        events.append(
            SfxEvent(
                id=f"sfx_{item.shot_id}",
                at_s=round(shot_start + turn.at_s, 3),
                event=event,
                source=source,
                trigger="visual_event",
                intensity="subtle",
                visual_ref=f"{item.shot_id}:turn",
                reason=f"the shot's turn is the only event worth hearing; the {item.art_direction.family} family carries it",
            )
        )
    return events


def ambience_cues(plan: DirectorPlan, design: VisualDesign | None) -> list[AmbienceCue]:
    if design is None:
        return []
    cues: list[AmbienceCue] = []
    for item in design.shots:
        source = AMBIENCE_BY_FAMILY.get(item.art_direction.family)
        if source is None:
            continue
        shot = next((entry for entry in plan.shots if entry.id == item.shot_id), None)
        if shot is None:
            continue
        cues.append(
            AmbienceCue(
                start_s=round(shot.start_s, 3),
                end_s=round(shot.end_s, 3),
                source=source,
                level="very_low",
                reason=(
                    f"{item.shot_id} shows a physical space, so it gets a floor, not a soundtrack; "
                    "confirm the actual room before recording it"
                ),
            )
        )
    return cues


def mix_plan(lesson: LessonConfig) -> MixPlan:
    duck = max((cue.duck_db for cue in lesson.audio.bgm), default=7.0)
    return MixPlan(bgm_duck_db=duck)


def build_sound(lesson: LessonConfig, plan: DirectorPlan, design: VisualDesign | None) -> SoundDesign:
    kind = lesson.audio.content_kind
    return SoundDesign(
        lesson_id=plan.lesson_id,
        content_kind=kind,
        style=STYLE_BY_KIND[kind],  # type: ignore[arg-type]
        voice=voice_cues(plan),
        music=music_cues(lesson, plan),
        sfx=sfx_events(plan, design),
        ambience=ambience_cues(plan, design),
        mix=mix_plan(lesson),
        checks=[],
    )


def load_visual_design(path: Path) -> VisualDesign | None:
    if not path.is_file():
        return None
    try:
        return VisualDesign.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None
