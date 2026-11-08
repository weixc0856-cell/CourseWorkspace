"""Contracts for the producer layer.

The producer owns the production order (what to make, with what resources),
tracks usage and stage status, assembles the delivery package, and records the
per-shot fingerprints used for incremental rebuilds.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ..contracts import StrictModel

ItemStatus = Literal["present", "partial", "blocked"]
DeliveryStatus = Literal["delivered", "awaiting_approval", "blocked"]
StateStatus = Literal["new", "planning", "blocked", "awaiting_approval", "delivered"]
ShotChange = Literal["unchanged", "redesign", "re-render", "re-narrate", "recompose"]


class ResourceLimits(StrictModel):
    max_wall_seconds: float = Field(default=14400.0, gt=0)
    max_api_cost_usd: float = Field(default=0.0, ge=0)
    max_local_model_calls: int = Field(default=0, ge=0)
    max_disk_gb: float = Field(default=20.0, gt=0)


class Authorizations(StrictModel):
    allow_network: bool = False
    allow_new_dependencies: bool = False
    allow_publish: bool = False
    allow_render: bool = True
    model_backends: list[Literal["claude_code", "local_llama", "voxcpm2", "remote"]] = Field(
        default_factory=lambda: ["claude_code", "local_llama"]
    )
    api_providers: list[str] = Field(default_factory=list)


class ProductionOrder(StrictModel):
    schema_version: Literal[1] = 1
    order_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")
    lesson_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    title: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    language: str = Field(min_length=2, max_length=16)
    target_seconds: float = Field(gt=0)
    style: dict[str, str] = Field(default_factory=dict)
    must_cover: list[str] = Field(min_length=1)
    must_not: list[str] = Field(default_factory=list)
    authorizations: Authorizations = Field(default_factory=Authorizations)
    limits: ResourceLimits = Field(default_factory=ResourceLimits)
    approved_by: str | None = None
    approved_at: str | None = None
    created_at: str
    note: str = ""


class Usage(StrictModel):
    wall_seconds: float = Field(default=0.0, ge=0)
    api_cost_usd: float = Field(default=0.0, ge=0)
    local_model_calls: int = Field(default=0, ge=0)
    disk_gb: float = Field(default=0.0, ge=0)
    updated_at: str | None = None


class ArtifactRecord(StrictModel):
    path: str
    sha256: str | None = None
    bytes: int | None = Field(default=None, ge=0)
    required: bool = True
    status: Literal["present", "missing", "not_applicable"]


class DeliveryItem(StrictModel):
    id: str = Field(pattern=r"^[0-9]{2}_[a-z0-9_]+$")
    title: str
    status: ItemStatus
    files: list[ArtifactRecord] = Field(default_factory=list)
    note: str = ""


class DeliveryManifest(StrictModel):
    schema_version: Literal[1] = 1
    lesson_id: str
    order_id: str
    generated_at: str
    status: DeliveryStatus
    items: list[DeliveryItem] = Field(min_length=1)
    missing: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _status_matches_items(self):
        all_present = all(item.status == "present" for item in self.items)
        if self.status == "delivered" and not all_present:
            raise ValueError("delivered requires every delivery item to be present")
        return self


class ShotFingerprint(StrictModel):
    shot_id: str
    slide: int = Field(ge=1)
    engine: str
    scene: str | None = None
    fingerprint: str = Field(min_length=64, max_length=64)
    content_sha256: str = Field(min_length=64, max_length=64)
    narration_sha256: str = Field(min_length=64, max_length=64)
    scene_sha256: str | None = None
    direction_sha256: str | None = None
    narration_ids: list[str] = Field(default_factory=list)


class ProductionState(StrictModel):
    schema_version: Literal[1] = 1
    lesson_id: str
    order_id: str
    status: StateStatus = "new"
    updated_at: str
    usage: Usage = Field(default_factory=Usage)
    stages: dict[str, str] = Field(default_factory=dict)
    director_plan_sha256: str | None = None
    delivery_status: DeliveryStatus | None = None
    shots: list[ShotFingerprint] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
