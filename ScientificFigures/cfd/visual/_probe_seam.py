"""OpenFOAM -> VTK seam probe on pitzDaily. Plumbing test only, not course content.

Checks: native OpenFOAM reader, kinematic-pressure Cp conversion, reverse-flow
contour (recirculation boundary), streamline integration, offscreen render quality.
"""
import sys
from pathlib import Path

import numpy as np
import pyvista as pv

case = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
U_INF = 10.0  # pitzDaily inlet

stub = case / "seam.foam"
stub.write_text("", encoding="utf-8")
reader = pv.OpenFOAMReader(str(stub))
reader.set_active_time_value(reader.time_values[-1])
reader.cell_to_point_creation = True
block = reader.read()
print("blocks:", block.keys())
mesh = block["internalMesh"]
print("cells", mesh.n_cells, "arrays", mesh.point_data.keys())

# incompressible simpleFoam: p is kinematic (m^2/s^2), p_inf = 0
mesh.point_data["Cp"] = mesh.point_data["p"] / (0.5 * U_INF**2)
ux = mesh.point_data["U"][:, 0]
mesh.point_data["Ux"] = ux
print(f"Cp range {mesh.point_data['Cp'].min():.3f} .. {mesh.point_data['Cp'].max():.3f}")
print(f"Ux range {ux.min():.3f} .. {ux.max():.3f}  reverse-flow cells: {(ux < 0).sum()}")

bounds = mesh.bounds
zmid = 0.5 * (bounds[4] + bounds[5])
slab = mesh.slice(normal="z", origin=(0, 0, zmid))

pv.OFF_SCREEN = True
p = pv.Plotter(off_screen=True, window_size=(1920, 1080))
p.set_background("#12161c")
p.add_mesh(
    slab,
    scalars="Cp",
    cmap="coolwarm",
    clim=(-0.6, 0.6),
    show_scalar_bar=False,
    smooth_shading=True,
)
# recirculation boundary: Ux = 0 iso-contour, computed from the solved field
rev = slab.contour(isosurfaces=[0.0], scalars="Ux")
if rev.n_points:
    p.add_mesh(rev, color="#e8733b", line_width=4, render_lines_as_tubes=True)
    print("reverse-flow contour points:", rev.n_points)
else:
    print("NO reverse-flow contour found")

seed = pv.Line(
    (bounds[0] + 1e-4, bounds[2] + 0.005, zmid),
    (bounds[0] + 1e-4, bounds[3] - 0.002, zmid),
    resolution=26,
)
lines = slab.streamlines_from_source(seed, vectors="U", max_length=2.0, integration_direction="forward")
print("streamline points:", lines.n_points)
if lines.n_points:
    p.add_mesh(lines, color="#f2efe6", line_width=2, opacity=0.75, render_lines_as_tubes=True)

p.enable_anti_aliasing("ssaa")
p.camera_position = [
    (0.5 * (bounds[0] + bounds[1]), 0.5 * (bounds[2] + bounds[3]), 0.55),
    (0.5 * (bounds[0] + bounds[1]), 0.5 * (bounds[2] + bounds[3]), zmid),
    (0, 1, 0),
]
p.camera.parallel_projection = True
p.camera.parallel_scale = 0.09
p.screenshot(str(out / "seam_cp.png"))
print("wrote", out / "seam_cp.png")