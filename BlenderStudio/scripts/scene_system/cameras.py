"""Camera creation with look-at aiming and depth of field."""

from __future__ import annotations

import math

import bpy
from mathutils import Vector

from . import scene as scene_ops
from .task_schema import TaskError


def aim_rotation(location, target=None, rotation=None):
    if target is not None:
        direction = Vector(target) - Vector(location)
        if direction.length < 1e-9:
            raise TaskError("camera/light target must differ from its location")
        return direction.to_track_quat("-Z", "Y").to_euler()
    return tuple(math.radians(value) for value in rotation)


def create_cameras(specs, task_id):
    created = {}
    active = None
    for spec in specs:
        name = spec["id"]
        if name in bpy.data.objects:
            raise TaskError(f"object already exists in base scene: {name}")
        data = bpy.data.cameras.new(name)
        data.type = "ORTHO" if spec["projection"] == "ORTHO" else "PERSP"
        data.ortho_scale = spec["ortho_scale"]
        data.lens = spec["focal_length"]
        data.sensor_width = spec["sensor_width"]
        data.dof.use_dof = spec["dof"]["enabled"]
        if spec["dof"]["enabled"]:
            data.dof.focus_distance = spec["dof"]["focus_distance"]
            data.dof.aperture_fstop = spec["dof"]["f_stop"]
        obj = bpy.data.objects.new(name, data)
        obj.location = spec["location"]
        obj.rotation_mode = "XYZ"
        obj.rotation_euler = aim_rotation(spec["location"], spec["target"], spec["rotation"])
        obj["scene_task_id"] = task_id
        scene_ops.assign_collection(obj, spec["collection"])
        created[name] = obj
        if spec["active"]:
            active = obj

    if active is not None:
        bpy.context.scene.camera = active
    return created
