import bpy, math, os, time
from pathlib import Path
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
try: sc.eevee.use_raytracing = True
except Exception as e: print("rt err", e)
sc.eevee.taa_render_samples = 16

# clear factory default world -> mid grey so a truly-empty render is distinguishable from a lit cube
w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.10, 0.10, 0.11, 1.0)
bg.inputs[1].default_value = 1.0

bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0,0,0))
sph = bpy.context.active_object
m = bpy.data.materials.new("M"); m.use_nodes=True
bsdf = m.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.8,0.2,0.2,1.0)
bsdf.inputs["Metallic"].default_value = 0.0
bsdf.inputs["Roughness"].default_value = 0.4
sph.data.materials.append(m)

# strong sun so a lit surface is unambiguous
sun = bpy.data.lights.new("SUN",'SUN'); sun.energy = 6.0; sun.angle = math.radians(3)
so = bpy.data.objects.new("SUN", sun); sc.collection.objects.link(so)
so.rotation_euler = (math.radians(45), 0, math.radians(30))

cam = bpy.data.cameras.new("C"); cam.lens = 50; co = bpy.data.objects.new("CAM", cam)
sc.collection.objects.link(co); sc.camera = co
co.location = (4,-4,2)
tgt = bpy.data.objects.new("TGT", None); sc.collection.objects.link(tgt)
ctr = co.constraints.new('TRACK_TO'); ctr.target=tgt; ctr.track_axis='TRACK_NEGATIVE_Z'; ctr.up_axis='UP_Y'

sc.render.resolution_x=480; sc.render.resolution_y=270
sc.view_settings.view_transform='AgX'
sc.render.image_settings.file_format='PNG'
_content = os.environ.get("COURSEWORKSPACE_CONTENT_ROOT") or str(
    Path(__file__).resolve().parents[3] / "content_data")
sc.render.filepath = _content + "/build/_logs/gpu5090_probe_lit.png"
t=time.time()
bpy.ops.render.render(write_still=True)
# measure non-background pixels
import numpy as np
img = bpy.data.images.load(sc.render.filepath)
px = np.array(img.pixels[:]).reshape(-1,4)
lum = px[:,:3].mean(axis=1)
print("PROBE_OK secs=%.1f  mean_lum=%.4f  frac_lum_gt_0.15=%.3f  max_lum=%.3f"
      % (time.time()-t, lum.mean(), (lum>0.15).mean(), lum.max()))
