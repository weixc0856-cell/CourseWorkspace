"""Task IR v2 validation for BlenderStudio.

This module is intentionally dependency-free: it must run inside Blender's
bundled Python, which does not ship Pydantic or PyYAML.
"""

from __future__ import annotations

import json
import os
import re

SCHEMA_VERSION = 2

STANDARD_ROOTS = ("ENVIRONMENT", "ASSETS", "ANIMATION", "MATERIALS", "OUTPUT")
STANDARD_COLLECTIONS = (
    "ENVIRONMENT/Background",
    "ENVIRONMENT/Ground",
    "ENVIRONMENT/Lighting",
    "ASSETS/Geometry",
    "ASSETS/Imported",
    "ASSETS/Procedural",
    "ANIMATION/Objects",
    "ANIMATION/Cameras",
    "ANIMATION/Effects",
    "MATERIALS",
    "OUTPUT",
)

ENGINE_ALIASES = {
    "BLENDER_EEVEE": "BLENDER_EEVEE",
    "BLENDER_EEVEE_NEXT": "BLENDER_EEVEE",
    "CYCLES": "CYCLES",
    "BLENDER_WORKBENCH": "BLENDER_WORKBENCH",
}
ALLOWED_FORMATS = {"png", "mp4"}
UNITS = {"METRIC", "IMPERIAL", "NONE"}
SHADERS = {"principled", "emission", "scientific_colormap"}
OBJECT_TYPES = {"MESH", "EMPTY", "TEXT", "CURVE"}
CAMERA_PROJECTIONS = {"PERSPECTIVE", "ORTHO"}
TEXT_ALIGN_X = {"LEFT", "CENTER", "RIGHT"}
TEXT_ALIGN_Y = {"TOP", "CENTER", "BOTTOM"}
MAX_TEXT_LENGTH = 512
MAX_CURVE_POINTS = 4096
LIGHT_TYPES = {"AREA", "POINT", "SUN", "SPOT"}

ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
ATTRIBUTE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
COLORMAP_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SEGMENT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
LESSON_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

MAX_RESOLUTION = 8192
MAX_FRAMES = 36000
MAX_OBJECTS = 1000
MAX_SCENE_ITEMS = 2000
MAX_PATH_DEPTH = 4

# name -> (default, minimum, maximum, kind)
PRIMITIVE_PARAMS = {
    "CUBE": {"size": (2.0, 1e-4, 1e5, "number")},
    "PLANE": {"size": (2.0, 1e-4, 1e5, "number")},
    "GRID": {
        "size": (2.0, 1e-4, 1e5, "number"),
        "x_segments": (10, 1, 512, "int"),
        "y_segments": (10, 1, 512, "int"),
    },
    "UV_SPHERE": {
        "radius": (1.0, 1e-4, 1e5, "number"),
        "u_segments": (32, 3, 512, "int"),
        "v_segments": (16, 2, 512, "int"),
    },
    "ICO_SPHERE": {
        "radius": (1.0, 1e-4, 1e5, "number"),
        "subdivisions": (2, 1, 6, "int"),
    },
    "CYLINDER": {
        "radius": (1.0, 1e-4, 1e5, "number"),
        "depth": (2.0, 1e-4, 1e5, "number"),
        "vertices": (32, 3, 512, "int"),
    },
    "CONE": {
        "radius1": (1.0, 0.0, 1e5, "number"),
        "radius2": (0.0, 0.0, 1e5, "number"),
        "depth": (2.0, 1e-4, 1e5, "number"),
        "vertices": (32, 3, 512, "int"),
    },
    "TORUS": {
        "major_radius": (1.0, 1e-4, 1e5, "number"),
        "minor_radius": (0.25, 1e-4, 1e5, "number"),
        "major_segments": (48, 3, 512, "int"),
        "minor_segments": (12, 3, 512, "int"),
    },
    "CIRCLE": {
        "radius": (1.0, 1e-4, 1e5, "number"),
        "vertices": (32, 3, 512, "int"),
        "fill": (True, None, None, "bool"),
    },
}


class TaskError(ValueError):
    """A deterministic task-contract violation."""


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _require_mapping(value, path):
    if not isinstance(value, dict):
        raise TaskError(f"{path} must be an object")
    return value


def _require_list(value, path):
    if not isinstance(value, list):
        raise TaskError(f"{path} must be a list")
    return value


