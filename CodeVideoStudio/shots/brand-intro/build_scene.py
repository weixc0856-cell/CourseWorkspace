"""Build the WAYNE opener's atelier scene in Blender and render the Environment
Art Gate frames.

Room: back wall with a tall opening, side wall, warm floor, three-step podium,
rolled drawings, a paper model, a ruler, sheets. The creator robot is appended
from character.blend and scaled into the scene.

Run headless:
  blender.exe --background --factory-startup --python build_scene.py -- <out_dir>
"""

import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0]) if argv else os.path.abspath(".")
HERE = os.path.dirname(os.path.abspath(__file__))


def clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def mat(name, color, rough=0.85, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m



def tex_mat(name, base, rough, noise_scale=10.0, bump=0.1, variation=0.05, metallic=0.0):
    """Procedural surface: noise-driven colour variation + bump, object coords."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    coord = nt.nodes.new("ShaderNodeTexCoord")
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = noise_scale
    tex.inputs["Detail"].default_value = 6.0
    tex.inputs["Roughness"].default_value = 0.6
    nt.links.new(coord.outputs["Object"], tex.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    lo = tuple(max(0.0, c - variation) for c in base)
    hi = tuple(min(1.0, c + variation) for c in base)
    ramp.color_ramp.elements[0].color = (*lo, 1.0)
    ramp.color_ramp.elements[1].color = (*hi, 1.0)
    nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = bump
    bmp.inputs["Distance"].default_value = 0.002
    nt.links.new(tex.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic
    return m

def box(name, size, loc, material, bevel=0.006, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        m = o.modifiers.new("bev", "BEVEL")
        m.width = bevel
        m.segments = 3
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier=m.name)
    o.data.materials.clear()
    o.data.materials.append(material)
    return o


def cyl(name, r, h, loc, material, rot=(0, 0, 0), seg=40):
    bpy.ops.mesh.primitive_cylinder_add(vertices=seg, radius=r, depth=h, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    o.data.materials.clear()
    o.data.materials.append(material)
    return o


def plane(name, w, d, loc, material, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    o.scale = (w, d, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.clear()
    o.data.materials.append(material)
    return o


def smooth_all():
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            for p in o.data.polygons:
                p.use_smooth = True


clear()

WALL = tex_mat("wall", (0.780, 0.752, 0.700), 0.96, 7.0, 0.25, 0.035)
FLOOR = tex_mat("floor", (0.520, 0.474, 0.404), 0.78, 26.0, 0.12, 0.045)
CERAMIC = tex_mat("ceramic", (0.720, 0.690, 0.630), 0.5, 4.0, 0.03, 0.018)
STONE = tex_mat("stone", (0.600, 0.548, 0.468), 0.7, 18.0, 0.12, 0.04)
GRAPHITE = mat("graphite", (0.028, 0.031, 0.036), 0.4, 0.3)
ORANGE = mat("orange", (0.790, 0.170, 0.038), 0.35)
PAPER = tex_mat("paper", (0.960, 0.949, 0.925), 0.85, 90.0, 0.10, 0.012)

# room (Blender Z up; the camera looks from -Y)
plane("Floor", 12, 12, (0, 0, 0), FLOOR)
box("WallL", (1.7, 0.12, 2.4), (-2.15, 1.7, 1.2), WALL)
box("WallR", (1.7, 0.12, 2.4), (2.15, 1.7, 1.2), WALL)
box("WallTop", (2.6, 0.12, 0.55), (0, 1.7, 2.12), WALL)
box("SideWall", (0.12, 3.4, 2.4), (-2.45, 0.0, 1.2), WALL)
box("RecessWall", (2.4, 0.10, 2.2), (0, 2.9, 1.1), mat("recess", (0.520, 0.470, 0.400), 1.0))

# podium steps
box("Step1", (2.6, 1.8, 0.10), (0, -0.15, 0.05), STONE, 0.004)
box("Step2", (1.7, 1.1, 0.16), (-0.15, -0.25, 0.18), CERAMIC, 0.004)
box("Step3", (1.2, 0.78, 0.08), (0.05, -0.30, 0.30), CERAMIC, 0.004)
TOP = 0.34

# props
def sheet(name, w, d, loc, rot_z=0.0):
    return box(name, (w, d, 0.0016), loc, PAPER, 0.0, (0, 0, rot_z))

sheet("SheetA", 0.34, 0.24, (0.12, -0.24, TOP + 0.002), 0.12)
sheet("SheetB", 0.30, 0.21, (0.10, -0.22, TOP + 0.004), -0.25)
cyl("Roll1", 0.035, 0.52, (-0.55, -0.55, 0.26 + TOP - 0.08), PAPER, (0.10, 0.06, 0))
cyl("Roll2", 0.028, 0.46, (-0.48, -0.48, 0.23 + TOP - 0.10), PAPER, (-0.05, 0.12, 0))
cyl("Roll3", 0.024, 0.40, (-0.42, -0.42, 0.20 + TOP - 0.12), PAPER, (0.06, -0.10, 0))
box("Ruler", (0.30, 0.03, 0.006), (0.16, -0.10, TOP + 0.008), GRAPHITE, 0.002)
box("ModelA", (0.22, 0.16, 0.16), (-0.85, -0.55, TOP + 0.08), PAPER, 0.004)
box("ModelB", (0.10, 0.10, 0.22), (-0.78, -0.50, TOP + 0.11), PAPER, 0.004)
box("Tray", (0.24, 0.16, 0.03), (-0.55, -0.45, TOP + 0.015), CERAMIC, 0.008)


# story props: pencil cup, sheet stack, copper weight
cyl("Cup", 0.050, 0.120, (-0.30, -0.36, TOP + 0.060), GRAPHITE)
for i, (dx, dy, tilt) in enumerate(((-0.012, 0.004, 0.12), (0.010, -0.006, -0.10),
                                    (0.002, 0.010, 0.04), (0.016, 0.006, 0.16))):
    cyl(f"Pencil{i}", 0.0055, 0.190, (-0.30 + dx, -0.36 + dy, TOP + 0.105),
        ORANGE if i == 3 else GRAPHITE, (tilt, 0.0, tilt * 0.5), 12)
for i in range(5):
    box(f"Stack{i}", (0.26, 0.19, 0.0016), (0.46 + i * 0.002, -0.40 - i * 0.001, TOP + 0.004 + i * 0.0017),
        PAPER, 0.0, (0, 0, 0.05 * i))
cyl("Weight", 0.030, 0.022, (0.30, -0.34, TOP + 0.011), mat("copper", (0.62, 0.30, 0.145), 0.30, 0.85), seg=32)

# story props: pencil cup, sheet stack, copper weight
cyl("Cup", 0.050, 0.120, (-0.30, -0.36, TOP + 0.060), GRAPHITE)
for i, (dx, dy, tilt) in enumerate(((-0.012, 0.004, 0.12), (0.010, -0.006, -0.10),
                                    (0.002, 0.010, 0.04), (0.016, 0.006, 0.16))):
    cyl(f"Pencil{i}", 0.0055, 0.190, (-0.30 + dx, -0.36 + dy, TOP + 0.105),
        ORANGE if i == 3 else GRAPHITE, (tilt, 0.0, tilt * 0.5), 12)
for i in range(5):
    box(f"Stack{i}", (0.26, 0.19, 0.0016), (0.46 + i * 0.002, -0.40 - i * 0.001, TOP + 0.004 + i * 0.0017),
        PAPER, 0.0, (0, 0, 0.05 * i))
cyl("Weight", 0.030, 0.022, (0.30, -0.34, TOP + 0.011), mat("copper", (0.62, 0.30, 0.145), 0.30, 0.85), seg=32)

smooth_all()

# ---------------------------------------------------------------- character
BLEND = os.path.join(HERE, "character.blend")
with bpy.data.libraries.load(BLEND) as (src, dst):
    dst.objects = src.objects

HERO = Vector((0.10, -0.24, TOP + 0.002))
S = 0.55
CHAR_OBJS = []
for obj in dst.objects:
    if obj is None or obj.type != "MESH":
        continue
    bpy.context.collection.objects.link(obj)
    obj.scale = (S, S, S)
    obj.location = HERO + Vector(obj.location) * S
    CHAR_OBJS.append(obj)

char_rig = bpy.data.objects.new("CharRig", None)
bpy.context.collection.objects.link(char_rig)
bpy.context.view_layer.update()
for o in CHAR_OBJS:
    o.parent = char_rig
    o.matrix_parent_inverse = char_rig.matrix_world.inverted()

if "--anim" in argv:
    hops = ((1, 0.0, 0.0), (30, 0.0, 0.0), (34, 0.10, 0.045), (38, 0.20, 0.0),
            (44, 0.32, 0.045), (48, 0.42, 0.0), (54, 0.50, 0.045), (58, 0.55, 0.0),
            (72, 0.55, 0.0))
    for frame, x, z in hops:
        char_rig.location = (x, 0.0, z)
        char_rig.keyframe_insert("location", frame=frame)


# ---------------------------------------------------------------- brand ending
BRAND = "--brand" in argv
ANIM = "--anim" in argv
W_PATH = [(24, 44), (66, 132), (120, 68), (174, 132), (216, 44)]
CURRENT = [(75, 121), (113, 77)]
BRAND_INK = mat("brand_ink", (0.020, 0.023, 0.028), 0.6)
BRAND_ORANGE = mat("brand_orange", (0.79, 0.17, 0.038), 0.35)


def ribbon(p0, p1, width, y, material, k, ox, oz, thick=0.004):
    x0, z0 = (p0[0] - 120) * k + ox, (88 - p0[1]) * k + oz
    x1, z1 = (p1[0] - 120) * k + ox, (88 - p1[1]) * k + oz
    length = math.hypot(x1 - x0, z1 - z0)
    angle = math.atan2(x1 - x0, z1 - z0)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=((x0 + x1) / 2, y, (z0 + z1) / 2),
                                    rotation=(0, angle, 0))
    o = bpy.context.object
    o.scale = (width, thick, length)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.clear()
    o.data.materials.append(material)
    return o


BRAND_OBJS = []


if BRAND:
    board = box("BrandBoard", (1.55, 0.025, 0.92), (0.0, 1.52, 0.47), PAPER, 0.004)
    BRAND_OBJS.append(board)
    k = 1.10 / 192
    for i in range(len(W_PATH) - 1):
        BRAND_OBJS.append(ribbon(W_PATH[i], W_PATH[i + 1], 0.085, 1.504, BRAND_INK, k, 0, 0.60))
    BRAND_OBJS.append(ribbon(CURRENT[0], CURRENT[1], 0.028, 1.503, BRAND_ORANGE, k, 0, 0.60))
    t = bpy.data.curves.new("Wordmark", type="FONT")
    t.body = "WAYNE"
    t.align_x = "CENTER"
    t.size = 0.13
    t.extrude = 0.002
    wo = bpy.data.objects.new("Wordmark", t)
    bpy.context.collection.objects.link(wo)
    wo.data.materials.append(BRAND_INK)
    wo.location = (0.0, 1.503, 0.20)
    wo.rotation_euler = (math.radians(90), 0, 0)
    BRAND_OBJS.append(wo)

    rig = bpy.data.objects.new("BrandRig", None)
    bpy.context.collection.objects.link(rig)
    rig.location = (0.0, 1.52, 0.47)
    bpy.context.view_layer.update()
    for o in BRAND_OBJS:
        o.parent = rig
        o.matrix_parent_inverse = rig.matrix_world.inverted()

    if ANIM:
        rig.rotation_mode = "XYZ"
        for frame, loc, rot in (
            (1, (0.0, -0.05, -0.42), (math.radians(-78), 0, 0)),
            (24, (0.0, 0.35, -0.18), (math.radians(-40), 0, 0)),
            (48, (0.0, 1.05, 0.02), (math.radians(-12), 0, 0)),
            (72, (0.0, 1.52, 0.0), (0, 0, 0)),
        ):
            rig.location = (loc[0], loc[1], 0.47 + loc[2])
            rig.rotation_euler = rot
            rig.keyframe_insert("location", frame=frame)
            rig.keyframe_insert("rotation_euler", frame=frame)

# ---------------------------------------------------------------- light
def area(name, loc, rot, energy, size, color=(1.0, 0.96, 0.90)):
    bpy.ops.object.light_add(type="AREA", location=loc, rotation=rot)
    l = bpy.context.object
    l.name = name
    l.data.energy = energy
    l.data.size = size
    l.data.color = color
    return l

KEY = area("Key", (-2.4, -2.6, 3.4), (math.radians(42), 0, math.radians(-40)), 130, 2.2)
FILL = area("Fill", (2.2, -1.8, 1.6), (math.radians(70), 0, math.radians(55)), 25, 3.0)
RIM = area("Rim", (1.6, 2.2, 2.4), (math.radians(120), 0, math.radians(160)), 60, 1.0)
GLOW = area("Glow", (0, 2.35, 0.35), (math.radians(90), 0, 0), 12, 1.2, (1.0, 0.94, 0.86))

# ---------------------------------------------------------------- cameras
def camera(name, loc, target):
    bpy.ops.object.camera_add(location=loc)
    c = bpy.context.object
    c.name = name
    c.data.lens = 50
    c.rotation_euler = (Vector(target) - c.location).to_track_quat("-Z", "Y").to_euler()
    return c

CAMS = {
    "wide": camera("CamWide", (3.2, -3.6, 1.75), (0.0, -0.20, 0.62)),
    "medium": camera("CamMed", (1.65, -1.95, 1.05), (0.10, -0.20, 0.50)),
    "close": camera("CamClose", (0.72, -0.92, 0.76), (0.10, -0.22, 0.48)),
    "brand": camera("CamBrand", (0.0, -3.4, 1.15), (0.0, 1.1, 0.55)),
}

scene = bpy.context.scene
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except TypeError:
    scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
scene.view_settings.exposure = -0.6

world = scene.world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.90, 0.88, 0.84, 1.0)
bg.inputs[1].default_value = 0.35

def render(name, cam):
    scene.camera = cam
    scene.render.filepath = os.path.join(OUT, f"env-{name}.png")
    bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "scene.blend"))
if BRAND and ANIM:
    scene.frame_start = 1
    scene.frame_end = 72
    scene.render.fps = 24
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    try:
        scene.eevee.taa_render_samples = 32
    except AttributeError:
        pass
    scene.camera = CAMS["brand"]
    anim_dir = os.path.join(OUT, "brand-rise")
    os.makedirs(anim_dir, exist_ok=True)
    for f in range(1, 73):
        scene.frame_set(f)
        scene.render.filepath = os.path.join(anim_dir, f"frame-{f:04d}.png")
        bpy.ops.render.render(write_still=True)
elif BRAND:
    render("brand-front", CAMS["brand"])
    render("brand-wide", CAMS["wide"])
else:
    for key in ("wide", "medium", "close"):
        render(key, CAMS[key])
    FILL.data.energy = 0
    RIM.data.energy = 0
    render("light-key-only", CAMS["medium"])
    FILL.data.energy = 25
    render("light-key-fill", CAMS["medium"])
    RIM.data.energy = 60
    render("light-key-fill-rim", CAMS["medium"])

print("SCENE_OK")
