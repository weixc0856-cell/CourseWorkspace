"""GPU teardown / explode / reassemble / install — procedural Blender 5.2 scene.

Headless, Cycles CPU only (GPU is busy with ComfyUI — do NOT switch to EEVEE/GPU).

Usage:
  blender.exe --background --python build_gpu_teardown.py -- test    # sample PNGs
  blender.exe --background --python build_gpu_teardown.py -- anim    # full MP4
"""
import bpy
import bmesh
import math
import sys
import time
from mathutils import Matrix, Vector

import os
from pathlib import Path

CONTENT = os.environ.get("COURSEWORKSPACE_CONTENT_ROOT") or str(
    Path(__file__).resolve().parents[3] / "content_data")
OUT = CONTENT + "/build/_shared/gpu-teardown"

# If wall-clock forces a reduction, run with env REDUCE=1 (sets FR_SCALE etc).
REDUCE = os.environ.get("GPU_TD_REDUCE", "0") == "1"

FPS = 24
TOTAL = 240
FR_SCALE = 0.8 if REDUCE else 1.0          # time-compress all keyframes
RES = (960, 540) if REDUCE else (1280, 720)
SAMPLES = 16 if REDUCE else 32
FRAME_END = int(TOTAL * FR_SCALE)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
coll = scene.collection

# ---------------------------------------------------------------- materials
def pmat(name, color, metallic=0.0, rough=0.5, emit=None, emit_str=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    if emit is not None:
        b.inputs["Emission Color"].default_value = (*emit, 1.0)
        b.inputs["Emission Strength"].default_value = emit_str
    return m

MAT_PCB     = pmat("MAT_PCB", (0.012, 0.035, 0.018), 0.0, 0.48)
MAT_GOLD    = pmat("MAT_Gold", (1.0, 0.62, 0.18), 1.0, 0.22)
MAT_ALU     = pmat("MAT_BrushedAlu", (0.72, 0.73, 0.75), 1.0, 0.35)
MAT_PLASTIC = pmat("MAT_DarkPlastic", (0.018, 0.018, 0.02), 0.0, 0.42)
MAT_FANBL   = pmat("MAT_FanBlade", (0.03, 0.03, 0.035), 0.0, 0.35)
MAT_ACCENT  = pmat("MAT_Accent", (0.01, 0.01, 0.01), 0.0, 0.5,
                   emit=(0.05, 0.9, 1.0), emit_str=6.0)
MAT_MOBO    = pmat("MAT_MOBO", (0.010, 0.022, 0.016), 0.0, 0.5)
MAT_SLOT    = pmat("MAT_Slot", (0.02, 0.02, 0.022), 0.0, 0.45)
MAT_RAM     = pmat("MAT_RAM", (0.03, 0.03, 0.035), 0.0, 0.5)
MAT_CPU     = pmat("MAT_CPU", (0.55, 0.56, 0.58), 1.0, 0.4)
MAT_FLOOR   = pmat("MAT_Floor", (0.020, 0.020, 0.023), 0.0, 0.75)

# ---------------------------------------------------------------- mesh helpers
def _box_bm(bm, size, loc, rot_z=0.0, rot_x=0.0):
    m = (Matrix.Translation(Vector(loc))
         @ Matrix.Rotation(rot_z, 4, "Z")
         @ Matrix.Rotation(rot_x, 4, "X")
         @ Matrix.Diagonal((size[0], size[1], size[2], 1.0)))
    bmesh.ops.create_cube(bm, size=1, matrix=m)

def new_obj(name, mat, parts):
    """parts: list of (size, loc[, rot_z[, rot_x]]) in object-local space."""
    bm = bmesh.new()
    for p in parts:
        rz = p[2] if len(p) > 2 else 0.0
        rx = p[3] if len(p) > 3 else 0.0
        _box_bm(bm, p[0], p[1], rz, rx)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob

def new_cyl(name, mat, radius, depth, loc, segments=28, axis='Z'):
    bm = bmesh.new()
    m = Matrix.Translation(Vector(loc))
    if axis == 'X':
        m = m @ Matrix.Rotation(math.radians(90), 4, 'Y')
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments,
                          radius1=radius, radius2=radius, depth=depth, matrix=m)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob

GPU = []  # (object, rest_z, exploded_z, explode_start, assemble_start)

def gpu_part(name, mat, parts, loc=(0, 0, 0)):
    ob = new_obj(name, mat, parts)
    ob.location = loc
    return ob

