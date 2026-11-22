"""RTX 5090 Founders-Edition-STYLE assembly animation — procedural Blender 5.2 scene.

Fidelity tier: PROCEDURAL FE-style (no free direct-download model existed; see
build/_shared/assets/gpu5090/README.md).  Fan-made concept, NOT official CAD,
no NVIDIA logo/wordmark.  Trademark/honesty label burned via compositor Text node.

Real dims honoured at 10x mm => 1 unit = 100 mm:  304 x 137 x 40 mm  (2-slot).
Assembly order: PCB -> Heatsink_Fins -> Fan_A -> Fan_B -> Frame -> Backplate ->
Power_Connector, then whole card seats into the MOBO PCIe x16 slot.

Headless usage (Blender 5.2):
  blender --background --python build_gpu5090.py -- test
  blender --background --python build_gpu5090.py -- anim
Engine override: env GPU5090_ENGINE=EEVEE (default) | CYCLES  (CYCLES = CPU fallback).
"""
import bpy, bmesh, math, sys, time, os
from pathlib import Path
from mathutils import Matrix, Vector

ROOT = os.environ.get("COURSEWORKSPACE_CONTENT_ROOT") or str(
    Path(__file__).resolve().parents[3] / "content_data")
OUT  = ROOT + r"/build/_shared/gpu5090"
os.makedirs(OUT, exist_ok=True)
os.makedirs(OUT + "/test", exist_ok=True)

ENGINE = os.environ.get("GPU5090_ENGINE", "EEVEE").upper()
FPS = 24
TOTAL = 288                      # ~12 s
RES = (1920, 1080)
SAMPLES = 32

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
coll = scene.collection

