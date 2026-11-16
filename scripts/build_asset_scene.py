"""Build an asset-based Blender environment or shot from a JSON spec.

Level 2 (environment) owns the reusable set: terrain, sky, set dressing, lights.
Level 3 (shot) references an environment and owns camera, timing and render.

Run with Blender:
    blender --background --factory-startup --python scripts/build_asset_scene.py -- \
        --spec <content_root>/assets/3d/kits/fengshui/shots/a1.json --profile blockout

The builder only arranges assets indexed in library.json.  It does not model a
new asset and it does not execute AI-written Python.  AI proposes a spec; this
program validates and renders it.

Every build writes a manifest (inputs, versions, render parameters, status) and
a log under ``manifests/`` next to the output.  A second build with the same
inputs and render parameters is served from cache unless ``--no-cache`` is set.

``--build environment`` writes ``blends/environments/<place>.blend``;
``--build shot`` links that environment, writes ``blends/shots/<shot>.blend``
and renders.  ``--build inline`` keeps the legacy merge path.
"""

from __future__ import annotations

import argparse
import copy
import importlib
import importlib.util
import json
import math
import os
import random
import sys
import time
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
    parser.add_argument("--build", choices=["auto", "environment", "shot", "inline"], default="auto")
    parser.add_argument("--frames", type=int, default=None, help="override frame count for still tests")
    parser.add_argument("--cache", action=argparse.BooleanOptionalAction, default=True,
                        help="reuse a passing manifest with the same inputs")
    parser.add_argument("--manifest-dir", default=None)
    parser.add_argument("--print-plan", action="store_true")
    return parser.parse_args(argv)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_library(path: Path) -> dict:
    data = load_json(path)
    return {item["id"]: item for item in data.get("assets", []) if "id" in item}


