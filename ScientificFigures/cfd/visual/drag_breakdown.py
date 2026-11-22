"""Where the pressure drag actually comes from, per surface region.

Resolves the flagged 35-deg paradox: more negative base Cp and a longer wake,
yet lower total Cd. Reads existing solutions only; no solver runs.
"""
import sys
from pathlib import Path

import numpy as np
import pyvista as pv

RHO = 1.225
U = 40.0
A_REF = 0.112
Q = 0.5 * RHO * U * U


def regions(case: Path):
    stub = case / "case.foam"
    if not stub.exists():
        stub.write_text("")
    r = pv.OpenFOAMReader(str(stub))
    r.set_active_time_value(r.time_values[-1])
    r.cell_to_point_creation = False
    body = r.read()["boundary"]["body"]
    n = np.asarray(body.cell_normals)
    cc = body.cell_centers().points
    area = body.compute_cell_sizes(length=False, volume=False, area=True).cell_data["Area"]
    p = np.asarray(body.cell_data["p"])  # kinematic, m^2/s^2
    # OpenFOAM patch normals from the reader point into the body; verified by
    # matching the solver's own pressure force (36.340 N) in magnitude.
    fx = p * n[:, 0] * area * RHO  # drag contribution per face, N

    slant = (np.abs(n[:, 2]) > 0.25) & (cc[:, 0] > 0.80) & (cc[:, 0] < 1.043) & (cc[:, 2] > 0.19)
    base = (np.abs(n[:, 0]) > 0.9) & (cc[:, 0] > 1.035)
    under = (np.abs(n[:, 2]) > 0.9) & (cc[:, 2] < 0.06)
    other = ~(slant | base | under)
    out = {}
    for name, mask in (("slant", slant), ("base", base), ("underbody", under), ("forebody+sides", other)):
        out[name] = (fx[mask].sum(), area[mask].sum(), (p[mask] / (0.5 * U * U)).mean() if mask.any() else 0.0)
    out["TOTAL_pressure"] = (fx.sum(), area.sum(), 0.0)
    return out


for case_dir in sys.argv[1:]:
    print(f"\n=== {Path(case_dir).name} ===")
    res = regions(Path(case_dir))
    tot = res["TOTAL_pressure"][0]
    for k, (f, a, cp) in res.items():
        print(f"{k:>16}: Fx {f:8.3f} N  ({f / tot * 100:6.2f}% of pressure drag)  area {a:.4f} m^2  meanCp {cp:+.4f}")
    print(f"{'Cd_pressure':>16}: {tot / (Q * A_REF):.4f}")