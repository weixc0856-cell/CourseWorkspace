"""Shader-node material templates driven by the task contract."""

from __future__ import annotations

import bpy

from .task_schema import TaskError


def _socket(node, name):
    socket = node.inputs.get(name)
    if socket is None:
        raise TaskError(f"node {node.bl_idname} has no input socket named {name!r}")
    return socket


def _set(node, name, value):
    _socket(node, name).default_value = value


def _enable_alpha(material, alpha):
    if alpha >= 1.0:
        return
    if hasattr(material, "surface_render_method"):
        material.surface_render_method = "BLENDED"
    elif hasattr(material, "blend_method"):
        material.blend_method = "BLEND"


def build_material(spec):
    material_id = spec["id"]
    if material_id in bpy.data.materials:
        raise TaskError(f"material already exists in base scene: {material_id}")
    material = bpy.data.materials.new(material_id)
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()

    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (400.0, 0.0)

    params = spec["params"]
    if spec["shader"] == "principled":
        shader = tree.nodes.new("ShaderNodeBsdfPrincipled")
        shader.location = (0.0, 0.0)
        _set(shader, "Base Color", params["base_color"])
        _set(shader, "Metallic", params["metallic"])
        _set(shader, "Roughness", params["roughness"])
        _set(shader, "Alpha", params["alpha"])
        _set(shader, "IOR", params["ior"])
        _set(shader, "Emission Color", params["emission_color"])
        _set(shader, "Emission Strength", params["emission_strength"])
        material.metallic = params["metallic"]
        material.roughness = params["roughness"]
        material.diffuse_color = params["base_color"]
        _enable_alpha(material, params["alpha"])
    else:
        shader = tree.nodes.new("ShaderNodeEmission")
        shader.location = (0.0, 0.0)
        _set(shader, "Color", params["color"])
        _set(shader, "Strength", params["strength"])
        material.diffuse_color = params["color"]

    tree.links.new(shader.outputs[0], output.inputs["Surface"])
    return material


def build_materials(specs):
    return {material_id: build_material(spec) for material_id, spec in specs.items()}