# rest layout (GPU space): PCB z 0..0.02, backplate below, heatsink fins, fans, shroud
bp = gpu_part("GPU_Backplate", MAT_ALU, [((2.50, 1.14, 0.012), (0, 0, -0.006)),
                                         ((0.35, 0.35, 0.02), (0.0, 0.1, -0.020))])
GPU.append([bp, 0.0, -0.85, 6, 140])

pcb = gpu_part("GPU_PCB", MAT_PCB, [((2.6, 1.2, 0.02), (0, 0, 0.01))])
gf = gpu_part("GPU_GoldFingers", MAT_GOLD, [((2.3, 0.022, 0.055), (0, -0.607, 0.012))])
GPU.append([pcb, 0.0, -0.30, 12, 136])
GPU.append([gf, 0.0, -0.30, 12, 136])

hs_parts = [((2.40, 1.10, 0.015), (0, 0, 0.0275))]
y = -0.50
for _ in range(41):
    hs_parts.append(((2.28, 0.007, 0.125), (0, y, 0.0975)))
    y += 0.025
hs = gpu_part("GPU_Heatsink", MAT_ALU, hs_parts)
GPU.append([hs, 0.0, 0.45, 18, 132])

def fan(name, cx):
    """One object: hub + ring + 7 pitched blades, geometry local to fan centre."""
    bm = bmesh.new()
    for i in range(7):
        th = i * 2 * math.pi / 7
        _box_bm(bm, (0.30, 0.13, 0.010),
                (0.265 * math.cos(th), 0.265 * math.sin(th), 0.0),
                th, math.radians(38))
    m = Matrix.Translation((0, 0, 0.004))
    bmesh.ops.create_cone(bm, cap_ends=True, segments=40,
                          radius1=0.435, radius2=0.435, depth=0.012, matrix=m)
    m = Matrix.Translation((0, 0, 0.016))
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24,
                          radius1=0.13, radius2=0.13, depth=0.05, matrix=m)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.materials.append(MAT_FANBL)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.location = (cx, 0, 0.195)
    return ob

fanL = fan("GPU_Fan_L", -0.65)
fanR = fan("GPU_Fan_R", 0.65)
GPU.append([fanL, 0.195, 0.95, 24, 128])
GPU.append([fanR, 0.195, 0.95, 30, 124])

shroud = gpu_part("GPU_Shroud", MAT_PLASTIC, [
    ((2.62, 0.030, 0.105), (0, -0.600, 0.2075)),
    ((2.62, 0.030, 0.105), (0,  0.600, 0.2075)),
    ((0.030, 1.17, 0.105), (-1.300, 0, 0.2075)),
    ((0.030, 1.17, 0.105), ( 1.300, 0, 0.2075)),
    ((2.62, 0.16, 0.014), (0, -0.535, 0.267)),
    ((2.62, 0.16, 0.014), (0,  0.535, 0.267)),
    ((0.16, 0.89, 0.014), (-1.05, 0, 0.267)),
    ((0.16, 0.89, 0.014), ( 1.05, 0, 0.267)),
])
GPU.append([shroud, 0.0, 1.55, 36, 120])

accent = new_obj("GPU_AccentLED", MAT_ACCENT,
                 [((0.6, 0.012, 0.022), (0.9, -0.612, 0.21))])
GPU.append([accent, 0.0, 1.55, 36, 120])   # travels with shroud

# GPU root empty (parent of all parts)
root = bpy.data.objects.new("GPU_ROOT", None)
coll.objects.link(root)
for item in GPU:
    item[0].parent = root
    item[0].matrix_parent_inverse = Matrix.Identity(4)

# ---------------------------------------------------------------- environment
new_obj("CASE_FLOOR", MAT_FLOOR, [((9.0, 7.0, 0.05), (0, 0.5, -0.025))])
new_obj("CASE_BACKDROP", MAT_FLOOR, [((9.0, 0.05, 3.6), (0, 3.6, 1.75))])
mobo = new_obj("MOBO", MAT_MOBO, [
    ((3.40, 2.60, 0.018), (0, 0.55, 0.009)),
    ((0.52, 0.52, 0.022), (-0.75, 1.15, 0.029)),          # CPU socket rim
    ((0.42, 0.42, 0.030), (-0.75, 1.15, 0.032)),          # CPU lid
    ((0.45, 0.45, 0.11),  (0.95, 0.45, 0.073)),           # chipset HS
])
mobo.name = "MOBO"
slot = new_obj("PCIe_x16_Slot", MAT_SLOT, [((2.45, 0.07, 0.06), (0, -0.1, 0.048))])
slot.name = "PCIe_x16_Slot"
for i in range(4):
    new_obj("MOBO_RAM%d" % i, MAT_RAM,
            [((0.05, 1.10, 0.32), (1.12 + 0.065 * i, 0.9, 0.178))])

