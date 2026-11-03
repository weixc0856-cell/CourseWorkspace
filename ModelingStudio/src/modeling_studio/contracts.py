from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

GeometryKind = Literal[
    "cuboid",
    "cylinder",
    "sphere",
    "cone",
    "torus",
    "flat_plate",
    "custom_mesh",
    "curved_surface",
    "unknown",
]

Vec3 = tuple[float, float, float]


class LooseModel(BaseModel):
    """LLM output: tolerate extra keys, normalize what we consume."""

    model_config = ConfigDict(extra="ignore")


class VisualPart(LooseModel):
    name: str = Field(min_length=1, max_length=120)
    geometry: GeometryKind = "unknown"
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    visible: bool = True
    description: str | None = None
    appearance: str | None = None
    relative_proportions: Vec3 | None = None


class VisualMaterial(LooseModel):
    name: str = Field(min_length=1, max_length=120)
    color: str = ""
    finish: str = ""
    confidence: float = Field(0.5, ge=0.0, le=1.0)


class VisualAnalysis(LooseModel):
    schema_version: Literal[1] = 1
    object: str = Field(min_length=1, max_length=160)
    summary: str = ""
    parts: list[VisualPart] = Field(min_length=1)
    spatial_relations: list[str] = Field(default_factory=list)
    materials: list[VisualMaterial] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    image_quality: str | None = None


class PlanPart(LooseModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
    name: str = Field(min_length=1, max_length=120)
    geometry: GeometryKind = "unknown"
    size: Vec3 = (0.1, 0.1, 0.1)
    location: Vec3 = (0.0, 0.0, 0.0)
    rotation: Vec3 = (0.0, 0.0, 0.0)
    material_id: str | None = None
    operations: list[str] = Field(default_factory=list)
    mesh_hint: str | None = None
    parent: str | None = None
    confidence: float = Field(0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _size_positive(self):
        if any(component <= 0 for component in self.size):
            raise ValueError("size components must be > 0")
        return self


class PlanMaterial(LooseModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
    base_color: tuple[float, float, float, float] = (0.6, 0.6, 0.6, 1.0)
    metallic: float = Field(0.0, ge=0.0, le=1.0)
    roughness: float = Field(0.5, ge=0.0, le=1.0)
    emission_color: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    emission_strength: float = Field(0.0, ge=0.0, le=100.0)

    @field_validator("base_color", "emission_color", mode="before")
    @classmethod
    def _rgba(cls, value):
        if not isinstance(value, (list, tuple)) or len(value) not in (3, 4):
            raise ValueError("color must be [r, g, b] or [r, g, b, a]")
        components = tuple(float(component) for component in value)
        return components if len(components) == 4 else (*components, 1.0)


class PlanCamera(LooseModel):
    location: Vec3 = (0.6, -0.6, 0.45)
    target: Vec3 = (0.0, 0.0, 0.1)
    focal_length: float = Field(50.0, ge=1.0, le=300.0)


class PlanLight(LooseModel):
    type: Literal["AREA", "POINT", "SUN", "SPOT"] = "AREA"
    location: Vec3 = (0.5, -0.4, 0.8)
    target: Vec3 = (0.0, 0.0, 0.1)
    energy: float = Field(150.0, ge=0.0, le=1e6)
    size: float = Field(0.6, gt=0.0, le=100.0)
    color: tuple[float, float, float] = (1.0, 1.0, 1.0)

    @field_validator("color", mode="before")
    @classmethod
    def _rgb(cls, value):
        if not isinstance(value, (list, tuple)) or len(value) not in (3, 4):
            raise ValueError("color must be [r, g, b] or [r, g, b, a]")
        return tuple(float(component) for component in value[:3])


class PlanRender(LooseModel):
    resolution: tuple[int, int] = (1280, 720)
    samples: int = Field(32, ge=1, le=512)


class ModelPlan(LooseModel):
    schema_version: Literal[1] = 1
    object_name: str = Field(min_length=1, max_length=160)
    units: Literal["METRIC"] = "METRIC"
    coordinate_system: Literal["Z_UP"] = "Z_UP"
    assumptions: list[str] = Field(default_factory=list)
    parts: list[PlanPart] = Field(min_length=1)
    materials: list[PlanMaterial] = Field(default_factory=list)
    camera: PlanCamera = PlanCamera()
    lights: list[PlanLight] = Field(default_factory=list)
    render: PlanRender = PlanRender()
    build_order: list[str] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="after")
    def _references(self):
        part_ids = [part.id for part in self.parts]
        if len(set(part_ids)) != len(part_ids):
            raise ValueError("part ids must be unique")
        materials = {material.id for material in self.materials}
        for part in self.parts:
            if part.material_id is not None and part.material_id not in materials:
                raise ValueError(f"{part.id} references unknown material {part.material_id}")
            if part.parent is not None and part.parent not in part_ids:
                raise ValueError(f"{part.id} references unknown parent {part.parent}")
        if self.build_order:
            missing = [part_id for part_id in part_ids if part_id not in self.build_order]
            if missing:
                raise ValueError(f"build_order is missing parts: {missing}")
        return self


class RevisionDifference(LooseModel):
    area: str = ""
    expected: str = ""
    observed: str = ""
    severity: Literal["high", "medium", "low"] = "medium"


class Revision(LooseModel):
    schema_version: Literal[1] = 1
    summary: str = ""
    differences: list[RevisionDifference] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    rebuild_recommended: bool = False


class ValidationCheck(BaseModel):
    id: str
    status: Literal["pass", "fail", "skipped"]
    detail: str = ""


class ValidationReport(BaseModel):
    schema_version: Literal[1] = 1
    job_id: str
    status: Literal["pass", "fail"]
    checks: list[ValidationCheck]
    files: dict[str, str] = Field(default_factory=dict)
    stats: dict[str, float | int | str | None] = Field(default_factory=dict)