def load_manifest_core():
    path = Path(__file__).resolve().parents[1] / "CourseControl/src/course_control/scene_spec/manifest_core.py"
    if not path.is_file():
        raise SystemExit(f"manifest core not found: {path}")
    spec = importlib.util.spec_from_file_location("asset_build_manifest_core", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_visual_grammar(value: str | None) -> dict | None:
    if not value:
        return None
    raw = str(value)
    grammar_id, version = (raw.rsplit("@", 1) if "@" in raw else (raw, None))
    path = Path(__file__).resolve().parents[1] / "shared/grammars/style-presets.json"
    if not path.is_file():
        raise SystemExit(f"visual grammar registry not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    preset = (data.get("presets") or {}).get(grammar_id)
    if preset is None:
        raise SystemExit(f"visual grammar preset not found: {grammar_id}")
    if version is not None and str(preset.get("version")) != version:
        raise SystemExit(f"visual grammar version mismatch: {raw}")
    return {**preset, "_id": grammar_id, "_version": str(preset.get("version"))}


def write_look(path: Path, grammar: dict | None) -> Path | None:
    if grammar is None:
        return None
    payload = {
        "visual_grammar": f"{grammar['_id']}@{grammar['_version']}",
        "builder": grammar.get("builder") or {},
        "composition": grammar.get("composition") or {},
        "sound": grammar.get("sound") or {},
    }
    target = path.with_suffix(".look.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")
    return target


def addon_versions() -> list[dict]:
    entries = []
    for addon in bpy.context.preferences.addons:
        module_name = str(getattr(addon, "module", ""))
        version = None
        try:
            module = importlib.import_module(module_name)
            info = getattr(module, "bl_info", None) or {}
            value = info.get("version") if isinstance(info, dict) else None
            if isinstance(value, (list, tuple)):
                version = ".".join(str(part) for part in value)
        except Exception:  # noqa: BLE001 - an addon may not be importable
            version = None
        entries.append({"name": module_name, "version": version})
    return sorted(entries, key=lambda item: item["name"])


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
    for key in ("objects", "lights", "water", "wind"):
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
    z = 8000.0
    for _ in range(6):
        hit, loc, _normal, _index, obj, _matrix = bpy.context.scene.ray_cast(
            deps, (x, y, z), (0, 0, -1)
        )
        if not hit:
            return 0.0
        if obj.name != "Atmosphere":
            return loc.z
        z = loc.z - 0.01
    return 0.0


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


def _collection(scene, name: str):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
    if collection.name not in scene.collection.children:
        scene.collection.children.link(collection)
    return collection


def wind_material(cfg: dict, frames: int):
    mat = bpy.data.materials.new("WindFlow")
    mat.use_nodes = True
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    if hasattr(mat, "blend_method"):
        mat.blend_method = "BLEND"
    mat.use_backface_culling = False
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    mix = nodes.new("ShaderNodeMixShader")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = tuple(cfg.get("color", [0.72, 0.88, 1.0, 1.0]))
    emission.inputs["Strength"].default_value = float(cfg.get("strength", 2.2))
    texcoord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    wave = nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = float(cfg.get("dash_scale", 7.0))
    wave.inputs["Distortion"].default_value = float(cfg.get("distortion", 0.5))
    wave.inputs["Detail"].default_value = 2.0
    ramp = nodes.new("ShaderNodeValToRGB")
    threshold = float(cfg.get("dash_threshold", 0.42))
    softness = float(cfg.get("dash_softness", 0.12))
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp.color_ramp.elements[1].position = threshold
    ramp.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
    peak = ramp.color_ramp.elements.new(threshold + softness * 0.5)
    peak.color = (1.0, 1.0, 1.0, 1.0)
    tail = ramp.color_ramp.elements.new(threshold + softness)
    tail.color = (0.0, 0.0, 0.0, 1.0)
    links.new(texcoord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], mix.inputs[0])
    links.new(transparent.outputs["BSDF"], mix.inputs[1])
    links.new(emission.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs["Shader"], output.inputs["Surface"])
    # One full texture period over the shot keeps the loop seamless.
    location = mapping.inputs["Location"]
    location.default_value[0] = 0.0
    location.keyframe_insert(data_path="default_value", frame=1)
    location.default_value[0] = 1.0
    location.keyframe_insert(data_path="default_value", frame=max(2, frames))
    if mat.node_tree.animation_data and mat.node_tree.animation_data.action:
        for layer in mat.node_tree.animation_data.action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:
                            key.interpolation = "LINEAR"
    return mat


def add_wind_mist(scene, cfg: dict, frames: int):
    size = cfg.get("size", [6000, 4000, 1800])
    location = cfg.get("location", [0, 0, 900])
    bpy.ops.mesh.primitive_cube_add(size=1, location=tuple(location))
    cube = bpy.context.active_object
    cube.name = "WindMist"
    cube.scale = (float(size[0]), float(size[1]), float(size[2]))
    material = bpy.data.materials.new("WindMist")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    volume = nodes.new("ShaderNodeVolumePrincipled")
    volume.inputs["Color"].default_value = tuple(cfg.get("color", [0.7, 0.8, 0.92, 1.0]))
    volume.inputs["Anisotropy"].default_value = float(cfg.get("anisotropy", 0.3))
    texcoord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = float(cfg.get("noise_scale", 2.5))
    noise.inputs["Detail"].default_value = float(cfg.get("noise_detail", 4.0))
    noise.inputs["Roughness"].default_value = float(cfg.get("noise_roughness", 0.65))
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = float(cfg.get("patch_threshold", 0.48))
    ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp.color_ramp.elements[1].position = float(cfg.get("patch_threshold", 0.48)) + 0.2
    ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    multiply = nodes.new("ShaderNodeMath")
    multiply.operation = "MULTIPLY"
    multiply.inputs[1].default_value = float(cfg.get("density", 0.00035))
    links.new(texcoord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], multiply.inputs[0])
    links.new(multiply.outputs["Value"], volume.inputs["Density"])
    links.new(volume.outputs["Volume"], output.inputs["Volume"])
    cube.data.materials.append(material)
    location_socket = mapping.inputs["Location"]
    location_socket.default_value[0] = 0.0
    location_socket.keyframe_insert(data_path="default_value", frame=1)
    location_socket.default_value[0] = float(cfg.get("travel", 1.0))
    location_socket.keyframe_insert(data_path="default_value", frame=max(2, frames))
    if material.node_tree.animation_data and material.node_tree.animation_data.action:
        for layer in material.node_tree.animation_data.action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:
                            key.interpolation = "LINEAR"


