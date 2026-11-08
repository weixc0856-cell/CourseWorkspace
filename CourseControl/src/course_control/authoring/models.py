from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from ..contracts import StrictModel

SLUG_RE = r"^[a-z0-9][a-z0-9-]{1,63}$"


class SourceEntry(StrictModel):
    id: str = Field(pattern=r"^[A-Z][0-9]{1,3}$")
    kind: Literal["url", "markdown", "text"]
    origin: str
    local_path: str
    sha256: str = Field(min_length=64, max_length=64)
    title: str = ""
    fetched_at: str
    http_status: int | None = None
    extractor: str = "stdlib"


class SourcesFile(StrictModel):
    schema_version: Literal[1] = 1
    lesson: str = Field(pattern=SLUG_RE)
    sources: list[SourceEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self):
        ids = [source.id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source ids must be unique")
        return self


class DigestSection(StrictModel):
    ref: str
    source_id: str
    heading: str
    level: int = Field(ge=1, le=6)
    ordinal: int = Field(ge=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    text_sha256: str = Field(min_length=64, max_length=64)
    excerpt: str


class SourceDigest(StrictModel):
    schema_version: Literal[1] = 1
    lesson: str = Field(pattern=SLUG_RE)
    generated_at: str
    sources: list[SourceEntry] = Field(default_factory=list)
    sections: list[DigestSection] = Field(default_factory=list)


class BriefPage(StrictModel):
    page: int = Field(ge=1)
    purpose: str
    source_refs: list[str] = Field(default_factory=list)


class Brief(StrictModel):
    schema_version: Literal[1] = 1
    lesson: str = Field(pattern=SLUG_RE)
    audience: str
    objectives: list[str] = Field(min_length=1)
    prerequisites: list[str] = Field(default_factory=list)
    duration: dict[str, Any]
    scope_in: list[str] = Field(default_factory=list)
    scope_out: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    source_map: list[BriefPage] = Field(default_factory=list)
    generator: dict[str, Any] = Field(default_factory=dict)


class OutlinePage(StrictModel):
    slide: int = Field(ge=1)
    title: str
    claim: str
    target_seconds: float = Field(gt=0)
    visual: str = ""
    visual_kind: str = "diagram"
    needs_3d: bool = False
    animation: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    no_source: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _citation_or_explicit(self):
        if not self.source_refs and not self.no_source:
            raise ValueError("outline page needs source_refs or an explicit no_source reason")
        return self


class OutlineChapter(StrictModel):
    id: str
    title: str
    pages: list[OutlinePage] = Field(min_length=1)


class Outline(StrictModel):
    schema_version: Literal[1] = 1
    lesson: str = Field(pattern=SLUG_RE)
    chapters: list[OutlineChapter] = Field(min_length=1)
    totals: dict[str, Any]
    generator: dict[str, Any] = Field(default_factory=dict)

    @property
    def pages(self) -> list[OutlinePage]:
        return [page for chapter in self.chapters for page in chapter.pages]


class ScriptSegment(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    text: str = Field(min_length=1)
    style: str | None = None
    pause_after_ms: int = Field(default=400, ge=0, le=5000)
    emphasis: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)

    @field_validator("style")
    @classmethod
    def _style_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.startswith("(") or not value.endswith(")") or len(value) > 122:
            raise ValueError("style must look like '(warm, measured pace)'")
        if "(" in value[1:-1] or ")" in value[1:-1]:
            raise ValueError("style must not contain nested parentheses")
        return value

    @field_validator("text")
    @classmethod
    def _no_stage_direction(cls, value: str) -> str:
        if "[ANIMATION" in value or "逐字口播" in value:
            raise ValueError("segment text must not contain stage directions")
        return value


class ScriptPage(StrictModel):
    slide: int = Field(ge=1)
    target_seconds: float = Field(gt=0)
    source_refs: list[str] = Field(default_factory=list)
    segments: list[ScriptSegment] = Field(min_length=1)

    @model_validator(mode="after")
    def _timing_shape(self):
        ids = [segment.id for segment in self.segments]
        if len(ids) != len(set(ids)):
            raise ValueError("segment ids must be unique within a page")
        return self


class ContentPage(StrictModel):
    slide: int = Field(ge=1)
    title: str = Field(min_length=1)
    slide_markdown: str = ""
    zh_sub: str = ""
    technical_check: str = ""


class NarrationScript(StrictModel):
    schema_version: Literal[1] = 1
    lesson: str = Field(pattern=SLUG_RE)
    language: Literal["en", "zh"] = "en"
    voice: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
    pages: list[ScriptPage] = Field(min_length=1)
    generator: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _pages_cover_slides(self):
        slides = [page.slide for page in self.pages]
        if slides != list(range(1, len(slides) + 1)):
            raise ValueError("script pages must cover slides 1..N in order")
        return self


class ApprovalEntry(StrictModel):
    kind: Literal["digest", "brief", "outline", "script", "content", "subtitles"]
    path: str
    sha256: str = Field(min_length=64, max_length=64)
    approved_by: str = "human"
    approved_at: str
    task_id: str | None = None


class ApprovalFile(StrictModel):
    schema_version: Literal[1] = 1
    lesson: str = Field(pattern=SLUG_RE)
    approvals: list[ApprovalEntry] = Field(default_factory=list)

    def get(self, kind: str) -> ApprovalEntry | None:
        for entry in reversed(self.approvals):
            if entry.kind == kind:
                return entry
        return None

    def find(self, path: str) -> ApprovalEntry | None:
        for entry in reversed(self.approvals):
            if entry.path == path:
                return entry
        return None
