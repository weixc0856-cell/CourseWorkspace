"""Light creation for AREA / POINT / SUN / SPOT."""

from __future__ import annotations

import math

import bpy

from . import scene as scene_ops
from .cameras import aim_rotation
from .task_schema import TaskError


def _configure_data(data, spec):
    data.energy = spec["energy"]
    data.color = spec["color"]
    light_type = spec["type"]
    if light_type == "AREA":
        data.shape = spec["shape"]
        data.size = spec["size"]
        if spec["shape"] == "RECTANGLE":
            data.size_y = spec["size_y"]
    elif light_type == "POINT":
        data.shadow_soft_size = spec["size"]
    elif light_type == "SPOT":
        data.spot_size = math.radians(spec["spot_size"])
        data.spot_blend = spec["spot_blend"]
        data.shadow_soft_size = spec["size"]
    elif light_type == "SUN":
        # For SUN, `size` is the angular diameter in degrees.
        data.angle = math.radians(spec["size"])
    else:
        raise TaskError(f"unsupported light type: {light_type}")


def create_lights(specs, task_id):
    created = {}
    for spec in specs:
        name = spec["id"]
        if name in bpy.data.objects:
            raise TaskError(f"object already exists in base scene: {name}")
        data = bpy.data.lights.new(name, type=spec["type"])
        _configure_data(data, spec)
        obj = bpy.data.objects.new(name, data)
        obj.location = spec["location"]
        obj.rotation_mode = "XYZ"
        obj.rotation_euler = aim_rotation(spec["location"], spec["target"], spec["rotation"])
        obj["scene_task_id"] = task_id
        scene_ops.assign_collection(obj, spec["collection"])
        created[name] = obj
    return created
