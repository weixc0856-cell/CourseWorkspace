"""Field-derived measures for an Ahmed case: base Cp, recirculation length, Cp extrema.

Post-processing only. Usage: python measure_fields.py <caseDir> [<caseDir> ...]
"""
import json
import sys
from pathlib import Path

import numpy as np
import pyvista as pv

U_INF = 40.0
BASE_X = 1.044


def measure(case: Path) -> dict:
    stub = case / "case.foam"
    if not stub.exists():
        stub.write_text("", encoding="utf-8")
    r = pv.OpenFOAMReader(str(stub))
    r.set_active_time_value(r.time_values[-1])
    r.cell_to_point_creation = True
    blk = r.read()
    m = blk["internalMesh"]
    body = blk["boundary"]["body"]
    out = {"case": case.name, "time": float(r.time_values[-1]), "cells": m.n_cells}

    cp = body.point_data["p"] / (0.5 * U_INF**2)
    out["body_Cp_min"] = float(cp.min())
    out["body_Cp_max"] = float(cp.max())

    n = np.asarray(body.cell_normals)
    cc = body.cell_centers().points
    base = body.extract_cells((np.abs(n[:, 0]) > 0.9) & (cc[:, 0] > 1.035))
    out["base_faces"] = int(base.n_cells)
    out["base_Cp_mean"] = float((base.point_data["p"] / (0.5 * U_INF**2)).mean()) if base.n_cells else None

    m.point_data["Ux"] = m.point_data["U"][:, 0]
    wake = m.clip_box((1.06, 3.5, -0.6, 0.6, 0.06, 0.9), invert=False)
    rev = wake.contour(isosurfaces=[-0.5], scalars="Ux")
    out["recirc_iso"] = "Ux = -0.5 m/s"
    out["recirc_length_m"] = float(rev.points[:, 0].max() - BASE_X) if rev.n_points else None
    out["recirc_length_over_L"] = out["recirc_length_m"] / BASE_X if out["recirc_length_m"] else None

    cm = case / "log.checkMesh"
    if cm.exists():
        out["mesh_check_failures"] = [
            ln.strip() for ln in cm.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip().startswith("***")
        ]
    return out


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(json.dumps(measure(Path(arg)), indent=2))