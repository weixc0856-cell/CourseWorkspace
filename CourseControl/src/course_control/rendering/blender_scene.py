from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from scene_expr import ExpressionError, compile_expression

from course_control.rendering.colormaps import load_colormaps
from course_control.content.paths import ContractError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$"
LESSON_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
COLLECTION_PATTERN = (
    r"^(?:ENVIRONMENT|ASSETS|ANIMATION|MATERIALS|OUTPUT)"
    r"(?:/[A-Za-z][A-Za-z0-9_-]{0,63}){0,3}$"
)

Id = Annotated[str, Field(pattern=ID_PATTERN)]
LessonSlug = Annotated[str, Field(pattern=LESSON_PATTERN)]
CollectionPath = Annotated[str, Field(pattern=COLLECTION_PATTERN)]
Vec3 = tuple[float, float, float]
Channel = Annotated[float, Field(ge=0.0, le=1.0)]
Color3 = tuple[Channel, Channel, Channel]
Color4 = tuple[Channel, Channel, Channel, Channel]

PRIMITIVE_PARAMS: dict[str, dict[str, tuple[float, float, str]]] = {
    "CUBE": {"size": (2.0, 1e-4, "number")},
    "PLANE": {"size": (2.0, 1e-4, "number")},
    "GRID": {
        "size": (2.0, 1e-4, "number"),
        "x_segments": (10, 1, "int"),
        "y_segments": (10, 1, "int"),
    },
    "UV_SPHERE": {
        "radius": (1.0, 1e-4, "number"),
        "u_segments": (32, 3, "int"),
        "v_segments": (16, 2, "int"),
    },
    "ICO_SPHERE": {"radius": (1.0, 1e-4, "number"), "subdivisions": (2, 1, "int")},
    "CYLINDER": {
        "radius": (1.0, 1e-4, "number"),
        "depth": (2.0, 1e-4, "number"),
        "vertices": (32, 3, "int"),
    },
    "CONE": {
        "radius1": (1.0, 0.0, "number"),
        "radius2": (0.0, 0.0, "number"),
        "depth": (2.0, 1e-4, "number"),
        "vertices": (32, 3, "int"),
    },
    "TORUS": {
        "major_radius": (1.0, 1e-4, "number"),
        "minor_radius": (0.25, 1e-4, "number"),
        "major_segments": (48, 3, "int"),
        "minor_segments": (12, 3, "int"),
    },
    "CIRCLE": {
        "radius": (1.0, 1e-4, "number"),
        "vertices": (32, 3, "int"),
        "fill": (True, None, "bool"),
    },
}


class SceneContractError(ValueError):
    def __init__(self, messages: list[str]):
        self.messages = messages
        super().__init__("\n".join(messages))


