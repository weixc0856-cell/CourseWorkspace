"""Shader-node material templates driven by the task contract."""

from __future__ import annotations

import json
import os

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


def _srgb_to_linear(value):
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _load_colormaps(workspace):
    path = os.path.join(workspace or os.getcwd(), "shared", "colormaps.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["colormaps"]


def _build_scientific(tree, output, params, material, workspace):
    colormaps = _load_colormaps(workspace)
    colormap = colormaps.get(params["colormap"])
    if colormap is None:
        raise TaskError(f"unknown colormap: {params['colormap']}")

    attribute = tree.nodes.new("ShaderNodeAttribute")
    attribute.location = (-1000.0, 0.0)
    attribute.attribute_name = params["source_attribute"]

    mapping = tree.nodes.new("ShaderNodeMapRange")
    mapping.location = (-760.0, 0.0)
    mapping.clamp = True
    _set(mapping, "From Min", params["min_value"])
    _set(mapping, "From Max", params["max_value"])
    _set(mapping, "To Min", 0.0)
    _set(mapping, "To Max", 1.0)

    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-520.0, 0.0)
    stops = colormap["stops"]
    elements = ramp.color_ramp.elements
    while len(elements) > 1:
        elements.remove(elements[-1])
    first = elements[0]
    first.position = stops[0][0]
    first.color = tuple(_srgb_to_linear(channel) for channel in stops[0][1]) + (1.0,)
    for position, color in stops[1:]:
        element = elements.new(position)
        element.color = tuple(_srgb_to_linear(channel) for channel in color) + (1.0,)

    emission = tree.nodes.new("ShaderNodeEmission")
    emission.location = (-280.0, 0.0)
    _set(emission, "Strength", 1.0)

    tree.links.new(attribute.outputs["Fac"], mapping.inputs["Value"])
    tree.links.new(mapping.outputs["Result"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], emission.inputs["Color"])
    tree.links.new(emission.outputs[0], output.inputs["Surface"])

    material["colormap_name"] = params["colormap"]
    material["source_attribute"] = params["source_attribute"]
    material["min_value"] = params["min_value"]
    material["max_value"] = params["max_value"]
    material["units"] = params["units"]
    material.diffuse_color = (0.5, 0.5, 0.5, 1.0)


def build_material(spec, workspace=None):
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
        _set(shader, "Coat Weight", params["coat_weight"])
        _set(shader, "Coat Roughness", params["coat_roughness"])
        if params["bump_strength"] > 0.0:
            noise = tree.nodes.new("ShaderNodeTexNoise")
            noise.location = (-600.0, -300.0)
            noise.inputs["Scale"].default_value = params["bump_scale"]
            noise.inputs["Detail"].default_value = params["bump_detail"]
            bump = tree.nodes.new("ShaderNodeBump")
            bump.location = (-300.0, -300.0)
            bump.inputs["Strength"].default_value = params["bump_strength"]
            bump.inputs["Distance"].default_value = params["bump_distance"]
            tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
            tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])
        material.metallic = params["metallic"]
        material.roughness = params["roughness"]
        material.diffuse_color = params["base_color"]
        _enable_alpha(material, params["alpha"])
    elif spec["shader"] == "emission":
        shader = tree.nodes.new("ShaderNodeEmission")
        shader.location = (0.0, 0.0)
        _set(shader, "Color", params["color"])
        _set(shader, "Strength", params["strength"])
        material.diffuse_color = params["color"]
    else:
        _build_scientific(tree, output, params, material, workspace)

    if spec["shader"] != "scientific_colormap":
        tree.links.new(shader.outputs[0], output.inputs["Surface"])
    return material


def build_materials(specs, workspace=None):
    return {
        material_id: build_material(spec, workspace)
        for material_id, spec in specs.items()
    }