# ---------------------------------------------------------------- lights
def area(name, loc, energy, size, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy; ld.size = size; ld.color = color
    ob = bpy.data.objects.new(name, ld)
    coll.objects.link(ob)
    ob.location = loc
    c = ob.constraints.new('TRACK_TO')
    c.target = light_target; c.track_axis = 'TRACK_NEGATIVE_Z'
    c.up_axis = 'UP_Y'
    return ob

light_target = bpy.data.objects.new("LIGHT_TARGET", None)
coll.objects.link(light_target)
light_target.location = (0, 0, 0.8)
area("KEY",  (4.5, -3.5, 5.0), 900, 5.0, (1.0, 0.88, 0.72))   # warm key
area("FILL", (-5.5, -4.0, 3.0), 280, 6.0, (0.68, 0.80, 1.0))  # cool fill
area("RIM",  (0.5, 5.5, 4.5), 700, 3.0, (0.9, 0.95, 1.0))     # rim/back
area("LOW",  (0.0, -2.5, 0.4), 25, 4.0, (0.05, 0.8, 1.0))     # cyan bounce

world = bpy.data.worlds.new("WORLD"); scene.world = world
try:
    world.use_nodes = True
except Exception:
    pass
wnt = world.node_tree
bg = wnt.nodes["Background"]
HDRI = CONTENT + "/build/_shared/assets/hdri/studio_small_08_2k.hdr"
import os as _os
if _os.path.exists(HDRI):
    env = wnt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(HDRI)
    ramp = wnt.nodes.new("ShaderNodeMapping")
    texco = wnt.nodes.new("ShaderNodeTexCoord")
    wnt.links.new(texco.outputs["Generated"], ramp.inputs["Vector"])
    ramp.inputs["Rotation"].default_value[2] = math.radians(105)
    wnt.links.new(ramp.outputs["Vector"], env.inputs["Vector"])
    wnt.links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.45   # lights stay dominant
    print("HDRI world loaded:", HDRI)
else:
    bg.inputs[0].default_value = (0.02, 0.022, 0.03, 1.0)
    bg.inputs[1].default_value = 1.0
    print("WARN: HDRI missing, flat world")

# ---------------------------------------------------------------- camera
cam_data = bpy.data.cameras.new("CAM"); cam_data.lens = 50
cam = bpy.data.objects.new("CAMERA", cam_data)
coll.objects.link(cam)
tgt_data = bpy.data.objects.new("CAM_TARGET", None)
coll.objects.link(tgt_data)
tc = cam.constraints.new('TRACK_TO')
tc.target = tgt_data; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
scene.camera = cam

def key(obj, f, **kws):
    f = max(1, round(f * FR_SCALE))
    for attr, val in kws.items():
        setattr(obj, attr, val)
        obj.keyframe_insert(attr, frame=f)

def anim_cam():
    cam_keys = [
        (1,   (3.1, -3.3, 2.1), (0, 0, 1.05)),
        (40,  (4.6, -3.4, 3.2), (0, 0, 1.28)),
        (72,  (6.0, -4.7, 4.4), (0, 0, 1.48)),
        (120, (4.8, -3.8, 3.4), (0, 0, 1.46)),
        (168, (-5.0, -3.7, 2.9), (0, -0.05, 1.00)),
        (190, (-4.8, -3.5, 2.8), (0, -0.05, 0.95)),
        (216, (-3.9, -3.3, 2.3), (0, -0.10, 0.70)),
        (240, (2.45, -0.62, 0.34), (0.75, -0.11, 0.065)),
    ]
    for f, cpos, tpos in cam_keys:
        key(cam, f, location=cpos)
        key(tgt_data, f, location=tpos)
    cam_data.lens = 50
    cam_data.keyframe_insert('lens', frame=round(176 * FR_SCALE))
    cam_data.lens = 62
    cam_data.keyframe_insert('lens', frame=round(240 * FR_SCALE))

def anim_gpu():
    # explode: rest offset 0 -> exploded ; assemble reverse to rest
    for ob, rest_z, exp_z, t0, t1 in GPU:
        base = rest_z
        span_exp, span_asm = 42, 24
        key(ob, 1,  location=(ob.location.x, ob.location.y, base))
        key(ob, t0, location=(ob.location.x, ob.location.y, base))
        key(ob, t0 + span_exp, location=(ob.location.x, ob.location.y, base + exp_z))
        key(ob, t1, location=(ob.location.x, ob.location.y, base + exp_z))
        key(ob, t1 + span_asm, location=(ob.location.x, ob.location.y, base))
    # fan spin
    for ob in (fanL, fanR):
        for f, r in ((1, 0), (30, 0), (90, 4 * math.pi), (150, 7 * math.pi), (240, 7 * math.pi)):
            key(ob, f, rotation_euler=(0, 0, r))
    # root: hover -> flip to install pose -> descend into slot
    key(root, 1,   location=(0, 0, 0.90), rotation_euler=(0, 0, 0))
    key(root, 164, location=(0, 0, 0.90), rotation_euler=(0, 0, 0))
    key(root, 184, location=(0, 0.02, 0.90), rotation_euler=(math.radians(90), 0, 0))
    key(root, 224, location=(0, -0.10, 0.68), rotation_euler=(math.radians(90), 0, 0))
    key(root, 240, location=(0, -0.10, 0.68), rotation_euler=(math.radians(90), 0, 0))

def iter_fcurves(action):
    """Blender >=4.4 slotted actions: fcurves live in layer/strip/channelbag."""
    if hasattr(action, "fcurves"):
        for fc in action.fcurves:
            yield fc
        return
    for layer in getattr(action, "layers", ()):
        for strip in getattr(layer, "strips", ()):
            for cb in getattr(strip, "channelbags", ()):
                if cb is None:
                    continue
                for fc in getattr(cb, "fcurves", ()):
                    yield fc

def smooth_eases():
    targets = [o[0] for o in GPU] + [root, fanL, fanR, cam, tgt_data]
    for ob in targets:
        if not ob.animation_data or not ob.animation_data.action:
            continue
        for fc in iter_fcurves(ob.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'
                kp.handle_left_type = 'AUTO_CLAMPED'
                kp.handle_right_type = 'AUTO_CLAMPED'

# ---------------------------------------------------------------- render cfg
def configure_render():
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    except TypeError:
        print("WARN: denoiser enum not found, using default")
    scene.cycles.max_bounces = 6
    scene.cycles.transparent_max_bounces = 2
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = FRAME_END
    scene.render.use_motion_blur = True
    for _setter in (lambda v: setattr(scene.cycles, "motion_blur_position", v),
                    lambda v: setattr(scene.render, "motion_blur_position", v)):
        try:
            _setter('CENTER')
            break
        except (AttributeError, TypeError):
            pass
    scene.render.motion_blur_shutter = 0.35
    scene.view_settings.view_transform = 'AgX'
    try:
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except TypeError:
        pass
    ii = scene.render.image_settings
    ii.media_type = 'VIDEO'          # Blender 5.2: FFMPEG gated behind VIDEO
    ii.file_format = 'FFMPEG'
    ff = scene.render.ffmpeg
    ff.format = 'MPEG4'
    ff.codec = 'H264'
    ff.constant_rate_factor = 'MEDIUM'
    ff.gopsize = 12
    scene.render.filepath = OUT + "/gpu_teardown.mp4"
    scene.render.use_file_extension = True
    scene.render.use_persistent_data = True

def configure_test():
    scene.render.image_settings.media_type = 'IMAGE'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = OUT + "/test/frame_"

# ---------------------------------------------------------------- run
arg = "anim"
if "--" in sys.argv:
    tail = sys.argv[sys.argv.index("--") + 1:]
    if tail:
        arg = tail[0]

anim_cam()
anim_gpu()
smooth_eases()

names = [o.name for o in bpy.data.objects if o.type == 'MESH']
print("MESH OBJECTS (%d): %s" % (len(names), ", ".join(sorted(names))))
print("CONFIG: reduce=%s res=%s samples=%d frame_end=%d fr_scale=%.2f"
      % (REDUCE, RES, SAMPLES, FRAME_END, FR_SCALE))

t0 = time.time()
if arg == "test":
    configure_render()
    configure_test()
    for f in [1, 60, 100, 150, 190, 216, 239]:
        if f <= FRAME_END:
            scene.frame_set(f)
            scene.render.filepath = OUT + "/test/frame_%04d.png" % f
            bpy.ops.render.render(write_still=True)
            print("TESTFRAME %d  t=%.1fs" % (f, time.time() - t0))
elif arg == "anim":
    configure_render()
    print("RENDER START", time.strftime("%H:%M:%S"))
    bpy.ops.render.render(animation=True)
    print("RENDER DONE  wall=%.1fs" % (time.time() - t0))
else:
    print("unknown mode", arg); sys.exit(2)