class Transform(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: Vec3 = (0.0, 0.0, 0.0)
    rotation: Vec3 = (0.0, 0.0, 0.0)
    scale: Vec3 = (1.0, 1.0, 1.0)

    @field_validator("location")
    @classmethod
    def _location_range(cls, value: Vec3) -> Vec3:
        if any(abs(component) > 1e6 for component in value):
            raise ValueError("location components must be within +/-1e6")
        return value

    @field_validator("rotation")
    @classmethod
    def _rotation_range(cls, value: Vec3) -> Vec3:
        if any(abs(component) > 360000 for component in value):
            raise ValueError("rotation components must be within +/-360000")
        return value

    @field_validator("scale")
    @classmethod
    def _scale_positive(cls, value: Vec3) -> Vec3:
        if any(component < 1e-6 or component > 1e4 for component in value):
            raise ValueError("scale components must be within [1e-6, 1e4]")
        return value


class PrincipledParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_color: Color4 = (0.8, 0.8, 0.8, 1.0)
    metallic: float = Field(0.0, ge=0.0, le=1.0)
    roughness: float = Field(0.5, ge=0.0, le=1.0)
    alpha: float = Field(1.0, ge=0.0, le=1.0)
    ior: float = Field(1.45, ge=1.0, le=3.0)
    emission_color: Color4 = (0.0, 0.0, 0.0, 1.0)
    emission_strength: float = Field(0.0, ge=0.0, le=1e5)
    coat_weight: float = Field(0.0, ge=0.0, le=1.0)
    coat_roughness: float = Field(0.03, ge=0.0, le=1.0)
    bump_strength: float = Field(0.0, ge=0.0, le=1.0)
    bump_distance: float = Field(0.02, ge=1e-4, le=1.0)
    bump_scale: float = Field(8.0, ge=0.1, le=1000.0)
    bump_detail: float = Field(4.0, ge=0.0, le=16.0)


class EmissionParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color: Color4 = (1.0, 1.0, 1.0, 1.0)
    strength: float = Field(1.0, ge=0.0, le=1e5)


class PrincipledMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Id
    shader: Literal["principled"]
    params: PrincipledParams = PrincipledParams()


class EmissionMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Id
    shader: Literal["emission"]
    params: EmissionParams = EmissionParams()


ATTRIBUTE_PATTERN = r"^[A-Za-z][A-Za-z0-9_]{0,63}$"
COLORMAP_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"


class AxisField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["axis"]
    axis: Literal["x", "y", "z"] = "z"
    scale: float = Field(1.0, ge=-1e6, le=1e6)
    offset: float = Field(0.0, ge=-1e6, le=1e6)


class DistanceField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["distance"]
    point: Vec3 = (0.0, 0.0, 0.0)
    scale: float = Field(1.0, ge=-1e6, le=1e6)


class NoiseField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["noise"]
    scale: float = Field(1.0, ge=0.0, le=1e6)
    seed: int = Field(0, ge=0, le=2**31 - 1)


class ExpressionField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["expression"]
    expression: str = Field(min_length=1, max_length=200)

    @field_validator("expression")
    @classmethod
    def _expression(cls, value: str) -> str:
        try:
            compile_expression(value)
        except ExpressionError as exc:
            raise ValueError(str(exc)) from exc
        return value


FieldSpec = Annotated[
    AxisField | DistanceField | NoiseField | ExpressionField,
    Field(discriminator="kind"),
]


class AttributeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=ATTRIBUTE_PATTERN)
    field: FieldSpec


class ScientificColormapParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_attribute: str = Field(pattern=ATTRIBUTE_PATTERN)
    min_value: float = Field(ge=-1e12, le=1e12)
    max_value: float = Field(ge=-1e12, le=1e12)
    units: str = Field(min_length=1, max_length=32)
    colormap: str = Field(pattern=COLORMAP_PATTERN)

    @model_validator(mode="after")
    def _range(self):
        if self.max_value <= self.min_value:
            raise ValueError("max_value must be greater than min_value")
        if not self.units.strip():
            raise ValueError("units must not be blank")
        return self


class ScientificColormapMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Id
    shader: Literal["scientific_colormap"]
    params: ScientificColormapParams


MaterialSpec = Annotated[
    PrincipledMaterial | EmissionMaterial | ScientificColormapMaterial,
    Field(discriminator="shader"),
]


class GeometryNodeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: Id
    params: dict[str, float | int | bool | str | Vec3] = Field(default_factory=dict)


class WorldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    background_color: Color4 = (0.05, 0.05, 0.05, 1.0)
    strength: float = Field(1.0, ge=0.0, le=1e5)


class SceneSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Id = "Scene"
    units: Literal["METRIC", "IMPERIAL", "NONE"] = "METRIC"
    unit_scale: float = Field(1.0, ge=1e-6, le=1e6)
    fps: int = Field(30, ge=1, le=240)
    frame_start: int = Field(1, ge=0, le=36000)
    frame_end: int = Field(1, ge=0, le=36000)
    seed: int = Field(0, ge=0, le=2**31 - 1)

    @model_validator(mode="after")
    def _frame_order(self):
        if "frame_end" not in self.model_fields_set:
            self.frame_end = self.frame_start
        if self.frame_end < self.frame_start:
            raise ValueError("frame_end must be >= frame_start")
        return self


class TextSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=512)
    size: float = Field(0.5, ge=1e-3, le=1e3)
    align_x: Literal["LEFT", "CENTER", "RIGHT"] = "LEFT"
    align_y: Literal["TOP", "CENTER", "BOTTOM"] = "BOTTOM"
    extrude: float = Field(0.0, ge=0.0, le=100.0)
    bevel_depth: float = Field(0.0, ge=0.0, le=100.0)
    space_line: float = Field(1.0, ge=0.1, le=10.0)

    @field_validator("body")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("body must not be blank")
        return value


class CurveSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: list[Vec3] = Field(min_length=2, max_length=4096)
    bevel_depth: float = Field(0.02, ge=1e-4, le=1e3)
    cyclic: bool = False

    @field_validator("points")
    @classmethod
    def _points(cls, value: list[Vec3]) -> list[Vec3]:
        for point in value:
            if any(abs(component) > 1e6 for component in point):
                raise ValueError("point components must be within +/-1e6")
        spans = [
            max(point[axis] for point in value) - min(point[axis] for point in value)
            for axis in range(3)
        ]
        if max(spans) <= 1e-6:
            raise ValueError("points must not all coincide")
        return value


class SurfaceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str = Field(min_length=1, max_length=200)
    x_range: tuple[float, float] = (-3.0, 3.0)
    y_range: tuple[float, float] = (-3.0, 3.0)
    x_segments: int = Field(60, ge=2, le=512)
    y_segments: int = Field(60, ge=2, le=512)
    z_scale: float = Field(1.0, ge=-1e6, le=1e6)
    z_offset: float = Field(0.0, ge=-1e6, le=1e6)

    @field_validator("expression")
    @classmethod
    def _expression(cls, value: str) -> str:
        try:
            compile_expression(value)
        except ExpressionError as exc:
            raise ValueError(str(exc)) from exc
        return value

    @field_validator("x_range", "y_range")
    @classmethod
    def _range(cls, value: tuple[float, float]) -> tuple[float, float]:
        if value[0] >= value[1]:
            raise ValueError("range start must be less than range end")
        if value[1] - value[0] > 1e4:
            raise ValueError("range span must be <= 1e4")
        return value


class ObjectSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Id
    type: Literal["MESH", "EMPTY", "TEXT", "CURVE", "SURFACE"] = "MESH"
    primitive: (
        Literal[
            "CUBE",
            "PLANE",
            "GRID",
            "UV_SPHERE",
            "ICO_SPHERE",
            "CYLINDER",
            "CONE",
            "TORUS",
            "CIRCLE",
        ]
        | None
    ) = None
    params: dict[str, float | int | bool] = Field(default_factory=dict)
    attributes: list[AttributeSpec] = Field(default_factory=list, max_length=8)
    text: TextSpec | None = None
    curve: CurveSpec | None = None
    surface: SurfaceSpec | None = None
    transform: Transform = Transform()
    material: Id | None = None
    collection: CollectionPath = "ASSETS/Geometry"
    smooth: bool = False
    parent: Id | None = None
    empty_size: float = Field(0.5, ge=1e-6, le=1e4)
    geometry_nodes: list[GeometryNodeEntry] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def _primitive_contract(self):
        if self.type == "EMPTY":
            if self.primitive is not None:
                raise ValueError("primitive is only valid for MESH objects")
            if self.params:
                raise ValueError("params are only valid for MESH objects")
            if self.geometry_nodes:
                raise ValueError("geometry_nodes are only valid for MESH objects")
            if self.material is not None:
                raise ValueError("material is only valid for MESH objects")
            if self.text is not None:
                raise ValueError("text is only valid for TEXT objects")
            if self.curve is not None:
                raise ValueError("curve is only valid for CURVE objects")
            if self.attributes:
                raise ValueError("attributes are only valid for MESH or SURFACE objects")
            if self.surface is not None:
                raise ValueError("surface is only valid for SURFACE objects")
            if self.smooth:
                raise ValueError("smooth is only valid for MESH objects")
            return self
        if self.type == "TEXT":
            if self.primitive is not None:
                raise ValueError("primitive is only valid for MESH objects")
            if self.params:
                raise ValueError("params are only valid for MESH objects")
            if self.geometry_nodes:
                raise ValueError("geometry_nodes are only valid for MESH objects")
            if self.curve is not None:
                raise ValueError("curve is only valid for CURVE objects")
            if self.text is None:
                raise ValueError("TEXT objects require text")
            if self.attributes:
                raise ValueError("attributes are only valid for MESH or SURFACE objects")
            if self.surface is not None:
                raise ValueError("surface is only valid for SURFACE objects")
            if self.smooth:
                raise ValueError("smooth is only valid for MESH objects")
            return self
        if self.type == "CURVE":
            if self.primitive is not None:
                raise ValueError("primitive is only valid for MESH objects")
            if self.params:
                raise ValueError("params are only valid for MESH objects")
            if self.geometry_nodes:
                raise ValueError("geometry_nodes are only valid for MESH objects")
            if self.text is not None:
                raise ValueError("text is only valid for TEXT objects")
            if self.curve is None:
                raise ValueError("CURVE objects require curve")
            if self.attributes:
                raise ValueError("attributes are only valid for MESH or SURFACE objects")
            if self.surface is not None:
                raise ValueError("surface is only valid for SURFACE objects")
            if self.smooth:
                raise ValueError("smooth is only valid for MESH objects")
            return self
        if self.type == "SURFACE":
            if self.primitive is not None:
                raise ValueError("primitive is only valid for MESH objects")
            if self.params:
                raise ValueError("params are only valid for MESH objects")
            if self.geometry_nodes:
                raise ValueError("geometry_nodes are only valid for MESH objects")
            if self.text is not None:
                raise ValueError("text is only valid for TEXT objects")
            if self.curve is not None:
                raise ValueError("curve is only valid for CURVE objects")
            if self.surface is None:
                raise ValueError("SURFACE objects require surface")
            names = [attribute.name for attribute in self.attributes]
            duplicates = sorted({name for name in names if names.count(name) > 1})
            if duplicates:
                raise ValueError(f"attribute names must be unique: {duplicates}")
            return self
        if self.surface is not None:
            raise ValueError("surface is only valid for SURFACE objects")
        if self.text is not None:
            raise ValueError("text is only valid for TEXT objects")
        if self.curve is not None:
            raise ValueError("curve is only valid for CURVE objects")
        names = [attribute.name for attribute in self.attributes]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"attribute names must be unique: {duplicates}")
        if self.primitive is None:
            raise ValueError("MESH objects require a primitive")
        table = PRIMITIVE_PARAMS[self.primitive]
        unknown = sorted(set(self.params) - set(table))
        if unknown:
            raise ValueError(
                f"unknown params for {self.primitive}: {unknown}; "
                f"expected {sorted(table)}"
            )
        normalized: dict[str, float | int | bool] = {}
        for name, (default, minimum, kind) in table.items():
            value = self.params.get(name, default)
            if kind == "bool":
                if not isinstance(value, bool):
                    raise ValueError(f"params.{name} must be a boolean")
                normalized[name] = value
                continue
            if kind == "int":
                if not isinstance(value, int) or isinstance(value, bool):
                    raise ValueError(f"params.{name} must be an integer")
                if value < minimum:
                    raise ValueError(f"params.{name} must be >= {minimum}")
                if name.endswith("_segments") or name == "vertices":
                    if value > 512:
                        raise ValueError(f"params.{name} must be <= 512")
                if name == "subdivisions" and value > 6:
                    raise ValueError("params.subdivisions must be <= 6")
            else:
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise ValueError(f"params.{name} must be a number")
                value = float(value)
                if value < minimum:
                    raise ValueError(f"params.{name} must be >= {minimum}")
            normalized[name] = value
        self.params = normalized
        return self


class DofSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    focus_distance: float = Field(5.0, ge=1e-3, le=1e6)
    f_stop: float = Field(2.8, ge=0.1, le=128.0)


class CameraSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Id
    location: Vec3 = (0.0, -6.0, 3.0)
    rotation: Vec3 | None = None
    target: Vec3 | None = None
    focal_length: float = Field(50.0, ge=1.0, le=500.0)
    sensor_width: float = Field(36.0, ge=1.0, le=200.0)
    projection: Literal["PERSPECTIVE", "ORTHO"] = "PERSPECTIVE"
    ortho_scale: float = Field(6.0, ge=1e-3, le=1e5)
    active: bool = True
    collection: CollectionPath = "ANIMATION/Cameras"
    dof: DofSpec = DofSpec()

    @model_validator(mode="after")
    def _aim(self):
        if (self.rotation is None) == (self.target is None):
            raise ValueError("exactly one of rotation or target must be set")
        return self


class LightSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Id
    type: Literal["AREA", "POINT", "SUN", "SPOT"]
    location: Vec3 = (0.0, 0.0, 5.0)
    rotation: Vec3 | None = None
    target: Vec3 | None = None
    color: Color3 = (1.0, 1.0, 1.0)
    energy: float = Field(1000.0, ge=0.0, le=1e7)
    size: float = Field(1.0, ge=1e-4, le=1e4)
    size_y: float = Field(1.0, ge=1e-4, le=1e4)
    shape: Literal["SQUARE", "RECTANGLE", "DISK"] = "SQUARE"
    spot_size: float = Field(45.0, ge=1.0, le=180.0)
    spot_blend: float = Field(0.15, ge=0.0, le=1.0)
    collection: CollectionPath = "ENVIRONMENT/Lighting"

    @model_validator(mode="after")
    def _aim(self):
        if (self.rotation is None) == (self.target is None):
            raise ValueError("exactly one of rotation or target must be set")
        return self


class Keyframe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frame: int = Field(ge=0, le=36000)
    value: float | Vec3
    interpolation: Literal["CONSTANT", "LINEAR", "BEZIER"] = "BEZIER"


class AnimationChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property: Literal["location", "rotation", "scale", "energy", "focal_length"]
    keyframes: list[Keyframe] = Field(min_length=2)

    @model_validator(mode="after")
    def _ordered(self):
        frames = [keyframe.frame for keyframe in self.keyframes]
        if any(b <= a for a, b in zip(frames, frames[1:])):
            raise ValueError("keyframe frames must be strictly increasing")
        if self.property in {"location", "rotation", "scale"}:
            for keyframe in self.keyframes:
                if not isinstance(keyframe.value, tuple):
                    raise ValueError(f"{self.property} keyframes require [x, y, z]")
                if self.property == "scale" and any(v <= 0 for v in keyframe.value):
                    raise ValueError("scale keyframes must be > 0")
        else:
            for keyframe in self.keyframes:
                if isinstance(keyframe.value, tuple):
                    raise ValueError(f"{self.property} keyframes require a scalar")
        return self


class AnimationSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: Id
    channels: list[AnimationChannel] = Field(min_length=1)


class RenderSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine: Literal["BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES", "BLENDER_WORKBENCH"] = (
        "BLENDER_EEVEE"
    )
    resolution: tuple[int, int] = (1920, 1080)
    fps: int | None = Field(None, ge=1, le=240)
    samples: int = Field(16, ge=1, le=4096)
    format: Literal["png", "mp4"] = "png"
    frame: int = Field(1, ge=0, le=36000)
    output: str
    save_blend: str | None = None
    view_transform: str | None = None
    look: str | None = None
    film_transparent: bool = False

    @field_validator("resolution")
    @classmethod
    def _resolution(cls, value: tuple[int, int]) -> tuple[int, int]:
        if any(component < 1 or component > 8192 for component in value):
            raise ValueError("resolution components must be between 1 and 8192")
        return value


class BlenderSceneTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2]
    task_id: Id
    lesson: LessonSlug
    operation: Literal["build_scene"] = "build_scene"
    scene: SceneSpec = SceneSpec()
    collections: list[CollectionPath] = Field(default_factory=list, max_length=64)
    world: WorldSpec | None = None
    materials: list[MaterialSpec] = Field(default_factory=list)
    objects: list[ObjectSpec] = Field(default_factory=list, max_length=1000)
    cameras: list[CameraSpec] = Field(default_factory=list)
    lights: list[LightSpec] = Field(default_factory=list)
    animations: list[AnimationSpec] = Field(default_factory=list)
    base_blend: str | None = None
    render: RenderSpec

    @model_validator(mode="after")
    def _scene_integrity(self):
        material_ids = [material.id for material in self.materials]
        if len(set(material_ids)) != len(material_ids):
            raise ValueError("material ids must be unique")
        names = (
            [obj.id for obj in self.objects]
            + [camera.id for camera in self.cameras]
            + [light.id for light in self.lights]
        )
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"object names must be unique: {duplicates}")

        scientific = {
            material.id: material
            for material in self.materials
            if material.shader == "scientific_colormap"
        }
        object_ids = {obj.id for obj in self.objects}
        for obj in self.objects:
            if obj.material is not None and obj.material not in material_ids:
                raise ValueError(f"{obj.id} references unknown material: {obj.material}")
            if obj.material in scientific:
                source = scientific[obj.material].params.source_attribute
                names = {attribute.name for attribute in obj.attributes}
                if source not in names:
                    raise ValueError(
                        f"{obj.id} uses scientific material {obj.material} but has no "
                        f"attribute {source}"
                    )
            if obj.parent is not None and obj.parent not in object_ids:
                raise ValueError(f"{obj.id} references unknown parent: {obj.parent}")
        self._check_parent_cycles()

        if sum(1 for camera in self.cameras if camera.active) > 1:
            raise ValueError("at most one camera may have active=true")
        if not self.cameras and self.base_blend is None:
            raise ValueError("render requires at least one camera")
        if "frame" not in self.render.model_fields_set:
            self.render.frame = self.scene.frame_start
        if self.render.fps is None:
            self.render.fps = self.scene.fps

        for animation in self.animations:
            self._check_animation(animation)
        return self

    def _check_parent_cycles(self):
        parent_of = {obj.id: obj.parent for obj in self.objects}
        for start in parent_of:
            seen = set()
            current = start
            while current is not None:
                if current in seen:
                    raise ValueError(f"parent cycle detected at object: {current}")
                seen.add(current)
                current = parent_of.get(current)

    def _check_animation(self, animation: AnimationSpec):
        targets = {obj.id: "object" for obj in self.objects}
        targets.update({camera.id: "camera" for camera in self.cameras})
        targets.update({light.id: "light" for light in self.lights})
        kind = targets.get(animation.target)
        if kind is None:
            raise ValueError(f"animation target not found: {animation.target}")
        allowed = {
            "object": {"location", "rotation", "scale"},
            "camera": {"location", "rotation", "scale", "focal_length"},
            "light": {"location", "rotation", "scale", "energy"},
        }[kind]
        seen = set()
        for channel in animation.channels:
            if channel.property not in allowed:
                raise ValueError(
                    f"{animation.target}.{channel.property} is not animatable for {kind}"
                )
            if channel.property in seen:
                raise ValueError(
                    f"duplicate animation channel: {animation.target}.{channel.property}"
                )
            seen.add(channel.property)
            for keyframe in channel.keyframes:
                if not (self.scene.frame_start <= keyframe.frame <= self.scene.frame_end):
                    raise ValueError(
                        f"{animation.target}.{channel.property} frame {keyframe.frame} "
                        "is outside the scene frame range"
                    )
                if channel.property in {"location", "rotation", "scale"}:
                    if not isinstance(keyframe.value, tuple):
                        raise ValueError(
                            f"{animation.target}.{channel.property} requires [x, y, z]"
                        )
                    if channel.property == "location" and any(
                        abs(component) > 1e6 for component in keyframe.value
                    ):
                        raise ValueError("location keyframe components must be within +/-1e6")
                    if channel.property == "rotation" and any(
                        abs(component) > 360000 for component in keyframe.value
                    ):
                        raise ValueError("rotation keyframe components must be within +/-360000")
                else:
                    if isinstance(keyframe.value, tuple):
                        raise ValueError(
                            f"{animation.target}.{channel.property} requires a scalar"
                        )
                    if channel.property == "energy" and not (
                        0.0 <= keyframe.value <= 1e7
                    ):
                        raise ValueError("energy keyframes must be within [0, 1e7]")
                    if channel.property == "focal_length" and not (
                        1.0 <= keyframe.value <= 500.0
                    ):
                        raise ValueError("focal_length keyframes must be within [1, 500]")


