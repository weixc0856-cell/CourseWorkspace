"""Offscreen VTK render capability probe. Plumbing test only, not course content."""
import sys
from pathlib import Path

import pyvista as pv

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)

pv.OFF_SCREEN = True
pv.global_theme.background = "#12161c"

p = pv.Plotter(off_screen=True, window_size=(1920, 1080))
p.set_background("#12161c")
body = pv.Sphere(radius=0.5, theta_resolution=120, phi_resolution=120)
p.add_mesh(body, color="#d8d2c4", smooth_shading=True, pbr=True, metallic=0.1, roughness=0.45)
plane = pv.Plane(center=(0, 0, -0.55), direction=(0, 0, 1), i_size=4, j_size=4)
p.add_mesh(plane, color="#2a3038", roughness=0.9)
p.add_mesh(body.slice(normal="y"), color="#e8733b", line_width=3)
p.enable_anti_aliasing("ssaa")
p.enable_ssao(radius=0.06, bias=0.005)
p.enable_shadows()
p.camera_position = [(2.4, -2.6, 1.3), (0, 0, 0), (0, 0, 1)]
p.camera.zoom(1.15)
p.screenshot(str(out / "probe_ssao.png"))
print("wrote", out / "probe_ssao.png")

p2 = pv.Plotter(off_screen=True, window_size=(1920, 1080))
p2.set_background("#fbfaf7")
p2.add_mesh(body, color="#3a4048", smooth_shading=True)
p2.enable_anti_aliasing("fxaa")
p2.camera_position = [(2.4, -2.6, 1.3), (0, 0, 0), (0, 0, 1)]
p2.screenshot(str(out / "probe_light.png"))
print("wrote", out / "probe_light.png")
print("vtk", pv.vtk_version_info, "pyvista", pv.__version__)