def _require_str(value, path, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise TaskError(f"{path} must be a non-empty string")
    return value.strip()


def _number(value, path, minimum=None, maximum=None):
    if not _is_number(value):
        raise TaskError(f"{path} must be a number")
    number = float(value)
    if minimum is not None and number < minimum:
        raise TaskError(f"{path} must be >= {minimum}")
    if maximum is not None and number > maximum:
        raise TaskError(f"{path} must be <= {maximum}")
    return number


def _integer(value, path, minimum=None, maximum=None):
    if not _is_int(value):
        raise TaskError(f"{path} must be an integer")
    if minimum is not None and value < minimum:
        raise TaskError(f"{path} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise TaskError(f"{path} must be <= {maximum}")
    return value


def _bool(value, path):
    if not isinstance(value, bool):
        raise TaskError(f"{path} must be a boolean")
    return value


def _vec(value, path, length, minimum=None, maximum=None):
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise TaskError(f"{path} must be a list of {length} numbers")
    return tuple(
        _number(item, f"{path}[{index}]", minimum, maximum)
        for index, item in enumerate(value)
    )


def _color(value, path, alpha=True):
    expected = 4 if alpha else 3
    if not isinstance(value, (list, tuple)) or len(value) != expected:
        raise TaskError(f"{path} must be a list of {expected} numbers")
    return _vec(value, path, expected, 0.0, 1.0)


def _identifier(value, path):
    text = _require_str(value, path)
    if not ID_RE.match(text):
        raise TaskError(
            f"{path} must match {ID_RE.pattern} (letters, digits, dot, dash, underscore; "
            "start with a letter)"
        )
    return text


def _attribute_name(value, path):
    text = _require_str(value, path)
    if not ATTRIBUTE_RE.match(text):
        raise TaskError(
            f"{path} must match {ATTRIBUTE_RE.pattern} (letters, digits, underscore)"
        )
    return text


def _field_spec(value, path):
    data = _require_mapping(value, path)
    kind = data.get("kind")
    if kind == "axis":
        allowed = {"kind", "axis", "scale", "offset"}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise TaskError(f"{path} has unknown fields {unknown}; expected {sorted(allowed)}")
        axis = data.get("axis", "z")
        if axis not in {"x", "y", "z"}:
            raise TaskError(f"{path}.axis must be one of ['x', 'y', 'z']")
        return {
            "kind": "axis",
            "axis": axis,
            "scale": _number(data.get("scale", 1.0), f"{path}.scale", -1e6, 1e6),
            "offset": _number(data.get("offset", 0.0), f"{path}.offset", -1e6, 1e6),
        }
    if kind == "distance":
        allowed = {"kind", "point", "scale"}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise TaskError(f"{path} has unknown fields {unknown}; expected {sorted(allowed)}")
        return {
            "kind": "distance",
            "point": _vec(data.get("point", (0.0, 0.0, 0.0)), f"{path}.point", 3, -1e6, 1e6),
            "scale": _number(data.get("scale", 1.0), f"{path}.scale", -1e6, 1e6),
        }
    if kind == "noise":
        allowed = {"kind", "scale", "seed"}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise TaskError(f"{path} has unknown fields {unknown}; expected {sorted(allowed)}")
        return {
            "kind": "noise",
            "scale": _number(data.get("scale", 1.0), f"{path}.scale", 0.0, 1e6),
            "seed": _integer(data.get("seed", 0), f"{path}.seed", 0, 2**31 - 1),
        }
    raise TaskError(f"{path}.kind must be one of ['axis', 'distance', 'noise']")


def _attributes(value, path):
    entries = _require_list(value or [], path)
    if len(entries) > 8:
        raise TaskError(f"{path} supports at most 8 attributes")
    attributes = []
    seen = set()
    for index, item in enumerate(entries):
        item_path = f"{path}[{index}]"
        data = _require_mapping(item, item_path)
        allowed = {"name", "field"}
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise TaskError(f"{item_path} has unknown fields {unknown}; expected {sorted(allowed)}")
        name = _attribute_name(data.get("name"), f"{item_path}.name")
        if name in seen:
            raise TaskError(f"{item_path}.name duplicated: {name}")
        seen.add(name)
        attributes.append(
            {
                "name": name,
                "field": _field_spec(data.get("field"), f"{item_path}.field"),
            }
        )
    return attributes


def _load_colormaps(cwd):
    path = os.path.join(cwd or os.getcwd(), "shared", "colormaps.json")
    if not os.path.isfile(path):
        raise TaskError(f"colormap library not found: {path}")
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return data.get("colormaps", {})


def _collection_path(value, path, default):
    if value is None:
        return default
    text = _require_str(value, path)
    segments = text.split("/")
    if len(segments) > MAX_PATH_DEPTH:
        raise TaskError(f"{path} depth must be <= {MAX_PATH_DEPTH}")
    for segment in segments:
        if not SEGMENT_RE.match(segment):
            raise TaskError(f"{path} has invalid collection segment: {segment!r}")
    if segments[0] not in STANDARD_ROOTS:
        raise TaskError(
            f"{path} must start with one of {sorted(STANDARD_ROOTS)}; got {segments[0]!r}"
        )
    return "/".join(segments)


def _transform(value, path):
    data = _require_mapping(value or {}, path)
    location = _vec(data.get("location", (0.0, 0.0, 0.0)), f"{path}.location", 3, -1e6, 1e6)
    rotation = _vec(data.get("rotation", (0.0, 0.0, 0.0)), f"{path}.rotation", 3, -360000.0, 360000.0)
    scale = _vec(data.get("scale", (1.0, 1.0, 1.0)), f"{path}.scale", 3, 1e-6, 1e4)
    return {"location": location, "rotation": rotation, "scale": scale}


def _rotation_or_target(data, path):
    has_rotation = data.get("rotation") is not None
    has_target = data.get("target") is not None
    if has_rotation and has_target:
        raise TaskError(f"{path} must not define both rotation and target")
    if has_target:
        return {"target": _vec(data["target"], f"{path}.target", 3, -1e6, 1e6), "rotation": None}
    if has_rotation:
        return {
            "rotation": _vec(data["rotation"], f"{path}.rotation", 3, -360000.0, 360000.0),
            "target": None,
        }
    raise TaskError(f"{path} must define either rotation (degrees) or target")


def _text_spec(value, path):
    data = _require_mapping(value, path)
    expected = (
        "align_x",
        "align_y",
        "bevel_depth",
        "body",
        "extrude",
        "size",
        "space_line",
    )
    unknown = sorted(set(data) - set(expected))
    if unknown:
        raise TaskError(f"{path} has unknown fields {unknown}; expected {list(expected)}")
    body = data.get("body")
    if not isinstance(body, str):
        raise TaskError(f"{path}.body must be a string")
    if not body.strip():
        raise TaskError(f"{path}.body must not be blank")
    if len(body) > MAX_TEXT_LENGTH:
        raise TaskError(f"{path}.body must be <= {MAX_TEXT_LENGTH} characters")
    align_x = data.get("align_x", "LEFT")
    if align_x not in TEXT_ALIGN_X:
        raise TaskError(f"{path}.align_x must be one of {sorted(TEXT_ALIGN_X)}")
    align_y = data.get("align_y", "BOTTOM")
    if align_y not in TEXT_ALIGN_Y:
        raise TaskError(f"{path}.align_y must be one of {sorted(TEXT_ALIGN_Y)}")
    return {
        "body": body,
        "size": _number(data.get("size", 0.5), f"{path}.size", 1e-3, 1e3),
        "align_x": align_x,
        "align_y": align_y,
        "extrude": _number(data.get("extrude", 0.0), f"{path}.extrude", 0.0, 100.0),
        "bevel_depth": _number(
            data.get("bevel_depth", 0.0), f"{path}.bevel_depth", 0.0, 100.0
        ),
        "space_line": _number(data.get("space_line", 1.0), f"{path}.space_line", 0.1, 10.0),
    }


def _curve_spec(value, path):
    data = _require_mapping(value, path)
    expected = ("bevel_depth", "cyclic", "points")
    unknown = sorted(set(data) - set(expected))
    if unknown:
        raise TaskError(f"{path} has unknown fields {unknown}; expected {list(expected)}")
    raw_points = _require_list(data.get("points"), f"{path}.points")
    if len(raw_points) < 2:
        raise TaskError(f"{path}.points requires at least 2 points")
    if len(raw_points) > MAX_CURVE_POINTS:
        raise TaskError(f"{path}.points supports at most {MAX_CURVE_POINTS} points")
    points = [
        _vec(point, f"{path}.points[{index}]", 3, -1e6, 1e6)
        for index, point in enumerate(raw_points)
    ]
    spans = [
        max(point[axis] for point in points) - min(point[axis] for point in points)
        for axis in range(3)
    ]
    if max(spans) <= 1e-6:
        raise TaskError(f"{path}.points must not all coincide")
    return {
        "points": points,
        "bevel_depth": _number(data.get("bevel_depth", 0.02), f"{path}.bevel_depth", 1e-4, 1e3),
        "cyclic": _bool(data.get("cyclic", False), f"{path}.cyclic"),
    }


def _path_inside(path, allowed_root, label, base=None):
    if not os.path.isabs(path):
        path = os.path.join(base or os.getcwd(), path)
    path_abs = os.path.abspath(path)
    root_abs = os.path.abspath(allowed_root)
    try:
        inside = os.path.commonpath([path_abs, root_abs]) == root_abs
    except ValueError:
        inside = False
    if not inside:
        raise TaskError(f"{label} must be inside {allowed_root}")
    return path_abs


def validate_task(task, cwd=None):
    """Validate a task IR v2 document and return a normalized copy."""
    if not isinstance(task, dict):
        raise TaskError("task must be a JSON object")
    if task.get("schema_version") != SCHEMA_VERSION:
        raise TaskError(f"schema_version must be {SCHEMA_VERSION}")

    task_id = _identifier(task.get("task_id"), "task_id")
    operation = task.get("operation", "build_scene")
    if operation != "build_scene":
        raise TaskError("operation must be 'build_scene'")

    lesson = task.get("lesson")
    if not isinstance(lesson, str) or not LESSON_RE.match(lesson):
        raise TaskError("lesson must be a slug matching ^[a-z0-9]+(?:-[a-z0-9]+)*$")

    scene_in = _require_mapping(task.get("scene", {}), "scene")
    scene_name = _require_str(scene_in.get("name", "Scene"), "scene.name")
    if not ID_RE.match(scene_name):
        raise TaskError(f"scene.name must match {ID_RE.pattern}")
    units = scene_in.get("units", "METRIC")
    if units not in UNITS:
        raise TaskError(f"scene.units must be one of {sorted(UNITS)}")
    unit_scale = _number(scene_in.get("unit_scale", 1.0), "scene.unit_scale", 1e-6, 1e6)
    fps = _integer(scene_in.get("fps", 30), "scene.fps", 1, 240)
    frame_start = _integer(scene_in.get("frame_start", 1), "scene.frame_start", 0, MAX_FRAMES)
    frame_end = _integer(scene_in.get("frame_end", frame_start), "scene.frame_end", 0, MAX_FRAMES)
    if frame_end < frame_start:
        raise TaskError("scene.frame_end must be >= scene.frame_start")
    seed = _integer(scene_in.get("seed", 0), "scene.seed", 0, 2**31 - 1)

    collections = list(STANDARD_COLLECTIONS)
    for index, value in enumerate(task.get("collections", [])):
        path = _collection_path(value, f"collections[{index}]", None)
        if path not in collections:
            collections.append(path)

    world_in = task.get("world")
    if world_in is None:
        world = None
    else:
        world_data = _require_mapping(world_in, "world")
        world = {
            "background_color": _color(
                world_data.get("background_color", (0.05, 0.05, 0.05, 1.0)),
                "world.background_color",
            ),
            "strength": _number(world_data.get("strength", 1.0), "world.strength", 0.0, 1e5),
        }

    materials = {}
    for index, item in enumerate(_require_list(task.get("materials", []), "materials")):
        path = f"materials[{index}]"
        data = _require_mapping(item, path)
        material_id = _identifier(data.get("id"), f"{path}.id")
        if material_id in materials:
            raise TaskError(f"duplicate material id: {material_id}")
        shader = data.get("shader")
        if shader not in SHADERS:
            raise TaskError(f"{path}.shader must be one of {sorted(SHADERS)}")
        params_in = _require_mapping(data.get("params", {}), f"{path}.params")
        params = {}
        if shader == "principled":
            params["base_color"] = _color(
                params_in.get("base_color", (0.8, 0.8, 0.8, 1.0)), f"{path}.params.base_color"
            )
            params["metallic"] = _number(params_in.get("metallic", 0.0), f"{path}.params.metallic", 0.0, 1.0)
            params["roughness"] = _number(params_in.get("roughness", 0.5), f"{path}.params.roughness", 0.0, 1.0)
            params["alpha"] = _number(params_in.get("alpha", 1.0), f"{path}.params.alpha", 0.0, 1.0)
            params["ior"] = _number(params_in.get("ior", 1.45), f"{path}.params.ior", 1.0, 3.0)
            params["emission_color"] = _color(
                params_in.get("emission_color", (0.0, 0.0, 0.0, 1.0)), f"{path}.params.emission_color"
            )
            params["emission_strength"] = _number(
                params_in.get("emission_strength", 0.0), f"{path}.params.emission_strength", 0.0, 1e5
            )
            params["coat_weight"] = _number(
                params_in.get("coat_weight", 0.0), f"{path}.params.coat_weight", 0.0, 1.0
            )
            params["coat_roughness"] = _number(
                params_in.get("coat_roughness", 0.03), f"{path}.params.coat_roughness", 0.0, 1.0
            )
            params["bump_strength"] = _number(
                params_in.get("bump_strength", 0.0), f"{path}.params.bump_strength", 0.0, 1.0
            )
            params["bump_distance"] = _number(
                params_in.get("bump_distance", 0.02), f"{path}.params.bump_distance", 1e-4, 1.0
            )
            params["bump_scale"] = _number(
                params_in.get("bump_scale", 8.0), f"{path}.params.bump_scale", 0.1, 1000.0
            )
            params["bump_detail"] = _number(
                params_in.get("bump_detail", 4.0), f"{path}.params.bump_detail", 0.0, 16.0
            )
        elif shader == "emission":
            params["color"] = _color(
                params_in.get("color", (1.0, 1.0, 1.0, 1.0)), f"{path}.params.color"
            )
            params["strength"] = _number(params_in.get("strength", 1.0), f"{path}.params.strength", 0.0, 1e5)
        else:
            allowed = {"source_attribute", "min_value", "max_value", "units", "colormap"}
            unknown = sorted(set(params_in) - allowed)
            if unknown:
                raise TaskError(f"{path}.params has unknown fields {unknown}")
            source = _attribute_name(
                params_in.get("source_attribute"), f"{path}.params.source_attribute"
            )
            min_value = _number(
                params_in.get("min_value"), f"{path}.params.min_value", -1e12, 1e12
            )
            max_value = _number(
                params_in.get("max_value"), f"{path}.params.max_value", -1e12, 1e12
            )
            if max_value <= min_value:
                raise TaskError(f"{path}.params.max_value must be greater than min_value")
            units_text = _require_str(params_in.get("units"), f"{path}.params.units")
            if len(units_text) > 32:
                raise TaskError(f"{path}.params.units must be <= 32 characters")
            colormap = _require_str(params_in.get("colormap"), f"{path}.params.colormap")
            if not COLORMAP_RE.match(colormap):
                raise TaskError(f"{path}.params.colormap must match {COLORMAP_RE.pattern}")
            params["source_attribute"] = source
            params["min_value"] = min_value
            params["max_value"] = max_value
            params["units"] = units_text
            params["colormap"] = colormap
        materials[material_id] = {"id": material_id, "shader": shader, "params": params}

    objects = []
    object_names = set()
    object_ids = set()
    total_items = len(materials)
    for index, item in enumerate(_require_list(task.get("objects", []), "objects")):
        path = f"objects[{index}]"
        data = _require_mapping(item, path)
        object_id = _identifier(data.get("id"), f"{path}.id")
        if object_id in object_names:
            raise TaskError(f"duplicate object name: {object_id}")
        object_names.add(object_id)
        object_ids.add(object_id)
        object_type = data.get("type", "MESH")
        if object_type not in OBJECT_TYPES:
            raise TaskError(f"{path}.type must be one of {sorted(OBJECT_TYPES)}")
        primitive = None
        params = {}
        attributes = []
        text_spec = None
        curve_spec = None
        if object_type == "MESH":
            if data.get("text") is not None:
                raise TaskError(f"{path}.text is only valid for TEXT objects")
            if data.get("curve") is not None:
                raise TaskError(f"{path}.curve is only valid for CURVE objects")
            attributes = _attributes(data.get("attributes"), f"{path}.attributes")
            primitive = data.get("primitive")
            if primitive not in PRIMITIVE_PARAMS:
                raise TaskError(f"{path}.primitive must be one of {sorted(PRIMITIVE_PARAMS)}")
            params_in = _require_mapping(data.get("params", {}), f"{path}.params")
            for key, (default, minimum, maximum, kind) in PRIMITIVE_PARAMS[primitive].items():
                value = params_in.get(key, default)
                if kind == "int":
                    params[key] = _integer(value, f"{path}.params.{key}", minimum, maximum)
                elif kind == "bool":
                    params[key] = _bool(value, f"{path}.params.{key}")
                else:
                    params[key] = _number(value, f"{path}.params.{key}", minimum, maximum)
        elif object_type == "TEXT":
            if data.get("primitive") is not None:
                raise TaskError(f"{path}.primitive is only valid for MESH objects")
            if data.get("params"):
                raise TaskError(f"{path}.params is only valid for MESH objects")
            if data.get("curve") is not None:
                raise TaskError(f"{path}.curve is only valid for CURVE objects")
            if data.get("attributes"):
                raise TaskError(f"{path}.attributes is only valid for MESH objects")
            if data.get("text") is None:
                raise TaskError(f"{path}.text is required for TEXT objects")
            if _bool(data.get("smooth", False), f"{path}.smooth"):
                raise TaskError(f"{path}.smooth is only valid for MESH objects")
            text_spec = _text_spec(data.get("text"), f"{path}.text")
        elif object_type == "CURVE":
            if data.get("primitive") is not None:
                raise TaskError(f"{path}.primitive is only valid for MESH objects")
            if data.get("params"):
                raise TaskError(f"{path}.params is only valid for MESH objects")
            if data.get("text") is not None:
                raise TaskError(f"{path}.text is only valid for TEXT objects")
            if data.get("attributes"):
                raise TaskError(f"{path}.attributes is only valid for MESH objects")
            if data.get("curve") is None:
                raise TaskError(f"{path}.curve is required for CURVE objects")
            if _bool(data.get("smooth", False), f"{path}.smooth"):
                raise TaskError(f"{path}.smooth is only valid for MESH objects")
            curve_spec = _curve_spec(data.get("curve"), f"{path}.curve")
        else:
            if data.get("primitive") is not None:
                raise TaskError(f"{path}.primitive is only valid for MESH objects")
            if data.get("params"):
                raise TaskError(f"{path}.params is only valid for MESH objects")
            if data.get("material") is not None:
                raise TaskError(f"{path}.material is only valid for MESH objects")
            if data.get("text") is not None:
                raise TaskError(f"{path}.text is only valid for TEXT objects")
            if data.get("curve") is not None:
                raise TaskError(f"{path}.curve is only valid for CURVE objects")
            if data.get("attributes"):
                raise TaskError(f"{path}.attributes is only valid for MESH objects")
            if _bool(data.get("smooth", False), f"{path}.smooth"):
                raise TaskError(f"{path}.smooth is only valid for MESH objects")
        material_id = data.get("material")
        if material_id is not None:
            material_id = _identifier(material_id, f"{path}.material")
            if material_id not in materials:
                raise TaskError(f"{path}.material references unknown material: {material_id}")
        parent = data.get("parent")
        if parent is not None:
            parent = _identifier(parent, f"{path}.parent")
            if parent == object_id:
                raise TaskError(f"{path}.parent must not reference itself")
        geometry_nodes = []
        for gn_index, entry in enumerate(
            _require_list(data.get("geometry_nodes", []), f"{path}.geometry_nodes")
        ):
            gn_path = f"{path}.geometry_nodes[{gn_index}]"
            if object_type != "MESH":
                raise TaskError(f"{gn_path} is only valid for MESH objects")
            gn_data = _require_mapping(entry, gn_path)
            asset_id = _identifier(gn_data.get("asset"), f"{gn_path}.asset")
            params_in = _require_mapping(gn_data.get("params", {}), f"{gn_path}.params")
            gn_params = {}
            for name, value in params_in.items():
                if not isinstance(name, str) or not name:
                    raise TaskError(f"{gn_path}.params keys must be non-empty strings")
                if isinstance(value, bool) or _is_number(value):
                    gn_params[name] = value
                elif isinstance(value, str) and value:
                    gn_params[name] = value
                elif isinstance(value, (list, tuple)) and len(value) == 3:
                    gn_params[name] = _vec(value, f"{gn_path}.params.{name}", 3)
                else:
                    raise TaskError(
                        f"{gn_path}.params.{name} must be a number, boolean, string, or [x, y, z]"
                    )
            geometry_nodes.append({"asset": asset_id, "params": gn_params})
        if len(geometry_nodes) > 8:
            raise TaskError(f"{path}.geometry_nodes supports at most 8 modifiers")
        objects.append(
            {
                "id": object_id,
                "type": object_type,
                "primitive": primitive,
                "params": params,
                "attributes": attributes,
                "text": text_spec,
                "curve": curve_spec,
                "transform": _transform(data.get("transform"), f"{path}.transform"),
                "material": material_id,
                "collection": _collection_path(
                    data.get("collection"), f"{path}.collection", "ASSETS/Geometry"
                ),
                "smooth": _bool(data.get("smooth", False), f"{path}.smooth"),
                "parent": parent,
                "empty_size": _number(
                    data.get("empty_size", 0.5), f"{path}.empty_size", 1e-6, 1e4
                ),
                "geometry_nodes": geometry_nodes,
            }
        )
    total_items += len(objects)

    for obj in objects:
        if obj["parent"] is not None and obj["parent"] not in object_ids:
            raise TaskError(f"object {obj['id']} references unknown parent: {obj['parent']}")
    _check_parent_cycles(objects)

    scientific_sources = {
        material_id: spec["params"]["source_attribute"]
        for material_id, spec in materials.items()
        if spec["shader"] == "scientific_colormap"
    }
    for obj in objects:
        source = scientific_sources.get(obj["material"])
        if source is not None:
            names = {attribute["name"] for attribute in obj["attributes"]}
            if source not in names:
                raise TaskError(
                    f"object {obj['id']} uses scientific material {obj['material']} "
                    f"but has no attribute {source}"
                )
    if scientific_sources:
        colormaps = _load_colormaps(cwd)
        for material_id, spec in materials.items():
            if spec["shader"] != "scientific_colormap":
                continue
            name = spec["params"]["colormap"]
            if name not in colormaps:
                raise TaskError(
                    f"{material_id}: unknown colormap {name}; available: {sorted(colormaps)}"
                )

    cameras = []
    active_cameras = 0
    for index, item in enumerate(_require_list(task.get("cameras", []), "cameras")):
        path = f"cameras[{index}]"
        data = _require_mapping(item, path)
        camera_id = _identifier(data.get("id"), f"{path}.id")
        if camera_id in object_names:
            raise TaskError(f"duplicate object name: {camera_id}")
        object_names.add(camera_id)
        location = _vec(data.get("location", (0.0, -6.0, 3.0)), f"{path}.location", 3, -1e6, 1e6)
        aim = _rotation_or_target(data, path)
        dof_in = data.get("dof") or {}
        dof_data = _require_mapping(dof_in, f"{path}.dof")
        active = _bool(data.get("active", True), f"{path}.active")
        active_cameras += 1 if active else 0
        projection = data.get("projection", "PERSPECTIVE")
        if projection not in CAMERA_PROJECTIONS:
            raise TaskError(f"{path}.projection must be one of {sorted(CAMERA_PROJECTIONS)}")
        cameras.append(
            {
                "id": camera_id,
                "location": location,
                "rotation": aim["rotation"],
                "target": aim["target"],
                "focal_length": _number(
                    data.get("focal_length", 50.0), f"{path}.focal_length", 1.0, 500.0
                ),
                "sensor_width": _number(
                    data.get("sensor_width", 36.0), f"{path}.sensor_width", 1.0, 200.0
                ),
                "projection": projection,
                "ortho_scale": _number(
                    data.get("ortho_scale", 6.0), f"{path}.ortho_scale", 1e-3, 1e5
                ),
                "active": active,
                "collection": _collection_path(
                    data.get("collection"), f"{path}.collection", "ANIMATION/Cameras"
                ),
                "dof": {
                    "enabled": _bool(dof_data.get("enabled", False), f"{path}.dof.enabled"),
                    "focus_distance": _number(
                        dof_data.get("focus_distance", 5.0), f"{path}.dof.focus_distance", 1e-3, 1e6
                    ),
                    "f_stop": _number(dof_data.get("f_stop", 2.8), f"{path}.dof.f_stop", 0.1, 128.0),
                },
            }
        )
    total_items += len(cameras)

    lights = []
    for index, item in enumerate(_require_list(task.get("lights", []), "lights")):
        path = f"lights[{index}]"
        data = _require_mapping(item, path)
        light_id = _identifier(data.get("id"), f"{path}.id")
        if light_id in object_names:
            raise TaskError(f"duplicate object name: {light_id}")
        object_names.add(light_id)
        light_type = data.get("type")
        if light_type not in LIGHT_TYPES:
            raise TaskError(f"{path}.type must be one of {sorted(LIGHT_TYPES)}")
        aim = _rotation_or_target(data, path)
        light = {
            "id": light_id,
            "type": light_type,
            "location": _vec(data.get("location", (0.0, 0.0, 5.0)), f"{path}.location", 3, -1e6, 1e6),
            "rotation": aim["rotation"],
            "target": aim["target"],
            "color": _color(data.get("color", (1.0, 1.0, 1.0)), f"{path}.color", alpha=False),
            "energy": _number(data.get("energy", 1000.0), f"{path}.energy", 0.0, 1e7),
            "size": _number(data.get("size", 1.0), f"{path}.size", 1e-4, 1e4),
            "size_y": _number(data.get("size_y", 1.0), f"{path}.size_y", 1e-4, 1e4),
            "shape": data.get("shape", "SQUARE"),
            "spot_size": _number(data.get("spot_size", 45.0), f"{path}.spot_size", 1.0, 180.0),
            "spot_blend": _number(data.get("spot_blend", 0.15), f"{path}.spot_blend", 0.0, 1.0),
            "collection": _collection_path(
                data.get("collection"), f"{path}.collection", "ENVIRONMENT/Lighting"
            ),
        }
        if light["shape"] not in {"SQUARE", "RECTANGLE", "DISK"}:
            raise TaskError(f"{path}.shape must be one of ['SQUARE', 'RECTANGLE', 'DISK']")
        lights.append(light)
    total_items += len(lights)

    target_kinds = {obj["id"]: "object" for obj in objects}
    target_kinds.update({camera["id"]: "camera" for camera in cameras})
    target_kinds.update({light["id"]: "light" for light in lights})
    animatable = {
        "object": {"location", "rotation", "scale"},
        "camera": {"location", "rotation", "scale", "focal_length"},
        "light": {"location", "rotation", "scale", "energy"},
    }
    animations = []
    seen_animation_channels = set()
    for index, item in enumerate(_require_list(task.get("animations", []), "animations")):
        path = f"animations[{index}]"
        data = _require_mapping(item, path)
        target = _identifier(data.get("target"), f"{path}.target")
        if target not in target_kinds:
            raise TaskError(f"{path}.target references unknown scene item: {target}")
        kind = target_kinds[target]
        channels = []
        seen_properties = set()
        for channel_index, channel in enumerate(
            _require_list(data.get("channels"), f"{path}.channels")
        ):
            channel_path = f"{path}.channels[{channel_index}]"
            channel_data = _require_mapping(channel, channel_path)
            prop = _require_str(channel_data.get("property"), f"{channel_path}.property")
            if prop not in animatable[kind]:
                raise TaskError(
                    f"{channel_path}.property must be one of {sorted(animatable[kind])} "
                    f"for {kind} targets"
                )
            if prop in seen_properties:
                raise TaskError(f"{channel_path}.property duplicated: {prop}")
            seen_properties.add(prop)
            key = (target, prop)
            if key in seen_animation_channels:
                raise TaskError(f"animation channel is defined twice for {target}.{prop}")
            seen_animation_channels.add(key)

            keyframes = []
            previous_frame = None
            for frame_index, keyframe in enumerate(
                _require_list(channel_data.get("keyframes"), f"{channel_path}.keyframes")
            ):
                frame_path = f"{channel_path}.keyframes[{frame_index}]"
                frame_data = _require_mapping(keyframe, frame_path)
                frame = _integer(frame_data.get("frame"), f"{frame_path}.frame", 0, MAX_FRAMES)
                if not (frame_start <= frame <= frame_end):
                    raise TaskError(
                        f"{frame_path}.frame must be inside scene frame range "
                        f"{frame_start}..{frame_end}"
                    )
                if previous_frame is not None and frame <= previous_frame:
                    raise TaskError(f"{frame_path}.frame must be strictly increasing")
                previous_frame = frame
                raw = frame_data.get("value")
                if prop in {"location", "rotation", "scale"}:
                    if prop == "rotation":
                        value = _vec(raw, f"{frame_path}.value", 3, -360000.0, 360000.0)
                    elif prop == "scale":
                        value = _vec(raw, f"{frame_path}.value", 3, 1e-6, 1e4)
                    else:
                        value = _vec(raw, f"{frame_path}.value", 3, -1e6, 1e6)
                elif prop == "energy":
                    value = _number(raw, f"{frame_path}.value", 0.0, 1e7)
                elif prop == "focal_length":
                    value = _number(raw, f"{frame_path}.value", 1.0, 500.0)
                else:  # pragma: no cover - guarded above
                    raise TaskError(f"{frame_path}.property is not animatable")
                interpolation = keyframe.get("interpolation", "BEZIER")
                if interpolation not in {"CONSTANT", "LINEAR", "BEZIER"}:
                    raise TaskError(
                        f"{frame_path}.interpolation must be CONSTANT, LINEAR, or BEZIER"
                    )
                keyframes.append(
                    {"frame": frame, "value": value, "interpolation": interpolation}
                )
            if len(keyframes) < 2:
                raise TaskError(f"{channel_path}.keyframes requires at least 2 keyframes")
            channels.append({"property": prop, "keyframes": keyframes})
        if not channels:
            raise TaskError(f"{path}.channels must not be empty")
        animations.append({"target": target, "channels": channels})

    if len(animations) > 200:
        raise TaskError("animations supports at most 200 targets")

    if total_items > MAX_SCENE_ITEMS:
        raise TaskError(f"scene has {total_items} items; limit is {MAX_SCENE_ITEMS}")
    if len(objects) > MAX_OBJECTS:
        raise TaskError(f"scene has {len(objects)} objects; limit is {MAX_OBJECTS}")

    base_blend = task.get("base_blend")
    if base_blend is not None:
        base_blend = _require_str(base_blend, "base_blend")
        if not base_blend.lower().endswith(".blend"):
            raise TaskError("base_blend must end with .blend")
        base_abs = (
            base_blend
            if os.path.isabs(base_blend)
            else os.path.join(cwd or os.getcwd(), base_blend)
        )
        workspace_root = os.path.abspath(cwd or os.getcwd())
        try:
            inside = os.path.commonpath([os.path.abspath(base_abs), workspace_root]) == workspace_root
        except ValueError:
            inside = False
        if not inside:
            raise TaskError("base_blend must be inside the workspace")
        # Existence is an execution precondition (scene.open_base_blend), not a
        # contract error: base files may be produced by an earlier task.

    render_in = _require_mapping(task.get("render"), "render")
    engine = render_in.get("engine", "BLENDER_EEVEE")
    if engine not in ENGINE_ALIASES:
        raise TaskError(f"render.engine must be one of {sorted(ENGINE_ALIASES)}")
    resolution = _vec(render_in.get("resolution", (1920, 1080)), "render.resolution", 2, 1, MAX_RESOLUTION)
    width, height = (int(value) for value in resolution)
    if float(width) != resolution[0] or float(height) != resolution[1]:
        raise TaskError("render.resolution must contain integers")
    render_fps = _integer(render_in.get("fps", fps), "render.fps", 1, 240)
    samples = _integer(render_in.get("samples", 16), "render.samples", 1, 4096)
    fmt = render_in.get("format", "png")
    if not isinstance(fmt, str) or fmt.lower() not in ALLOWED_FORMATS:
        raise TaskError(f"render.format must be one of {sorted(ALLOWED_FORMATS)}")
    fmt = fmt.lower()
    frame = _integer(render_in.get("frame", frame_start), "render.frame", 0, MAX_FRAMES)
    if fmt == "png" and not (frame_start <= frame <= frame_end):
        raise TaskError("render.frame must be inside scene.frame_start..scene.frame_end")
    if not cameras and base_blend is None:
        raise TaskError("render requires at least one camera")
    if active_cameras > 1:
        raise TaskError("at most one camera may have active=true")

    output = _require_str(render_in.get("output"), "render.output")
    expected_suffix = "." + fmt
    if not output.lower().endswith(expected_suffix):
        raise TaskError(f"render.output must end with {expected_suffix}")
    lesson_root = os.path.join(cwd or os.getcwd(), "build", lesson, "blender")
    output_abs = _path_inside(output, lesson_root, "render.output", base=cwd)

    save_blend = render_in.get("save_blend")
    if save_blend is not None:
        save_blend = _require_str(save_blend, "render.save_blend")
        if not save_blend.lower().endswith(".blend"):
            raise TaskError("render.save_blend must end with .blend")
        save_blend = _path_inside(save_blend, lesson_root, "render.save_blend", base=cwd)

    view_transform = render_in.get("view_transform")
    if view_transform is not None:
        view_transform = _require_str(view_transform, "render.view_transform")
    look = render_in.get("look")
    if look is not None:
        look = _require_str(look, "render.look")

    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "lesson": lesson,
        "operation": operation,
        "scene": {
            "name": scene_name,
            "units": units,
            "unit_scale": unit_scale,
            "fps": fps,
            "frame_start": frame_start,
            "frame_end": frame_end,
            "seed": seed,
        },
        "collections": collections,
        "world": world,
        "materials": materials,
        "objects": objects,
        "cameras": cameras,
        "lights": lights,
        "animations": animations,
        "base_blend": base_blend,
        "render": {
            "engine": ENGINE_ALIASES[engine],
            "resolution": (width, height),
            "fps": render_fps,
            "samples": samples,
            "format": fmt,
            "frame": frame,
            "output": output_abs,
            "save_blend": save_blend,
            "view_transform": view_transform,
            "look": look,
            "film_transparent": _bool(render_in.get("film_transparent", False), "render.film_transparent"),
        },
    }


def _check_parent_cycles(objects):
    parent_of = {obj["id"]: obj["parent"] for obj in objects}
    for start in parent_of:
        seen = set()
        current = start
        while current is not None:
            if current in seen:
                raise TaskError(f"parent cycle detected at object: {current}")
            seen.add(current)
            current = parent_of.get(current)