def _format_pydantic_error(exc: ValidationError) -> list[str]:
    messages = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "<root>"
        messages.append(f"{location}: {error['msg']}")
    return messages


def _check_output_path(value: str, lesson: str, label: str, suffix: str) -> None:
    if "\\" in value:
        raise SceneContractError([f"{label}: backslashes are not allowed; use /"])
    if value.startswith("/") or (len(value) > 1 and value[1] == ":"):
        raise SceneContractError([f"{label}: absolute paths are not allowed"])
    if ".." in value.split("/"):
        raise SceneContractError([f"{label}: '..' segments are not allowed"])
    if not value.lower().endswith(suffix):
        raise SceneContractError([f"{label}: must end with {suffix}"])
    root = f"build/{lesson}/blender/"
    if not value.startswith(root):
        raise SceneContractError([f"{label}: must be inside {root}"])


def _load_colormaps(workspace: Path) -> dict:
    try:
        return load_colormaps(workspace)
    except ContractError as exc:
        raise SceneContractError([str(exc)]) from exc


def _validate_colormaps(task: BlenderSceneTask, workspace: Path) -> list[str]:
    scientific = [
        material
        for material in task.materials
        if material.shader == "scientific_colormap"
    ]
    if not scientific:
        return []
    colormaps = _load_colormaps(workspace)
    return [
        f"{material.id}: unknown colormap {material.params.colormap}; "
        f"available: {sorted(colormaps)}"
        for material in scientific
        if material.params.colormap not in colormaps
    ]