def add_wind_particles(scene, cfg: dict, frames: int):
    count = int(cfg.get("count", 350))
    # Small glowing dust motes; motion blur turns them into short wind streaks.
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1.0, location=(0, 0, 0))
    mote = bpy.context.active_object
    mote.name = "WindMote"
    mote.hide_render = False
    mat = bpy.data.materials.new("WindMote")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = tuple(cfg.get("color", [0.72, 0.84, 0.95, 1.0]))
    bsdf.inputs["Emission Color"].default_value = tuple(cfg.get("color", [0.72, 0.84, 0.95, 1.0]))
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = float(cfg.get("strength", 1.0))
    mote.data.materials.append(mat)

    bpy.ops.mesh.primitive_plane_add(size=1, location=tuple(cfg.get("location", [-2600, 0, 1100])))
    emitter = bpy.context.active_object
    emitter.name = "WindEmitter"
    emitter.rotation_euler[1] = math.radians(90)
    emitter.scale = (float(cfg.get("height_m", 1800)), float(cfg.get("width_m", 4200)), 1.0)
    emitter_mat = bpy.data.materials.new("WindEmitter")
    emitter_mat.use_nodes = True
    emitter_bsdf = emitter_mat.node_tree.nodes.get("Principled BSDF")
    emitter_bsdf.inputs["Alpha"].default_value = 0.0
    if hasattr(emitter_mat, "surface_render_method"):
        emitter_mat.surface_render_method = "BLENDED"
    emitter.data.materials.append(emitter_mat)
    modifier = emitter.modifiers.new("WindParticles", "PARTICLE_SYSTEM")
    psys = modifier.particle_system
    settings = psys.settings
    settings.count = count
    settings.frame_start = 1 - frames
    settings.frame_end = frames
    settings.lifetime = frames
    settings.emit_from = "FACE"
    settings.use_emit_random = True
    settings.normal_factor = float(cfg.get("speed", 2.2))
    settings.factor_random = float(cfg.get("speed_random", 0.3))
    settings.physics_type = "NEWTON"
    settings.effector_weights.gravity = 0.0
    settings.render_type = "OBJECT"
    settings.instance_object = mote
    settings.particle_size = float(cfg.get("particle_size", 2.0))
    settings.size_random = float(cfg.get("size_random", 0.6))
    settings.use_rotations = False
    emitter.hide_render = False
    settings.display_method = "RENDER"
    psys.point_cache.frame_start = 1 - frames
    psys.point_cache.frame_end = frames
    bpy.context.scene.frame_set(1)
    bpy.ops.ptcache.bake_all(bake=True)


def add_wind_motes(scene, cfg: dict, frames: int):
    count = int(cfg.get("count", 120))
    region = cfg.get("region", [-2600, 2600, -1400, 1400])
    xmin, xmax, ymin, ymax = (float(value) for value in region)
    z_min = float(cfg.get("z_min", 700))
    z_max = float(cfg.get("z_max", 1200))
    travel = float(cfg.get("travel_m", 500))
    rng = random.Random(int(cfg.get("seed", 7)))
    material = bpy.data.materials.new("WindMote")
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = tuple(cfg.get("color", [0.72, 0.84, 0.95, 1.0]))
    bsdf.inputs["Emission Color"].default_value = tuple(cfg.get("color", [0.72, 0.84, 0.95, 1.0]))
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = float(cfg.get("strength", 1.2))
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    template = bpy.context.active_object
    template.name = "WindMoteTemplate"
    template.data.materials.append(material)
    template.hide_render = True
    collection = _collection(scene, "WIND")
    for index in range(count):
        obj = template.copy()
        obj.data = template.data
        obj.hide_render = False
        collection.objects.link(obj)
        obj.name = f"WindMote_{index:03d}"
        y = ymin + (ymax - ymin) * ((index + 0.5) / count) + rng.uniform(-0.03, 0.03) * (ymax - ymin)
        x = rng.uniform(xmin, xmax)
        z = rng.uniform(z_min, z_max)
        obj.location = (x, y, z)
        obj.scale = (float(cfg.get("length_m", 8.0)), float(cfg.get("width_m", 0.7)), float(cfg.get("width_m", 0.7)))
        obj.rotation_euler[2] = rng.uniform(-0.08, 0.08)
        obj.keyframe_insert(data_path="location", frame=1)
        obj.location.x = min(xmax, x + travel)
        obj.keyframe_insert(data_path="location", frame=max(2, frames))
        if obj.animation_data and obj.animation_data.action:
            for layer in obj.animation_data.action.layers:
                for strip in layer.strips:
                    for bag in strip.channelbags:
                        for curve in bag.fcurves:
                            for key in curve.keyframe_points:
                                key.interpolation = "LINEAR"


