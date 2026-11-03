from __future__ import annotations

from .contracts import ModelPlan


def fallback_script(plan: ModelPlan) -> str:
    """Deterministic primitive builder used when the coder cannot produce safe code."""
    parts = [
        {
            "id": part.id,
            "geometry": part.geometry,
            "size": list(part.size),
        }
        for part in plan.parts
    ]
    lines = [
        "# Fallback builder generated from model_plan.json.",
        "import bpy",
        "",
        f"PARTS = {parts!r}",
        "",
        "",
        "def build():",
        "    for part in PARTS:",
        "        geometry = part['geometry']",
        "        size = part['size']",
        "        if geometry == 'cylinder':",
        "            bpy.ops.mesh.primitive_cylinder_add(radius=size[0] / 2, depth=size[2])",
        "        elif geometry == 'sphere':",
        "            bpy.ops.mesh.primitive_uv_sphere_add(radius=size[0] / 2)",
        "        elif geometry == 'cone':",
        "            bpy.ops.mesh.primitive_cone_add(radius1=size[0] / 2, radius2=0, depth=size[2])",
        "        elif geometry == 'torus':",
        "            minor = max(size[2] / 2, 0.001)",
        "            major = max(size[0] / 2 - minor, 0.002)",
        "            bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor)",
        "        elif geometry == 'curved_surface':",
        "            bpy.ops.mesh.primitive_uv_sphere_add(radius=size[0] / 2)",
        "        else:",
        "            bpy.ops.mesh.primitive_cube_add(size=1)",
        "        obj = bpy.context.active_object",
        "        obj.name = part['id']",
        "",
    ]
    return "\n".join(lines)
