"""Data-level geometry creation with bmesh (no context-dependent operators)."""

from __future__ import annotations

import math

import bmesh
import bpy

from .task_schema import TaskError


def _torus(bm, params):
    major = params["major_radius"]
    minor = params["minor_radius"]
    major_segments = params["major_segments"]
    minor_segments = params["minor_segments"]
    if minor >= major:
        raise TaskError("TORUS minor_radius must be smaller than major_radius")
    rings = []
    for i in range(major_segments):
        theta = math.tau * i / major_segments
        ring = []
        for j in range(minor_segments):
            phi = math.tau * j / minor_segments
            radius = major + minor * math.cos(phi)
            ring.append(
                bm.verts.new((radius * math.cos(theta), radius * math.sin(theta), minor * math.sin(phi)))
            )
        rings.append(ring)
    for i in range(major_segments):
        next_i = (i + 1) % major_segments
        for j in range(minor_segments):
            next_j = (j + 1) % minor_segments
            bm.faces.new(
                (rings[i][j], rings[next_i][j], rings[next_i][next_j], rings[i][next_j])
            )


def _fill_bmesh(bm, primitive, params):
    if primitive == "CUBE":
        bmesh.ops.create_cube(bm, size=params["size"], calc_uvs=True)
    elif primitive == "PLANE":
        bmesh.ops.create_grid(
            bm, x_segments=1, y_segments=1, size=params["size"], calc_uvs=True
        )
    elif primitive == "GRID":
        bmesh.ops.create_grid(
            bm,
            x_segments=params["x_segments"],
            y_segments=params["y_segments"],
            size=params["size"],
            calc_uvs=True,
        )
    elif primitive == "UV_SPHERE":
        bmesh.ops.create_uvsphere(
            bm,
            u_segments=params["u_segments"],
            v_segments=params["v_segments"],
            radius=params["radius"],
            calc_uvs=True,
        )
    elif primitive == "ICO_SPHERE":
        bmesh.ops.create_icosphere(
            bm,
            subdivisions=params["subdivisions"],
            radius=params["radius"],
            calc_uvs=True,
        )
    elif primitive == "CYLINDER":
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            cap_tris=False,
            segments=params["vertices"],
            radius1=params["radius"],
            radius2=params["radius"],
            depth=params["depth"],
            calc_uvs=True,
        )
    elif primitive == "CONE":
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            cap_tris=False,
            segments=params["vertices"],
            radius1=params["radius1"],
            radius2=params["radius2"],
            depth=params["depth"],
            calc_uvs=True,
        )
    elif primitive == "CIRCLE":
        bmesh.ops.create_circle(
            bm,
            cap_ends=params["fill"],
            cap_tris=False,
            segments=params["vertices"],
            radius=params["radius"],
            calc_uvs=True,
        )
    elif primitive == "TORUS":
        _torus(bm, params)
    else:  # validated earlier; keep the executor total
        raise TaskError(f"unsupported primitive: {primitive}")


def build_text(name, spec):
    """Create a text data-block using Blender's built-in font.

    The built-in font is used deliberately: no external font file is loaded, so
    the scene stays reproducible and no extra asset dependency is introduced.
    """
    curve = bpy.data.curves.new(name, type="FONT")
    curve.body = spec["body"]
    curve.size = spec["size"]
    curve.align_x = spec["align_x"]
    curve.align_y = spec["align_y"]
    curve.extrude = spec["extrude"]
    curve.bevel_depth = spec["bevel_depth"]
    curve.space_line = spec["space_line"]
    if not curve.body.strip():
        raise TaskError("text body must not be blank")
    return curve


def build_curve(name, spec):
    """Create a 3D polyline curve with a round bevel profile."""
    points = spec["points"]
    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 6
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, coordinate in zip(spline.points, points):
        point.co = (coordinate[0], coordinate[1], coordinate[2], 1.0)
    spline.use_cyclic_u = spec["cyclic"]
    curve.bevel_depth = spec["bevel_depth"]
    curve.bevel_resolution = 3
    curve.use_fill_caps = True
    if not curve.splines or not curve.splines[0].points:
        raise TaskError("curve produced no points")
    return curve


def build_mesh(name, primitive, params, smooth=False):
    bm = bmesh.new()
    try:
        _fill_bmesh(bm, primitive, params)
        if not bm.verts:
            raise TaskError(f"primitive {primitive} produced no vertices")
        mesh = bpy.data.meshes.new(name)
        bm.to_mesh(mesh)
    finally:
        bm.free()
    mesh.validate(verbose=False)
    mesh.update()
    if not mesh.vertices:
        raise TaskError(f"primitive {primitive} produced an empty mesh")
    if smooth:
        for polygon in mesh.polygons:
            polygon.use_smooth = True
    return mesh
