"""Visual-direction contract for animation shots.

This is the missing design layer between a script and renderer code. It records
what the viewer should understand, the visual metaphor, composition, camera,
motion, continuity, reference standard and acceptance criteria before a scene
is written.
"""
from __future__ import annotations

from dataclasses import field as dataclass_field
from typing import Literal

from pydantic import Field

from course_control.content.contracts import StrictModel


class MotionBeat(StrictModel):
    name: str
    start_s: float = Field(ge=0)
    duration_s: float = Field(gt=0)
    easing: str = "ease_in_out"
    target: str = ""


class LabelLifecycle(StrictModel):
    label: str
    appears_s: float = Field(ge=0)
    follows: str | None = None
    disappears_s: float | None = Field(default=None, ge=0)


class ShotDirection(StrictModel):
    shot_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    learning_intent: str = Field(min_length=1)
    visual_metaphor: str = Field(min_length=1)
    composition: str = Field(min_length=1)
    focus: str = Field(min_length=1)
    camera: str = Field(min_length=1)
    shot_size: Literal["wide", "medium", "closeup"] = "medium"
    camera_anchor: str = ""
    motion: list[str] = Field(min_length=1)
    motion_beats: list[MotionBeat] = Field(default_factory=list)
    label_lifecycle: list[LabelLifecycle] = Field(default_factory=list)
    object_state: dict[str, str] = Field(default_factory=dict)
    transition: str = "continuous"
    end_state: str = ""
    continuity: str = Field(min_length=1)
    on_screen_text: list[str] = Field(default_factory=list)
    reference: str = Field(min_length=1)
    acceptance: list[str] = Field(min_length=1)

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


class AnimationDirection(StrictModel):
    schema_version: Literal[1] = 1
    lesson_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    title: str = Field(min_length=1)
    total_seconds: float = Field(gt=0)
    style: dict = Field(default_factory=dict)
    shots: list[ShotDirection] = Field(min_length=1)

    def problems(self) -> list[str]:
        issues: list[str] = []
        cursor = 0.0
        for shot in self.shots:
            if abs(shot.start_s - cursor) > 0.01:
                issues.append(f"{shot.shot_id}: starts at {shot.start_s}, expected {cursor}")
            if shot.end_s <= shot.start_s:
                issues.append(f"{shot.shot_id}: end must be after start")
            cursor = shot.end_s
        if abs(cursor - self.total_seconds) > 0.01:
            issues.append(f"shots end at {cursor}, total_seconds={self.total_seconds}")
        return issues
