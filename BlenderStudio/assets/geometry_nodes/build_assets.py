"""Build the reusable Geometry Nodes asset library.

Run with Blender:
    blender --background --factory-startup --python-exit-code 1 \
        --python BlenderStudio/assets/geometry_nodes/build_assets.py

The generated gn_library.blend is a source asset and is committed.
"""

from __future__ import annotations

import os

import bpy

WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUTPUT = os.path.join(WORKSPACE, "BlenderStudio", "assets", "geometry_nodes", "gn_library.blend")


def _input(ng, name, socket_type, default=None, minimum=None, maximum=None):
    socket = ng.interface.new_socket(name=name, in_out="INPUT", socket_type=socket_type)
    if default is not None:
        socket.default_value = default
    if minimum is not None:
        socket.min_value = minimum
    if maximum is not None:
        socket.max_value = maximum
    return socket


def _output(ng, name):
    ng.interface.new_socket(name=name, in_out="OUTPUT", socket_type="NodeSocketGeometry")


def build_displace_noise():
    ng = bpy.data.node_groups.new("GN_DisplaceNoise", "GeometryNodeTree")
    ng.description = "Displace geometry along a 4D noise field."
    _input(ng, "Geometry", "NodeSocketGeometry")
    _input(ng, "Scale", "NodeSocketFloat", 2.0, 0.0, 1000.0)
    _input(ng, "Strength", "NodeSocketFloat", 0.2, 0.0, 100.0)
    _input(ng, "Seed", "NodeSocketInt", 0, 0, 1000000)
    _output(ng, "Geometry")

    nodes = ng.nodes
    links = ng.links
    group_in = nodes.new("NodeGroupInput")
    group_in.location = (-600, 0)
    group_out = nodes.new("NodeGroupOutput")
    group_out.location = (600, 0)
    position = nodes.new("GeometryNodeInputPosition")
    position.location = (-600, -250)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-350, -150)
    noise.noise_dimensions = "4D"
    subtract = nodes.new("ShaderNodeVectorMath")
    subtract.location = (-100, -200)
    subtract.operation = "SUBTRACT"
    subtract.inputs[1].default_value = (0.5, 0.5, 0.5)
    scale = nodes.new("ShaderNodeVectorMath")
    scale.location = (100, -200)
    scale.operation = "SCALE"
    set_position = nodes.new("GeometryNodeSetPosition")
    set_position.location = (350, 0)

    links.new(position.outputs["Position"], noise.inputs["Vector"])
    links.new(group_in.outputs["Scale"], noise.inputs["Scale"])
    links.new(group_in.outputs["Seed"], noise.inputs["W"])
    links.new(noise.outputs["Color"], subtract.inputs[0])
    links.new(subtract.outputs["Vector"], scale.inputs[0])
    links.new(group_in.outputs["Strength"], scale.inputs["Scale"])
    links.new(group_in.outputs["Geometry"], set_position.inputs["Geometry"])
    links.new(scale.outputs["Vector"], set_position.inputs["Offset"])
    links.new(set_position.outputs["Geometry"], group_out.inputs["Geometry"])
    return ng


def build_scatter_cubes():
    ng = bpy.data.node_groups.new("GN_ScatterCubes", "GeometryNodeTree")
    ng.description = "Scatter instanced cubes over input faces."
    _input(ng, "Geometry", "NodeSocketGeometry")
    _input(ng, "Density", "NodeSocketFloat", 20.0, 0.0, 100000.0)
    _input(ng, "Scale", "NodeSocketFloat", 1.0, 0.0, 1000.0)
    _input(ng, "Seed", "NodeSocketInt", 0, 0, 1000000)
    _input(ng, "Material", "NodeSocketMaterial")
    _output(ng, "Geometry")

    nodes = ng.nodes
    links = ng.links
    group_in = nodes.new("NodeGroupInput")
    group_in.location = (-600, 0)
    group_out = nodes.new("NodeGroupOutput")
    group_out.location = (600, 0)
    distribute = nodes.new("GeometryNodeDistributePointsOnFaces")
    distribute.location = (-300, 0)
    cube = nodes.new("GeometryNodeMeshCube")
    cube.location = (-300, -300)
    cube.inputs["Size"].default_value = (0.2, 0.2, 0.2)
    instance = nodes.new("GeometryNodeInstanceOnPoints")
    instance.location = (150, 0)
    realize = nodes.new("GeometryNodeRealizeInstances")
    realize.location = (400, 0)
    set_material = nodes.new("GeometryNodeSetMaterial")
    set_material.location = (600, 0)

    links.new(group_in.outputs["Geometry"], distribute.inputs["Mesh"])
    links.new(group_in.outputs["Density"], distribute.inputs["Density"])
    links.new(group_in.outputs["Seed"], distribute.inputs["Seed"])
    links.new(distribute.outputs["Points"], instance.inputs["Points"])
    links.new(cube.outputs["Mesh"], instance.inputs["Instance"])
    links.new(group_in.outputs["Scale"], instance.inputs["Scale"])
    links.new(instance.outputs["Instances"], realize.inputs["Geometry"])
    links.new(realize.outputs["Geometry"], set_material.inputs["Geometry"])
    links.new(group_in.outputs["Material"], set_material.inputs["Material"])
    links.new(set_material.outputs["Geometry"], group_out.inputs["Geometry"])
    return ng


def main():
    for group in list(bpy.data.node_groups):
        bpy.data.node_groups.remove(group)
    groups = [build_displace_noise(), build_scatter_cubes()]
    for group in groups:
        group.use_fake_user = True
        group.asset_mark()
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=OUTPUT, check_existing=False)
    for group in groups:
        sockets = [
            item.name
            for item in group.interface.items_tree
            if item.item_type == "SOCKET"
        ]
        print(f"GN_ASSET {group.name} SOCKETS {sockets}")
    print(f"GN_LIBRARY {OUTPUT}")


if __name__ == "__main__":
    main()