def add_wind(scene, cfg: dict, spec: dict, frames: int):
    if not cfg:
        return
    style = cfg.get("style", "ribbons")
    if style == "mist":
        add_wind_mist(scene, cfg, frames)
        return
    if style == "particles":
        add_wind_particles(scene, cfg, frames)
        return
    if style == "motes":
        add_wind_motes(scene, cfg, frames)
        return
    count = int(cfg.get("count", 24))
    point_count = int(cfg.get("points", 28))
    region = cfg.get("region", [-2600, 2600, -1400, 1400])
    xmin, xmax, ymin, ymax = (float(value) for value in region)
    clearance = float(cfg.get("clearance_m", 90))
    lift = float(cfg.get("lift_m", 0))
    ridge_x = float(cfg.get("ridge_x", 0))
    ridge_width = max(1.0, float(cfg.get("ridge_width_m", 700)))
    wave_height = float(cfg.get("wave_height_m", 0))
    wave_length = max(1.0, float(cfg.get("wave_length_m", 900)))
    water_z = float((spec.get("water") or {}).get("z", (spec.get("water") or {}).get("location", [0, 0, -10000])[2]))
    rng = random.Random(int(cfg.get("seed", 7)))
    material = wind_material(cfg, frames)
    collection = _collection(scene, "WIND")
    for index in range(count):
        base_y = ymin + (ymax - ymin) * ((index + 0.5) / count)
        y_jitter = rng.uniform(-0.08, 0.08) * (ymax - ymin)
        y = base_y + y_jitter
        points = []
        for step in range(point_count):
            t = step / (point_count - 1)
            x = xmin + (xmax - xmin) * t
            z = surface_z(x, y)
            z = max(z, water_z)
            z += clearance
            z += lift * math.exp(-((x - ridge_x) / ridge_width) ** 2)
            if wave_height:
                z += wave_height * math.sin((x / wave_length) * math.pi * 2 + index)
            points.append((x, y, z))
        # Low-pass the vertical path so wind reads as flow, not a terrain contour.
        zs = [point[2] for point in points]
        smoothed = []
        for idx in range(len(zs)):
            window = zs[max(0, idx - 4): min(len(zs), idx + 5)]
            smoothed.append(sum(window) / len(window))
        points = [(point[0], point[1], smoothed[idx]) for idx, point in enumerate(points)]
        curve = bpy.data.curves.new(f"WindStream_{index:02d}", type="CURVE")
        curve.dimensions = "3D"
        curve.resolution_u = 1
        curve.bevel_depth = float(cfg.get("thickness_m", 1.4))
        curve.bevel_resolution = 0
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for point, value in zip(spline.points, points):
            point.co = (*value, 1.0)
        obj = bpy.data.objects.new(f"WindStream_{index:02d}", curve)
        collection.objects.link(obj)
        curve.materials.append(material)


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