# ------------------------------------------------------------------ materials
def pmat(name, color, metallic=0.0, rough=0.5, aniso=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    try: b.inputs["Anisotropic"].default_value = aniso
    except KeyError: pass
    return m

MAT_FRAME  = pmat("MAT_BrushedAlu", (0.60, 0.61, 0.64), 1.0, 0.30, aniso=0.6)
MAT_BACK   = pmat("MAT_Backplate",  (0.42, 0.43, 0.46), 1.0, 0.34, aniso=0.5)
MAT_FIN    = pmat("MAT_FinDark",    (0.045,0.048,0.055),1.0, 0.55)
MAT_BASE   = pmat("MAT_VaporBase",  (0.55,0.56,0.58),   1.0, 0.30)
MAT_PCB    = pmat("MAT_PCB",        (0.014,0.030,0.016),0.0, 0.46)
MAT_GOLD   = pmat("MAT_Gold",       (0.90, 0.55, 0.16), 1.0, 0.24)
MAT_FANBL  = pmat("MAT_FanBlade",   (0.020,0.020,0.024),0.0, 0.40)
MAT_PLAST  = pmat("MAT_DarkPlastic",(0.016,0.016,0.018),0.0, 0.42)
MAT_MOBO   = pmat("MAT_MOBO",       (0.010,0.022,0.015),0.0, 0.50)
MAT_SLOT   = pmat("MAT_Slot",       (0.02,0.02,0.024),  0.3, 0.45)
MAT_FLOOR  = pmat("MAT_Floor",      (0.018,0.018,0.021),0.0, 0.75)
MAT_DIE    = pmat("MAT_Die",        (0.70,0.71,0.73),   1.0, 0.25)

# ------------------------------------------------------------------ mesh helpers
def _mkmat(name, mats):
    me = bpy.data.meshes.new(name)
    for m in mats: me.materials.append(m)
    return me

def new_obj(name, mats, parts):
    """parts: list of ('box',matidx,(sx,sy,sz),loc[,rot]) or ('cyl',matidx,r,depth,loc,axis[,seg])"""
    bm = bmesh.new()
    for p in parts:
        pre = len(bm.faces)
        if p[0] == 'box':
            _, mi, size, loc = p[0], p[1], p[2], p[3]
            rot = p[4] if len(p) > 4 else (0,0,0)
            m = (Matrix.Translation(Vector(loc))
                 @ Matrix.Rotation(rot[2],4,'Z') @ Matrix.Rotation(rot[1],4,'Y')
                 @ Matrix.Rotation(rot[0],4,'X')
                 @ Matrix.Diagonal((size[0],size[1],size[2],1.0)))
            bmesh.ops.create_cube(bm, size=1, matrix=m)
        elif p[0] == 'cyl':
            _, mi, r, depth, loc = p[0], p[1], p[2], p[3], p[4]
            axis = p[5] if len(p) > 5 else 'Z'; seg = p[6] if len(p) > 6 else 24
            m = Matrix.Translation(Vector(loc))
            if axis == 'Y': m = m @ Matrix.Rotation(math.radians(90),4,'X')
            if axis == 'X': m = m @ Matrix.Rotation(math.radians(90),4,'Y')
            bmesh.ops.create_cone(bm, cap_ends=True, segments=seg,
                                 radius1=r, radius2=r, depth=depth, matrix=m)
        for f in bm.faces[pre:]:
            f.material_index = p[1]
    me = _mkmat(name, mats)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    return ob

def make_fan(name, cx, cz):
    """single-mesh axial fan: hub + pitched blades + thin outer ring (open centre)."""
    bm = bmesh.new()
    r_in, r_out = 0.15, 0.50
    # hub
    bmesh.ops.create_cone(bm, cap_ends=True, segments=28, radius1=r_in, radius2=r_in,
                          depth=0.05, matrix=Matrix.Translation((0,0,0.004)))
    # blades: chord fits between hub and rim, does NOT cross centre; dense spiral
    n = 15
    chord = r_out - r_in            # 0.35 radial
    rmid  = (r_in + r_out) / 2.0    # 0.325
    for i in range(n):
        th = i * 2*math.pi / n
        m = (Matrix.Translation((rmid*math.cos(th), rmid*math.sin(th), 0.0))
             @ Matrix.Rotation(th, 4, 'Z')
             @ Matrix.Rotation(math.radians(33), 4, 'X')
             @ Matrix.Diagonal((chord, 0.22, 0.016, 1.0)))
        bmesh.ops.create_cube(bm, size=1, matrix=m)
    # thin outer ring: 30 small boxes around r_out
    nr = 30
    for i in range(nr):
        th = i * 2*math.pi / nr
        m = (Matrix.Translation((r_out*math.cos(th), r_out*math.sin(th), 0.0))
             @ Matrix.Rotation(th, 4, 'Z')
             @ Matrix.Diagonal((0.04, 0.07, 0.06, 1.0)))
        bmesh.ops.create_cube(bm, size=1, matrix=m)
    me = _mkmat(name, [MAT_FANBL])
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    ob.location = (cx, 0, cz)
    return ob

# ================================================================== CARD PARTS
# rest layout in CARD-LOCAL space (card flat, cooler normal = local Z, +Z = front/top)
# thickness envelope  z in [-0.20, +0.20]  (= 40 mm @10x).  length X +/-1.52, width Y +/-0.685
parts = {}

pcb = new_obj("PCB", [MAT_PCB, MAT_GOLD, MAT_DIE, MAT_PLAST], [
    ('box',0,(2.86,1.30,0.022),(0.0, 0.0, 0.0)),                 # board
    ('box',1,(0.80,0.006,0.045),(-1.00,-0.655,-0.020)),          # PCIe gold fingers (bottom edge)
    ('box',3,(0.20,0.006,0.030),(-0.60,-0.655,-0.018)),          # aux contact pad
    ('box',2,(0.62,0.62,0.020),(0.35, 0.0, 0.016)),              # GPU die + substrate
    ('box',0,(0.04,0.9,0.10),(1.45,0,0.05)),                     # bracket-end I/O hint
])
parts['PCB'] = (pcb, (0.0, 0.5, 0.75))

fin_parts = [('box',1,(2.30,1.22,0.014),(0,0,0.027))]            # vapor-chamber base
yy = -0.56
for _ in range(46):
    fin_parts.append(('box',0,(2.15,0.007,0.150),(0,yy,0.110)))
    yy += 0.0245
hs = new_obj("Heatsink_Fins", [MAT_FIN, MAT_BASE], fin_parts)
parts['Heatsink_Fins'] = (hs, (0.0, -0.35, 0.85))

fanA = make_fan("Fan_A", 0.72, 0.180)
parts['Fan_A'] = (fanA, (0.5, 0.25, 0.75))
fanB = make_fan("Fan_B", -0.72, -0.180)
parts['Fan_B'] = (fanB, (-0.5, -0.25, -0.75))

frame = new_obj("Frame", [MAT_FRAME], [
    # top shroud frame (picture-frame) with openings over the two fans + centre fins
    ('box',0,(3.02,0.10,0.030),(0.0,-0.635,0.205)),
    ('box',0,(3.02,0.10,0.030),(0.0, 0.635,0.205)),
    ('box',0,(0.10,1.20,0.030),(-1.45,0.0,0.205)),
    ('box',0,(0.10,1.20,0.030),( 1.45,0.0,0.205)),
    ('box',0,(0.42,0.30,0.030),(-0.30,0.0,0.205)),               # mid bar (between fans)
    # side rails wrapping the thickness
    ('box',0,(3.02,0.02,0.34),(0.0,-0.675,0.03)),
    ('box',0,(3.02,0.02,0.34),(0.0, 0.675,0.03)),
    ('box',0,(0.02,1.34,0.34),(-1.50,0.0,0.03)),
    ('box',0,(0.02,1.34,0.34),( 1.50,0.0,0.03)),
])
parts['Frame'] = (frame, (0.0, 0.0, 0.95))

backplate = new_obj("Backplate", [MAT_BACK], [
    ('box',0,(3.00,0.16,0.016),(0.0,-0.605,-0.200)),
    ('box',0,(3.00,0.16,0.016),(0.0, 0.605,-0.200)),
    ('box',0,(0.16,1.20,0.016),(-1.42,0.0,-0.200)),
    ('box',0,(0.16,1.20,0.016),( 1.42,0.0,-0.200)),
    ('box',0,(0.40,0.20,0.016),(0.0,0.0,-0.200)),                # mid rib
])
parts['Backplate'] = (backplate, (0.0, 0.0, -0.90))

connector = new_obj("Power_Connector", [MAT_PLAST, MAT_GOLD], [
    ('box',0,(0.26,0.40,0.10),(1.05,0.30,0.205)),                # 12V-2x6 housing (top edge)
    ('box',1,(0.20,0.34,0.012),(1.05,0.30,0.160)),               # pins base
])
parts['Power_Connector'] = (connector, (0.35, 0.25, 0.60))

# root empty parent of the card so seating can move/rotate the whole assembly
root = bpy.data.objects.new("CARD_ROOT", None); coll.objects.link(root)
for nm,(ob,off) in parts.items():
    ob.parent = root; ob.matrix_parent_inverse = Matrix.Identity(4)
    ob["rest"] = tuple(ob.location); ob["off"] = off

# ================================================================== ENVIRONMENT
new_obj("CASE_FLOOR", [MAT_FLOOR], [('box',0,(11.0,9.0,0.06),(0,0.6,-0.03))])
new_obj("CASE_BACKDROP",[MAT_FLOOR],[('box',0,(11.0,0.06,4.2),(0,4.2,2.1))])
new_obj("MOBO", [MAT_MOBO], [
    ('box',0,(4.20,3.00,0.020),(0.0,0.6,0.0)),
    ('box',0,(0.55,0.55,0.022),(-1.0,1.25,0.021)),               # CPU socket rim
    ('box',0,(0.46,0.46,0.030),(-1.0,1.25,0.026)),               # CPU lid
    ('box',0,(0.50,0.50,0.14),(1.35,0.85,0.08)),                 # chipset HS
])
new_obj("PCIe_x16_Slot", [MAT_SLOT, MAT_GOLD], [
    ('box',0,(0.95,0.10,0.055),(-1.05,-0.15,0.037)),
    ('box',0,(1.55,0.10,0.055),( 0.30,-0.15,0.037)),
    ('box',1,(0.90,0.02,0.03),(-1.05,-0.15,0.020)),
    ('box',1,(1.50,0.02,0.03),( 0.30,-0.15,0.020)),
])

# ================================================================== LIGHTS
light_target = bpy.data.objects.new("LIGHT_TARGET", None); coll.objects.link(light_target)
light_target.location = (0, 0, 0.7)
def area(name, loc, energy, size, color=(1,1,1)):
    ld = bpy.data.lights.new(name,'AREA'); ld.energy=energy; ld.size=size; ld.color=color
    ob = bpy.data.objects.new(name, ld); coll.objects.link(ob); ob.location=loc
    c = ob.constraints.new('TRACK_TO'); c.target=light_target
    c.track_axis='TRACK_NEGATIVE_Z'; c.up_axis='UP_Y'
    return ob
area("KEY", (3.6,-2.8,4.2), 720, 4.5, (1.0,0.90,0.76))
area("FILL",(-4.6,-3.2,2.6), 210, 5.5, (0.66,0.78,1.0))
area("RIM", (0.4, 4.4,3.6), 560, 2.8, (0.9,0.95,1.0))

world = bpy.data.worlds.new("WORLD"); scene.world = world
wnt = world.node_tree; bg = wnt.nodes["Background"]
HDRI = ROOT + r"/build/_shared/assets/hdri/studio_small_08_2k.hdr"
if os.path.exists(HDRI):
    env = wnt.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(HDRI)
    ramp = wnt.nodes.new("ShaderNodeMapping"); texco = wnt.nodes.new("ShaderNodeTexCoord")
    wnt.links.new(texco.outputs['Generated'], ramp.inputs['Vector'])
    ramp.inputs['Rotation'].default_value[2] = math.radians(120)
    wnt.links.new(ramp.outputs['Vector'], env.inputs['Vector'])
    wnt.links.new(env.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 0.35
    print("HDRI world:", HDRI)
else:
    bg.inputs[0].default_value=(0.02,0.022,0.03,1.0)

# ================================================================== CAMERA
cam_data = bpy.data.cameras.new("CAM"); cam_data.lens = 50
cam = bpy.data.objects.new("CAMERA", cam_data); coll.objects.link(cam)
tgt = bpy.data.objects.new("CAM_TARGET", None); coll.objects.link(tgt)
c = cam.constraints.new('TRACK_TO'); c.target=tgt; c.track_axis='TRACK_NEGATIVE_Z'; c.up_axis='UP_Y'
scene.camera = cam
dof = bpy.data.objects.new("DOF_TARGET", None); coll.objects.link(dof)
cam_data.dof.use_dof = True; cam_data.dof.focus_object = dof
cam_data.dof.aperture_fstop = 8.0

# ================================================================== ANIMATION
def key(obj, f, **kws):
    for a,v in kws.items():
        setattr(obj, a, v); obj.keyframe_insert(a, frame=int(round(f)))

def assemble_card():
    order = ['PCB','Heatsink_Fins','Fan_A','Fan_B','Frame','Backplate','Power_Connector']
    t0s =   [ 10,  30,          52,      74,     98,   122,        146 ]
    span = 18
    for nm, t0 in zip(order, t0s):
        ob, off = parts[nm][0], parts[nm][1]
        rest = tuple(ob["rest"]); start = tuple(rest[i]+off[i] for i in range(3))
        key(ob, 1, location=start)
        key(ob, t0, location=start)
        key(ob, t0+span, location=rest)
        # slight lateral sway so it is not robotic
        key(ob, t0+span*0.5, location=(rest[0]+off[0]*0.15, rest[1], rest[2]+off[2]*0.45))
    # gentle fan spin once seated (subtle life)
    for ob in (fanA, fanB):
        for f,r in ((t0s[2]+span, 0.0), (250, 0.0), (288, 1.5*math.pi)):
            key(ob, f, rotation_euler=(0,0,r))

def seat_card():
    key(root, 1,   location=(0,0,0.60), rotation_euler=(0,0,0))
    key(root, 168, location=(0,0,0.60), rotation_euler=(0,0,0))
    key(root, 184, location=(0,0,1.35), rotation_euler=(0,0,0))            # lift
    key(root, 206, location=(0,-0.18,1.30), rotation_euler=(math.radians(90),0,0))  # stand up over slot
    key(root, 232, location=(0,-0.18,0.70), rotation_euler=(math.radians(90),0,0))   # descend into PCIe
    key(root, 244, location=(0,-0.18,0.685),rotation_euler=(math.radians(90),0,0))   # settle
    key(root, 288, location=(0,-0.18,0.685),rotation_euler=(math.radians(90),0,0))

def animate_camera():
    # (frame, cam_pos, target)
    keys = [
        (1,   (3.9,-4.3, 2.9), (0.00, 0.00, 0.55)),   # 3/4 establishing, whole card zone
        (52,  (3.2,-4.2, 2.4), (0.55,-0.05, 0.55)),   # Fan_A seats (front)
        (98,  (-3.7,-4.2,2.4), (-0.45, 0.00, 0.50)),  # Frame / Backplate (rear, -X)
        (130, (3.7,-3.9, 2.8), (0.95, 0.25, 0.70)),   # Power connector plug-in
        (168, (5.4,-3.6, 2.9), (0.00, 0.00, 0.85)),   # pull back: assembled card
        (188, (5.0,-3.3, 2.6), (0.00,-0.10, 1.05)),   # lift
        (212, (-4.4,-2.6, 1.5), (0.00,-0.20, 0.65)),  # seating: watch fingers enter PCIe slot
        (244, (-3.9,-2.7, 1.7), (0.00,-0.20, 0.72)),  # settle, slot plane visible
        (288, (-5.4,-4.2, 3.1), (0.00,-0.18, 0.92)),  # final product reveal (whole card)
    ]
    for f,cp,tp in keys:
        key(cam, f, location=cp)
        key(tgt, f, location=tp)
        key(dof, f, location=tp)
    cam_data.lens = 46; cam_data.keyframe_insert('lens', frame=1)
    cam_data.lens = 49; cam_data.keyframe_insert('lens', frame=150)
    cam_data.lens = 46; cam_data.keyframe_insert('lens', frame=288)

def iter_fcurves(action):
    if hasattr(action, "fcurves"):
        for fc in action.fcurves: yield fc
        return
    for layer in getattr(action,"layers",()):
        for strip in getattr(layer,"strips",()):
            for cb in getattr(strip,"channelbags",()):
                if cb:
                    for fc in getattr(cb,"fcurves",()): yield fc

def smooth_eases():
    objs = [parts[n][0] for n in parts] + [root, fanA, fanB, cam, tgt, dof]
    for ob in objs:
        if not ob.animation_data or not ob.animation_data.action: continue
        for fc in iter_fcurves(ob.animation_data.action):
            for kp in fc.keyframe_points:
                kp.interpolation='BEZIER'; kp.handle_left_type='AUTO_CLAMPED'; kp.handle_right_type='AUTO_CLAMPED'

# ================================================================== LABEL (3D text parented to camera)
def build_label():
    label = "RTX 5090-STYLE - FAN-MADE CONCEPT ASSEMBLY\n(NOT OFFICIAL CAD)"
    # dark backing plate (contrast guarantee) + unlit white text, both locked to frame bottom
    plate_mat = bpy.data.materials.new("MAT_LabelPlate"); plate_mat.use_nodes = True
    pb = plate_mat.node_tree.nodes.get("Principled BSDF")
    pb.inputs["Base Color"].default_value = (0.01,0.01,0.012,1.0)
    pb.inputs["Roughness"].default_value = 0.9
    txt_mat = bpy.data.materials.new("MAT_LabelText"); txt_mat.use_nodes = True
    tb = txt_mat.node_tree.nodes.get("Principled BSDF")
    tb.inputs["Emission Color"].default_value = (1,1,1,1)
    tb.inputs["Emission Strength"].default_value = 3.0
    tb.inputs["Base Color"].default_value = (1,1,1,1)

    # backing plate: thin box slightly behind text, centred low in camera space
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1,
        matrix=Matrix.Diagonal((2.70, 0.40, 0.02, 1.0)))
    me = bpy.data.meshes.new("LabelPlate"); bm.to_mesh(me); bm.free()
    me.materials.append(plate_mat)
    plate = bpy.data.objects.new("LabelPlate", me); coll.objects.link(plate)
    plate.parent = cam; plate.matrix_parent_inverse = Matrix.Identity(4)
    plate.location = (0, -0.60, -4.05)

    cu = bpy.data.curves.new("LabelText", 'FONT'); cu.body = label
    cu.size = 0.085; cu.align_x='CENTER'; cu.align_y='BOTTOM'
    cu.space_character = 0.70; cu.space_line = 1.10
    cu.extrude = 0.0; cu.offset_y = 0.0
    tob = bpy.data.objects.new("LabelText", cu); coll.objects.link(tob)
    tob.parent = cam; tob.matrix_parent_inverse = Matrix.Identity(4)
    tob.location = (0, -0.78, -4.00)
    tob.data.materials.append(txt_mat)
    tob.visible_shadow = False
    plate.visible_shadow = False
    return True

# ================================================================== RENDER CFG
def configure_render():
    if ENGINE == "CYCLES":
        scene.render.engine='CYCLES'; scene.cycles.device='CPU'
        scene.cycles.samples=SAMPLES; scene.cycles.use_denoising=True
        try: scene.cycles.denoiser='OPENIMAGEDENOISE'
        except TypeError: pass
        scene.cycles.max_bounces=6
        scene.render.resolution_x, scene.render.resolution_y = (1280,720)
    else:
        scene.render.engine='BLENDER_EEVEE'
        try: scene.eevee.use_raytracing=True
        except Exception as e: print("EEVEE rt err",e)
        scene.eevee.taa_render_samples=SAMPLES
        try:
            scene.eevee.use_gtao=True; scene.eevee.gtao_distance=0.3
        except Exception as e: print("EEVEE gtao err",e)
        try: scene.eevee.use_shadows=True
        except Exception: pass
        scene.render.resolution_x, scene.render.resolution_y = RES
    scene.render.resolution_percentage=100
    scene.render.fps=FPS; scene.frame_start=1; scene.frame_end=TOTAL
    scene.view_settings.view_transform='AgX'
    try: scene.view_settings.look='AgX - Medium High Contrast'
    except TypeError:
        try: scene.view_settings.look='AgX - Punchy'
        except Exception: pass
    ii=scene.render.image_settings
    ii.media_type='VIDEO'; ii.file_format='FFMPEG'
    ff=scene.render.ffmpeg; ff.format='MPEG4'; ff.codec='H264'
    ff.constant_rate_factor='HIGH'; ff.gopsize=12
    scene.render.filepath=OUT+"/assembly.mp4"; scene.render.use_file_extension=True
    scene.render.use_persistent_data=True

def configure_stills():
    scene.render.image_settings.media_type='IMAGE'
    scene.render.image_settings.file_format='PNG'

assemble_card(); seat_card(); animate_camera(); smooth_eases()
build_label()

if __name__ == "__main__" or True:
    arg = "test"
    if "--" in sys.argv:
        tail = sys.argv[sys.argv.index("--")+1:]
        if tail: arg = tail[0]
    names = sorted(o.name for o in bpy.data.objects if o.type=='MESH')
    print("ENGINE=%s  RES=%s  SAMPLES=%d  frames=%d" % (ENGINE, RES, SAMPLES, TOTAL))
    print("MESH OBJECTS (%d): %s" % (len(names), ", ".join(names)))
    t0=time.time()
    if arg=="test":
        configure_render(); configure_stills()
        for f in (20, 45, 70, 100, 130, 150, 200, 236, 280):
            scene.frame_set(f)
            scene.render.filepath = OUT + "/test/f_%04d.png" % f
            bpy.ops.render.render(write_still=True)
            print("TESTFRAME %d t=%.1fs" % (f, time.time()-t0))
    elif arg=="anim":
        configure_render()
        print("RENDER START", time.strftime("%H:%M:%S"), flush=True)
        bpy.ops.render.render(animation=True)
        print("RENDER DONE wall=%.1fs" % (time.time()-t0))
    else:
        print("unknown", arg); sys.exit(2)
