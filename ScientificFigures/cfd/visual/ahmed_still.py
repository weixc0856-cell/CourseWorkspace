"""Ahmed 25 deg RANS mean field, presentation still. All elements solver-derived."""
import sys
from pathlib import Path

import numpy as np
import pyvista as pv

sys.path.insert(0, str(Path(__file__).parent))
from flowfield import load, pathlines

case_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
c = load(case_dir, u_inf=40.0)
m, body = c.mesh, c.body

cp_body = body.point_data["Cp"]
print(f"body Cp min {cp_body.min():.3f} max {cp_body.max():.3f}")
n = np.asarray(body.cell_normals)
cc = body.cell_centers().points
base_mask = (np.abs(n[:, 0]) > 0.9) & (cc[:, 0] > 1.035)
base = body.extract_cells(base_mask)
if base.n_cells:
    print(f"base faces {base.n_cells} mean base Cp {(base.point_data['p'] / 800.0).mean():.4f}")
else:
    print("base faces: none matched")

wake = m.clip_box((1.06, 3.5, -0.6, 0.6, 0.06, 0.9), invert=False)
rev = wake.contour(isosurfaces=[-0.5], scalars="Ux")
rev_pts = rev.points
print("recirc iso points", rev.n_points, "length behind base",
      f"{rev_pts[:, 0].max() - 1.044:.3f} m" if rev.n_points else "n/a")

body.point_data["wssx"] = body.point_data["wallShearStress"][:, 0]
# separation line only where the surface faces upstream-up: on the vertical base
# wss_x is trivially ~0 and its zero contour carries no separation meaning
slant_mask = (np.abs(n[:, 2]) > 0.25) & (cc[:, 0] > 0.80) & (cc[:, 0] < 1.043) & (cc[:, 2] > 0.19)
slant = body.extract_cells(slant_mask)
sep = slant.contour(isosurfaces=[0.0], scalars="wssx")
print("slant faces", slant.n_cells, "separation-line points", sep.n_points)

ys = np.linspace(-0.17, 0.17, 11)
zs = np.linspace(0.07, 0.40, 13)
far = np.array([[-0.6, y, z] for z in zs for y in ys])
rake = np.array([[0.55, y, z] for z in np.linspace(0.292, 0.36, 9) for y in np.linspace(-0.16, 0.16, 9)])
pl = pathlines(m, pv.PolyData(np.vstack([far, rake])), max_length=6.0)
rng = np.random.default_rng(7)
phase = np.array([rng.uniform(0, t[-1]) for t in pl.travel])
print("pathlines", len(pl.points))

pv.OFF_SCREEN = True
p = pv.Plotter(off_screen=True, window_size=(1920, 1080))
p.set_background("#0e1218")
p.add_mesh(pv.Plane(center=(1.2, 0, 0), direction=(0, 0, 1), i_size=9, j_size=6),
           color="#242c36", roughness=0.95)
p.add_mesh(body, scalars="Cp", cmap="RdBu_r", clim=(-0.6, 0.6), show_scalar_bar=False,
           smooth_shading=True)
if rev.n_points:
    p.add_mesh(rev, color="#6fa8d6", opacity=0.30, smooth_shading=True)
if sep.n_points:
    p.add_mesh(sep, color="#e8733b", line_width=7, render_lines_as_tubes=True)
for pts in pl.points:
    p.add_mesh(pv.Spline(pts, max(len(pts) // 3, 10)), color="#9fb0c4", line_width=2, opacity=0.40)
T = np.array([t[-1] for t in pl.travel])
pos, spd = [], []
for shift in (0.0, 1 / 3, 2 / 3):
    q, s = pl.markers(0.0, phase + shift * T)
    pos.append(q)
    spd.append(s)
cloud = pv.PolyData(np.vstack(pos))
cloud.point_data["speed"] = np.concatenate(spd)
p.add_mesh(cloud, scalars="speed", cmap="autumn", clim=(0, 45), render_points_as_spheres=True,
           point_size=10, show_scalar_bar=False)
p.enable_anti_aliasing("ssaa")
p.camera_position = [(2.30, -1.30, 0.70), (1.00, 0.0, 0.17), (0, 0, 1)]
p.camera.view_angle = 30
p.screenshot(str(out / "ahmed25_v3.png"))
print("wrote", out / "ahmed25_v3.png")