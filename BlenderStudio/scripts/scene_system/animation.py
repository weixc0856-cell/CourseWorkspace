"""Deterministic keyframe animation for transform, light energy, and camera lens."""

from __future__ import annotations

import math

import bpy

from .task_schema import TaskError

TRANSFORM_PATHS = {
    "location": "location",
    "rotation": "rotation_euler",
    "scale": "scale",
}
SCALAR_PATHS = {
    "energy": "energy",
    "focal_length": "lens",
}


def _owner(target, prop):
    """Return (id_block, data_path). Scalar channels animate the data-block."""
    if prop in TRANSFORM_PATHS:
        return target, TRANSFORM_PATHS[prop]
    return target.data, SCALAR_PATHS[prop]


def _assign(obj, prop, value):
    if prop == "location":
        obj.location = value
    elif prop == "rotation":
        obj.rotation_mode = "XYZ"
        obj.rotation_euler = tuple(math.radians(component) for component in value)
    elif prop == "scale":
        obj.scale = value
    elif prop == "energy":
        obj.data.energy = value
    elif prop == "focal_length":
        obj.data.lens = value
    else:  # pragma: no cover - schema guards
        raise TaskError(f"unsupported animation property: {prop}")


def _fcurves(obj):
    animation_data = obj.animation_data
    if animation_data is None or animation_data.action is None:
        return []
    action = animation_data.action
    layers = getattr(action, "layers", None)
    if layers is None:
        return list(getattr(action, "fcurves", []))
    slot = getattr(animation_data, "action_slot", None)
    if slot is None and len(action.slots):
        slot = action.slots[0]
    curves = []
    for layer in layers:
        for strip in layer.strips:
            if not hasattr(strip, "channelbag"):
                continue
            bag = strip.channelbag(slot) if slot is not None else None
            if bag is not None:
                curves.extend(bag.fcurves)
    return curves


def apply_animations(specs, scene):
    keyframes = 0
    for spec in specs:
        target = bpy.data.objects.get(spec["target"])
        if target is None:
            raise TaskError(f"animation target not found: {spec['target']}")
        for channel in spec["channels"]:
            prop = channel["property"]
            owner, data_path = _owner(target, prop)
            for keyframe in channel["keyframes"]:
                _assign(target, prop, keyframe["value"])
                owner.keyframe_insert(
                    data_path=data_path,
                    frame=keyframe["frame"],
                    group=f"{target.name}.{prop}",
                )
                keyframes += 1

            interpolations = {
                keyframe["frame"]: keyframe["interpolation"]
                for keyframe in channel["keyframes"]
            }
            for curve in _fcurves(owner):
                if curve.data_path != data_path:
                    continue
                for point in curve.keyframe_points:
                    frame = int(round(point.co[0]))
                    if frame in interpolations:
                        point.interpolation = interpolations[frame]
                curve.update()

    scene.frame_set(scene.frame_start)
    return keyframes
