"""Scene quality verification for a saved .blend file.

Run inside Blender:
    blender --background --factory-startup --python-exit-code 1 \
        --python scripts/verify_scene.py -- --blend path/to/scene.blend --strict
"""

from __future__ import annotations

import json
import os
import sys

import bpy


def get_arg(argv, name, default=None):
    if name not in argv:
        return default
    index = argv.index(name)
    if index + 1 >= len(argv):
        raise SystemExit(f"SCENE_CHECK_ERROR: {name} requires a value")
    return argv[index + 1]


def collection_paths(collections, prefix=""):
    paths = []
    for collection in collections:
        path = f"{prefix}/{collection.name}" if prefix else collection.name
        paths.append(path)
        paths.extend(collection_paths(collection.children, path))
    return paths


def object_collection_paths(obj):
    paths = []
    for collection in obj.users_collection:
        path = collection.name
        parent = collection
        while True:
            parent = _collection_parent(parent)
            if parent is None:
                break
            path = f"{parent.name}/{path}"
        paths.append(path)
    return sorted(paths)


def _collection_parent(collection):
    scene_root = bpy.context.scene.collection
    if collection == scene_root:
        return None
    stack = [scene_root]
    while stack:
        current = stack.pop()
        for child in current.children:
            if child == collection:
                return current
            stack.append(child)
    return None


def _action_fcurves(owner):
    animation_data = getattr(owner, "animation_data", None)
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


def collect_animations(scene):
    entries = []
    owners = [(obj.name, obj) for obj in scene.objects]
    for obj in scene.objects:
        if obj.data is not None and obj.type in {"CAMERA", "LIGHT"}:
            owners.append((obj.name, obj.data))
    for name, owner in owners:
        curves = _action_fcurves(owner)
        if not curves:
            continue
        channels = []
        for curve in curves:
            channels.append(
                {
                    "data_path": curve.data_path,
                    "array_index": curve.array_index,
                    "frames": [round(point.co[0], 3) for point in curve.keyframe_points],
                    "interpolations": [point.interpolation for point in curve.keyframe_points],
                }
            )
        entries.append({"owner": name, "data_type": type(owner).__name__, "channels": channels})
    return entries


def _json_value(value):
    if isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "to_list"):
        return value.to_list()
    if isinstance(value, (list, tuple)):
        return list(value)
    if hasattr(value, "name"):
        return value.name
    return str(value)


def _modifier_info(obj):
    entries = []
    for modifier in obj.modifiers:
        entry = {"name": modifier.name, "type": modifier.type}
        if modifier.type == "NODES" and modifier.node_group is not None:
            entry["node_group"] = modifier.node_group.name
            inputs = {}
            interface = modifier.node_group.interface.items_tree
            for item in interface:
                if item.item_type != "SOCKET" or item.in_out != "INPUT":
                    continue
                try:
                    inputs[item.name] = _json_value(
                        getattr(modifier.properties.inputs, item.identifier).value
                    )
                except AttributeError:
                    continue
            entry["inputs"] = inputs
        entries.append(entry)
    return entries


def build_report(filepath):
    scene = bpy.context.scene
    issues = []

    objects = []
    for obj in scene.objects:
        entry = {
            "name": obj.name,
            "type": obj.type,
            "parent": obj.parent.name if obj.parent else None,
            "collections": object_collection_paths(obj),
            "modifiers": _modifier_info(obj),
        }
        if obj.type == "MESH" and obj.data is not None:
            mesh = obj.data
            entry["verts"] = len(mesh.vertices)
            entry["edges"] = len(mesh.edges)
            entry["polygons"] = len(mesh.polygons)
            entry["materials"] = [
                slot.material.name if slot.material else None for slot in obj.material_slots
            ]
            if len(mesh.vertices) == 0:
                issues.append({"code": "EMPTY_MESH", "message": f"{obj.name}: mesh has no vertices"})
            if len(mesh.polygons) == 0:
                issues.append({"code": "NO_FACES", "message": f"{obj.name}: mesh has no faces"})
            if mesh.validate(verbose=False):
                issues.append({"code": "INVALID_MESH", "message": f"{obj.name}: mesh data required fixes"})
        objects.append(entry)

    cameras = []
    for obj in scene.objects:
        if obj.type == "CAMERA":
            cameras.append(
                {
                    "name": obj.name,
                    "lens": obj.data.lens,
                    "active": scene.camera == obj,
                    "location": list(obj.location),
                }
            )
    lights = []
    for obj in scene.objects:
        if obj.type == "LIGHT":
            lights.append(
                {
                    "name": obj.name,
                    "light_type": obj.data.type,
                    "energy": obj.data.energy,
                }
            )

    if not objects:
        issues.append({"code": "NO_OBJECTS", "message": "scene contains no objects"})
    if not cameras:
        issues.append({"code": "NO_CAMERA", "message": "scene has no camera"})
    elif scene.camera is None:
        issues.append({"code": "NO_ACTIVE_CAMERA", "message": "no active scene camera"})

    missing_files = []
    for image in bpy.data.images:
        path = bpy.path.abspath(image.filepath) if image.filepath else ""
        if not path or image.packed_file is not None:
            continue
        if not os.path.isfile(path):
            missing_files.append(path)
    for library in bpy.data.libraries:
        path = bpy.path.abspath(library.filepath) if library.filepath else ""
        if path and not os.path.isfile(path):
            missing_files.append(path)
    for path in missing_files:
        issues.append({"code": "MISSING_RESOURCE", "message": f"missing file: {path}"})

    animations = collect_animations(scene)
    animated = sorted({entry["owner"] for entry in animations})

    return {
        "ok": not issues,
        "blender_version": bpy.app.version_string,
        "file": os.path.abspath(filepath),
        "scene": {
            "name": scene.name,
            "units": scene.unit_settings.system,
            "unit_scale": scene.unit_settings.scale_length,
            "fps": scene.render.fps,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
            "engine": scene.render.engine,
            "active_camera": scene.camera.name if scene.camera else None,
        },
        "collections": collection_paths(scene.collection.children),
        "objects": objects,
        "cameras": cameras,
        "lights": lights,
        "animated_objects": animated,
        "animations": animations,
        "issues": issues,
    }


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    blend = get_arg(argv, "--blend")
    if not blend:
        raise SystemExit("SCENE_CHECK_ERROR: missing --blend <path>")
    if not os.path.isfile(blend):
        raise SystemExit(f"SCENE_CHECK_ERROR: blend not found: {blend}")

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
    report = build_report(blend)

    json_path = get_arg(argv, "--json")
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if json_path:
        os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as handle:
            handle.write(payload)
        print(f"SCENE_CHECK_JSON {os.path.abspath(json_path)}")
    else:
        print("SCENE_CHECK_JSON_BEGIN")
        print(payload)
        print("SCENE_CHECK_JSON_END")

    for issue in report["issues"]:
        print(f"SCENE_CHECK_ISSUE {issue['code']}: {issue['message']}")

    strict = "--strict" in argv
    if strict and report["issues"]:
        raise SystemExit(1)
    print("SCENE_CHECK_OK" if report["ok"] else "SCENE_CHECK_WARN")


if __name__ == "__main__":
    main()
