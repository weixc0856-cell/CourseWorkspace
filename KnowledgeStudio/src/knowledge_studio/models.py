"""Data contracts for the textbook knowledge base.

Everything is page-addressed: a course can only ever cite pages that exist in
the source, and every citation carries the page hash it was built from.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SLUG_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceMeta(StrictModel):
    schema_version: int = 1
    source_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    edition: str | None = None
    publisher: str | None = None
    year: int | None = None
    isbn: str | None = None
    language: str | None = None
    kind: Literal["textbook", "paper", "report", "notes"] = "textbook"
    # A textbook is copyrighted until proven otherwise: keep it local.
    local_only: bool = True
    license_note: str = "未核实；仅本地使用，不进入仓库与公网"
    original: str
    original_sha256: str
    pdf_pages: int
    extractor: str
    extracted_at: str

    @field_validator("source_id")
    @classmethod
    def _slug(cls, value: str) -> str:
        if not SLUG_RE.match(value):
            raise ValueError("source_id must be a lowercase slug (a-z0-9, - or _)")
        return value


class FigureRecord(StrictModel):
    pdf_page: int
    kind: Literal["figure", "table", "equation"]
    label: str
    caption: str


class PageRecord(StrictModel):
    pdf_page: int
    printed_page: int | None = None
    chars: int
    sha256: str
    headings: list[str] = Field(default_factory=list)
    figures: list[FigureRecord] = Field(default_factory=list)


class TocEntry(StrictModel):
    level: int = Field(default=1, ge=1, le=6)
    title: str
    printed_page: int | None = None
    pdf_page: int | None = None


class UnitMeta(StrictModel):
    schema_version: int = 1
    unit_id: str
    title: str
    chapter: str | None = None
    pdf_pages: tuple[int, int]
    printed_pages: tuple[int, int] | None = None
    keywords: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    figure_count: int = 0

    @field_validator("pdf_pages")
    @classmethod
    def _ordered(cls, value: tuple[int, int]) -> tuple[int, int]:
        start, end = value
        if start < 1 or end < start:
            raise ValueError("pdf_pages must be 1 <= start <= end")
        return value


class Citation(StrictModel):
    ref: str
    source_id: str
    pdf_page: int
    printed_page: int | None = None
    page_sha256: str
    excerpt_sha256: str


class Excerpt(StrictModel):
    ref: str
    pdf_page: int
    printed_page: int | None = None
    unit_id: str | None = None
    score: float
    text: str


class RetrievalResult(StrictModel):
    schema_version: int = 1
    query_id: str
    query: str
    source_id: str
    created_at: str
    max_pages: int
    total_pages: int
    pages_read: int
    units: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    excerpts: list[Excerpt] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def ratio(self) -> float:
        return 0.0 if not self.total_pages else self.pages_read / self.total_pages


class ClaimRef(StrictModel):
    claim_id: str
    statement: str
    citations: list[Citation] = Field(default_factory=list)
    # A human or an explicit review pass decides; the tool never marks verified.
    verification: Literal["pending", "verified", "rejected"] = "pending"


class EvidenceFile(StrictModel):
    schema_version: int = 1
    source_id: str
    retrieval: str
    generated_at: str
    claims: list[ClaimRef] = Field(default_factory=list)
    citation_pool: list[Citation] = Field(default_factory=list)
