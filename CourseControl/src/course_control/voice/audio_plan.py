"""Audio policy and BGM planning.

The plan is deliberately data-only: it validates BGM licence and level policy
and writes a JSON artifact.  Content kind no longer decides whether music is
allowed (D-097); it only informs the default.  Rendering/mixing stays in the
Remotion layer.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from course_control.content.contracts import BgmCue, LessonConfig, StrictModel


class AudioPlan(StrictModel):
    schema_version: Literal[1] = 1
    kind: Literal["audio_plan"] = "audio_plan"
    lesson_id: str
    content_kind: Literal["popular_science", "formal_course", "news"]
    bgm_allowed: bool
    cues: list[BgmCue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    status: Literal["ready", "blocked"] = "ready"


def build_audio_plan(lesson: LessonConfig) -> AudioPlan:
    policy = lesson.audio
    cues = list(policy.bgm)
    errors: list[str] = []
    warnings: list[str] = []
    # Music is a creative decision, not a permission.  Content kind informs the
    # default; only delivery quality (licence, level, the final mix) gates a film.
    bgm_allowed = True

    if not cues:
        warnings.append("no BGM cue configured")

    for index, cue in enumerate(cues, start=1):
        label = cue.track_id or f"cue-{index}"
        if cue.license_status == "unknown":
            errors.append(f"{label}: licence is unknown")
        if cue.license_status == "cc_by" and not cue.attribution:
            errors.append(f"{label}: CC BY requires an attribution line")
        if cue.license_status == "owner_authorized_unverified" and cue.commercial_allowed:
            errors.append(f"{label}: unverified owner authorization cannot be marked commercial_allowed")
        if cue.gain_db > -18.0:
            warnings.append(f"{label}: {cue.gain_db:.0f} dB is too loud for narration; start around -25 dB")
        if cue.duck_db > 12.0:
            warnings.append(f"{label}: {cue.duck_db:.0f} dB ducking is aggressive; 6-8 dB is the starting point")

    return AudioPlan(
        lesson_id=lesson.lesson_id,
        content_kind=policy.content_kind,
        bgm_allowed=bgm_allowed,
        cues=cues,
        warnings=warnings,
        errors=errors,
        status="blocked" if errors else "ready",
    )


def write_audio_plan(build_root: Path, lesson: LessonConfig) -> tuple[AudioPlan, Path]:
    plan = build_audio_plan(lesson)
    target = build_root / "audio" / "audio_plan.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(plan.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return plan, target
