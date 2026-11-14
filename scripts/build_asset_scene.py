"""Build a Blender scene from a JSON recipe and the local 3D asset library.

Run with Blender:
    blender --background --factory-startup --python scripts/build_asset_scene.py -- \
        --recipe <content_root>/assets/3d/scenes/hero_srtm.json

The recipe only arranges existing assets: terrain, HDRI, camera, lights and
models. It never models a new asset. Paths are resolved through library.json.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--library", default=None)
    parser.add_argument("--out", default=None)
    return parser.parse_args(argv)


def load_library(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["id"]: item for item in data.get("assets", []) if "id" in item}


def clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.textures):
        for block in list(collection):
            if block.users == 0:
                collection.remove(block)


def resolve(library: dict, asset_id: str, root: Path) -> Path:
    asset = library.get(asset_id)
    if asset is None:
        raise SystemExit(f"asset not in library: {asset_id}")
    path = Path(str(asset.get("path") or ""))
    return path if path.is_absolute() else root / path


def image_node(nodes, path: Path, label: str):
    node = nodes.new("ShaderNodeTexImage")
    node.label = label
    node.image = bpy.data.images.load(str(path), check_existing=True)
    return node


def terrain_material(texture_id: str, root: Path, library: dict, uv_scale: float):
    folder = resolve(library, texture_id, root)
    diff = next(folder.glob("*diff*"), None)
    normal = next(folder.glob("*nor*"), None)
    rough = next(folder.glob("*rough*"), None)
    disp = next(folder.glob("*disp*"), None)
    if diff is None:
        raise SystemExit(f"no diffuse map in {folder}")

    mat = bpy.data.materials.new("TerrainPBR")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.92
    coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (uv_scale, uv_scale, uv_scale)
    links.new(coord.outputs["UV"], mapping.inputs["Vector"])
    n_diff = image_node(nodes, diff, "diffuse")
    links.new(mapping.outputs["Vector"], n_diff.inputs["Vector"])
    links.new(n_diff.outputs["Color"], bsdf.inputs["Base Color"])
    if rough:
        n_rough = image_node(nodes, rough, "roughness")
        links.new(mapping.outputs["Vector"], n_rough.inputs["Vector"])
        links.new(n_rough.outputs["Color"], bsdf.inputs["Roughness"])
    if normal:
        n_normal = image_node(nodes, normal, "normal")
        links.new(mapping.outputs["Vector"], n_normal.inputs["Vector"])
        normal_map = nodes.new("ShaderNodeNormalMap")
        links.new(n_normal.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
    if disp:
        n_disp = image_node(nodes, disp, "displacement")
        links.new(mapping.outputs["Vector"], n_disp.inputs["Vector"])
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.3
        bump.inputs["Distance"].default_value = 0.2
        links.new(n_disp.outputs["Color"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def add_atmosphere(scene, cfg: dict):
    size = float(cfg.get("size_m", 6000))
    location = tuple(cfg.get("location", [0, 0, 600]))
    bpy.ops.mesh.primitive_cube_add(size=size, location=location)
    cube = bpy.context.active_object
    cube.name = "Atmosphere"
    mat = bpy.data.materials.new("Atmosphere")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    volume = nodes.new("ShaderNodeVolumePrincipled")
    volume.inputs["Density"].default_value = float(cfg.get("density", 0.0008))
    volume.inputs["Color"].default_value = tuple(cfg.get("color", [0.55, 0.65, 0.75, 1.0]))
    volume.inputs["Anisotropy"].default_value = float(cfg.get("anisotropy", 0.3))
    links.new(volume.outputs["Volume"], out.inputs["Volume"])
    cube.data.materials.append(mat)


def setup_world(hdri: Path, strength: float):
    world = bpy.data.worlds.new("AssetWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    bg = nodes.get("Background")
    env = nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(hdri), check_existing=True)
    links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength


def import_asset(path: Path):
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [obj for obj in bpy.context.scene.objects if obj not in before]


def bounds(objects):
    points = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    if not points:
        return None
    mn = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    mx = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return mn, mx


def scale_group(objects, factor: float):
    for obj in objects:
        if obj.parent is None:
            obj.scale = tuple(value * factor for value in obj.scale)


def move_group(objects, offset):
    for obj in objects:
        if obj.parent is None:
            obj.location += Vector(offset)


def surface_z(x: float, y: float) -> float:
    deps = bpy.context.evaluated_depsgraph_get()
    hit, loc, _normal, _index, _obj, _matrix = bpy.context.scene.ray_cast(
        deps, (x, y, 8000.0), (0, 0, -1)
    )
    return loc.z if hit else 0.0


def main():
    args = parse_args()
    recipe_path = Path(args.recipe).resolve()
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    root = Path(recipe.get("asset_root") or recipe_path.parent.parent).resolve()
    library_path = Path(args.library) if args.library else root / "library.json"
    library = load_library(library_path)
    out = Path(args.out) if args.out else (recipe_path.parent / recipe.get("render", {}).get("output", "render.png"))

    clear()
    scene = bpy.context.scene
    render = recipe.get("render", {})
    scene.render.engine = render.get("engine", "CYCLES")
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = int(render.get("samples", 40))
        scene.cycles.use_denoising = True
        scene.cycles.max_bounces = 6
    else:
        scene.eevee.taa_render_samples = int(render.get("samples", 64))
        scene.eevee.use_volumetric_shadows = True
        scene.eevee.volumetric_start = 10.0
        scene.eevee.volumetric_end = 9000.0
        scene.eevee.volumetric_samples = 64
        scene.eevee.volumetric_tile_size = "4"
    width, height = render.get("resolution", [1080, 1920])
    scene.render.resolution_x = int(width)
    scene.render.resolution_y = int(height)
    scene.render.resolution_percentage = 100
    frames = int(render.get("frames", 1))
    scene.frame_start = 1
    scene.frame_end = max(1, frames)
    scene.render.fps = int(render.get("fps", 30))
    if frames > 1:
        if hasattr(scene.render, "use_motion_blur"):
            scene.render.use_motion_blur = True
            scene.render.motion_blur_shutter = 0.5
        scene.render.image_settings.media_type = "VIDEO"
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        scene.render.ffmpeg.audio_codec = "NONE"
    else:
        scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(out)
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"

    hdri = resolve(library, recipe["hdri"], root)
    setup_world(hdri, float(recipe.get("world_strength", 1.0)))
    if recipe.get("atmosphere"):
        add_atmosphere(scene, recipe["atmosphere"])

    terrain = recipe["terrain"]
    height = resolve(library, terrain["heightmap"], root) if terrain.get("heightmap") in library else (root / terrain["heightmap"])
    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=int(terrain.get("subdivisions", 300)),
        y_subdivisions=int(terrain.get("subdivisions", 300)),
        size=float(terrain.get("size_m", 2400)),
        location=(0, 0, float(terrain.get("z", 0))),
    )
    ground = bpy.context.active_object
    ground.name = "Terrain"
    ground.data.materials.append(
        terrain_material(terrain["material"], root, library, float(terrain.get("uv_scale", 10)))
    )
    height_tex = bpy.data.textures.new("HeightMap", type="IMAGE")
    height_tex.image = bpy.data.images.load(str(height), check_existing=True)
    mod = ground.modifiers.new("Displace", "DISPLACE")
    mod.texture = height_tex
    mod.texture_coords = "UV"
    mod.strength = float(terrain.get("displacement_m", 900))
    mod.mid_level = float(terrain.get("mid_level", 0.0))
    bpy.context.view_layer.update()

    for item in recipe.get("objects", []):
        path = resolve(library, item["asset"], root)
        objects = import_asset(path)
        scale_group(objects, float(item.get("scale", 1.0)))
        x, y = float(item.get("x", 0)), float(item.get("y", 0))
        z = surface_z(x, y) if item.get("align_to_terrain", True) else float(item.get("z", 0))
        b = bounds(objects)
        if b:
            move_group(objects, (x - (b[0].x + b[1].x) / 2, y - (b[0].y + b[1].y) / 2, z - b[0].z))
        for obj in objects:
            if obj.parent is None:
                obj.rotation_euler[2] += math.radians(float(item.get("rotation_deg", 0)))
    bpy.context.view_layer.update()

    camera = dict(recipe["camera"])
    if camera.get("keyframes"):
        first = camera["keyframes"][0]
        camera.setdefault("location", first.get("location", [0, -10, 3]))
        camera.setdefault("target", first.get("target", [0, 0, 0]))
        camera.setdefault("lens", first.get("lens", 35))
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = tuple(camera["location"])
    cam.data.lens = float(camera.get("lens", 35))
    cam.data.sensor_width = 36
    cam.data.clip_start = 0.1
    cam.data.clip_end = 20000.0
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = float(camera.get("focus_distance", 10))
    cam.data.dof.aperture_fstop = float(camera.get("fstop", 8))
    target = bpy.data.objects.new("CamTarget", None)
    scene.collection.objects.link(target)
    target.location = tuple(camera["target"])
    track = cam.constraints.new(type="TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    scene.camera = cam

    if frames > 1:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = "BEZIER"
        bpy.context.preferences.edit.keyframe_new_handle_type = "AUTO_CLAMPED"
        keys = camera.get("keyframes")
        if keys:
            for item in keys:
                frame_no = int(item.get("frame", 1))
                bpy.context.preferences.edit.keyframe_new_interpolation_type = str(
                    item.get("easing", "BEZIER")
                ).upper()
                if item.get("location"):
                    cam.location = tuple(item["location"])
                if item.get("target"):
                    target.location = tuple(item["target"])
                if item.get("lens"):
                    cam.data.lens = float(item["lens"])
                cam.keyframe_insert(data_path="location", frame=frame_no)
                cam.data.keyframe_insert(data_path="lens", frame=frame_no)
                target.keyframe_insert(data_path="location", frame=frame_no)
        else:
            cam.keyframe_insert(data_path="location", frame=1)
            cam.data.keyframe_insert(data_path="lens", frame=1)
            if camera.get("end_location"):
                cam.location = tuple(camera["end_location"])
                cam.keyframe_insert(data_path="location", frame=frames)
            if camera.get("end_lens"):
                cam.data.lens = float(camera["end_lens"])
                cam.data.keyframe_insert(data_path="lens", frame=frames)
            if camera.get("end_target"):
                target.location = tuple(camera["end_target"])
                target.keyframe_insert(data_path="location", frame=frames)
        # Blender 5.2 actions are layered: fcurves live on channelbags.
        easing_by_frame = {
            int(item.get("frame", 1)): str(item.get("easing", "BEZIER")).upper()
            for item in keys
        }
        for obj in (cam, target):
            if not (obj.animation_data and obj.animation_data.action):
                continue
            for layer in obj.animation_data.action.layers:
                for strip in layer.strips:
                    for bag in strip.channelbags:
                        for curve in bag.fcurves:
                            for key in curve.keyframe_points:
                                easing = easing_by_frame.get(round(key.co[0]), "BEZIER")
                                key.interpolation = easing
                                if easing == "BEZIER":
                                    key.handle_left_type = "AUTO_CLAMPED"
                                    key.handle_right_type = "AUTO_CLAMPED"
    sun_data = recipe.get("sun")
    if sun_data:
        light = bpy.data.lights.new("Sun", type="SUN")
        light.energy = float(sun_data.get("energy", 2.0))
        light.angle = math.radians(float(sun_data.get("angle_deg", 2.0)))
        light.color = tuple(sun_data.get("color", [1.0, 0.88, 0.72]))
        obj = bpy.data.objects.new("Sun", light)
        scene.collection.objects.link(obj)
        obj.location = tuple(sun_data.get("location", [0, 0, 10]))
        obj.rotation_euler = tuple(math.radians(v) for v in sun_data.get("rotation_deg", [50, 0, 35]))

    for item in recipe.get("lights", []):
        light_data = bpy.data.lights.new(str(item.get("id", "Light")), type=item.get("type", "AREA"))
        light_data.energy = float(item.get("energy", 500.0))
        light_data.color = tuple(item.get("color", [1.0, 1.0, 1.0]))
        if hasattr(light_data, "size"):
            light_data.size = float(item.get("size", 5.0))
        if item.get("type") == "SUN" and hasattr(light_data, "angle"):
            light_data.angle = math.radians(float(item.get("angle_deg", 2.0)))
        obj = bpy.data.objects.new(str(item.get("id", "Light")), light_data)
        scene.collection.objects.link(obj)
        obj.location = tuple(item.get("location", [0, 0, 10]))
        if item.get("target"):
            aim = bpy.data.objects.new(f"{item.get('id', 'Light')}Target", None)
            scene.collection.objects.link(aim)
            aim.location = tuple(item["target"])
            track = obj.constraints.new(type="TRACK_TO")
            track.target = aim
            track.track_axis = "TRACK_NEGATIVE_Z"
            track.up_axis = "UP_Y"
        elif item.get("rotation_deg"):
            obj.rotation_euler = tuple(math.radians(v) for v in item["rotation_deg"])

    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out.with_suffix(".blend")))
    if frames > 1:
        bpy.ops.render.render(animation=True)
    else:
        bpy.ops.render.render(write_still=True)
    print(f"ASSET_SCENE_DONE {out}")


if __name__ == "__main__":
    main()
