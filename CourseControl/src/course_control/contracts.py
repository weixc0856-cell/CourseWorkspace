from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


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


class Storyboard(StrictModel):
    schema_version: Literal[1]
    lesson: str
    shots: list[ShotSpec] = Field(min_length=1)


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


class ShotsFile(StrictModel):
    schema_version: Literal[1] = 1
    lesson: str
    generated_at: str
    timeline: Timeline
    shots: list[Shot]
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
