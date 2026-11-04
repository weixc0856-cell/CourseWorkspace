"""Task IR v2 executor: validate, build, save, render."""

from __future__ import annotations

import random

import bpy

from . import animation, cameras, geometry_nodes, lighting, materials, objects, rendering
from . import scene as scene_ops
from .task_schema import STANDARD_COLLECTIONS, TaskError, validate_task


def execute(task, cwd=None):
    spec = validate_task(task, cwd=cwd)
    scene_spec = spec["scene"]

    if spec["base_blend"]:
        scene_ops.open_base_blend(spec["base_blend"])
        scene = scene_ops.rename_scene(scene_spec["name"])
        if scene.name != scene_spec["name"]:
            raise RuntimeError(f"scene name is already taken: {scene_spec['name']}")
    else:
        scene = scene_ops.reset_scene(scene_spec["name"])
        if scene.name != scene_spec["name"]:
            raise RuntimeError(f"cannot name scene: {scene_spec['name']}")

    random.seed(scene_spec["seed"])
    scene["scene_task_id"] = spec["task_id"]
    scene["scene_seed"] = scene_spec["seed"]

    scene_ops.configure_units(scene, scene_spec["units"], scene_spec["unit_scale"])
    scene_ops.configure_timeline(
        scene, scene_spec["fps"], scene_spec["frame_start"], scene_spec["frame_end"]
    )
    extra_collections = [
        path for path in spec["collections"] if path not in STANDARD_COLLECTIONS
    ]
    scene_ops.ensure_standard_collections(extra_collections)
    scene_ops.configure_world(scene, spec["world"])

    material_map = materials.build_materials(spec["materials"], cwd)
    object_map = objects.create_objects(spec["objects"], material_map, spec["task_id"])
    applied_modifiers = 0
    for object_spec in spec["objects"]:
        entries = object_spec.get("geometry_nodes") or []
        if not entries:
            continue
        applied = geometry_nodes.apply_to_object(
            object_map[object_spec["id"]], entries, materials=material_map, workspace=cwd
        )
        applied_modifiers += len(applied)
    cameras.create_cameras(spec["cameras"], spec["task_id"])
    lighting.create_lights(spec["lights"], spec["task_id"])
    if scene.camera is None:
        raise TaskError("render requires an active scene camera")

    keyframe_count = animation.apply_animations(spec["animations"], scene)
    rendering.configure(scene, spec["render"])

    print(f"BLENDER_TASK_SCHEMA {spec['schema_version']}")
    print(f"BLENDER_TASK_ID {spec['task_id']}")
    print(f"BLENDER_TASK_LESSON {spec['lesson']}")
    print(f"BLENDER_SCENE {scene.name}")
    print(f"BLENDER_SCENE_OBJECTS {len(object_map)}")
    print(f"BLENDER_SCENE_MATERIALS {len(material_map)}")
    print(f"BLENDER_GEOMETRY_NODES {applied_modifiers}")
    print(f"BLENDER_SCENE_CAMERAS {len(spec['cameras'])}")
    print(f"BLENDER_SCENE_LIGHTS {len(spec['lights'])}")
    print(f"BLENDER_ANIMATION_KEYFRAMES {keyframe_count}")
    print(f"BLENDER_TASK_ENGINE {scene.render.engine}")
    print(f"BLENDER_TASK_RES {scene.render.resolution_x}x{scene.render.resolution_y}")
    print(f"BLENDER_TASK_FPS {scene.render.fps}")
    print(f"BLENDER_TASK_FRAMES {scene.frame_start}-{scene.frame_end}")
    print(f"BLENDER_TASK_FORMAT {spec['render']['format']}")
    print(f"BLENDER_TASK_OUT {spec['render']['output']}")

    if spec["render"]["save_blend"]:
        scene_ops.save_blend(spec["render"]["save_blend"])
        print(f"BLENDER_SCENE_BLEND {spec['render']['save_blend']}")

    rendering.render(scene, spec["render"])
    print("BLENDER_TASK_OK")
