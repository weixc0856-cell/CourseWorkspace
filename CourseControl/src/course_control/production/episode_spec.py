from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, field_validator, model_validator

from course_control.content.contracts import StrictModel

BEAT_TYPES = ("question", "case", "mechanism", "derivation", "evidence", "conclusion")


class SourceRef(StrictModel):
    chapter: str = Field(min_length=1)
    section: str | None = None
    figure: str | None = None
    table: str | None = None
    page: int | None = Field(default=None, ge=1)
    pdf_page: int | None = Field(default=None, ge=1)
    printed_page: int | None = Field(default=None, ge=1)
    source_edition: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _locatable(self):
        if not (self.figure or self.table or self.page or self.section):
            raise ValueError("source needs figure, table, page or section")
        return self


class Claim(StrictModel):
    # C-ids are the legacy episode-local numbering; K-ids are the book index
    # claims. One evidence table can carry either, and the index remains the
    # source for K-ids.
    id: str = Field(pattern=r"^(?:C[0-9]{2,3}|K-[A-Za-z0-9-]+)$")
    text: str = Field(min_length=1)
    source: SourceRef
    status: Literal["must_teach", "support", "cut"] = "must_teach"
    condition: str | None = None
    visual: str | None = None


class Beat(StrictModel):
    id: str = Field(min_length=1)
    type: Literal["question", "case", "mechanism", "derivation", "evidence", "conclusion"]
    seconds: float = Field(gt=0)
    claims: list[str] = Field(min_length=1)
    visual: str | None = None


class EpisodeSpec(StrictModel):
    schema_version: Literal[1] = 1
    episode: str = Field(min_length=1)
    title: str = Field(min_length=1)
    core_question: str = Field(min_length=1)
    claims: list[Claim] = Field(min_length=1)
    beats: list[Beat] = Field(min_length=1)
    target_seconds: float = Field(default=600, gt=0)
    min_seconds: float = Field(default=480, ge=0)
    max_seconds: float = Field(default=900, gt=0)
    assets: list[dict] = Field(default_factory=list)
    cut_list: list[str] = Field(default_factory=list)
    not_claimed: list[str] = Field(default_factory=list)
    voice: dict = Field(default_factory=dict)
    rights: dict = Field(default_factory=dict)

    @field_validator("claims")
    @classmethod
    def _unique_claims(cls, value: list[Claim]):
        ids = [c.id for c in value]
        if len(ids) != len(set(ids)):
            raise ValueError("claim ids must be unique")
        return value

    @model_validator(mode="after")
    def _chain(self):
        ids = {c.id for c in self.claims}
        for beat in self.beats:
            missing = [c for c in beat.claims if c not in ids]
            if missing:
                raise ValueError(f"beat {beat.id} references unknown claims: {missing}")
        taught = set()
        for beat in self.beats:
            taught.update(beat.claims)
        missing_beats = [c.id for c in self.claims if c.status == "must_teach" and c.id not in taught]
        if missing_beats:
            raise ValueError(f"must_teach claims not used by any beat: {missing_beats}")
        present = {b.type for b in self.beats}
        absent = [t for t in BEAT_TYPES if t not in present]
        if absent:
            raise ValueError(f"beats missing types: {absent}")
        if not self.cut_list:
            raise ValueError("cut_list must not be empty")
        return self

    @property
    def total_seconds(self) -> float:
        return round(sum(b.seconds for b in self.beats), 3)


class EpisodeSpecError(ValueError):
    pass


def load_episode_spec(path: Path) -> EpisodeSpec:
    if not path.is_file():
        raise EpisodeSpecError(f"episode spec not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return EpisodeSpec.model_validate(data)
    except EpisodeSpecError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise EpisodeSpecError(f"invalid episode spec {path}: {exc}") from exc
