"""Build an asset-based Blender environment or shot from a JSON spec.

Level 2 (environment) owns the reusable set: terrain, sky, set dressing, lights.
Level 3 (shot) references an environment and owns camera, timing and render.

Run with Blender:
    blender --background --factory-startup --python scripts/build_asset_scene.py -- \
        --spec <content_root>/assets/3d/kits/fengshui/shots/a1.json --profile blockout

The builder only arranges assets indexed in library.json.  It does not model a
new asset and it does not execute AI-written Python.  AI proposes a spec; this
program validates and renders it.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

PROFILES = {
    "blockout": {"engine": "BLENDER_EEVEE", "samples": 16, "resolution": [540, 960]},
    "preview": {"engine": "BLENDER_EEVEE", "samples": 32, "resolution": [540, 960]},
    "hero": {},
}

PASS_MAP = {
    "beauty": ("Image", "RGBA", None),
    "ao": ("Ambient Occlusion", "RGBA", "use_pass_ambient_occlusion"),
    "depth": ("Depth", "FLOAT", "use_pass_z"),
    "mist": ("Mist", "FLOAT", "use_pass_mist"),
    "normal": ("Normal", "VECTOR", "use_pass_normal"),
    "emission": ("Emission", "RGBA", "use_pass_emit"),
    "cryptomatte": ("Cryptomatte Object", "RGBA", "use_pass_cryptomatte_object"),
}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", "--recipe", dest="spec", required=True)
    parser.add_argument("--library", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--profile", choices=sorted(PROFILES), default=None)
    parser.add_argument("--frames", type=int, default=None, help="override frame count for still tests")
    parser.add_argument("--print-plan", action="store_true")
    return parser.parse_args(argv)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_library(path: Path) -> dict:
    data = load_json(path)
    return {item["id"]: item for item in data.get("assets", []) if "id" in item}


def resolve_spec(path: Path) -> tuple[dict, dict | None]:
    """Load a spec and, for a shot, merge it over its environment."""
    data = load_json(path)
    kind = data.get("kind") or ("environment" if "terrain" in data else None)
    if kind == "environment":
        data.setdefault("kind", "environment")
        return data, None
    if kind != "shot":
        raise SystemExit(f"{path}: spec must declare kind: environment | shot")

    env_rel = Path(str(data.get("environment") or ""))
    env_path = env_rel if env_rel.is_absolute() else path.parent / env_rel
    if not env_path.is_file():
        raise SystemExit(f"{path}: environment not found: {env_path}")
    env = load_json(env_path)
    if env.get("kind") not in (None, "environment"):
        raise SystemExit(f"{env_path}: not an environment spec")

    merged = copy.deepcopy(env)
    merged["kind"] = "shot"
    merged["environment_spec"] = str(env_path)
    merged["shot"] = data
    for key in ("objects", "lights", "water"):
        if data.get(key) is not None:
            merged[key] = copy.deepcopy(data[key])
    merged["camera"] = copy.deepcopy(data.get("camera") or {})
    render = copy.deepcopy(env.get("render") or {})
    render.update(copy.deepcopy(data.get("render") or {}))
    merged["render"] = render
    merged["id"] = data.get("id") or path.stem
    merged["name"] = data.get("name") or merged.get("name") or merged["id"]
    for key in ("beat", "lane", "duration_s", "notes"):
        if data.get(key) is not None:
            merged[key] = data[key]
    return merged, data


def apply_profile(spec: dict, profile: str | None) -> str | None:
    render = spec.setdefault("render", {})
    chosen = profile or render.get("profile")
    if not chosen:
        return None
    if chosen not in PROFILES:
        raise SystemExit(f"unknown render profile: {chosen}")
    for key, value in PROFILES[chosen].items():
        if profile:
            render[key] = value
        else:
            render.setdefault(key, value)
    return chosen


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


def add_water(scene, cfg: dict):
    size = float(cfg.get("size_m", 6000))
    z = float(cfg.get("z", cfg.get("location", [0, 0, 0])[2]))
    location = cfg.get("location") or [0, 0, z]
    bpy.ops.mesh.primitive_plane_add(size=size, location=tuple(location))
    plane = bpy.context.active_object
    plane.name = "Water"
    mat = bpy.data.materials.new("Water")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = tuple(cfg.get("color", [0.05, 0.14, 0.18, 1.0]))
    bsdf.inputs["Roughness"].default_value = float(cfg.get("roughness", 0.08))
    bsdf.inputs["Metallic"].default_value = float(cfg.get("metallic", 0.0))
    for name in ("Transmission Weight", "Transmission"):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = float(cfg.get("transmission", 0.25))
            break
    if cfg.get("bump", True):
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = float(cfg.get("bump_scale", 18.0))
        noise.inputs["Detail"].default_value = 4.0
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = float(cfg.get("bump_strength", 0.12))
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    plane.data.materials.append(mat)


def _key(frame, location, target, lens, easing):
    return {
        "frame": int(frame),
        "location": list(location),
        "target": list(target),
        "lens": float(lens),
        "easing": easing,
    }


def camera_keys(camera: dict, frames: int, fps: int) -> list[dict]:
    """Expand a named camera template into explicit keyframes."""
    if camera.get("keyframes"):
        return camera["keyframes"]
    template = camera.get("template")
    if not template or template == "static_hold":
        return [_key(1, camera.get("location", [0, -10, 3]), camera.get("target", [0, 0, 0]),
                     camera.get("lens", 35), "BEZIER")]

    location = camera.get("location")
    end_location = camera.get("end_location")
    target = camera.get("target", [0, 0, 0])
    end_target = camera.get("end_target", target)
    lens = float(camera.get("lens", 35))
    end_lens = float(camera.get("end_lens", lens))

    if template == "orbit":
        center = camera["center"]
        radius = float(camera["radius"])
        height = float(camera.get("height", center[2]))
        start = math.radians(float(camera.get("start_angle_deg", 0)))
        end = math.radians(float(camera.get("end_angle_deg", 90)))
        count = int(camera.get("key_count", 9))
        keys = []
        for index in range(count):
            t = index / (count - 1)
            angle = start + (end - start) * t
            keys.append(_key(
                round(1 + t * (frames - 1)),
                [center[0] + math.cos(angle) * radius,
                 center[1] + math.sin(angle) * radius,
                 height],
                target,
                lens,
                "BEZIER" if index in (0, count - 1) else "LINEAR",
            ))
        return keys

    if template == "tilt":
        end_location = location

    if template == "dolly_out":
        location, end_location = end_location, location
        target, end_target = end_target, target
        lens, end_lens = end_lens, lens

    if location is None or end_location is None:
        raise SystemExit(f"camera template {template}: needs location and end_location")

    hold_start = max(0, int(round(float(camera.get("hold_start_s", 1.0)) * fps)))
    hold_end = max(0, int(round(float(camera.get("hold_end_s", 1.0)) * fps)))
    move_s = camera.get("move_s")
    if move_s is None:
        move_s = max(0.0, frames / fps - hold_start / fps - hold_end / fps)
    move_frames = max(1, int(round(float(move_s) * fps)))
    f1 = 1
    f2 = min(frames, f1 + hold_start)
    f3 = min(frames, f2 + move_frames)
    f4 = frames
    if f2 >= f4:
        f2 = f4
    if f3 <= f2:
        f3 = f4
    return [
        _key(f1, location, target, lens, "BEZIER"),
        _key(f2, location, target, lens, "LINEAR"),
        _key(f3, end_location, end_target, end_lens, "BEZIER"),
        _key(f4, end_location, end_target, end_lens, "BEZIER"),
    ]


def setup_camera(scene, camera: dict, frames: int, fps: int, shot_id: str):
    keys = camera_keys(camera, frames, fps)
    first = keys[0]
    cam_data = bpy.data.cameras.new(f"cam_{shot_id}")
    cam = bpy.data.objects.new(f"cam_{shot_id}", cam_data)
    scene.collection.objects.link(cam)
    cam.location = tuple(first["location"])
    cam.data.lens = float(first.get("lens", camera.get("lens", 35)))
    cam.data.sensor_width = 36
    cam.data.clip_start = 0.1
    cam.data.clip_end = 20000.0
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = float(camera.get("focus_distance", 10))
    cam.data.dof.aperture_fstop = float(camera.get("fstop", 8))

    target = bpy.data.objects.new(f"cam_{shot_id}_target", None)
    scene.collection.objects.link(target)
    target.location = tuple(first["target"])
    track = cam.constraints.new(type="TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    scene.camera = cam

    if frames > 1:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = "BEZIER"
        bpy.context.preferences.edit.keyframe_new_handle_type = "AUTO_CLAMPED"
        for item in keys:
            frame_no = int(item["frame"])
            cam.location = tuple(item["location"])
            cam.data.lens = float(item.get("lens", cam.data.lens))
            target.location = tuple(item["target"])
            cam.keyframe_insert(data_path="location", frame=frame_no)
            cam.data.keyframe_insert(data_path="lens", frame=frame_no)
            target.keyframe_insert(data_path="location", frame=frame_no)
        easing_by_frame = {int(item["frame"]): str(item.get("easing", "BEZIER")).upper() for item in keys}
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
    return cam


def setup_passes(scene, passes: list[str], pass_dir: Path, shot_id: str):
    if not passes:
        return
    view_layer = scene.view_layers[0]
    for name in passes:
        entry = PASS_MAP.get(name)
        if entry is None:
            continue
        attr = entry[2]
        if attr and hasattr(view_layer, attr):
            setattr(view_layer, attr, True)
    group = bpy.data.node_groups.new("Passes", "CompositorNodeTree")
    scene.compositing_node_group = group
    layers = group.nodes.new("CompositorNodeRLayers")
    output = group.nodes.new("CompositorNodeOutputFile")
    output.directory = str(pass_dir)
    output.file_name = f"{shot_id}_"
    output.format.file_format = "OPEN_EXR_MULTILAYER"
    for name in passes:
        entry = PASS_MAP.get(name)
        if entry is None or entry[0] not in layers.outputs:
            continue
        output.file_output_items.new(entry[1], name)
        try:
            group.links.new(layers.outputs[entry[0]], output.inputs[name])
        except Exception as exc:  # noqa: BLE001 - optional pass must not kill the render
            print(f"pass {name} skipped: {exc}")


def main():
    args = parse_args()
    spec_path = Path(args.spec).resolve()
    spec, shot = resolve_spec(spec_path)
    profile = apply_profile(spec, args.profile)
    if args.frames is not None:
        spec.setdefault("render", {})["frames"] = max(1, int(args.frames))
    root = Path(spec.get("asset_root") or spec_path.parent.parent).resolve()
    library_path = Path(args.library) if args.library else root / "library.json"
    library = load_library(library_path)
    render = spec.get("render", {})
    out = Path(args.out) if args.out else Path(str(render.get("output") or "render.png"))
    if not out.is_absolute():
        out = spec_path.parent / out
    if args.print_plan:
        print(json.dumps({
            "spec": str(spec_path),
            "kind": spec.get("kind"),
            "id": spec.get("id"),
            "profile": profile,
            "environment": spec.get("environment_spec"),
            "camera": spec.get("camera", {}).get("template") or "explicit",
            "frames": int(render.get("frames", 1)),
            "resolution": render.get("resolution", [1080, 1920]),
            "output": str(out),
        }, ensure_ascii=False, indent=2))
        return

    clear()
    scene = bpy.context.scene
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
    fps = int(render.get("fps", 30))
    scene.frame_start = 1
    scene.frame_end = max(1, frames)
    scene.render.fps = fps
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

    hdri = resolve(library, spec["hdri"], root)
    setup_world(hdri, float(spec.get("world_strength", 1.0)))
    if spec.get("atmosphere"):
        add_atmosphere(scene, spec["atmosphere"])

    terrain = spec.get("terrain") or {}
    if terrain:
        height = resolve(library, terrain["heightmap"], root) if terrain.get("heightmap") in library else (root / str(terrain.get("heightmap") or ""))
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
        if terrain.get("heightmap"):
            height_tex = bpy.data.textures.new("HeightMap", type="IMAGE")
            height_tex.image = bpy.data.images.load(str(height), check_existing=True)
            mod = ground.modifiers.new("Displace", "DISPLACE")
            mod.texture = height_tex
            mod.texture_coords = "UV"
            mod.strength = float(terrain.get("displacement_m", 900))
            mod.mid_level = float(terrain.get("mid_level", 0.0))
        bpy.context.view_layer.update()

    if spec.get("water"):
        add_water(scene, spec["water"])

    for item in spec.get("objects", []):
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

    setup_camera(scene, spec.get("camera") or {}, frames, fps, str(spec.get("id") or "shot"))

    sun_data = spec.get("sun")
    if sun_data:
        light = bpy.data.lights.new("Sun", type="SUN")
        light.energy = float(sun_data.get("energy", 2.0))
        light.angle = math.radians(float(sun_data.get("angle_deg", 2.0)))
        light.color = tuple(sun_data.get("color", [1.0, 0.88, 0.72]))
        obj = bpy.data.objects.new("Sun", light)
        scene.collection.objects.link(obj)
        obj.location = tuple(sun_data.get("location", [0, 0, 10]))
        obj.rotation_euler = tuple(math.radians(v) for v in sun_data.get("rotation_deg", [50, 0, 35]))

    for item in spec.get("lights", []):
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

    passes = render.get("passes") or []
    if passes:
        pass_dir = Path(str(render.get("pass_dir") or (out.parent / "passes")))
        setup_passes(scene, passes, pass_dir, str(spec.get("id") or "shot"))

    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out.with_suffix(".blend")))
    if frames > 1:
        bpy.ops.render.render(animation=True)
    else:
        bpy.ops.render.render(write_still=True)
    print(f"ASSET_SCENE_DONE {out}")


if __name__ == "__main__":
    main()
