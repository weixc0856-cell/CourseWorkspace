"""Pydantic contracts for environment and shot specifications."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TerrainSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heightmap: str | None = None
    size_m: float = 2400
    subdivisions: int = Field(default=300, ge=2)
    displacement_m: float = 900
    material: str
    uv_scale: float = 10
    z: float = 0
    mid_level: float = 0
    edge_falloff: float = 0


class EnvironmentSpec(BaseModel):
    """Level 2: one reusable place/set."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    kind: Literal["environment"]
    id: str
    name: str = ""
    style: str | None = None
    visual_grammar: str | None = None
    asset_root: str | None = None
    hdri: str
    world_strength: float = 1.0
    atmosphere: dict[str, Any] | None = None
    terrain: TerrainSpec
    objects: list[dict[str, Any]] = Field(default_factory=list)
    sun: dict[str, Any] | None = None
    lights: list[dict[str, Any]] = Field(default_factory=list)
    water: dict[str, Any] | None = None
    camera: dict[str, Any] | None = None
    render: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


class CameraSpec(BaseModel):
    """Camera rig.  Either explicit keyframes or a named template."""

    model_config = ConfigDict(extra="allow")

    template: str | None = None
    location: list[float] | None = None
    target: list[float] | None = None
    lens: float = 35
    fstop: float = 8
    focus_distance: float = 10
    end_location: list[float] | None = None
    end_target: list[float] | None = None
    end_lens: float | None = None
    keyframes: list[dict[str, Any]] = Field(default_factory=list)
    hold_start_s: float = 1.0
    move_s: float | None = None
    hold_end_s: float | None = None
    center: list[float] | None = None
    radius: float | None = None
    height: float | None = None
    start_angle_deg: float = 0
    end_angle_deg: float = 90
    key_count: int = Field(default=9, ge=3)

    @model_validator(mode="after")
    def _has_motion(self) -> "CameraSpec":
        if self.keyframes:
            return self
        if self.template in {"orbit"}:
            if self.center is None or self.radius is None:
                raise ValueError("orbit camera needs center and radius")
            return self
        if self.template == "tilt":
            if self.location is None or self.end_target is None:
                raise ValueError("camera template 'tilt' needs location and end_target")
            return self
        if self.template:
            if self.location is None or self.end_location is None:
                raise ValueError(f"camera template {self.template!r} needs location and end_location")
            return self
        if self.location is None:
            raise ValueError("camera needs location, keyframes or a template")
        return self


class RenderSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: Literal["blockout", "preview", "hero"] | None = None
    engine: str = "BLENDER_EEVEE"
    samples: int = Field(default=32, ge=1)
    resolution: list[int] = Field(default_factory=lambda: [1080, 1920])
    frames: int = Field(default=1, ge=1)
    fps: int = Field(default=30, ge=1)
    output: str = "render.mp4"
    passes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _resolution(self) -> "RenderSpec":
        if len(self.resolution) != 2 or min(self.resolution) < 1:
            raise ValueError("resolution must be [width, height]")
        return self


class ShotSpec(BaseModel):
    """Level 3: one camera setup that references an environment."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    kind: Literal["shot"]
    id: str
    name: str = ""
    environment: str
    beat: str | None = None
    lane: Literal["A", "B", "C"] | None = None
    visual_grammar: str | None = None
    duration_s: float | None = None
    camera: CameraSpec
    render: RenderSpec = Field(default_factory=RenderSpec)
    objects: list[dict[str, Any]] | None = None
    lights: list[dict[str, Any]] | None = None
    water: dict[str, Any] | None = None
    notes: str = ""


def load_spec(path: Path) -> EnvironmentSpec | ShotSpec:
    data = json.loads(path.read_text(encoding="utf-8"))
    kind = data.get("kind")
    if kind == "shot":
        return ShotSpec.model_validate(data)
    if kind == "environment" or "terrain" in data:
        data.setdefault("kind", "environment")
        return EnvironmentSpec.model_validate(data)
    raise ValueError("spec must declare kind: environment | shot")
