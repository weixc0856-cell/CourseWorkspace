"""Executable models for the shared production contracts.

`ledger`, `product` and `production-timeline` used to exist only as hand-written
JSON Schema: nothing validated them, so a typo passed silently. The models here
are the single source; `contract-schemas` exports the JSON Schema from them and
`contract-validate` checks a YAML or JSON file.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, ValidationError

from course_control.content.contracts import StrictModel


class ContractModelError(ValueError):
    pass


class Duration(StrictModel):
    target_s: float = Field(gt=0)
    # Optional but not nullable: a missing key is fine, an explicit null is not.
    min_s: float = Field(default=None, ge=0)  # type: ignore[assignment]
    max_s: float = Field(default=None, gt=0)  # type: ignore[assignment]


class Evidence(StrictModel):
    requirements: list[str] = Field(min_length=1)
    data_authority: str = None  # type: ignore[assignment]
    render_only: list[str] = Field(default_factory=list)


class Acceptance(StrictModel):
    rubric: str = Field(min_length=1)
    spec: str = None  # type: ignore[assignment]
    gates: list[str] = Field(default_factory=list)


class ProductProfile(StrictModel):
    schema_version: Literal[1]
    product: str = Field(min_length=1)
    title: str = None  # type: ignore[assignment]
    format: Literal["course", "news", "explainer"]
    time_authority: Literal["spec", "timeline", "audio"]
    duration: Duration
    visual_sources: list[str] = Field(default_factory=list)
    narration: dict[str, Any] = None  # type: ignore[assignment]
    evidence: Evidence
    acceptance: Acceptance


class LedgerRecord(StrictModel):
    asset_id: str = Field(min_length=1)
    kind: Literal["book_figure", "paper_figure", "photo", "video", "screen", "render", "schematic", "data"]
    role: Literal["render_only", "evidence", "context", "schematic", "data"]
    path: str = None  # type: ignore[assignment]
    source: str = Field(min_length=1)
    source_url: str = None  # type: ignore[assignment]
    publisher: str = None  # type: ignore[assignment]
    captured_at: datetime = None  # type: ignore[assignment]
    license: str = Field(min_length=1)
    attribution: str = None  # type: ignore[assignment]
    tags: list[str] = Field(default_factory=list)
    used_in: list[str] = Field(default_factory=list)
    notes: str = None  # type: ignore[assignment]


class Ledger(StrictModel):
    schema_version: Literal[1]
    product: str = Field(min_length=1)
    records: list[LedgerRecord]


class TimelineEntry(StrictModel):
    id: str = Field(min_length=1)
    kind: Literal["scene", "slide", "clip", "audio", "subtitle", "card"]
    source: str = None  # type: ignore[assignment]
    start_s: float = Field(ge=0)
    duration_s: float = Field(gt=0)
    in_s: float = Field(default=None, ge=0)  # type: ignore[assignment]
    out_s: float = Field(default=None, gt=0)  # type: ignore[assignment]
    renderer: str = None  # type: ignore[assignment]
    claim_ids: list[str] = Field(default_factory=list)
    asset_ids: list[str] = Field(default_factory=list)
    text: str = None  # type: ignore[assignment]


class ProductionTimeline(StrictModel):
    schema_version: Literal[1]
    product: str = Field(min_length=1)
    fps: int = Field(ge=1)
    resolution: list[int] = Field(default=None, min_length=2, max_length=2)  # type: ignore[assignment]
    duration_s: float = Field(gt=0)
    entries: list[TimelineEntry]


CONTRACTS: dict[str, type[StrictModel]] = {
    "product": ProductProfile,
    "ledger": Ledger,
    "timeline": ProductionTimeline,
}

SCHEMA_FILES = {
    "product": "product.schema.json",
    "ledger": "ledger.schema.json",
    "timeline": "production-timeline.schema.json",
}

SCHEMA_TITLES = {
    "product": "Product profile",
    "ledger": "Visual asset ledger",
    "timeline": "Production timeline (distinct from timeline-v1)",
}


def load_contract(kind: str, path: Path) -> StrictModel:
    model = CONTRACTS.get(kind)
    if model is None:
        raise ContractModelError(f"unknown contract kind {kind!r}; expected {', '.join(CONTRACTS)}")
    if not path.is_file():
        raise ContractModelError(f"contract file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ContractModelError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractModelError(f"{path}: expected a mapping at the top level")
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        lines = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"]) or "<root>"
            lines.append(f"{location}: {error['msg']}")
        raise ContractModelError(f"{path}:\n  " + "\n  ".join(lines)) from exc


def export_schemas(output: Path) -> list[Path]:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    written = []
    for kind, name in SCHEMA_FILES.items():
        target = output / name
        schema = CONTRACTS[kind].model_json_schema()
        document = {
            **schema,
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"https://courseworkspace.local/schemas/{name}",
            "title": SCHEMA_TITLES[kind],
        }
        payload = json.dumps(document, ensure_ascii=False, indent=2) + chr(10)
        target.write_text(payload, encoding="utf-8")
        written.append(target)
    return written
