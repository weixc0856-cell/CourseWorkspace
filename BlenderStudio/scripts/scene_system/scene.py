"""Scene graph primitives: reset, collections, units, timeline, save."""

from __future__ import annotations

import os

import bpy

from .task_schema import STANDARD_COLLECTIONS, TaskError


def reset_scene(name):
    """Remove every object and collection, then name the active scene."""
    scene = bpy.context.scene
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    orphan_meshes = [mesh for mesh in bpy.data.meshes if mesh.users == 0]
    for mesh in orphan_meshes:
        bpy.data.meshes.remove(mesh)
    scene.name = name
    return scene


def rename_scene(name):
    scene = bpy.context.scene
    scene.name = name
    return scene


def _find_child(parent, name):
    for child in parent.children:
        if child.name == name:
            return child
    return None


def ensure_collection(path):
    """Create (or reuse) a nested collection path under the scene root."""
    parent = bpy.context.scene.collection
    for part in path.split("/"):
        child = _find_child(parent, part)
        if child is None:
            child = bpy.data.collections.new(part)
            parent.children.link(child)
        parent = child
    return parent


def ensure_standard_collections(extra=()):
    for path in (*STANDARD_COLLECTIONS, *extra):
        ensure_collection(path)


def assign_collection(obj, path):
    collection = ensure_collection(path)
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    collection.objects.link(obj)


def configure_units(scene, units, unit_scale):
    scene.unit_settings.system = units
    scene.unit_settings.scale_length = unit_scale


def configure_timeline(scene, fps, frame_start, frame_end):
    scene.render.fps = fps
    scene.render.fps_base = 1.0
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.frame_set(frame_start)


def open_base_blend(path):
    if not os.path.isfile(path):
        raise TaskError(f"base_blend not found: {path}")
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(path))


def save_blend(path):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path))


def ensure_world(scene):
    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        scene.world = world
    return world


def configure_world(scene, world_spec):
    world = ensure_world(scene)
    if world_spec is None:
        return
    # Blender 5.2 still supports nodes; the deprecation is scheduled for 6.0.
    if not world.use_nodes:
        world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is None:
        raise TaskError("world node tree is missing the Background node")
    background.inputs["Color"].default_value = world_spec["background_color"]
    background.inputs["Strength"].default_value = world_spec["strength"]
