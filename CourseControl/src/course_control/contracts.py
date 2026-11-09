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
    mode: Literal["deck", "scene", "recording"]
    base_video: str | None = None
    renderer: Literal["timeline", "legacy"] = "timeline"

    @model_validator(mode="after")
    def recording_needs_base(self):
        if self.mode == "recording" and not self.base_video:
            raise ValueError("recording mode requires compose.base_video")
        return self


class Narration(StrictModel):
    enabled: bool = False
    source: str | None = None
    timing: Literal["planned", "measured"] = "planned"
    mode: Literal["reference_only", "prompt_reference"] = "reference_only"
    style_enabled: bool = True
    text_frontend: bool = True
    speed: float = Field(default=1.0, gt=0.5, le=2.0)


class Subtitles(StrictModel):
    enabled: bool = False
    render: Literal["remotion", "burn_in"] = "remotion"
    top_language: str = "en"
    bottom_language: str = "zh-Hans"
    # Distance in pixels between the bottom of the subtitle block and the frame
    # edge.  190 was the old fixed value; lowering it frees the lower band for
    # diagrams (the block grows upward from this anchor).
    bottom_margin: int = Field(default=190, ge=0, le=400)
    # Subtitle colours are per-lesson: light text for dark simulation plates,
    # dark text for paper slides.
    text_color: str = "#111111"
    outline_color: str = "#FBFAF7"
    outline_width: int = Field(default=0, ge=0, le=6)


class DurationPolicy(StrictModel):
    """Course-level duration contract (R1-5B)."""

    profile: Literal["standard", "short", "news"] = "standard"
    target_seconds: float | None = Field(default=None, gt=0)
    min_seconds: float | None = Field(default=None, ge=0)
    max_seconds: float | None = Field(default=None, gt=0)
    page_tolerance_seconds: float = Field(default=1.5, ge=0)

    @model_validator(mode="after")
    def _window_order(self):
        if self.min_seconds is not None and self.max_seconds is not None:
            if self.min_seconds > self.max_seconds:
                raise ValueError("min_seconds must be <= max_seconds")
        if self.target_seconds is not None:
            if self.min_seconds is not None and self.min_seconds > self.target_seconds:
                raise ValueError("min_seconds must be <= target_seconds")
            if self.max_seconds is not None and self.max_seconds < self.target_seconds:
                raise ValueError("max_seconds must be >= target_seconds")
        return self


class Authoring(StrictModel):
    """Optional paths to AI-drafted, human-approved authoring artifacts."""

    sources: str | None = None
    digest: str | None = None
    brief: str | None = None
    outline: str | None = None
    script: str | None = None
    approval: str | None = None
    narrative: str | None = None


class Acceptance(StrictModel):
    notes_total_seconds: float | None = None
    duration_tolerance_seconds: float = 2.0


class BuildOptions(StrictModel):
    # Legacy switch; the Motion Canvas adapter now renders headlessly and ignores it.
    allow_manual_animation_export: bool = True
    # Fail the Manim render when runtime layout checks find overlaps/out-of-frame text.
    strict_layout: bool = False


class BgmCue(StrictModel):
    """One music bed interval; licence and level are part of the contract."""

    track_id: str = Field(min_length=1)
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    gain_db: float = Field(-25.0, ge=-60.0, le=0.0)
    duck_db: float = Field(6.0, ge=0.0, le=24.0)
    attribution: str | None = None
    license_status: Literal[
        "public_domain",
        "cc_by",
        "owner_authorized_unverified",
        "unknown",
    ] = "unknown"
    commercial_allowed: bool = False

    @model_validator(mode="after")
    def _ordered(self):
        if self.end_s <= self.start_s:
            raise ValueError("end_s must be greater than start_s")
        return self


class AudioPolicy(StrictModel):
    """Content-kind policy; formal courses and news never carry BGM."""

    content_kind: Literal["popular_science", "formal_course", "news"] = "formal_course"
    bgm: list[BgmCue] = Field(default_factory=list)


class MotionPolicy(StrictModel):
    """Slow still-image camera move for captured slides."""

    slides: Literal["static", "ken_burns"] = "ken_burns"
    scale: float = Field(default=1.05, gt=1.0, le=1.15)
    pan_percent: float = Field(default=1.2, ge=0.0, le=4.0)


class LessonConfig(StrictModel):
    schema_version: Literal[1]
    lesson_id: str
    title_en: str
    title_zh: str
    status: Literal["draft", "review", "final"]
    content: Content
    outputs: Outputs
    engines: list[Literal["motion_canvas", "manim", "blender", "code_video"]]
    compose: Compose
    narration: Narration = Narration()
    subtitles: Subtitles = Subtitles()
    acceptance: Acceptance = Acceptance()
    build: BuildOptions = BuildOptions()
    motion: MotionPolicy = MotionPolicy()
    audio: AudioPolicy = AudioPolicy()
    video_form: Literal["long", "short"] = "long"
    duration: DurationPolicy | None = None
    authoring: Authoring | None = None

    @field_validator("lesson_id")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        if not SLUG_RE.match(value):
            raise ValueError("lesson_id must be a lowercase slug")
        return value


class ShotSpec(StrictModel):
    id: str
    slide: int = Field(ge=1)
    engine: Literal["motion_canvas", "manim", "blender", "code_video"]
    scene: str
    cue_seconds: float = Field(ge=0)
    expected_duration_s: float | None = Field(default=None, gt=0)
    blend_task: str | None = None
    note: str | None = None
    engine_profile: str | None = None
    inputs: dict | None = None
    validation: dict | None = None
    formula_ids: list[str] = Field(default_factory=list)


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


class RenderArtifact(StrictModel):
    """Normalized artifact produced by an animation/composition adapter."""

    path: str
    sha256: str
    bytes: int = Field(ge=0)
    kind: Literal["video", "image", "audio", "blend", "script", "other"] = "video"
    origin: Literal["rendered", "generated", "external", "copied"] = "rendered"
    engine: str | None = None
    duration_s: float | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    fps: str | None = None
    encoder: str | None = None
    source_sha: str | None = None


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