def configure_render(scene, render: dict, filepath: Path, grammar: dict | None = None) -> tuple[int, int]:
    frames = int(render.get("frames", 1))
    fps = int(render.get("fps", 30))
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
    scene.frame_start = 1
    scene.frame_end = max(1, frames)
    scene.render.fps = fps
    if frames > 1:
        if hasattr(scene.render, "use_motion_blur"):
            scene.render.use_motion_blur = True
            shutter = (grammar or {}).get("builder", {}).get("motion_blur_shutter", 0.5)
            scene.render.motion_blur_shutter = float(shutter)
        scene.render.image_settings.media_type = "VIDEO"
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        scene.render.ffmpeg.audio_codec = "NONE"
    else:
        scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(filepath)
    builder = (grammar or {}).get("builder") or {}
    transform = str(builder.get("color_management", "agx")).lower()
    scene.view_settings.view_transform = "Standard" if transform == "standard" else "AgX"
    look = builder.get("look")
    if look:
        try:
            scene.view_settings.look = str(look)
        except Exception:  # noqa: BLE001 - look names vary by Blender version
            pass
    scene.view_settings.exposure = float(builder.get("exposure", 0.0))
    return frames, fps


def add_lights(scene, data: dict):
    sun_data = data.get("sun")
    if sun_data:
        light = bpy.data.lights.new("Sun", type="SUN")
        light.energy = float(sun_data.get("energy", 2.0))
        light.angle = math.radians(float(sun_data.get("angle_deg", 2.0)))
        light.color = tuple(sun_data.get("color", [1.0, 0.88, 0.72]))
        obj = bpy.data.objects.new("Sun", light)
        scene.collection.objects.link(obj)
        obj.location = tuple(sun_data.get("location", [0, 0, 10]))
        obj.rotation_euler = tuple(math.radians(v) for v in sun_data.get("rotation_deg", [50, 0, 35]))

    for item in data.get("lights", []):
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


def move_to_collection(obj, collection):
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    collection.objects.link(obj)


def prepare_environment_collections(scene):
    env = bpy.data.collections.new("ENV")
    assets = bpy.data.collections.new("ENV_ASSETS")
    lights = bpy.data.collections.new("ENV_LIGHTS")
    for collection in (env, assets, lights):
        scene.collection.children.link(collection)
    for obj in list(scene.objects):
        if obj.type == "LIGHT" or (obj.type == "EMPTY" and obj.name.endswith("Target")):
            move_to_collection(obj, lights)
        elif obj.name in {"Terrain", "Atmosphere", "Water"}:
            move_to_collection(obj, env)
        else:
            move_to_collection(obj, assets)


def environment_blend_path(environment_spec_path: Path) -> Path:
    return environment_spec_path.resolve().parent.parent / "blends" / "environments" / f"{environment_spec_path.stem}.blend"


def shot_blend_path(shot_spec_path: Path) -> Path:
    return shot_spec_path.resolve().parent.parent / "blends" / "shots" / f"{shot_spec_path.stem}.blend"


def link_environment(scene, environment_blend: Path):
    if not environment_blend.is_file():
        raise SystemExit(f"environment blend not found: {environment_blend}; build it first")
    with bpy.data.libraries.load(str(environment_blend), link=True) as (src, dst):
        names = [name for name in ("ENV", "ENV_ASSETS", "ENV_LIGHTS") if name in src.collections]
        dst.collections = names
        dst.worlds = ["AssetWorld"] if "AssetWorld" in src.worlds else []
    for collection in dst.collections:
        scene.collection.children.link(collection)
    if dst.worlds:
        scene.world = dst.worlds[0]
    return dst


def resolve_build_mode(requested: str, spec_path: Path, spec: dict, shot: dict | None, legacy: bool) -> str:
    if requested != "auto":
        return requested
    if legacy:
        return "inline"
    if shot is None:
        return "environment"
    env_spec_path = Path(str(spec.get("environment_spec") or "")).resolve()
    if environment_blend_path(env_spec_path).is_file():
        return "shot"
    return "inline"


