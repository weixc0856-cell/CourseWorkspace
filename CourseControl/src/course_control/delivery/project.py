"""ProjectSpec: the one entry contract for a production project.

A project is bigger than a lesson: one book or one topic expands into many
lessons or videos.  The spec says what is being made, from which sources, under
which quality profile and resource limits.  Lessons keep their existing
``lesson.yaml``; a project without a ``project.yaml`` is synthesised from the
lesson so old courses keep working unchanged.

The model is additive.  Nothing in the build pipeline reads it yet; it exists so
the research, planning and orchestration layers can share one definition.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from course_control.content.contracts import StrictModel
from course_control.content.paths import LessonPaths
from course_control.delivery.schema import ResourceLimits
from course_control.platform.workspace_layout import lessons_root, projects_root

PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,79}$")

SourceKind = Literal[
    "book", "paper", "report", "web", "notes", "course_material"
]
Authority = Literal["primary", "secondary", "supporting"]
Mode = Literal["course", "topic_video"]
Autonomy = Literal["A0", "A1", "A2", "A3"]


class SourceRef(StrictModel):
    type: SourceKind
    uri: str = Field(min_length=1)
    authority: Authority = "primary"
    note: str | None = None


class ProjectInput(StrictModel):
    sources: list[SourceRef] = Field(default_factory=list)
    topic: str | None = None


class CountRange(StrictModel):
    target: int = Field(default=40, ge=1)
    min: int = Field(default=30, ge=1)
    max: int = Field(default=50, ge=1)

    @model_validator(mode="after")
    def _order(self):
        if not self.min <= self.target <= self.max:
            raise ValueError("lesson_count requires min <= target <= max")
        return self


class SecondsRange(StrictModel):
    min: float = Field(default=600.0, gt=0)
    max: float = Field(default=1800.0, gt=0)

    @model_validator(mode="after")
    def _order(self):
        if self.min > self.max:
            raise ValueError("lesson_seconds requires min <= max")
        return self


class CoursePlan(StrictModel):
    lesson_count: CountRange = Field(default_factory=CountRange)
    lesson_seconds: SecondsRange = Field(default_factory=SecondsRange)
    justification: str | None = None


class TopicPlan(StrictModel):
    series: Literal["auto", "single"] = "auto"
    target_seconds: float = Field(default=900.0, gt=0)


class ProductionSpec(StrictModel):
    quality_profile: Literal["premium", "standard"] = "premium"
    course: CoursePlan | None = None
    topic_video: TopicPlan | None = None


class MediaSpec(StrictModel):
    resolution: str = Field(default="1920x1080", pattern=r"^[0-9]{3,5}x[0-9]{3,5}$")
    frame_rate: int = Field(default=30, gt=0, le=120)
    video_format: Literal["mp4", "mov", "webm"] = "mp4"
    audio_format: Literal["wav", "mp3", "aac"] = "wav"
    subtitles: list[Literal["srt", "vtt"]] = Field(default_factory=lambda: ["srt"])


class DeliverySpec(StrictModel):
    include: list[str] = Field(
        default_factory=lambda: [
            "videos",
            "audio",
            "transcripts",
            "sources",
            "quality_report",
        ]
    )


class ExecutionSpec(StrictModel):
    autonomy: Autonomy = "A1"
    retry_policy: Literal["none", "fixed", "adaptive"] = "adaptive"
    delivery_policy: Literal["quality_gated", "manual"] = "quality_gated"
    limits: ResourceLimits = Field(default_factory=ResourceLimits)


class ProjectMeta(StrictModel):
    id: str
    mode: Mode
    title: str = Field(min_length=1)
    language: str = Field(default="en", min_length=2, max_length=16)
    audience: str = "unspecified"

    @model_validator(mode="after")
    def _id(self):
        if not PROJECT_ID_RE.match(self.id):
            raise ValueError("project.id must be a lowercase slug (3-80 chars)")
        return self


class ProjectSpec(StrictModel):
    schema_version: Literal[1] = 1
    project: ProjectMeta
    input: ProjectInput
    production: ProductionSpec
    media: MediaSpec = Field(default_factory=MediaSpec)
    delivery: DeliverySpec = Field(default_factory=DeliverySpec)
    execution: ExecutionSpec = Field(default_factory=ExecutionSpec)
    synthesized: bool = False

    @model_validator(mode="after")
    def _mode_requirements(self):
        mode = self.project.mode
        if mode == "course":
            if not self.input.sources:
                raise ValueError("course mode requires at least one input source")
            if self.production.course is None:
                raise ValueError("course mode requires production.course")
        if mode == "topic_video":
            if not self.input.topic:
                raise ValueError("topic_video mode requires input.topic")
            if self.production.topic_video is None:
                raise ValueError("topic_video mode requires production.topic_video")
        return self


def project_path(workspace: Path, project_id: str) -> Path:
    return projects_root(workspace) / project_id / "project.yaml"


def load_project(path: Path) -> ProjectSpec:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"project spec must be a mapping: {path}")
    return ProjectSpec.model_validate(data)


def save_project(spec: ProjectSpec, path: Path) -> Path:
    payload = spec.model_dump(mode="json", exclude_none=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return path


def find_project(workspace: Path, project_id: str) -> Path | None:
    candidate = project_path(workspace, project_id)
    return candidate if candidate.is_file() else None


def synthesize_for_lesson(workspace: Path, slug: str) -> ProjectSpec:
    """Build a spec for a lesson that predates ProjectSpec.

    The lesson contract stays the authority for that course; this spec only
    records what the project layer needs, and is marked ``synthesized`` so no
    report mistakes it for a declared project.
    """
    paths = LessonPaths.load(workspace, lessons_root(workspace) / slug)
    lesson = paths.lesson
    sources = [
        SourceRef(type="notes", uri=paths.content_path(lesson.content.notes).name)
    ]
    if lesson.authoring is not None and lesson.authoring.sources:
        sources.append(
            SourceRef(type="course_material", uri=lesson.authoring.sources, authority="supporting")
        )
    seconds = lesson.duration
    lesson_seconds = SecondsRange()
    if seconds is not None:
        lesson_seconds = SecondsRange(
            min=seconds.min_seconds or lesson_seconds.min,
            max=seconds.max_seconds or lesson_seconds.max,
        )
    spec = ProjectSpec(
        project=ProjectMeta(
            id=slug,
            mode="course",
            title=lesson.title_en,
            language="en",
            audience="unspecified",
        ),
        input=ProjectInput(sources=sources),
        production=ProductionSpec(
            course=CoursePlan(
                lesson_count=CountRange(target=1, min=1, max=1),
                lesson_seconds=lesson_seconds,
            )
        ),
        execution=ExecutionSpec(autonomy="A0"),
        synthesized=True,
    )
    return spec


__all__ = [
    "PROJECT_ID_RE",
    "ProjectSpec",
    "ProjectMeta",
    "ProjectInput",
    "SourceRef",
    "CoursePlan",
    "TopicPlan",
    "ProductionSpec",
    "MediaSpec",
    "DeliverySpec",
    "ExecutionSpec",
    "load_project",
    "save_project",
    "find_project",
    "project_path",
    "synthesize_for_lesson",
]
