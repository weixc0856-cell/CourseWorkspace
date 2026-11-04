"""Object creation and transform application."""

from __future__ import annotations

import math

import bpy

from . import scene as scene_ops
from .geometry import build_curve, build_mesh, build_text
from .task_schema import TaskError


def _apply_transform(obj, transform):
    obj.location = transform["location"]
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = tuple(math.radians(value) for value in transform["rotation"])
    obj.scale = transform["scale"]


def create_objects(specs, materials, task_id):
    created = {}
    for spec in specs:
        name = spec["id"]
        if name in bpy.data.objects:
            raise TaskError(f"object already exists in base scene: {name}")

        if spec["type"] == "MESH":
            mesh = build_mesh(name, spec["primitive"], spec["params"], spec["smooth"])
            obj = bpy.data.objects.new(name, mesh)
            material = materials.get(spec["material"]) if spec["material"] else None
            if material is not None:
                obj.data.materials.append(material)
        elif spec["type"] == "TEXT":
            data = build_text(name, spec["text"])
            obj = bpy.data.objects.new(name, data)
            material = materials.get(spec["material"]) if spec["material"] else None
            if material is not None:
                obj.data.materials.append(material)
        elif spec["type"] == "CURVE":
            data = build_curve(name, spec["curve"])
            obj = bpy.data.objects.new(name, data)
            material = materials.get(spec["material"]) if spec["material"] else None
            if material is not None:
                obj.data.materials.append(material)
        else:
            obj = bpy.data.objects.new(name, None)
            obj.empty_display_type = "PLAIN_AXES"
            obj.empty_display_size = spec["empty_size"]

        obj["scene_task_id"] = task_id
        _apply_transform(obj, spec["transform"])
        scene_ops.assign_collection(obj, spec["collection"])
        created[name] = obj

    bpy.context.view_layer.update()
    for spec in specs:
        parent_id = spec["parent"]
        if parent_id is None:
            continue
        obj = created[spec["id"]]
        parent = created[parent_id]
        obj.parent = parent
        obj.matrix_parent_inverse = parent.matrix_world.inverted()

    return created
