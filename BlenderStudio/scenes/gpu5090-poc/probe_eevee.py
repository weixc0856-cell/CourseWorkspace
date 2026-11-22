import bpy, os, sys, time
from pathlib import Path

# --- available render engines
eng_prop = bpy.types.RenderSettings.bl_rna.properties["engine"]
print("ENGINES:", [i.identifier for i in eng_prop.enum_items])

# --- gpu backend options
sysp = bpy.context.preferences.system
try:
    gp_prop = sysp.bl_rna.properties["gpu_backend"]
    print("GPU_BACKEND_OPTIONS:", [i.identifier for i in gp_prop.enum_items])
except Exception as e:
    print("gpu_backend prop err:", e)
print("GPU_BACKEND_CURRENT:", getattr(sysp, "gpu_backend", "n/a"))

# --- cycles compute devices (informational; fallback is CPU)
try:
    cp = bpy.context.preferences.addons["cycles"].preferences
    print("COMPUTE_DEVICE_TYPES:", [i.identifier for i in cp.bl_rna.properties["compute_type"].enum_items])
    for dt in ("OPTIX","CUDA","HIP","ONEAPI","METAL","VULKAN"):
        try:
            cp.compute_device_type = dt
            cp.get_devices()
            devs = [(d.name, d.type, d.use) for d in cp.devices]
            print("  ", dt, "->", devs)
        except Exception as e:
            print("  ", dt, "err", e)
except Exception as e:
    print("cycles pref err:", e)

# --- try EEVEE Next single tiny frame render
target_engines = [i.identifier for i in eng_prop.enum_items]
eevee = None
for cand in ("BLENDER_EEVEE_NEXT","BLENDER_EEVEE"):
    if cand in target_engines:
        eevee = cand; break
print("EEVEE_IDENTIFIER:", eevee)

if eevee:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = eevee
    # try to enable raytracing etc, tolerant
    for attr in ("use_raytracing",):
        try: setattr(sc.eevee, attr, True)
        except Exception as e: print("eevee set err", attr, e)
    try: sc.eevee.taa_render_samples = 8
    except Exception as e: print("taa err", e)
    # minimal cube + light
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,0))
    bpy.ops.object.light_add(type='AREA', location=(2,-2,3))
    cam = bpy.data.cameras.new("C"); co = bpy.data.objects.new("CAM", cam); sc.collection.objects.link(co); sc.camera=co; co.location=(4,-4,3)
    dco = co.constraints.new('TRACK_TO'); dco.target = bpy.context.active_object
    sc.render.resolution_x=320; sc.render.resolution_y=180
    sc.render.image_settings.file_format='PNG'
    _content = os.environ.get("COURSEWORKSPACE_CONTENT_ROOT") or str(
        Path(__file__).resolve().parents[3] / "content_data")
    sc.render.filepath = _content + "/build/_logs/gpu5090_probe_eevee.png"
    t=time.time()
    try:
        bpy.ops.render.render(write_still=True)
        print("EEVEE_RENDER_OK  secs=%.1f" % (time.time()-t))
    except Exception as e:
        print("EEVEE_RENDER_FAIL:", repr(e))
