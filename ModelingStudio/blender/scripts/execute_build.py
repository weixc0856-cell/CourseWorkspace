"""Execute a generated build module, then save/export/render under wrapper control.

Run inside Blender:
    blender --background --factory-startup --python-exit-code 1 \
        --python execute_build.py -- --script build_model.py \
        --out-dir scene --plan model_plan.json
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import random
import sys
import traceback

import bpy
from mathutils import Vector


def fail(message):
    print(f"MODEL_BUILD_ERROR: {message}")
    sys.exit(1)


def get_arg(argv, name, default=None):
    if name not in argv:
        return default
    index = argv.index(name)
    if index + 1 >= len(argv):
        fail(f"{name} requires a value")
    return argv[index + 1]


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def reset_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = 30
    scene.frame_start = 1
    scene.frame_end = 1
    return scene


def ensure_collection(name="MODEL"):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection


def link_object(obj, collection):
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    collection.objects.link(obj)


def ensure_world(scene, color=(0.05, 0.06, 0.08, 1.0), strength=0.6):
    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        scene.world = world
    if not world.use_nodes:
        world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs["Color"].default_value = color
        background.inputs["Strength"].default_value = strength


def aim_at(obj, target):
    direction = Vector(target) - obj.location
    if direction.length < 1e-9:
        return
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def ensure_camera(scene, plan):
    camera_spec = plan.get("camera") or {}
    location = camera_spec.get("location", (0.6, -0.6, 0.45))
    target = camera_spec.get("target", (0.0, 0.0, 0.1))
    lens = float(camera_spec.get("focal_length", 50.0))
    camera = bpy.data.objects.get("Camera")
    if camera is None or camera.type != "CAMERA":
        data = bpy.data.cameras.new("Camera")
        camera = bpy.data.objects.new("Camera", data)
        link_object(camera, ensure_collection())
    camera.location = location
    camera.data.lens = lens
    aim_at(camera, target)
    if scene.camera is None:
        scene.camera = camera
    return camera


def ensure_light(scene, plan):
    if any(obj.type == "LIGHT" for obj in scene.objects):
        return
    spec = (plan.get("lights") or [{}])[0]
    light_type = spec.get("type", "AREA")
    data = bpy.data.lights.new("KeyLight", type=light_type)
    data.energy = float(spec.get("energy", 150.0))
    if light_type == "AREA":
        data.size = float(spec.get("size", 0.6))
    obj = bpy.data.objects.new("KeyLight", data)
    obj.location = spec.get("location", (0.5, -0.4, 0.8))
    aim_at(obj, spec.get("target", (0.0, 0.0, 0.1)))
    link_object(obj, ensure_collection())


def apply_plan_transforms(plan):
    """Make the plan authoritative for size, placement, rotation, and parenting."""
    objects = {}
    for part in plan.get("parts", []):
        obj = bpy.data.objects.get(part.get("id"))
        if obj is None:
            continue
        objects[part["id"]] = obj
        obj.parent = None
        obj.rotation_mode = "XYZ"
        obj.rotation_euler = (0.0, 0.0, 0.0)
        size = part.get("size")
        if size and len(size) == 3 and all(component > 0 for component in size):
            obj.dimensions = size
        obj.location = part.get("location", (0.0, 0.0, 0.0))
        obj.rotation_euler = tuple(
            math.radians(component) for component in part.get("rotation", (0.0, 0.0, 0.0))
        )
    bpy.context.view_layer.update()
    for part in plan.get("parts", []):
        parent_id = part.get("parent")
        obj = objects.get(part["id"])
        parent = objects.get(parent_id)
        if obj is None or parent is None:
            continue
        obj.parent = parent
        obj.matrix_parent_inverse = parent.matrix_world.inverted()
    bpy.context.view_layer.update()


def frame_camera(scene, camera, plan):
    """Frame the whole model with the planned viewing direction."""
    points = []
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not points:
        return
    minimum = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    maximum = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    center = (minimum + maximum) / 2
    radius = max((maximum - minimum).length / 2, 0.01)

    spec = plan.get("camera") or {}
    direction = Vector(spec.get("location", (0.6, -0.6, 0.45))) - Vector(
        spec.get("target", (0.0, 0.0, 0.1))
    )
    if direction.length < 1e-9:
        direction = Vector((1.0, -1.0, 0.7))
    direction.normalize()

    lens = float(spec.get("focal_length", 50.0))
    sensor = 36.0
    width = max(scene.render.resolution_x, 1)
    height = max(scene.render.resolution_y, 1)
    sensor_y = sensor * height / max(width, height)
    half_fov = math.atan((sensor_y / 2.0) / lens)
    distance = radius / math.sin(half_fov) * 1.15
    camera.location = center + direction * distance
    aim_at(camera, center)


def build_material(spec):
    material_id = spec.get("id")
    existing = bpy.data.materials.get(material_id)
    if existing is not None:
        return existing
    material = bpy.data.materials.new(material_id)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    if shader is not None:
        shader.inputs["Base Color"].default_value = tuple(spec.get("base_color", (0.6, 0.6, 0.6, 1.0)))
        shader.inputs["Metallic"].default_value = float(spec.get("metallic", 0.0))
        shader.inputs["Roughness"].default_value = float(spec.get("roughness", 0.5))
        shader.inputs["Emission Color"].default_value = tuple(
            spec.get("emission_color", (0.0, 0.0, 0.0, 1.0))
        )
        shader.inputs["Emission Strength"].default_value = float(
            spec.get("emission_strength", 0.0)
        )
    return material


def assign_plan_materials(plan):
    material_specs = [spec for spec in plan.get("materials", []) if spec.get("id")]
    materials = {spec["id"]: build_material(spec) for spec in material_specs}
    default_material = materials.get(material_specs[0]["id"]) if material_specs else None
    for part in plan.get("parts", []):
        material_id = part.get("material_id")
        material = materials.get(material_id) if material_id else default_material
        obj = bpy.data.objects.get(part.get("id"))
        if obj is None or obj.type != "MESH" or material is None:
            continue
        if not obj.data.materials:
            obj.data.materials.append(material)
    return materials


def configure_render(scene, plan):
    render = plan.get("render") or {}
    width, height = render.get("resolution", (1280, 720))
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = int(width)
    scene.render.resolution_y = int(height)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.eevee.taa_render_samples = int(render.get("samples", 32))


def world_bounds(objects):
    points = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    if not points:
        return None
    minimum = [min(point[i] for point in points) for i in range(3)]
    maximum = [max(point[i] for point in points) for i in range(3)]
    return {"min": minimum, "max": maximum}


def scene_report(scene, plan):
    issues = []
    objects = []
    for obj in scene.objects:
        entry = {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation": list(obj.rotation_euler),
            "scale": list(obj.scale),
        }
        if obj.type == "MESH":
            mesh = obj.data
            entry["verts"] = len(mesh.vertices)
            entry["polygons"] = len(mesh.polygons)
            entry["materials"] = [
                slot.material.name if slot.material else None for slot in obj.material_slots
            ]
            if len(mesh.vertices) == 0:
                issues.append({"code": "EMPTY_MESH", "message": f"{obj.name}: no vertices"})
            if len(mesh.polygons) == 0:
                issues.append({"code": "NO_FACES", "message": f"{obj.name}: no faces"})
            if mesh.validate(verbose=False):
                issues.append({"code": "INVALID_MESH", "message": f"{obj.name}: mesh fixed"})
        objects.append(entry)
    cameras = [obj.name for obj in scene.objects if obj.type == "CAMERA"]
    lights = [obj.name for obj in scene.objects if obj.type == "LIGHT"]
    meshes = [obj for obj in scene.objects if obj.type == "MESH"]
    if not meshes:
        issues.append({"code": "NO_MESH", "message": "scene has no mesh objects"})
    if not cameras:
        issues.append({"code": "NO_CAMERA", "message": "scene has no camera"})
    if scene.camera is None:
        issues.append({"code": "NO_ACTIVE_CAMERA", "message": "no active scene camera"})
    return {
        "schema_version": 1,
        "scene": {
            "name": scene.name,
            "units": scene.unit_settings.system,
            "fps": scene.render.fps,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
            "engine": scene.render.engine,
            "active_camera": scene.camera.name if scene.camera else None,
        },
        "counts": {
            "objects": len(objects),
            "meshes": len(meshes),
            "cameras": len(cameras),
            "lights": len(lights),
            "materials": len(bpy.data.materials),
        },
        "bounds": world_bounds(meshes),
        "objects": objects,
        "plan_parts": len(plan.get("parts", [])),
        "issues": issues,
    }


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    script_path = get_arg(argv, "--script")
    out_dir = get_arg(argv, "--out-dir")
    plan_path = get_arg(argv, "--plan")
    if not script_path or not os.path.isfile(script_path):
        fail(f"script not found: {script_path}")
    if not out_dir:
        fail("missing --out-dir")
    if not plan_path or not os.path.isfile(plan_path):
        fail(f"plan not found: {plan_path}")

    plan = load_json(plan_path)
    os.makedirs(out_dir, exist_ok=True)
    scene = reset_scene()
    ensure_world(scene)
    collection = ensure_collection()

    spec = importlib.util.spec_from_file_location("generated_build", script_path)
    if spec is None or spec.loader is None:
        fail("cannot load generated script")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - report generated-code failure
        traceback.print_exc()
        fail(f"generated script raised during import: {exc}")
    build = getattr(module, "build", None)
    if not callable(build):
        fail("generated script does not define build()")
    random.seed(int(plan.get("seed", 0)))
    try:
        build()
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        fail(f"build() raised: {exc}")

    bpy.context.view_layer.update()
    for obj in scene.objects:
        if not obj.users_collection:
            link_object(obj, collection)

    apply_plan_transforms(plan)
    assign_plan_materials(plan)
    ensure_camera(scene, plan)
    ensure_light(scene, plan)
    configure_render(scene, plan)
    frame_camera(scene, scene.camera, plan)

    blend_path = os.path.join(out_dir, "model.blend")
    glb_path = os.path.join(out_dir, "model.glb")
    fbx_path = os.path.join(out_dir, "model.fbx")
    preview_path = os.path.join(out_dir, "preview.png")
    report_path = os.path.join(out_dir, "scene_report.json")

    bpy.ops.wm.save_as_mainfile(filepath=blend_path, check_existing=False)
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception:
        pass
    bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB", use_selection=False)
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_fbx")
    except Exception:
        pass
    try:
        bpy.ops.export_scene.fbx(
            filepath=fbx_path, use_selection=False, apply_scale_options="FBX_SCALE_ALL"
        )
    except Exception as exc:  # noqa: BLE001 - FBX is an optional deliverable
        print(f"MODEL_BUILD_WARNING: FBX export failed: {exc}")

    scene.render.filepath = preview_path
    scene.frame_set(scene.frame_start)
    bpy.ops.render.render(write_still=True)

    report = scene_report(scene, plan)
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    print(f"MODEL_BUILD_SCRIPT {script_path}")
    print(f"MODEL_BUILD_OBJECTS {report['counts']['objects']}")
    print(f"MODEL_BUILD_MESHES {report['counts']['meshes']}")
    print(f"MODEL_BUILD_BLEND {blend_path}")
    print(f"MODEL_BUILD_GLB {glb_path}")
    if os.path.isfile(fbx_path):
        print(f"MODEL_BUILD_FBX {fbx_path}")
    print(f"MODEL_BUILD_PREVIEW {preview_path}")
    print(f"MODEL_BUILD_REPORT {report_path}")
    if report["issues"]:
        for issue in report["issues"]:
            print(f"MODEL_BUILD_ISSUE {issue['code']}: {issue['message']}")
    print("MODEL_BUILD_OK")


if __name__ == "__main__":
    main()
