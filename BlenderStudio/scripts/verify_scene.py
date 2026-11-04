"""Scene quality verification for a saved .blend file.

Run inside Blender:
    blender --background --factory-startup --python-exit-code 1 \
        --python scripts/verify_scene.py -- --blend path/to/scene.blend --strict
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy

from scene_system.fields import evaluate_field


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
    if hasattr(value, "__len__") and hasattr(value, "__iter__"):
        try:
            return [float(item) for item in value]
        except (TypeError, ValueError):
            pass
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


def _socket_value(node, name):
    socket = node.inputs.get(name)
    if socket is None:
        return None
    return _json_value(socket.default_value)


def _material_info(material):
    entry = {"name": material.name, "shader": None, "params": {}, "bump": None}
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return entry
    if "colormap_name" in material:
        attribute = next(
            (node for node in tree.nodes if node.bl_idname == "ShaderNodeAttribute"),
            None,
        )
        mapping = next(
            (node for node in tree.nodes if node.bl_idname == "ShaderNodeMapRange"),
            None,
        )
        entry["shader"] = "scientific_colormap"
        entry["params"] = {
            "source_attribute": getattr(attribute, "attribute_name", None),
            "min_value": mapping.inputs["From Min"].default_value if mapping else None,
            "max_value": mapping.inputs["From Max"].default_value if mapping else None,
            "units": material.get("units"),
            "colormap": material.get("colormap_name"),
        }
        return entry
    shader = None
    for node in tree.nodes:
        if node.bl_idname == "ShaderNodeBsdfPrincipled":
            shader = node
            entry["shader"] = "principled"
            break
        if node.bl_idname == "ShaderNodeEmission":
            shader = node
            entry["shader"] = "emission"
            break
    if shader is None:
        return entry
    if entry["shader"] == "principled":
        names = (
            "Base Color",
            "Metallic",
            "Roughness",
            "Alpha",
            "IOR",
            "Emission Color",
            "Emission Strength",
            "Coat Weight",
            "Coat Roughness",
        )
    else:
        names = ("Color", "Strength")
    for name in names:
        value = _socket_value(shader, name)
        if value is not None:
            entry["params"][name] = value
    if entry["shader"] == "principled":
        normal = shader.inputs.get("Normal")
        if normal is not None and normal.is_linked:
            source = normal.links[0].from_node
            if source.bl_idname == "ShaderNodeBump":
                bump = {
                    "strength": _socket_value(source, "Strength"),
                    "distance": _socket_value(source, "Distance"),
                    "noise_scale": None,
                    "noise_detail": None,
                }
                height = source.inputs.get("Height")
                if height is not None and height.is_linked:
                    noise = height.links[0].from_node
                    if noise.bl_idname == "ShaderNodeTexNoise":
                        bump["noise_scale"] = _socket_value(noise, "Scale")
                        bump["noise_detail"] = _socket_value(noise, "Detail")
                entry["bump"] = bump
    return entry


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
            fields_json = obj.get("attribute_fields")
            if fields_json:
                try:
                    fields = json.loads(fields_json)
                except (TypeError, ValueError):
                    fields = {}
                samples = {}
                for name, field in fields.items():
                    attribute = mesh.attributes.get(name)
                    if attribute is None:
                        issues.append(
                            {
                                "code": "ATTRIBUTE_MISSING",
                                "message": f"{obj.name}: attribute {name} is missing",
                            }
                        )
                        continue
                    indices = sorted({0, len(mesh.vertices) // 2, len(mesh.vertices) - 1})
                    values = [float(attribute.data[index].value) for index in indices]
                    samples[name] = {"indices": indices, "values": values}
                    for index, value in zip(indices, values):
                        expected = evaluate_field(field, mesh.vertices[index].co)
                        if abs(value - expected) > 1e-4:
                            issues.append(
                                {
                                    "code": "ATTRIBUTE_MISMATCH",
                                    "message": (
                                        f"{obj.name}.{name}[{index}]: {value} != {expected}"
                                    ),
                                }
                            )
                            break
                entry["attributes"] = samples
        elif obj.type == "FONT" and obj.data is not None:
            text = obj.data
            entry["text"] = {
                "body": text.body,
                "size": text.size,
                "align_x": text.align_x,
                "align_y": text.align_y,
                "extrude": text.extrude,
                "bevel_depth": text.bevel_depth,
                "space_line": text.space_line,
                "font": getattr(text.font, "name", None),
            }
            entry["materials"] = [
                slot.material.name if slot.material else None for slot in obj.material_slots
            ]
            if not text.body.strip():
                issues.append({"code": "EMPTY_TEXT", "message": f"{obj.name}: text body is blank"})
        elif obj.type == "CURVE" and obj.data is not None:
            curve = obj.data
            coordinates = []
            for spline in curve.splines:
                if spline.type == "BEZIER":
                    coordinates.extend(tuple(point.co[:3]) for point in spline.bezier_points)
                else:
                    coordinates.extend(tuple(point.co[:3]) for point in spline.points)
            point_count = len(coordinates)
            entry["curve"] = {
                "splines": len(curve.splines),
                "points": point_count,
                "cyclic": any(spline.use_cyclic_u for spline in curve.splines),
                "bevel_depth": curve.bevel_depth,
                "dimensions": curve.dimensions,
            }
            entry["materials"] = [
                slot.material.name if slot.material else None for slot in obj.material_slots
            ]
            if point_count < 2:
                issues.append(
                    {
                        "code": "CURVE_TOO_FEW_POINTS",
                        "message": f"{obj.name}: curve has {point_count} points (need >= 2)",
                    }
                )
            if curve.bevel_depth <= 0.0:
                issues.append(
                    {
                        "code": "CURVE_NO_BEVEL",
                        "message": f"{obj.name}: curve bevel_depth is {curve.bevel_depth}",
                    }
                )
            if coordinates:
                spans = [
                    max(point[axis] for point in coordinates)
                    - min(point[axis] for point in coordinates)
                    for axis in range(3)
                ]
                if max(spans) <= 1e-6:
                    issues.append(
                        {
                            "code": "CURVE_DEGENERATE",
                            "message": f"{obj.name}: curve points all coincide",
                        }
                    )
        objects.append(entry)

    cameras = []
    for obj in scene.objects:
        if obj.type == "CAMERA":
            cameras.append(
                {
                    "name": obj.name,
                    "lens": obj.data.lens,
                    "projection": obj.data.type,
                    "ortho_scale": obj.data.ortho_scale,
                    "active": scene.camera == obj,
                    "location": list(obj.location),
                }
            )
            if obj.data.type == "ORTHO" and obj.data.ortho_scale <= 0.0:
                issues.append(
                    {
                        "code": "ORTHO_SCALE_INVALID",
                        "message": f"{obj.name}: ortho_scale is {obj.data.ortho_scale}",
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

    materials = [_material_info(material) for material in bpy.data.materials]
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
        "materials": materials,
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
