"""Contracts for the director layer.

The director turns approved authoring artifacts (brief, outline, narration
script, storyboard) into one executable production plan: chapters, shots,
engine assignments, narration placement and validation findings.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ..contracts import StrictModel

HEX = r"^#[0-9A-Fa-f]{6}$"
SHOT_ID = r"^shot_[0-9]{3}$"

Engine = Literal["motion_canvas", "manim", "blender", "code_video", "remotion"]
Readiness = Literal["ready", "planned"]
Purpose = Literal["introduce", "explain", "demonstrate", "contrast", "summarize", "recap"]
Level = Literal["error", "warning", "info"]
Status = Literal["draft", "ready", "blocked"]


class DurationPlan(StrictModel):
    profile: Literal["standard", "short", "news"]
    target_seconds: float = Field(gt=0)
    min_seconds: float | None = Field(default=None, ge=0)
    max_seconds: float | None = Field(default=None, gt=0)
    planned_seconds: float = Field(gt=0)
    tolerance_seconds: float = Field(default=2.0, ge=0)


class Typography(StrictModel):
    heading_px: int = Field(ge=8, le=400)
    body_px: int = Field(ge=8, le=400)
    label_px: int = Field(ge=8, le=400)
    heading_font: str = Field(min_length=1)
    body_font: str = Field(min_length=1)


class VisualStyle(StrictModel):
    background: str = Field(pattern=HEX)
    ink: str = Field(pattern=HEX)
    muted: str = Field(pattern=HEX)
    accent: str = Field(pattern=HEX)
    warm: str = Field(pattern=HEX)
    green: str = Field(pattern=HEX)
    typography: Typography
    color_semantics: dict[str, str]
    consistency_required: bool = True

    @model_validator(mode="after")
    def _semantics_are_hex(self):
        for role, value in self.color_semantics.items():
            if not value.startswith("#") or len(value) != 7:
                raise ValueError(f"color role {role!r} must be a #RRGGBB value")
        return self


class NarrationSegmentPlan(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    shot_id: str = Field(pattern=SHOT_ID)
    page: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=1200)
    style: str | None = None
    pause_after_ms: int = Field(default=400, ge=0, le=5000)
    estimated_seconds: float = Field(gt=0)
    emphasis: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class ShotPlan(StrictModel):
    id: str = Field(pattern=SHOT_ID)
    chapter_id: str
    slide: int = Field(ge=1)
    title: str = Field(min_length=1)
    purpose: Purpose
    engine: Engine
    engine_profile: str = Field(min_length=1)
    scene: str | None = None
    blend_task: str | None = None
    asset_seconds: float | None = Field(default=None, gt=0)
    readiness: Readiness
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    cue_seconds: float = Field(ge=0)
    target_seconds: float = Field(gt=0)
    transition: Literal["cut", "continuous"]
    layout_template: str = Field(pattern=r"^[a-z][a-z0-9_]{2,40}$")
    layout_regions: dict[str, list[float]] = Field(default_factory=dict)
    shot_size: Literal["wide", "medium", "closeup"] = "medium"
    learning_intent: str = Field(min_length=1)
    visual_metaphor: str = Field(min_length=1)
    composition: str = Field(min_length=1)
    camera: str = Field(min_length=1)
    motion: list[str] = Field(min_length=1)
    on_screen_text: list[str] = Field(default_factory=list)
    narration_ids: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    direction_file: str | None = None
    notes: str = ""

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


class ChapterPlan(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    learning_objective: str = Field(min_length=1)
    target_seconds: float = Field(gt=0)
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    shot_ids: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(default_factory=list)


class ApprovalArtifact(StrictModel):
    kind: str
    path: str
    status: Literal["ok", "missing", "mismatch", "unapproved"]
    sha256: str = ""
    approved_at: str | None = None


class ApprovalState(StrictModel):
    approved: bool
    artifacts: list[ApprovalArtifact] = Field(default_factory=list)


class DirectorCheck(StrictModel):
    id: str
    rule: str
    level: Level
    message: str
    shot_id: str | None = None
    chapter_id: str | None = None


class DirectorSummary(StrictModel):
    status: Status
    errors: int = Field(default=0, ge=0)
    warnings: int = Field(default=0, ge=0)
    infos: int = Field(default=0, ge=0)
    shots: int = Field(ge=0)
    ready_shots: int = Field(ge=0)
    planned_shots: int = Field(ge=0)
    chapters: int = Field(ge=0)
    narration_segments: int = Field(ge=0)


class DirectorPlan(StrictModel):
    schema_version: Literal[1] = 1
    lesson_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    title: str = Field(min_length=1)
    status: Status
    approval: ApprovalState
    duration: DurationPlan
    style: VisualStyle
    chapters: list[ChapterPlan] = Field(min_length=1)
    shots: list[ShotPlan] = Field(min_length=1)
    narration: list[NarrationSegmentPlan] = Field(default_factory=list)
    checks: list[DirectorCheck] = Field(default_factory=list)
    summary: DirectorSummary
    generator: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _ids_unique(self):
        shots = [shot.id for shot in self.shots]
        if len(shots) != len(set(shots)):
            raise ValueError("shot ids must be unique")
        chapters = [chapter.id for chapter in self.chapters]
        if len(chapters) != len(set(chapters)):
            raise ValueError("chapter ids must be unique")
        segments = [segment.id for segment in self.narration]
        if len(segments) != len(set(segments)):
            raise ValueError("narration ids must be unique")
        return self
