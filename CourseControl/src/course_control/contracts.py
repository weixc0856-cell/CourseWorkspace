from __future__ import annotations

import re
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
Unit = Annotated[float, Field(ge=0.0, le=1.0)]


class Status(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"
    NOT_RUN = "not_run"
    NOT_APPLICABLE = "not_applicable"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Content(StrictModel):
    slides: str
    notes: str
    outline: str | None = None
    storyboard: str
    assets: str
    subtitles: str | None = None


class Outputs(StrictModel):
    fps: int = 30
    resolution: tuple[int, int] = (1920, 1080)
    slides_canvas: tuple[int, int] = (1280, 720)
    animation_canvas: tuple[int, int] = (1920, 1080)


class Compose(StrictModel):
    mode: Literal["deck", "recording"]
    base_video: str | None = None

    @model_validator(mode="after")
    def recording_needs_base(self):
        if self.mode == "recording" and not self.base_video:
            raise ValueError("recording mode requires compose.base_video")
        return self


class Narration(StrictModel):
    enabled: bool = False
    source: str | None = None


class Subtitles(StrictModel):
    enabled: bool = False


class Acceptance(StrictModel):
    notes_total_seconds: float | None = None
    duration_tolerance_seconds: float = 2.0


class BuildOptions(StrictModel):
    allow_manual_animation_export: bool = True


class LessonConfig(StrictModel):
    schema_version: Literal[1]
    lesson_id: str
    title_en: str
    title_zh: str
    status: Literal["draft", "review", "final"]
    content: Content
    outputs: Outputs
    engines: list[Literal["motion_canvas", "manim", "blender"]]
    compose: Compose
    narration: Narration = Narration()
    subtitles: Subtitles = Subtitles()
    acceptance: Acceptance = Acceptance()
    build: BuildOptions = BuildOptions()

    @field_validator("lesson_id")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        if not SLUG_RE.match(value):
            raise ValueError("lesson_id must be a lowercase slug")
        return value


class ShotSpec(StrictModel):
    id: str
    slide: int = Field(ge=1)
    engine: Literal["motion_canvas", "manim", "blender"]
    scene: str
    cue_seconds: float = Field(ge=0)
    expected_duration_s: float | None = Field(default=None, gt=0)
    blend_task: str | None = None
    note: str | None = None


class AnnotationBase(StrictModel):
    id: str
    slide: int = Field(ge=1)
    cue_seconds: float = Field(ge=0)
    duration_s: float = Field(gt=0)
    position: tuple[Unit, Unit] = (0.5, 0.1)


class TextAnnotationSpec(AnnotationBase):
    kind: Literal["text"]
    text: str = Field(min_length=1, max_length=200)
    size: float = Field(36.0, ge=8, le=200)
    align: Literal["left", "center", "right"] = "center"
    color: Literal["text", "muted", "orange", "white"] = "text"
    background: bool = False

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class LegendAnnotationSpec(AnnotationBase):
    kind: Literal["legend"]
    colormap: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    min_value: float = Field(ge=-1e12, le=1e12)
    max_value: float = Field(ge=-1e12, le=1e12)
    units: str = Field(min_length=1, max_length=32)
    bar_height: float = Field(240.0, ge=40, le=800)
    bar_width: float = Field(28.0, ge=8, le=120)
    label_size: float = Field(24.0, ge=8, le=96)

    @model_validator(mode="after")
    def _legend_range(self):
        if self.max_value <= self.min_value:
            raise ValueError("max_value must be greater than min_value")
        if not self.units.strip():
            raise ValueError("units must not be blank")
        return self


AnnotationSpec = Annotated[
    TextAnnotationSpec | LegendAnnotationSpec, Field(discriminator="kind")
]


class Storyboard(StrictModel):
    schema_version: Literal[1]
    lesson: str
    shots: list[ShotSpec] = Field(min_length=1)
    annotations: list[AnnotationSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self):
        names = [shot.id for shot in self.shots] + [item.id for item in self.annotations]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"storyboard ids must be unique: {duplicates}")
        return self


class Timeline(StrictModel):
    fps: int = Field(gt=0)
    resolution: tuple[int, int]
    total_duration_s: float = Field(gt=0)


class Shot(StrictModel):
    id: str
    kind: Literal["slide", "animation", "recording"]
    slide: int | None = None
    engine: str | None = None
    source: str
    start_s: float = Field(ge=0)
    duration_s: float = Field(gt=0)
    timeline_role: Literal["base", "overlay"]
    presentation: Literal["cutaway", "picture_in_picture", "transparent_overlay"] | None = None

    @model_validator(mode="after")
    def overlay_needs_presentation(self):
        if self.timeline_role == "overlay" and not self.presentation:
            raise ValueError("overlay shot requires presentation")
        if self.timeline_role == "base" and self.presentation is not None:
            raise ValueError("base shot must have presentation=null")
        return self


class TextAnnotation(StrictModel):
    id: str
    kind: Literal["text"]
    text: str
    start_s: float = Field(ge=0)
    duration_s: float = Field(gt=0)
    position: tuple[Unit, Unit]
    size: float = Field(ge=8, le=200)
    align: Literal["left", "center", "right"] = "center"
    color: Literal["text", "muted", "orange", "white"] = "text"
    background: bool = False


class LegendAnnotation(StrictModel):
    id: str
    kind: Literal["legend"]
    start_s: float = Field(ge=0)
    duration_s: float = Field(gt=0)
    position: tuple[Unit, Unit]
    colormap: str
    min_value: float
    max_value: float
    units: str
    stops: list[tuple[float, tuple[float, float, float]]]
    bar_height: float = Field(ge=40, le=800)
    bar_width: float = Field(ge=8, le=120)
    label_size: float = Field(ge=8, le=96)


Annotation = Annotated[
    TextAnnotation | LegendAnnotation, Field(discriminator="kind")
]


class ShotsFile(StrictModel):
    schema_version: Literal[1] = 1
    lesson: str
    generated_at: str
    timeline: Timeline
    shots: list[Shot]
    annotations: list[Annotation] = Field(default_factory=list)
    narration: dict | None = None
    subtitles: dict | None = None


class StageRecord(StrictModel):
    name: str
    status: Status
    started_at: str
    finished_at: str | None = None
    duration_ms: int = 0
    outputs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    reason: str | None = None


class CheckRecord(StrictModel):
    id: str
    status: Status
    expected: str | None = None
    actual: str | None = None
    detail: str | None = None


class Artifact(StrictModel):
    path: str
    kind: str
    size_bytes: int
    probe: dict | None = None


class BuildReport(StrictModel):
    schema_version: Literal[1] = 1
    lesson: str
    started_at: str
    finished_at: str
    toolchain: dict[str, str]
    stages: list[StageRecord]
    artifacts: list[Artifact]
    checks: list[CheckRecord]
    verdict: Literal["pass", "fail", "incomplete"]
    failures: list[str] = Field(default_factory=list)
