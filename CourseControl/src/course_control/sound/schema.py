"""The sound design layer: what each part of the lesson should sound like.

Picture and sound are designed together.  This layer takes the narration, the
shot list, the visual keyframes and the content-kind policy, and writes down the
five tracks separately — voice, music, effects, ambience and the mix target —
so that "add some music at the end" never happens.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from course_control.content.contracts import StrictModel

ContentKind = Literal["popular_science", "formal_course", "news"]
Delivery = Literal[
    "calm_explanatory",
    "question",
    "conclusion",
    "contrast",
    "example",
    "transition",
]
Trigger = Literal["visual_event", "narration", "transition"]
Intensity = Literal["subtle", "medium", "strong"]
Level = Literal["error", "warning", "info"]
MusicAction = Literal["enter", "hold", "duck", "lift", "leave", "silence"]
AmbienceLevel = Literal["very_low", "low", "medium"]


class VoiceCue(StrictModel):
    segment_id: str = Field(min_length=1)
    shot_id: str = Field(pattern=r"^shot_[0-9]{3}$")
    at_s: float = Field(ge=0)
    delivery: Delivery
    emphasis: list[str] = Field(default_factory=list)
    pause_after_ms: int = Field(default=400, ge=0, le=5000)
    reason: str = Field(min_length=1)


class MusicCue(StrictModel):
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    action: MusicAction
    mood: str = Field(min_length=1)
    track_id: str | None = None
    gain_db: float = Field(default=-25.0, ge=-60.0, le=0.0)
    license_status: Literal[
        "public_domain", "cc_by", "owner_authorized_unverified", "unknown", "none"
    ] = "none"
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def _ordered(self):
        if self.end_s <= self.start_s:
            raise ValueError("end_s must be greater than start_s")
        return self


class SfxEvent(StrictModel):
    id: str = Field(pattern=r"^sfx_[a-z0-9_]{1,40}$")
    at_s: float = Field(ge=0)
    event: str = Field(min_length=1)
    source: str = Field(min_length=1)
    trigger: Trigger
    intensity: Intensity = "subtle"
    visual_ref: str | None = None
    reason: str = Field(min_length=1)


class AmbienceCue(StrictModel):
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    source: str = Field(min_length=1)
    level: AmbienceLevel = "very_low"
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def _ordered(self):
        if self.end_s <= self.start_s:
            raise ValueError("end_s must be greater than start_s")
        return self


class MixPlan(StrictModel):
    loudness_lufs: float = Field(default=-16.0, ge=-30.0, le=-8.0)
    true_peak_db: float = Field(default=-1.0, ge=-6.0, le=0.0)
    narration_priority: bool = True
    bgm_duck_db: float = Field(default=7.0, ge=0.0, le=24.0)
    note: str = "starting targets, not platform rules; verify on headphones and a phone speaker"


class SoundCheck(StrictModel):
    id: str
    level: Level
    rule: str
    message: str
    at_s: float | None = None


class SoundDesign(StrictModel):
    schema_version: Literal[1] = 1
    lesson_id: str
    content_kind: ContentKind
    style: Literal["lecture", "documentary", "explainer", "news"]
    voice: list[VoiceCue] = Field(default_factory=list)
    music: list[MusicCue] = Field(default_factory=list)
    sfx: list[SfxEvent] = Field(default_factory=list)
    ambience: list[AmbienceCue] = Field(default_factory=list)
    mix: MixPlan = Field(default_factory=MixPlan)
    checks: list[SoundCheck] = Field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for item in self.checks if item.level == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for item in self.checks if item.level == "warning")

    def timeline(self) -> list[tuple[float, str, str]]:
        """Every cue as (at_s, track, description), for a readable cue sheet."""
        rows: list[tuple[float, str, str]] = []
        for cue in self.music:
            track = cue.track_id or "no track"
            rows.append((cue.start_s, "music", f"{cue.action} · {track} · {cue.mood}"))
        for event in self.sfx:
            rows.append((event.at_s, "sfx", f"{event.event} · {event.intensity}"))
        for cue in self.ambience:
            rows.append((cue.start_s, "ambience", f"{cue.source} · {cue.level}"))
        return sorted(rows, key=lambda row: (row[0], row[1]))