def _validate_registry(task: BlenderSceneTask, workspace: Path) -> list[str]:
    registry_path = workspace / "BlenderStudio" / "assets" / "geometry_nodes" / "registry.json"
    if not registry_path.is_file():
        return [f"geometry nodes registry not found: {registry_path}"]
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assets = registry.get("assets", {})
    material_ids = {material.id for material in task.materials}
    errors = []
    for obj in task.objects:
        for entry in obj.geometry_nodes:
            spec = assets.get(entry.asset)
            if spec is None:
                errors.append(
                    f"{obj.id}: unknown geometry node asset {entry.asset}; "
                    f"available: {sorted(assets)}"
                )
                continue
            inputs = spec.get("inputs", {})
            unknown = sorted(set(entry.params) - set(inputs))
            if unknown:
                errors.append(f"{obj.id}/{entry.asset}: unknown inputs {unknown}")
            for name, definition in inputs.items():
                if name in entry.params:
                    value = entry.params[name]
                elif "default" in definition:
                    value = definition["default"]
                elif definition.get("required", True):
                    errors.append(f"{obj.id}/{entry.asset}: missing input {name}")
                    continue
                else:
                    continue
                value_type = definition.get("type", "float")
                if value_type == "float" and (
                    not isinstance(value, (int, float)) or isinstance(value, bool)
                ):
                    errors.append(f"{obj.id}/{entry.asset}.{name} must be a number")
                elif value_type == "int" and (
                    not isinstance(value, int) or isinstance(value, bool)
                ):
                    errors.append(f"{obj.id}/{entry.asset}.{name} must be an integer")
                elif value_type == "material" and value not in material_ids:
                    errors.append(
                        f"{obj.id}/{entry.asset}.{name} references unknown material: {value}"
                    )
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    minimum = definition.get("min")
                    maximum = definition.get("max")
                    if minimum is not None and value < minimum:
                        errors.append(f"{obj.id}/{entry.asset}.{name} must be >= {minimum}")
                    if maximum is not None and value > maximum:
                        errors.append(f"{obj.id}/{entry.asset}.{name} must be <= {maximum}")
    return errors


def validate_scene_task(
    data: dict, workspace: Path | None = None
) -> BlenderSceneTask:
    try:
        task = BlenderSceneTask.model_validate(data)
    except ValidationError as exc:
        raise SceneContractError(_format_pydantic_error(exc)) from exc

    errors = []
    _check_output_path(task.render.output, task.lesson, "render.output", f".{task.render.format}")
    if task.render.save_blend is not None:
        _check_output_path(task.render.save_blend, task.lesson, "render.save_blend", ".blend")
    if task.render.format == "png" and not (
        task.scene.frame_start <= task.render.frame <= task.scene.frame_end
    ):
        errors.append("render.frame must be inside the scene frame range")
    if task.base_blend is not None and not task.base_blend.lower().endswith(".blend"):
        errors.append("base_blend: must end with .blend")
    elif task.base_blend is not None and workspace is not None:
        if ".." in task.base_blend.replace("\\", "/").split("/"):
            errors.append("base_blend: '..' segments are not allowed")
        else:
            base_path = Path(task.base_blend)
            if not base_path.is_absolute():
                base_path = workspace / base_path
            try:
                base_path.resolve().relative_to(workspace.resolve())
            except ValueError:
                errors.append("base_blend: must be inside the workspace")
    if not task.cameras and task.base_blend is None:
        errors.append("render requires at least one camera")
    elif task.cameras and not any(camera.active for camera in task.cameras):
        # A base blend may supply the active camera; otherwise fail early.
        if task.base_blend is None:
            errors.append("render requires one camera with active=true")
    if workspace is not None:
        errors.extend(_validate_registry(task, workspace))
        errors.extend(_validate_colormaps(task, workspace))
    if errors:
        raise SceneContractError(errors)
    return task


def task_summary(task: BlenderSceneTask) -> dict:
    return {
        "task_id": task.task_id,
        "lesson": task.lesson,
        "scene": task.scene.name,
        "objects": len(task.objects),
        "text_objects": sum(1 for obj in task.objects if obj.type == "TEXT"),
        "curve_objects": sum(1 for obj in task.objects if obj.type == "CURVE"),
        "ortho_cameras": sum(1 for camera in task.cameras if camera.projection == "ORTHO"),
        "surface_objects": sum(1 for obj in task.objects if obj.type == "SURFACE"),
        "materials": len(task.materials),
        "cameras": len(task.cameras),
        "lights": len(task.lights),
        "geometry_nodes": sum(len(obj.geometry_nodes) for obj in task.objects),
        "animations": len(task.animations),
        "render": {
            "engine": task.render.engine,
            "format": task.render.format,
            "output": task.render.output,
            "save_blend": task.render.save_blend,
        },
    }
