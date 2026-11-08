"""Build and render the POC hex world from simulation.json.

Run headless:
  blender -b -P world.py -- --sim build/primer-poc/simulation.json \
      --out build/primer-poc/world/world.mp4 --width 1280 --height 720 [--still png]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy


def hex_to_linear(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    rgb = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return tuple(linear)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
        for block in list(datablocks):
            datablocks.remove(block)


def simple_material(name: str, color: tuple[float, float, float], roughness: float = 0.7):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    return material


def object_color_material(name: str, roughness: float = 0.55):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    info = nodes.new("ShaderNodeObjectInfo")
    links.new(info.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    return material


def hex_prism(radius: float, height: float):
    verts = []
    for z in (0.0, height):
        for k in range(6):
            angle = math.radians(60 * k)
            verts.append((radius * math.cos(angle), radius * math.sin(angle), z))
    faces = [tuple(range(5, -1, -1)), tuple(range(6, 12))]
    for k in range(6):
        n = (k + 1) % 6
        faces.append((k, n, n + 6, k + 6))
    mesh = bpy.data.meshes.new("hex_tile")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def ico(name: str, radius: float, subdiv: int = 2):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdiv, radius=radius, location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    return obj


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--still", type=Path, default=None)
    args = parser.parse_args(argv)

    data = json.loads(args.sim.read_text(encoding="utf-8"))
    frames = data["frames_species"]
    cells = data["cells"]
    species_colors = [hex_to_linear(item["hex"]) for item in data["species"]]

    clear_scene()
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.fps = data.get("fps", 30)
    scene.frame_start = 1
    scene.frame_end = len(frames)
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"

    world = bpy.data.worlds.new("slate")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (*hex_to_linear("#2D3033"), 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
    scene.world = world

    ground = bpy.data.meshes.new("ground")
    ground.from_pydata(
        [(-30, -30, -0.05), (30, -30, -0.05), (30, 30, -0.05), (-30, 30, -0.05)],
        [],
        [(0, 1, 2, 3)],
    )
    ground.update()
    ground_obj = bpy.data.objects.new("ground", ground)
    bpy.context.collection.objects.link(ground_obj)
    ground_obj.data.materials.append(simple_material("ground_mat", hex_to_linear("#26292C"), 0.95))

    tile_mat = object_color_material("tile_color", roughness=0.9)
    tile_mesh = hex_prism(0.99, 0.14)
    tiles = []
    for cell in cells:
        tile = bpy.data.objects.new(f"tile_{cell['q']}_{cell['r']}", tile_mesh)
        bpy.context.collection.objects.link(tile)
        tile.location = (cell["x"], cell["y"], 0.0)
        tile.data.materials.append(tile_mat)
        tiles.append(tile)

    body_mat = object_color_material("blob_body")
    eye_mat = simple_material("blob_eye", (0.012, 0.012, 0.014), 0.3)
    body = ico("blob_body", 0.30, 2)
    body.scale = (1.0, 0.86, 1.12)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    body.data.materials.append(body_mat)
    eyes = []
    for side in (-1, 1):
        eye = ico(f"eye_{side}", 0.048, 1)
        eye.location = (0.095 * side, -0.235, 0.105)
        eye.data.materials.append(eye_mat)
        eyes.append(eye)
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    for eye in eyes:
        eye.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    template = bpy.context.object
    template.name = "blob_template"
    template.data.materials.clear()
    template.data.materials.append(body_mat)
    template.data.materials.append(eye_mat)

    camera_target = bpy.data.objects.new("camera_target", None)
    bpy.context.collection.objects.link(camera_target)
    camera_target.location = (0, 0, 0.25)
    cam_data = bpy.data.cameras.new("camera")
    cam_data.lens = 52
    camera = bpy.data.objects.new("camera", cam_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    track = camera.constraints.new("TRACK_TO")
    track.target = camera_target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    camera.location = (14.0, -18.0, 16.0)
    camera.keyframe_insert("location", frame=1)
    camera.location = (17.0, -14.0, 15.0)
    camera.keyframe_insert("location", frame=len(frames) // 2)
    camera.location = (13.5, -18.5, 16.3)
    camera.keyframe_insert("location", frame=len(frames))

    key = bpy.data.lights.new("key", "AREA")
    key.energy = 1900
    key.size = 10
    key_obj = bpy.data.objects.new("key", key)
    bpy.context.collection.objects.link(key_obj)
    key_obj.location = (6, -6, 14)
    key_obj.rotation_euler = (math.radians(35), 0, math.radians(35))
    fill = bpy.data.lights.new("fill", "AREA")
    fill.energy = 520
    fill.size = 12
    fill_obj = bpy.data.objects.new("fill", fill)
    bpy.context.collection.objects.link(fill_obj)
    fill_obj.location = (-8, -3, 8)
    fill_obj.rotation_euler = (math.radians(55), 0, math.radians(-55))

    phase = {index: (index * 0.7) % (2 * math.pi) for index in range(len(cells))}
    objects = []
    for index, cell in enumerate(cells):
        blob = bpy.data.objects.new(f"blob_{index}", template.data)
        bpy.context.collection.objects.link(blob)
        blob.location = (cell["x"], cell["y"], 0.36)
        blob.rotation_euler = (0, 0, math.atan2(camera.location.x, -camera.location.y))
        objects.append(blob)

    slate = hex_to_linear("#3D4349")
    def tile_color(species_index):
        color = species_colors[species_index]
        return tuple(slate[k] * 0.72 + color[k] * 0.28 for k in range(3))

    for index, blob in enumerate(objects):
        tile = tiles[index]
        current = frames[0][index]
        blob.color = (*species_colors[current], 1.0)
        blob.keyframe_insert("color", frame=1)
        tile.color = (*tile_color(current), 1.0)
        tile.keyframe_insert("color", frame=1)
        for frame_index in range(1, len(frames)):
            value = frames[frame_index][index]
            if value != current:
                blob.color = (*species_colors[current], 1.0)
                blob.keyframe_insert("color", frame=frame_index)
                blob.color = (*species_colors[value], 1.0)
                blob.keyframe_insert("color", frame=frame_index + 1)
                tile.color = (*tile_color(current), 1.0)
                tile.keyframe_insert("color", frame=frame_index)
                tile.color = (*tile_color(value), 1.0)
                tile.keyframe_insert("color", frame=frame_index + 1)
                current = value
        for frame_index in range(0, len(frames), 4):
            z = 0.36 + 0.035 * math.sin(phase[index] + frame_index * 0.09)
            blob.location.z = z
            blob.keyframe_insert("location", index=2, frame=frame_index + 1)

    bpy.ops.object.select_all(action="DESELECT")
    template.hide_render = True
    template.hide_viewport = True

    if args.still is not None:
        scene.frame_set(1)
        scene.render.filepath = str(args.still)
        bpy.ops.render.render(write_still=True)
        print(f"still={args.still}")
        return 0

    frames_dir = args.out.parent / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(frames_dir / "frame_")
    bpy.ops.render.render(animation=True)
    print(f"frames={frames_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
