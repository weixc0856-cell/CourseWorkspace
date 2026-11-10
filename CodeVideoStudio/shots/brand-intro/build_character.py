"""Build the WAYNE creator-robot in Blender and export it for the three.js shot.

Designed from the reference image the user supplied: a small creator robot with a
large helmet-like head, a dark glossy visor with two warm eyes, copper trim, side
ear discs, an antenna, a compact body, segmented arms with gripper hands and short
articulated legs. White ceramic / warm gray / graphite / copper / dark glass.

Blender is Z-up; the exporter converts to three.js Y-up (x, z, -y).

Run headless:
  blender.exe --background --factory-startup --python build_character.py -- <out_dir>

Writes character.blend, character.json, character-front.png (and 45/side/back).
"""

import json
import math
import os
import sys

import bpy
from mathutils import Vector, noise as mnoise

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0]) if argv else os.path.abspath(".")

SEG, RING = 32, 20
PARTS = []      # (obj, group, material_key, pivot)
GROUPS = [      # (name, parent, pivot)
    ("Body", "Root", (0.0, 0.0, 0.145)),
    ("Head", "Body", (0.0, 0.0, 0.290)),
    ("ShoulderL", "Body", (-0.098, 0.0, 0.255)),
    ("ShoulderR", "Body", (0.098, 0.0, 0.255)),
    ("ElbowL", "ShoulderL", (-0.128, 0.0, 0.170)),
    ("ElbowR", "ShoulderR", (0.128, 0.0, 0.170)),
    ("HipL", "Root", (-0.055, 0.0, 0.140)),
    ("HipR", "Root", (0.055, 0.0, 0.140)),
    ("KneeL", "HipL", (-0.060, 0.0, 0.075)),
    ("KneeR", "HipR", (0.060, 0.0, 0.075)),
]
GROUP_PIVOT = {name: Vector(pivot) for name, _, pivot in GROUPS}


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def material(name, base, roughness=0.5, metallic=0.0, emission=None, strength=0.0, coat=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if coat:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = 0.15
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = strength
    return mat


MATS = {
    "ceramic": material("ceramic", (0.955, 0.948, 0.930), roughness=0.42, coat=0.12),
    "warmgray": material("warmgray", (0.760, 0.735, 0.690), roughness=0.58),
    "graphite": material("graphite", (0.055, 0.062, 0.070), roughness=0.42, metallic=0.35),
    "copper": material("copper", (0.620, 0.300, 0.145), roughness=0.28, metallic=0.9),
    "visor": material("visor", (0.006, 0.008, 0.012), roughness=0.16, metallic=0.10, coat=1.0),
    "eye": material("eye", (1.0, 0.36, 0.12), roughness=0.3, emission=(1.0, 0.30, 0.08), strength=1.5),
    "orange": material("orange", (0.80, 0.18, 0.045), roughness=0.32, emission=(0.80, 0.18, 0.045), strength=1.2),
}


def smooth(obj):
    for poly in obj.data.polygons:
        poly.use_smooth = True
    return obj


def register(obj, group, mat, pivot):
    obj.data.materials.clear()
    obj.data.materials.append(MATS[mat])
    PARTS.append((obj, group, mat, Vector(pivot)))
    return obj


def sphere(name, loc, scale, group, mat, segments=SEG, rings=RING):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings,
                                         radius=1.0, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    smooth(obj)
    return register(obj, group, mat, GROUP_PIVOT[group])


def box(name, size, loc, group, mat, bevel=0.004, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    smooth(obj)
    return register(obj, group, mat, GROUP_PIVOT[group])


def cylinder(name, radius, depth, loc, group, mat, rot=(0, 0, 0), vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth,
                                        location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    smooth(obj)
    return register(obj, group, mat, GROUP_PIVOT[group])


def torus(name, major, minor, loc, group, mat, rot=(0, 0, 0), scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     major_segments=48, minor_segments=12,
                                     location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    smooth(obj)
    return register(obj, group, mat, GROUP_PIVOT[group])


def rod(name, base, direction, length, radius, group, mat, vertices=16):
    d = Vector(direction).normalized()
    center = Vector(base) + d * (length / 2)
    rot = Vector((0, 0, 1)).rotation_difference(d).to_euler()
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=length,
                                        location=center, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    smooth(obj)
    return register(obj, group, mat, GROUP_PIVOT[group])




def sculpt(obj, dents=(), seams=(), chip=0.00025):
    """A small sculpt pass in local space: dents, seam grooves, surface noise."""
    mesh = obj.data
    for v in mesh.vertices:
        n = v.normal.copy()
        co = v.co.copy()
        unit = co.normalized() if co.length > 1e-6 else Vector((0, 0, 1))
        d = chip * (0.5 + 0.5 * mnoise.noise(co * 42.0))
        for (direction, sigma, amp) in dents:
            ang = unit.angle(Vector(direction).normalized())
            d += amp * math.exp(-(ang / sigma) ** 2)
        for (axis, offset, halfwidth, amp) in seams:
            val = co[{'x': 0, 'y': 1, 'z': 2}[axis]]
            if abs(val - offset) < halfwidth:
                d += amp * (1 - abs(val - offset) / halfwidth)
        v.co -= n * d
    mesh.update()

def clay(obj, strength=0.0016, noise_scale=0.11):
    """A light sculpt pass: break the perfect primitive surfaces."""
    tex = bpy.data.textures.new(f"{obj.name}_clay", type="CLOUDS")
    tex.noise_scale = noise_scale
    mod = obj.modifiers.new("clay", "DISPLACE")
    mod.texture = tex
    mod.strength = strength
    mod.mid_level = 0.5
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj

# ---------------------------------------------------------------- build (Z up)
clear_scene()

# head: large helmet, slightly flattened at the sides
helmet = sphere("Helmet", (0, 0, 0.385), (0.118, 0.108, 0.112), "Head", "ceramic", 112, 72)
sculpt(helmet,
       dents=[((0.55, -0.30, 0.72), 0.30, 0.0016), ((-0.35, 0.55, 0.68), 0.26, 0.0011),
              ((0.10, -0.75, -0.55), 0.24, 0.0009)],
       seams=[("x", 0.0, 0.0035, 0.0007)])
clay(helmet, 0.0009, 0.16)
box("HeadSeam", (0.003, 0.010, 0.105), (0, 0.091, 0.400), "Head", "graphite", bevel=0.001)

# face: copper trim ring, dark glass, two warm eyes
torus("VisorTrim", 0.077, 0.0055, (0, -0.094, 0.385), "Head", "copper",
      rot=(math.radians(90), 0, 0), scale=(1.10, 0.86, 1))
sphere("VisorGlass", (0, -0.100, 0.385), (0.080, 0.020, 0.058), "Head", "visor", 48, 32)
sphere("EyeL", (-0.027, -0.1168, 0.390), (0.0115, 0.0045, 0.0115), "Head", "eye", 24, 16)
sphere("EyeR", (0.027, -0.1168, 0.390), (0.0115, 0.0045, 0.0115), "Head", "eye", 24, 16)

# side ear discs with copper rims
for side, x in (("L", -0.114), ("R", 0.114)):
    cylinder(f"Ear{side}", 0.034, 0.014, (x, 0.0, 0.370), "Head", "graphite",
             rot=(0, math.radians(90), 0), vertices=40)
    torus(f"EarRing{side}", 0.034, 0.0035, (x, 0.0, 0.370), "Head", "copper",
          rot=(0, math.radians(90), 0))

# antenna out of the left ear
rod("Antenna", (-0.122, -0.010, 0.378), (-0.62, -0.18, 0.76), 0.105, 0.0026, "Head", "graphite")
rod("AntennaTip", (-0.122 - 0.62 / 0.999 * 0.105, -0.010 - 0.18 / 0.999 * 0.105, 0.378 + 0.76 / 0.999 * 0.105),
    (-0.62, -0.18, 0.76), 0.018, 0.0075, "Head", "orange", vertices=16)

# torso
clay(box("Torso", (0.150, 0.112, 0.132), (0, 0, 0.222), "Body", "ceramic", bevel=0.030), 0.0012, 0.16)
box("ChestPanel", (0.096, 0.014, 0.070), (0, -0.058, 0.228), "Body", "warmgray", bevel=0.006)
cylinder("Badge", 0.013, 0.006, (0, -0.068, 0.226), "Body", "copper",
         rot=(math.radians(90), 0, 0), vertices=32)
cylinder("Waist", 0.050, 0.022, (0, 0, 0.148), "Body", "graphite", vertices=40)
cylinder("Neck", 0.044, 0.020, (0, 0, 0.302), "Body", "graphite", vertices=40)

# arms: ball shoulder, upper arm, elbow ball, forearm, gripper
for side, sx in (("L", -1), ("R", 1)):
    g = f"Shoulder{side}"
    sphere(f"ShoulderBall{side}", (sx * 0.098, 0, 0.255), (0.028,) * 3, g, "graphite", 24, 16)
    sphere(f"UpperArm{side}", (sx * 0.120, 0, 0.208), (0.025, 0.025, 0.050), g, "ceramic", 24, 16)

    e = f"Elbow{side}"
    sphere(f"ElbowBall{side}", (sx * 0.128, 0, 0.170), (0.022,) * 3, e, "graphite", 24, 16)
    sphere(f"Forearm{side}", (sx * 0.131, 0, 0.136), (0.022, 0.022, 0.042), e, "ceramic", 24, 16)
    box(f"Palm{side}", (0.030, 0.024, 0.020), (sx * 0.133, -0.006, 0.104), e, "graphite", bevel=0.006)
    for k, off in enumerate((-0.009, 0.0, 0.009)):
        rod(f"Finger{side}{k}", (sx * 0.133 + off, -0.014, 0.098),
            (off * 0.6, -0.75, -0.66), 0.026, 0.0034, e, "graphite")

# legs
for side, sx in (("L", -1), ("R", 1)):
    h = f"Hip{side}"
    sphere(f"HipBall{side}", (sx * 0.055, 0, 0.140), (0.026,) * 3, h, "graphite", 24, 16)
    sphere(f"Thigh{side}", (sx * 0.058, 0, 0.108), (0.027, 0.027, 0.032), h, "ceramic", 24, 16)

    k = f"Knee{side}"
    sphere(f"KneeBall{side}", (sx * 0.060, 0, 0.075), (0.022,) * 3, k, "graphite", 24, 16)
    sphere(f"Shin{side}", (sx * 0.062, 0, 0.050), (0.024, 0.024, 0.028), k, "ceramic", 24, 16)
    box(f"Foot{side}", (0.062, 0.100, 0.030), (sx * 0.062, -0.020, 0.020), k, "warmgray", bevel=0.008)


# ---------------------------------------------------------------- mechanical detail
# neck stack
for i, (r, z) in enumerate(((0.036, 0.296), (0.030, 0.308), (0.026, 0.320))):
    cylinder(f"Neck{i}", r, 0.010, (0, 0, z), "Body", "graphite", vertices=32)

# torso panel lines + rivets
for i, z in enumerate((0.252, 0.244)):
    box(f"TorsoLine{i}", (0.070, 0.004, 0.003), (0, -0.0645, z), "Body", "graphite", bevel=0.001)
for i, (x, z) in enumerate(((-0.032, 0.252), (0.032, 0.252), (-0.032, 0.204), (0.032, 0.204))):
    sphere(f"Rivet{i}", (x, -0.0655, z), (0.0035,) * 3, "Body", "copper", 16, 10)

# shoulder / elbow / wrist / hip / knee / ankle rings
for side, sx in (("L", -1), ("R", 1)):
    torus(f"ShoulderRing{side}", 0.030, 0.004, (sx * 0.098, 0, 0.255), f"Shoulder{side}", "copper",
          rot=(0, math.radians(90), 0))
    torus(f"ElbowRing{side}", 0.023, 0.0035, (sx * 0.128, 0, 0.170), f"Elbow{side}", "copper",
          rot=(0, math.radians(90), 0))
    torus(f"WristRing{side}", 0.017, 0.003, (sx * 0.133, 0, 0.112), f"Elbow{side}", "copper",
          rot=(0, math.radians(90), 0))
    torus(f"HipRing{side}", 0.027, 0.0035, (sx * 0.055, 0, 0.140), f"Hip{side}", "copper",
          rot=(0, math.radians(90), 0))
    torus(f"KneeRing{side}", 0.023, 0.0032, (sx * 0.060, 0, 0.075), f"Knee{side}", "copper",
          rot=(0, math.radians(90), 0))
    # arm piston
    rod(f"ArmPiston{side}", (sx * 0.108, 0.020, 0.245), (sx * 0.02, 0.0, -0.075), 0.070, 0.0045,
        f"Shoulder{side}", "graphite")
    # thigh piston
    rod(f"LegPiston{side}", (sx * 0.066, 0.022, 0.128), (0.0, 0.0, -0.055), 0.055, 0.0042,
        f"Hip{side}", "graphite")
    # ankle + toe plate
    cylinder(f"Ankle{side}", 0.017, 0.014, (sx * 0.062, 0.004, 0.032), f"Knee{side}", "graphite",
             rot=(0, math.radians(90), 0), vertices=24)
    box(f"Toe{side}", (0.052, 0.026, 0.014), (sx * 0.062, -0.052, 0.014), f"Knee{side}", "ceramic", bevel=0.005)
    # knuckle plates
    box(f"Knuckle{side}", (0.026, 0.014, 0.010), (sx * 0.133, -0.016, 0.094), f"Elbow{side}", "graphite", bevel=0.003)

# helmet brow + back seam
box("Brow", (0.150, 0.012, 0.010), (0, -0.070, 0.352), "Head", "graphite", bevel=0.003)
box("HelmetSeamL", (0.003, 0.120, 0.003), (-0.058, 0.010, 0.462), "Head", "graphite", bevel=0.001)
box("HelmetSeamR", (0.003, 0.120, 0.003), (0.058, 0.010, 0.462), "Head", "graphite", bevel=0.001)

# ---------------------------------------------------------------- previews
scene = bpy.context.scene
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except TypeError:
    scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 760
scene.render.resolution_y = 760

world = scene.world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.88, 0.865, 0.835, 1.0)
bg.inputs[1].default_value = 1.0

bpy.ops.object.light_add(type="AREA", location=(-0.55, -0.75, 0.80))
key = bpy.context.object
key.data.energy = 240
key.data.size = 0.9
key.rotation_euler = (math.radians(52), 0, math.radians(-36))

bpy.ops.object.light_add(type="AREA", location=(0.70, -0.50, 0.55))
fill = bpy.context.object
fill.data.energy = 70
fill.data.size = 1.3
fill.rotation_euler = (math.radians(64), 0, math.radians(52))

bpy.ops.object.camera_add(location=(0.0, -1.15, 0.34))
cam = bpy.context.object
cam.data.lens = 75
scene.camera = cam

def shoot(name, loc):
    cam.location = loc
    target = Vector((0.0, 0.0, 0.26))
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(OUT, f"character-{name}.png")
    bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "character.blend"))
shoot("front", (0.0, -1.15, 0.34))
shoot("45", (0.78, -0.82, 0.36))
shoot("side", (1.12, 0.0, 0.34))
shoot("back", (0.0, 1.15, 0.34))

# ---------------------------------------------------------------- export
def to_three(v):
    return [round(v.x, 5), round(v.z, 5), round(-v.y, 5)]


def export_part(obj, group, mat, pivot):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    mesh.calc_loop_triangles()
    world_m = obj.matrix_world.copy()
    positions, normals, indices, colors = [], [], [], []
    normal_matrix = world_m.to_3x3().inverted().transposed()
    for v in mesh.vertices:
        co = world_m @ v.co
        positions.extend(to_three(co - pivot))
        normals.extend(to_three((normal_matrix @ v.normal).normalized()))
        w = 0.93 + 0.07 * (0.5 + 0.5 * mnoise.noise(co * 26.0))
        colors.extend([round(w, 3), round(w * 0.988, 3), round(w * 0.972, 3)])
    for tri in mesh.loop_triangles:
        indices.extend([tri.vertices[0], tri.vertices[1], tri.vertices[2]])
    ev.to_mesh_clear()
    return {"name": obj.name, "group": group, "mat": mat,
            "pivot": to_three(pivot), "positions": positions,
            "normals": normals, "indices": indices, "colors": colors}


payload = {
    "units": "metres",
    "height": 0.527,
    "groups": [{"name": n, "parent": p, "pivot": to_three(Vector(pv))} for n, p, pv in GROUPS],
    "parts": [export_part(*part) for part in PARTS],
}
with open(os.path.join(OUT, "character.json"), "w", encoding="utf-8") as f:
    json.dump(payload, f, separators=(",", ":"))

print("CHARACTER_OK", len(PARTS), "parts",
      sum(len(p["indices"]) // 3 for p in payload["parts"]), "triangles")
