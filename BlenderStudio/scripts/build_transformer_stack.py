"""Build the R1 Transformer stack-explode Blender scene.

Run with:
  blender -b --factory-startup --python BlenderStudio/scripts/build_transformer_stack.py
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "BlenderStudio" / "scenes" / "01-transformer-demo" / "stack_explode.blend"


def material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.35
        bsdf.inputs["Metallic"].default_value = 0.15
    return mat


def add_cube(name: str, location, scale, mat, explode_to) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    obj.keyframe_insert(data_path="location", frame=1)
    obj.location = explode_to
    obj.keyframe_insert(data_path="location", frame=80)
    return obj


def add_label(text: str, location, size: float = 0.45) -> bpy.types.Object:
    curve = bpy.data.curves.new(type="FONT", name=f"label-{text}")
    curve.body = text
    curve.size = size
    obj = bpy.data.objects.new(f"label-{text}", curve)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (math.radians(90), 0, 0)
    return obj


def main() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.name != "Collection":
            bpy.data.collections.remove(collection)

    encoder_mat = material("EncoderOrange", (0.92, 0.38, 0.0, 1.0))
    decoder_mat = material("DecoderBlue", (0.18, 0.43, 0.70, 1.0))
    label_mat = material("LabelDark", (0.1, 0.1, 0.1, 1.0))

    for index in range(6):
        z = 0.8 + index * 1.35
        add_cube(
            f"encoder_{index + 1}",
            (-2.6, 0.0, z),
            (1.6, 1.6, 1.0),
            encoder_mat,
            (-3.4 - index * 0.08, 0.0, z + index * 0.05),
        )
        add_cube(
            f"decoder_{index + 1}",
            (2.6, 0.0, z),
            (1.6, 1.6, 1.0),
            decoder_mat,
            (3.4 + index * 0.08, 0.0, z + index * 0.05),
        )
        label = add_label(f"E{index + 1}", (-2.6, -0.86, z + 0.55), 0.34)
        label.data.materials.append(label_mat)
        label = add_label(f"D{index + 1}", (2.6, -0.86, z + 0.55), 0.34)
        label.data.materials.append(label_mat)

    # Central encoder -> decoder flow, so the eye stays between the stacks
    # after they separate.
    beam_mat = material("ContextBeam", (0.92, 0.38, 0.0, 1.0))
    beam_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (
        0.92, 0.38, 0.0, 1.0
    )
    beam_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 2.5
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.07, depth=4.6, location=(0.0, 0.0, 5.4),
        rotation=(0.0, math.radians(90), 0.0),
    )
    beam = bpy.context.active_object
    beam.name = "context_flow"
    beam.data.materials.append(beam_mat)
    bpy.ops.mesh.primitive_cone_add(
        radius1=0.22, depth=0.55, location=(2.45, 0.0, 5.4),
        rotation=(0.0, math.radians(90), 0.0),
    )
    arrow = bpy.context.active_object
    arrow.name = "context_arrow"
    arrow.data.materials.append(beam_mat)
    context_label = add_label("context", (0.0, -0.86, 5.85), 0.38)
    context_label.data.materials.append(label_mat)

    bpy.ops.object.camera_add(location=(0.0, -17.0, 6.8))
    camera = bpy.context.active_object
    camera.data.lens = 45
    direction = Vector((0.0, 0.0, 4.5)) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = camera

    bpy.ops.object.light_add(type="AREA", location=(6.0, -8.0, 12.0))
    key = bpy.context.active_object
    key.data.energy = 1400
    key.data.size = 8
    bpy.ops.object.light_add(type="AREA", location=(-7.0, -4.0, 7.0))
    fill = bpy.context.active_object
    fill.data.energy = 700
    fill.data.size = 7

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
        background.inputs[1].default_value = 0.85

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.fps = 30
    scene.frame_start = 1
    scene.frame_end = 750
    scene.eevee.taa_render_samples = 16
    scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = str(ROOT / "build" / "01-transformer-demo" / "blender" / "stack_explode.mp4")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(TARGET))
    print(f"SAVED {TARGET}")


if __name__ == "__main__":
    main()
