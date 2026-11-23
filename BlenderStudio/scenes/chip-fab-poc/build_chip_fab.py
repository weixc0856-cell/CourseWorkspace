"""chip-fab-poc — procedural semiconductor micro-fabrication showcase.

Builds (in correct process order):
  wafer substrate -> oxide -> photoresist spin-coat -> photomask descend ->
  EUV projection -> exposure + develop (resist dissolve) -> trench etch
  (boolean) -> resist strip -> copper interconnect growth.

Headless usage (run with Blender 5.2):
  blender --background --python build_chip_fab.py -- --mode build
  blender --background --python build_chip_fab.py -- --mode stills --engine cycles_cpu --out DIR
  blender --background --python build_chip_fab.py -- --mode anim --engine eevee --out FILE.mp4

No external assets. Everything procedural.
"""
import argparse
import math
import os
import re
import sys

import bpy
import mathutils

# ---------------------------------------------------------------- timeline --
FPS = 24
FRAME_START = 1
FRAME_END = 288

# Stage windows (frame ranges, ~0.3s = 7f causal stagger baked into the numbers)
S_SUB = (1, 25)
S_OXIDE = (26, 49)
S_RESIST = (50, 75)
S_MASK = (76, 109)
S_EUV = (110, 153)
S_DEV = (154, 181)
S_ETCH = (182, 211)
S_STRIP = (212, 235)
S_CU = (236, 277)
S_FINAL = (278, 288)

X_SLOTS = (-1.5, -0.5, 0.5, 1.5)
SLOT_W = 0.5
SLOT_L = 2.6

WA = 4.4  # wafer size X
WB = 3.2  # wafer size Y
Z_SUB_TOP = 0.0
T_SUB = 0.45
Z_OX_TOP = 0.045
Z_RES_TOP = 0.115
MASK_Z = 0.85
TRENCH_FLOOR = -0.18


def lin(v0, v1, t0, t1, x):
    if t1 == t0:
        return v1
    u = min(max((x - t0) / (t1 - t0), 0.0), 1.0)
    return v0 + (v1 - v0) * u


def rgb(h):
    h = h.lstrip("#")
    s = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(c ** 2.2 if c > 0.04 else c / 12.92 for c in s) + (1.0,)


# ---------------------------------------------------------------- keyframing
_TOK_RE = re.compile(r'([A-Za-z_]\w*)|\[(-?\d+)\]|\["([^"]+)"\]')


def _steps(path):
    out = []
    for m in _TOK_RE.finditer(path):
        if m.group(1):
            out.append(("attr", m.group(1)))
        elif m.group(2) is not None:
            out.append(("idx", int(m.group(2))))
        else:
            out.append(("key", m.group(3)))
    return out


def set_prop(id_data, path, value):
    steps = _steps(path)
    obj = id_data
    for kind, val in steps[:-1]:
        obj = getattr(obj, val) if kind == "attr" else obj[val]
    kind, val = steps[-1]
    if kind == "attr":
        setattr(obj, val, value)
    else:
        obj[val] = value


def iter_fcurves(id_data):
    """Yield (fcurve) across Blender 4.4+/5.x layered actions and legacy ones."""
    ad = getattr(id_data, "animation_data", None)
    if not ad or not ad.action:
        return
    act = ad.action
    try:
        for layer in act.layers:
            for strip in layer.strips:
                for cbag in strip.channelbags:
                    for fc in cbag.fcurves:
                        yield fc
        return
    except AttributeError:
        pass
    for fc in getattr(act, "fcurves", []):
        yield fc


def anim(id_data, path, keys, interp="BEZIER", easing="AUTO"):
    idx_m = re.search(r"\[(-?\d+)\]$", path)
    base = path[:idx_m.start()] if idx_m else path
    idx = int(idx_m.group(1)) if idx_m else -1
    for f, v in keys:
        set_prop(id_data, path, v)
        id_data.keyframe_insert(data_path=base, frame=f, index=idx)
    for fc in iter_fcurves(id_data):
        if (fc.data_path or "") != base:
            continue
        if idx_m and fc.array_index != int(idx_m.group(1)):
            continue
        for kp in fc.keyframe_points:
            kp.interpolation = interp
            kp.easing = easing
            try:
                kp.handle_left_type = "AUTO_CLAMPED"
                kp.handle_right_type = "AUTO_CLAMPED"
            except TypeError:
                pass


