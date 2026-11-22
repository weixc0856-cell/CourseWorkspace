"""Pathline animation probe on the seam case. Plumbing test, not course content."""
import sys
from pathlib import Path

import numpy as np
import pyvista as pv

sys.path.insert(0, str(Path(__file__).parent))
from flowfield import load, pathlines, screen_xy

case_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
c = load(case_dir, u_inf=10.0)
b = c.mesh.bounds
zmid = 0.5 * (b[4] + b[5])
slab = c.mesh.slice(normal="z", origin=(0, 0, zmid))
print("Cp clim from data:", np.round(c.cp_clim, 3), "time", c.time)

seed = pv.Line((b[0] + 2e-4, b[2] + 0.004, zmid), (b[0] + 2e-4, b[3] - 0.001, zmid), resolution=30)
pl = pathlines(slab, seed, max_length=1.0)
print("pathlines:", len(pl.points), "max travel time", max(t[-1] for t in pl.travel))
phase = np.linspace(0, 1, len(pl.points)) * max(t[-1] for t in pl.travel)

W, H = b[1] - b[0], b[3] - b[2]
cx, cy = 0.5 * (b[0] + b[1]), 0.5 * (b[2] + b[3])
scale = max(H / 2, W / 2 / (16 / 9)) * 1.08

pv.OFF_SCREEN = True
for k, t in enumerate([0.0, 0.012, 0.024]):
    p = pv.Plotter(off_screen=True, window_size=(1920, 1080))
    p.set_background("#0f1319")
    p.add_mesh(slab, scalars="Cp", cmap="RdBu_r", clim=c.cp_clim, show_scalar_bar=False, smooth_shading=True)
    rev = slab.contour(isosurfaces=[0.0], scalars="Ux")
    if rev.n_points:
        p.add_mesh(rev, color="#e8733b", line_width=5, render_lines_as_tubes=True)
    for pts in pl.points:
        p.add_mesh(pv.Spline(pts, max(len(pts) // 2, 8)), color="#cfd6e0", line_width=1, opacity=0.28)
    pos, spd = pl.markers(t, phase)
    cloud = pv.PolyData(pos)
    cloud.point_data["speed"] = spd
    p.add_mesh(
        cloud,
        scalars="speed",
        cmap="autumn",
        clim=(0, 11),
        render_points_as_spheres=True,
        point_size=11,
        show_scalar_bar=False,
    )
    p.enable_anti_aliasing("ssaa")
    p.camera_position = [(cx, cy, zmid + 0.5), (cx, cy, zmid), (0, 1, 0)]
    p.camera.parallel_projection = True
    p.camera.parallel_scale = scale
    p.screenshot(str(out / f"anim_{k:02d}.png"))
    if k == 0:
        print("anchor px for step corner:", screen_xy(p, (0.0, b[2], zmid), 1080))
    p.close()
print("wrote 3 frames to", out)