def main():
    args = parse_args()
    spec_path = Path(args.spec).resolve()
    raw_spec = load_json(spec_path)
    legacy = "kind" not in raw_spec and "terrain" in raw_spec
    spec, shot = resolve_spec(spec_path)
    args.build = resolve_build_mode(args.build, spec_path, spec, shot, legacy)
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
    if args.build == "environment":
        out = environment_blend_path(spec_path)
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
            "build": args.build,
        }, ensure_ascii=False, indent=2))
        return

    if profile:
        render["profile"] = profile
    grammar = load_visual_grammar(spec.get("visual_grammar") or spec.get("style"))
    builder = (grammar or {}).get("builder") or {}
    manifest_core = load_manifest_core()
    addons = addon_versions()
    env_blend = None
    extra_inputs = None
    if args.build == "shot":
        env_spec_path = Path(str(spec.get("environment_spec") or "")).resolve()
        env_blend = environment_blend_path(env_spec_path)
        if not env_blend.is_file():
            raise SystemExit(f"environment blend not found: {env_blend}; build the environment first")
        extra_inputs = {"environment_blend": manifest_core.hash_path(env_blend)}
    prepared = manifest_core.prepare(
        spec_path=spec_path,
        spec=spec,
        render=render,
        out=out,
        builder_path=Path(__file__),
        builder_version=manifest_core.BUILDER_VERSION,
        blender_version=bpy.app.version_string,
        python_version=sys.version.split()[0],
        addons=addons,
        library_path=library_path,
        manifest_dir=Path(args.manifest_dir) if args.manifest_dir else None,
        use_cache=args.cache,
        visual_grammar=spec.get("visual_grammar") or spec.get("style"),
        grammar_path=Path(__file__).resolve().parents[1] / "shared/grammars/style-presets.json",
        seed=int(spec.get("seed", 0)),
        build_kind=args.build,
        extra_inputs=extra_inputs,
    )
    if prepared.cache_hit:
        print(f"ASSET_SCENE_CACHED {prepared.cached_manifest} {out}")
        return
    log_path = prepared.log_path
    manifest_path = prepared.manifest_path
    build_id = prepared.manifest["build_id"]
    temp_out = out.parent / f".{out.stem}.{build_id}.tmp{out.suffix}"
    out.parent.mkdir(parents=True, exist_ok=True)
    started = manifest_core.start_clock()
    manifest_core.log_line(log_path, f"spec={spec_path}")
    manifest_core.log_line(log_path, f"cache_key={prepared.manifest['cache_key']}")
    manifest_core.log_line(log_path, f"render={json.dumps(render, ensure_ascii=False, sort_keys=True)}")
    if env_blend is not None:
        manifest_core.log_line(log_path, f"environment_blend={env_blend}")

    if args.build == "shot":
        clear()
        scene = bpy.context.scene
        link_environment(scene, env_blend)
        frames, fps = configure_render(scene, render, temp_out, grammar)
        add_wind(scene, spec.get("wind") or {}, spec, frames)
        camera_spec = dict(spec.get("camera") or {})
        if "lens" not in camera_spec and builder.get("lens_default") is not None:
            camera_spec["lens"] = float(builder["lens_default"])
        setup_camera(scene, camera_spec, frames, fps, str(spec.get("id") or "shot"))
        shot_lights = {
            "sun": (shot or {}).get("sun"),
            "lights": (shot or {}).get("lights") or [],
        }
        add_lights(scene, shot_lights)
        passes = render.get("passes") or []
        if passes:
            pass_dir = Path(str(render.get("pass_dir") or (out.parent / "passes")))
            setup_passes(scene, passes, pass_dir, str(spec.get("id") or "shot"))
        look_path = write_look(out, grammar)
        if look_path:
            manifest_core.log_line(log_path, f"look={look_path}")
        shot_blend = shot_blend_path(spec_path)
        shot_blend.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(shot_blend))
        manifest_core.log_line(log_path, f"shot_blend={shot_blend}")
        try:
            if frames > 1:
                bpy.ops.render.render(animation=True)
            else:
                bpy.ops.render.render(write_still=True)
            os.replace(str(temp_out), str(out))
        except Exception as exc:  # noqa: BLE001
            manifest_core.finalize(
                manifest_path, status="fail", output=out, temp_output=temp_out,
                elapsed_s=time.time() - started, error=f"{type(exc).__name__}: {exc}",
            )
            manifest_core.log_line(log_path, f"FAILED: {type(exc).__name__}: {exc}")
            raise
        manifest_core.finalize(
            manifest_path, status="pass", output=out, temp_output=temp_out, blend=shot_blend,
            elapsed_s=time.time() - started, error=None,
        )
        manifest_core.log_line(log_path, f"output={out}")
        print(f"ASSET_SCENE_DONE {out}")
        return

    clear()
    scene = bpy.context.scene
    frames, fps = configure_render(scene, render, temp_out, grammar)

    hdri = resolve(library, spec["hdri"], root)
    world_strength = spec.get("world_strength")
    if world_strength is None:
        world_strength = builder.get("world_strength", 1.0)
    setup_world(hdri, float(world_strength))
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
            falloff = float(terrain.get("edge_falloff", 0.0))
            if falloff > 0:
                bpy.context.view_layer.update()
                bpy.ops.object.modifier_apply(modifier=mod.name)
                half = float(terrain.get("size_m", 2400)) / 2.0
                for vertex in ground.data.vertices:
                    edge = max(abs(vertex.co.x), abs(vertex.co.y)) / half
                    if edge <= 0.65:
                        continue
                    t = min(1.0, (edge - 0.65) / 0.35)
                    smooth = t * t * (3 - 2 * t)
                    vertex.co.z *= max(0.0, 1.0 - falloff * smooth)
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

    if args.build != "environment":
        add_wind(scene, spec.get("wind") or {}, spec, frames)
        camera_spec = dict(spec.get("camera") or {})
        if "lens" not in camera_spec and builder.get("lens_default") is not None:
            camera_spec["lens"] = float(builder["lens_default"])
        setup_camera(scene, camera_spec, frames, fps, str(spec.get("id") or "shot"))

    add_lights(scene, spec)

    if args.build == "environment":
        look_path = write_look(out, grammar)
        if look_path:
            manifest_core.log_line(log_path, f"look={look_path}")
        prepare_environment_collections(scene)
        out.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(out))
        manifest_core.finalize(
            manifest_path, status="pass", output=out, temp_output=None, blend=out,
            elapsed_s=time.time() - started, error=None,
        )
        manifest_core.log_line(log_path, f"environment_blend={out}")
        print(f"ASSET_SCENE_DONE {out}")
        return

    passes = render.get("passes") or []
    if passes:
        pass_dir = Path(str(render.get("pass_dir") or (out.parent / "passes")))
        setup_passes(scene, passes, pass_dir, str(spec.get("id") or "shot"))

    look_path = write_look(out, grammar)
    if look_path:
        manifest_core.log_line(log_path, f"look={look_path}")
    bpy.ops.wm.save_as_mainfile(filepath=str(out.with_suffix(".blend")))
    manifest_core.log_line(log_path, f"blend={out.with_suffix('.blend')}")
    try:
        if frames > 1:
            bpy.ops.render.render(animation=True)
        else:
            bpy.ops.render.render(write_still=True)
        os.replace(str(temp_out), str(out))
    except Exception as exc:  # noqa: BLE001 - manifest records the failure
        manifest_core.finalize(
            manifest_path,
            status="fail",
            output=out,
            temp_output=temp_out,
            elapsed_s=time.time() - started,
            error=f"{type(exc).__name__}: {exc}",
        )
        manifest_core.log_line(log_path, f"FAILED: {type(exc).__name__}: {exc}")
        raise
    manifest_core.finalize(
        manifest_path,
        status="pass",
        output=out,
        temp_output=temp_out,
        blend=out.with_suffix(".blend"),
        elapsed_s=time.time() - started,
        error=None,
    )
    manifest_core.log_line(log_path, f"output={out}")
    print(f"ASSET_SCENE_DONE {out}")


if __name__ == "__main__":
    main()