def dim_keys(active_spans, dim=0.6, ramp=5.0):
    """Value-vs-frame curve for a 'dim' node: 0 inside own active spans, dim elsewhere."""
    keys = []
    t = FRAME_START
    for (a, b) in active_spans:
        if a - ramp > t:
            keys.append((t, dim))
            keys.append((a - ramp, dim))
        keys.append((a + ramp, 0.0))
        keys.append((b - ramp, 0.0))
        t = b + ramp
    if t < FRAME_END:
        keys.append((t, dim))
        keys.append((FRAME_END, dim))
    return keys


def gate(obj, f_on):
    """Hard visibility gate: hidden before its stage (paper-thin scaled sheets
    must not float as wires in earlier shots)."""
    obj.hide_render = True
    anim(obj, "hide_render", [(f_on - 1, True), (f_on, False)], interp="CONSTANT")


# ----------------------------------------------------------------- materials
def new_mat(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (250, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    try:
        mat.surface_render_method = "BLENDED"
    except Exception:
        pass
    return mat, nt, bsdf


def pset(bsdf, sock, val):
    if sock in bsdf.inputs:
        bsdf.inputs[sock].default_value = val


def add_dim(nt, bsdf, spans, dim=0.6):
    """Multiply a DIM value into the Base Color chain of a Principled setup."""
    dimnode = nt.nodes.new("ShaderNodeValue")
    dimnode.name = "DIM"
    dimnode.label = "DIM"
    dimnode.location = (-200, -350)
    dimnode.outputs[0].default_value = 0.0
    src = bsdf.inputs["Base Color"]
    link = src.links[0] if src.is_linked else None
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    mix.location = (0, -200)
    if link:
        nt.links.new(link.from_socket, mix.inputs["A"])
    else:
        mix.inputs["A"].default_value = tuple(src.default_value)
    mix.inputs["B"].default_value = (1 - dim, 1 - dim, 1 - dim, 1)
    nt.links.new(dimnode.outputs[0], mix.inputs["Factor"])
    anim(nt, 'nodes["DIM"].outputs[0].default_value', dim_keys(spans, dim=dim))
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    return dimnode


def mat_silicon():
    mat, nt, b = new_mat("M_silicon")
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.location = (-600, 200)
    lw.inputs["Blend"].default_value = 0.55
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-400, 200)
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = rgb("#2A3138")
    e = cr.elements.new(0.28)
    e.color = rgb("#1E4C7A")
    e = cr.elements.new(0.5)
    e.color = rgb("#1FA6A0")
    e = cr.elements.new(0.72)
    e.color = rgb("#C8B44E")
    e = cr.elements.new(0.92)
    e.color = rgb("#B45AA8")
    nt.links.new(lw.outputs["Facing"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    pset(b, "Metallic", 0.3)
    pset(b, "Roughness", 0.3)
    pset(b, "Coat Weight", 0.35)
    pset(b, "Coat Roughness", 0.05)
    add_dim(nt, b, [S_SUB, S_ETCH])
    return mat


def mat_oxide():
    mat, nt, b = new_mat("M_oxide")
    pset(b, "Base Color", rgb("#AFC8F0"))
    pset(b, "Roughness", 0.08)
    pset(b, "Metallic", 0.0)
    pset(b, "Transmission Weight", 0.55)
    pset(b, "IOR", 1.46)
    pset(b, "Coat Weight", 0.4)
    add_dim(nt, b, [S_OXIDE])
    return mat


def mat_resist(green=True):
    mat, nt, b = new_mat("M_resist" if green else "M_resist_exposed")
    pset(b, "Base Color", rgb("#1FA34A" if green else "#C9D45C"))
    pset(b, "Roughness", 0.16)
    pset(b, "Coat Weight", 0.3)
    return mat


def mat_strip():
    """Exposed resist strips: color shifts to pale yellow on exposure, glows,
    then dissolves (alpha + Z collapse)."""
    mat, nt, b = new_mat("M_strip")
    mixc = nt.nodes.new("ShaderNodeMix")
    mixc.data_type = "RGBA"
    mixc.blend_type = "MIX"
    mixc.location = (-250, 150)
    mixc.inputs["A"].default_value = rgb("#1FA34A")
    mixc.inputs["B"].default_value = rgb("#D9E26A")
    expo = nt.nodes.new("ShaderNodeValue")
    expo.name = "EXPO"
    expo.location = (-450, -100)
    expo.outputs[0].default_value = 0.0
    nt.links.new(expo.outputs[0], mixc.inputs["Factor"])
    nt.links.new(mixc.outputs["Result"], b.inputs["Base Color"])
    pset(b, "Roughness", 0.16)
    em = nt.nodes.new("ShaderNodeValue")
    em.name = "GLOW"
    em.location = (-450, -300)
    em.outputs[0].default_value = 0.0
    if "Emission Strength" in b.inputs:
        nt.links.new(em.outputs[0], b.inputs["Emission Strength"])
        pset(b, "Emission Color", rgb("#8A4BFF"))
    # alpha dissolve
    al = nt.nodes.new("ShaderNodeValue")
    al.name = "ALPHA"
    al.location = (-450, -500)
    al.outputs[0].default_value = 1.0
    if "Alpha" in b.inputs:
        nt.links.new(al.outputs[0], b.inputs["Alpha"])
    mat.blend_method = "BLEND"
    try:
        mat.surface_render_method = "BLENDED"
    except Exception:
        pass
    return mat


def mat_mask():
    mat, nt, b = new_mat("M_mask")
    pset(b, "Base Color", rgb("#31363D"))
    pset(b, "Metallic", 0.85)
    pset(b, "Roughness", 0.3)
    pset(b, "Transmission Weight", 0.15)
    add_dim(nt, b, [S_MASK, S_EUV])
    return mat


def mat_copper():
    mat, nt, b = new_mat("M_copper")
    pset(b, "Base Color", rgb("#E08A4E"))
    pset(b, "Metallic", 1.0)
    pset(b, "Roughness", 0.24)
    pset(b, "Anisotropic", 0.85)
    pset(b, "Anisotropic Rotation", math.pi / 2)
    # brushed micro-streaks via stretched noise bump
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-900, -250)
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.location = (-720, -250)
    mp.inputs["Scale"].default_value = (2, 300, 2)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.location = (-540, -250)
    noise.inputs["Scale"].default_value = 6.0
    noise.inputs["Detail"].default_value = 4.0
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.location = (-300, -300)
    bump.inputs["Strength"].default_value = 0.06
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    add_dim(nt, b, [S_CU])
    return mat


def mat_beam(color="#7A2BFF"):
    """Volume-only emissive beam (no surface output)."""
    mat = bpy.data.materials.new("M_beam")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    vol = nt.nodes.new("ShaderNodeEmission")
    vol.location = (100, -150)
    vol.inputs["Color"].default_value = rgb(color)
    vol.inputs["Strength"].default_value = 0.0
    vol.name = "BeamEmit"
    nt.links.new(vol.outputs["Emission"], out.inputs["Volume"])
    return mat


def mat_floor():
    mat, nt, b = new_mat("M_floor")
    pset(b, "Base Color", rgb("#0B0D10"))
    pset(b, "Roughness", 0.38)
    pset(b, "Metallic", 0.15)
    pset(b, "Specular IOR Level", 0.8) if "Specular IOR Level" in b.inputs else pset(b, "Specular", 0.8)
    return mat


def mat_chrome():
    mat, nt, b = new_mat("M_chrome")
    pset(b, "Base Color", rgb("#9AA0A8"))
    pset(b, "Metallic", 1.0)
    pset(b, "Roughness", 0.18)
    return mat


# ------------------------------------------------------------------- geometry
def link_to_scene(obj):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    bpy.context.scene.collection.objects.link(obj)


def add_box(name, dims, center, origin=None, coll=None):
    """Box mesh; object origin at `origin` (world), verts built relative."""
    o = origin if origin is not None else center
    x, y, z = dims
    hx, hy, hz = x / 2, y / 2, z / 2
    cx, cy, cz = (center[i] - o[i] for i in range(3))
    verts = [
        (cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz),
    ]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    obj.location = o
    link_to_scene(obj)
    return obj


def bool_cut(target, cutter_objs, apply=True):
    for c in cutter_objs:
        m = target.modifiers.new("bool_" + c.name, "BOOLEAN")
        m.operation = "DIFFERENCE"
        m.solver = "EXACT"
        m.object = c
        m.show_viewport = True
        m.show_render = True
    if apply:
        prev = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = target
        for m in [x for x in target.modifiers if x.type == "BOOLEAN"]:
            bpy.ops.object.modifier_apply(modifier=m.name)
        bpy.context.view_layer.objects.active = prev
        for c in cutter_objs:  # clean up leftover cutters so they don't render
            bpy.data.objects.remove(c, do_unlink=True)


def bevel(obj, width=0.02, segs=2):
    m = obj.modifiers.new("bevel", "BEVEL")
    m.width = width
    m.segments = segs
    m.limit_method = "ANGLE"
    return m


def assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# --------------------------------------------------------------------- build
def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                  bpy.data.cameras, bpy.data.worlds):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def build():
    scene = bpy.context.scene
    clear_scene()
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = FPS

    # world: CC0 studio HDRI (Poly Haven studio_small_08) kept dim so the dark
    # studio mood holds while metals/glass get real softbox reflections.
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    hdri = os.environ.get(
        "CHIPFAB_HDRI",
        os.path.join(root, "build", "_shared", "assets", "hdri",
                     "studio_small_08_2k.hdr"))
    world = bpy.data.worlds.new("studio")
    scene.world = world
    world.use_nodes = True
    wnt = world.node_tree
    wnt.nodes.clear()
    wout = wnt.nodes.new("ShaderNodeOutputWorld")
    bg = wnt.nodes.new("ShaderNodeBackground")
    if os.path.isfile(hdri):
        env = wnt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(hdri, check_existing=True)
        mp = wnt.nodes.new("ShaderNodeMapping")
        tc = wnt.nodes.new("ShaderNodeTexCoord")
        mp.inputs["Rotation"].default_value[2] = 2.1
        wnt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
        wnt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
        wnt.links.new(env.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.3
        # camera rays see a near-black backdrop; reflections/lights still use HDRI
        bgdark = wnt.nodes.new("ShaderNodeBackground")
        bgdark.inputs[0].default_value = (0.008, 0.010, 0.014, 1.0)
        bgdark.inputs[1].default_value = 1.0
        lp = wnt.nodes.new("ShaderNodeLightPath")
        mixs = wnt.nodes.new("ShaderNodeMixShader")
        wnt.links.new(lp.outputs["Is Camera Ray"], mixs.inputs["Fac"])
        wnt.links.new(bg.outputs["Background"], mixs.inputs[1])
        wnt.links.new(bgdark.outputs["Background"], mixs.inputs[2])
        wnt.links.new(mixs.outputs["Shader"], wout.inputs["Surface"])
        print("WORLD_HDRI", hdri)
    else:
        bg.inputs[0].default_value = (0.012, 0.015, 0.022, 1.0)
        bg.inputs[1].default_value = 1.0
        wnt.links.new(bg.outputs["Background"], wout.inputs["Surface"])
        print("WORLD_HDRI_MISSING_FLATFALLBACK")

    # floor
    floor = add_box("floor", (60, 60, 0.1), (0, 0, -T_SUB - 0.05 - 0.05))
    assign(floor, mat_floor())

    # substrate (wafer slice) — origin at center so scale-in works
    sub = add_box("substrate", (WA, WB, T_SUB), (0, 0, -T_SUB / 2))
    bevel(sub, 0.03, 3)
    assign(sub, mat_silicon())
    sub.scale = (0.2, 0.2, 0.2)
    anim(sub, "scale[0]", [(5, 0.2), (17, 1.0)])
    anim(sub, "scale[1]", [(5, 0.2), (17, 1.0)])
    anim(sub, "scale[2]", [(5, 0.2), (17, 1.0)])

    # oxide layer — grows up from wafer top (origin at z=0)
    ox = add_box("oxide", (WA, WB, Z_OX_TOP), (0, 0, Z_OX_TOP / 2), origin=(0, 0, 0))
    assign(ox, mat_oxide())
    ox.scale[2] = 0.001
    anim(ox, "scale[2]", [(27, 0.001), (41, 1.0)])
    gate(ox, 27)

    # unexposed photoresist slab with 4 slots (spin-coat: spread along Y)
    slot_cutters = []
    res = add_box("resist", (WA, WB, Z_RES_TOP - Z_OX_TOP),
                  (0, 0, (Z_RES_TOP + Z_OX_TOP) / 2), origin=(0, 0, Z_OX_TOP))
    for i, x in enumerate(X_SLOTS):
        slot_cutters.append(add_box(f"slotcutter{i}", (SLOT_W, SLOT_L, 1.0),
                                    (x, 0, Z_OX_TOP + 0.5)))
    bool_cut(res, slot_cutters, apply=True)
    assign(res, mat_resist(True))
    res.scale[1] = 0.001
    anim(res, "scale[1]", [(52, 0.001), (68, 1.0)])
    gate(res, 52)

    # exposed resist strips (sit inside the slots; dissolve on develop)
    strips = []
    for i, x in enumerate(X_SLOTS):
        st = add_box(f"strip{i}", (SLOT_W - 0.002, SLOT_L - 0.002, Z_RES_TOP - Z_OX_TOP),
                     (x, 0, (Z_RES_TOP + Z_OX_TOP) / 2), origin=(x, 0, Z_OX_TOP))
        assign(st, mat_strip())
        st.scale[2] = 0.001
        gate(st, 52)
        strips.append(st)

    # photomask plate with matching cut-outs; chrome frame
    plate = add_box("mask", (SLOT_W * 4 + 1.8, SLOT_L + 1.0, 0.06),
                    (0, 0, MASK_Z), origin=(0, 0, MASK_Z))
    mask_cut = [add_box(f"maskhole{i}", (SLOT_W, SLOT_L, 1.0), (x, 0, MASK_Z))
                for i, x in enumerate(X_SLOTS)]
    bool_cut(plate, mask_cut, apply=True)
    assign(plate, mat_mask())
    frame = add_box("maskframe", (SLOT_W * 4 + 2.4, SLOT_L + 1.6, 0.10),
                    (0, 0, MASK_Z), origin=(0, 0, MASK_Z))
    fh = add_box("framehole", (SLOT_W * 4 + 1.7, SLOT_L + 0.9, 1.2), (0, 0, MASK_Z))
    bool_cut(frame, [fh], apply=True)
    assign(frame, mat_chrome())
    for ob in (plate, frame):
        ob.location[2] = 3.6
        anim(ob, "location[2]", [(78, 3.6), (103, MASK_Z),
                                 (158, MASK_Z), (180, 4.8)])
        gate(ob, 76)
        anim(ob, "hide_render", [(181, False), (182, True)], interp="CONSTANT")

    # EUV source head
    head = add_box("euv_head", (3.6, 2.0, 0.5), (0, 0, 3.8), origin=(0, 0, 3.8))
    assign(head, mat_chrome())
    head.scale[2] = 0.001
    anim(head, "scale[2]", [(104, 0.001), (114, 1.0)])
    gate(head, 104)

    # EUV beam: downward-widening cone volume + per-slot shafts
    me = bpy.data.meshes.new("beamcone")
    z_top, z_bot = 3.52, 0.95
    r_top, r_bot = 0.24, 1.85
    verts, faces = [], []
    n = 48
    for k in range(n):
        a = 2 * math.pi * k / n
        verts.append((r_top * math.cos(a), r_top * math.sin(a), z_top))
    for k in range(n):
        a = 2 * math.pi * k / n
        verts.append((r_bot * math.cos(a), r_bot * math.sin(a), z_bot))
    for k in range(n):
        k2 = (k + 1) % n
        faces.append((k, k2, n + k2))
        faces.append((k, n + k2, n + k))
    faces.append(tuple(range(n - 1, -1, -1)))
    faces.append(tuple(range(n, 2 * n)))
    me.from_pydata(verts, [], faces)
    me.update()
    beam = bpy.data.objects.new("beam", me)
    link_to_scene(beam)
    m_beam = mat_beam("#7A2BFF")
    assign(beam, m_beam)

    shafts = []
    for i, x in enumerate(X_SLOTS):
        sh = add_box(f"shaft{i}", (SLOT_W - 0.02, SLOT_L - 0.02, 0.72),
                     (x, 0, (0.80 + 0.08) / 2))
        assign(sh, m_beam)
        shafts.append(sh)

    def beam_keys(base):
        return [(111, 0.0), (118, base), (126, base * 0.85), (134, base),
                (142, base * 0.85), (148, base), (154, 0.0)]

    anim(m_beam.node_tree, 'nodes["BeamEmit"].inputs["Strength"].default_value',
         beam_keys(1.8))
    # volume-only meshes show as glass slabs outside the beam window: cull them
    for b in [beam] + shafts:
        b.hide_render = True
        anim(b, "hide_render", [(109, True), (110, False),
                                (156, False), (157, True)],
             interp="CONSTANT")

    # etch cutters (animated downward; boolean modifiers kept live)
    cutters = []
    for i, x in enumerate(X_SLOTS):
        c = add_box(f"etchcutter{i}", (SLOT_W, SLOT_L, 1.2),
                    (x, 0, TRENCH_FLOOR + 0.6 + 0.40), origin=(x, 0, TRENCH_FLOOR + 0.6 + 0.40))
        c.display_type = "WIRE"
        c.hide_render = True
        cutters.append(c)
        anim(c, "location[2]", [(183, TRENCH_FLOOR + 1.0 + 0.34),
                                (207, TRENCH_FLOOR + 0.6)])
    # live booleans: carve oxide + substrate
    for tgt in (ox, sub):
        for c in cutters:
            m = tgt.modifiers.new("etch_" + c.name, "BOOLEAN")
            m.operation = "DIFFERENCE"
            m.solver = "EXACT"
            m.object = c

    # copper interconnect pillars: grow from trench floor
    cus = []
    for i, x in enumerate(X_SLOTS):
        cu = add_box(f"copper{i}", (SLOT_W - 0.10, SLOT_L - 0.18, 0.50),
                     (x, 0, TRENCH_FLOOR + 0.25 - 0.07), origin=(x, 0, TRENCH_FLOOR))
        bevel(cu, 0.012, 2)
        assign(cu, mat_copper())
        cu.scale[2] = 0.001
        f0 = 238 + i * 4
        anim(cu, "scale[2]", [(f0, 0.001), (f0 + 18, 1.0)])
        gate(cu, f0)
        cus.append(cu)

    # ---------------- strip-stage animation on resist + exposed strips -------
    m_strip = bpy.data.materials["M_strip"]
    nt = m_strip.node_tree
    # exposure glow + color shift while beam on
    anim(nt, 'nodes["GLOW"].outputs[0].default_value',
         [(112, 0.0), (120, 2.4), (134, 1.6), (148, 2.4), (155, 0.4), (164, 0.0)])
    anim(nt, 'nodes["EXPO"].outputs[0].default_value',
         [(150, 0.0), (158, 1.0)])
    # develop: dissolve exposed strips (alpha + Z collapse)
    anim(nt, 'nodes["ALPHA"].outputs[0].default_value',
         [(162, 1.0), (176, 0.0)])
    for st in strips:
        anim(st, "scale[2]", [(52, 0.001), (68, 1.0), (162, 1.0), (178, 0.06)])
        anim(st, "hide_render", [(179, False), (180, True)], interp="CONSTANT")
    # strip stage: remove remaining resist
    anim(res, "scale[2]", [(214, 1.0), (232, 0.02)])
    anim(res, "hide_render", [(233, False), (234, True)], interp="CONSTANT")
    m_res = bpy.data.materials["M_resist"]
    if "Alpha" in m_res.node_tree.nodes["Principled BSDF"].inputs and \
            "Principled BSDF" in m_res.node_tree.nodes:
        pb = m_res.node_tree.nodes["Principled BSDF"]
        if pb.inputs["Alpha"].is_linked:
            pass
        else:
            pb.inputs["Alpha"].default_value = 1.0
            anim(m_res.node_tree, 'nodes["Principled BSDF"].inputs["Alpha"].default_value',
                 [(214, 1.0), (232, 0.0)])

    # dims: strip material has its own handling (keep un-dimmed small)
    # ---------------- lights --------------------------------------------------
    def area(name, loc, energy, size, color, target=(0, 0, 0.1)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = size
        ld.color = color
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        link_to_scene(ob)
        d = mathutils.Vector(target) - mathutils.Vector(loc)
        ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        return ob

    area("key", (4.5, -3.5, 5.0), 620, 4.0, (1.0, 0.95, 0.88))
    area("fill", (-5.0, -2.5, 2.2), 110, 3.0, (0.75, 0.84, 1.0))
    area("rim", (-1.0, 5.0, 3.8), 460, 2.0, (0.9, 0.96, 1.0))
    evu_light = area("euv_light", (0, 0, 2.4), 0.0, 1.6, (0.55, 0.25, 1.0))
    anim(evu_light.data, "energy", [(111, 0.0), (118, 110.0), (148, 110.0), (154, 0.0)])

    # ---------------- camera ---------------------------------------------------
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 50
    cam = bpy.data.objects.new("camera", cam_data)
    link_to_scene(cam)
    scene.camera = cam
    tgt = bpy.data.objects.new("cam_target", None)
    link_to_scene(tgt)
    con = cam.constraints.new("TRACK_TO")
    con.target = tgt
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"

    cam_path = [
        (1, (9.0, -8.4, 5.6)), (S_SUB[1], (8.4, -7.7, 4.9)),
        (S_RESIST[0], (7.6, -6.8, 4.0)), (S_MASK[0], (7.4, -6.2, 3.6)),
        (S_EUV[0], (7.0, -5.8, 3.4)), (S_DEV[0], (6.4, -5.4, 3.1)),
        (S_ETCH[0], (6.2, -5.0, 2.8)), (S_STRIP[0], (5.8, -4.8, 2.6)),
        (S_CU[0], (5.6, -4.4, 2.3)), (S_CU[1], (5.2, -4.2, 2.2)),
        (FRAME_END, (4.8, -3.8, 2.0)),
    ]
    tgt_path = [
        (1, (0, 0, 0.0)), (S_OXIDE[0], (0, 0, 0.05)),
        (S_RESIST[0], (0, 0, 0.08)), (S_MASK[0], (0, 0, 0.9)),
        (S_EUV[0], (0, 0, 0.9)), (S_DEV[0], (0, 0, 0.15)),
        (S_ETCH[0], (0.2, 0, 0.0)), (S_STRIP[0], (0, 0, 0.05)),
        (S_CU[0], (0, 0, 0.12)), (FRAME_END, (0, 0, 0.15)),
    ]
    for f, (x, y, z) in cam_path:
        set_prop(cam, "location[0]", x)
        set_prop(cam, "location[1]", y)
        set_prop(cam, "location[2]", z)
        cam.keyframe_insert("location", frame=f)
    for f, (x, y, z) in tgt_path:
        set_prop(tgt, "location[0]", x)
        set_prop(tgt, "location[1]", y)
        set_prop(tgt, "location[2]", z)
        tgt.keyframe_insert("location", frame=f)
    for ob in (cam, tgt):
        for fc in iter_fcurves(ob):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.easing = "AUTO"
                try:
                    kp.handle_left_type = "AUTO_CLAMPED"
                    kp.handle_right_type = "AUTO_CLAMPED"
                except TypeError:
                    pass
    cam_data.dof.use_dof = True
    cam_data.dof.focus_object = tgt
    cam_data.dof.aperture_fstop = 5.0
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.5

    # ---------------- compositor glare (bloom for volumetric EUV) --------------
    try:  # Blender 5.x: compositor node group with socket-driven params
        ng = bpy.data.node_groups.new("chipfab_comp", "CompositorNodeTree")
        scene.compositing_node_group = ng
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        rl = ng.nodes.new("CompositorNodeRLayers")
        glare = ng.nodes.new("CompositorNodeGlare")
        glare.inputs["Type"].default_value = "Fog Glow"
        glare.inputs["Threshold"].default_value = 1.1
        glare.inputs["Size"].default_value = 8
        glare.inputs["Strength"].default_value = 0.7
        out = ng.nodes.new("NodeGroupOutput")
        ng.links.new(rl.outputs["Image"], glare.inputs["Image"])
        ng.links.new(glare.outputs["Image"], out.inputs["Image"])
        print("COMPOSITOR_OK")
    except Exception as exc:
        print("COMPOSITOR_SKIP", type(exc).__name__, exc)

    # view transform
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Punchy"
    except Exception:
        try:
            scene.view_settings.view_transform = "Filmic"
        except Exception:
            pass
    try:
        scene.view_settings.exposure = -0.6
    except Exception:
        pass

    # strip material has no DIM node; give strips/mask-lite their own subtle dim via base? skip.
    return scene


# -------------------------------------------------------------------- render
def set_engine(engine):
    scene = bpy.context.scene
    if engine == "eevee":
        ok = None
        for cand in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            try:
                scene.render.engine = cand
                ok = cand
                break
            except TypeError:
                continue
        if ok is None:
            raise RuntimeError("cannot set EEVEE engine")
        ee = scene.eevee
        ee.taa_render_samples = 24
        for attr, val in (
            ("use_raytracing", True),
            ("use_gtao", True),
            ("gtao_distance", 0.3),
            ("volumetric_tile_size", "4"),
            ("volumetric_samples", 96),
            ("volumetric_end", 30.0),
            ("use_shadows", True),
            ("ray_tracing_method", "PROBE" if hasattr(ee, "ray_tracing_method") else None),
        ):
            if val is None:
                continue
            try:
                setattr(ee, attr, val)
            except Exception:
                pass
        print(f"ENGINE {ok}")
        return ok
    scene.render.engine = "CYCLES"
    try:
        bpy.ops.preferences.addon_enable(module="cycles")
    except Exception:
        pass
    cy = scene.cycles
    cy.use_denoising = True
    try:
        cy.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.05
    cy.max_bounces = 6
    cy.transmission_bounces = 6
    cy.volume_bounces = 0
    cy.volume_step_rate = 1.6
    cy.blur_glossy = 1.0
    scene.render.use_persistent_data = True
    if engine == "cycles_gpu":
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "ONEAPI"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == "ONEAPI"
        scene.cycles.device = "GPU"
        print("CYCLES_DEVICES", [d.name for d in prefs.devices if d.use])
    else:
        scene.cycles.device = "CPU"
    print(f"ENGINE CYCLES {engine}")
    return "CYCLES"


def configure_output(out_path, res, samples):
    scene = bpy.context.scene
    w, h = res
    scene.render.resolution_x = w
    scene.render.resolution_y = h
    scene.render.resolution_percentage = 100
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = samples
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    ext = os.path.splitext(out_path)[1].lower()
    if ext == ".mp4":
        scene.render.image_settings.media_type = "VIDEO"
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "HIGH"
        scene.render.ffmpeg.audio_codec = "NONE"
        scene.render.filepath = out_path
    else:
        scene.render.image_settings.media_type = "IMAGE"
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = out_path


def debug_dump(scene):
    for f in (15, 60, 130, 255):
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        print(f"=== FRAME {f} render-visible objects ===")
        for ob in scene.objects:
            vis = getattr(ob, "visible_render", None)
            if vis is None:
                vis = not ob.hide_render
            if not vis:
                continue
            ev = ob.evaluated_get(dg)
            bb = [ev.matrix_world @ mathutils.Vector(c) for c in ev.bound_box]
            mn = [min(v[i] for v in bb) for i in range(3)]
            mx = [max(v[i] for v in bb) for i in range(3)]
            mats = [m.name if m else "-" for m in ev.data.materials] if hasattr(ev.data, "materials") else []
            print(f"  {ob.name:14s} x[{mn[0]:+.2f},{mx[0]:+.2f}] y[{mn[1]:+.2f},{mx[1]:+.2f}] z[{mn[2]:+.2f},{mx[2]:+.2f}] {mats}")
    w = scene.world
    if w and w.use_nodes:
        print("WORLD nodes:", [n.bl_idname for n in w.node_tree.nodes])


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="build",
                    choices=["build", "stills", "anim", "debug"])
    ap.add_argument("--engine", default="eevee",
                    choices=["eevee", "cycles_gpu", "cycles_cpu"])
    ap.add_argument("--res", default="1920x1080")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--frames", default="1-288")
    ap.add_argument("--out", default="")
    ap.add_argument("--blend", default="")
    args = ap.parse_args(argv)
    if args.out:
        args.out = os.path.abspath(args.out)
    if args.blend:
        args.blend = os.path.abspath(args.blend)

    scene = build()
    set_engine(args.engine)
    w, h = (int(v) for v in args.res.lower().split("x"))

    if args.blend:
        os.makedirs(os.path.dirname(os.path.abspath(args.blend)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=args.blend)
        print("BLEND_SAVED", args.blend)

    if args.mode == "build":
        print(f"STATS objects={len(scene.objects)} frames={scene.frame_end}")
        return 0
    if args.mode == "debug":
        debug_dump(scene)
        return 0
    if args.mode == "anim":
        a, b = (int(v) for v in args.frames.split("-"))
        scene.frame_start, scene.frame_end = a, b
        configure_output(args.out, (w, h), args.samples)
        bpy.ops.render.render(animation=True)
        print("RENDER_OK", args.out)
        return 0
    if args.mode == "stills":
        configure_output(os.path.join(args.out, "prev_"), (w, h), args.samples)
        for f in (int(v) for v in args.frames.split(",")):
            scene.frame_set(f)
            scene.render.filepath = os.path.join(args.out, f"prev_{f:03d}.png")
            bpy.ops.render.render(write_still=True)
            print("STILL", f)
        print("STILLS_OK")
        return 0


if __name__ == "__main__":
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    sys.exit(main(argv))
