"""Ahmed reference body (Ahmed et al. 1984) as a watertight STL, from published dimensions."""

import sys
from pathlib import Path

import numpy as np
import trimesh

L = 1.044
W = 0.389
H_TOP = 0.288
CLEARANCE = 0.05
NOSE_R = 0.1
SLANT_LEN = 0.222
ARC_SEG = 12


def profile(slant_deg: float) -> np.ndarray:
    th = np.radians(slant_deg)
    run = SLANT_LEN * np.cos(th)
    drop = SLANT_LEN * np.sin(th)
    z_base_top = H_TOP - drop
    x_slant = L - run

    pts = [(0.0, CLEARANCE + NOSE_R), (0.0, H_TOP - NOSE_R)]

    a = np.linspace(np.pi, np.pi / 2, ARC_SEG + 1)[1:]
    pts += [(NOSE_R + NOSE_R * np.cos(t), H_TOP - NOSE_R + NOSE_R * np.sin(t)) for t in a]

    pts += [(x_slant, H_TOP), (L, z_base_top), (L, CLEARANCE), (NOSE_R, CLEARANCE)]

    a = np.linspace(1.5 * np.pi, np.pi, ARC_SEG + 1)[1:-1]
    pts += [(NOSE_R + NOSE_R * np.cos(t), CLEARANCE + NOSE_R + NOSE_R * np.sin(t)) for t in a]

    return np.asarray(pts, dtype=float)


def build(slant_deg: float) -> trimesh.Trimesh:
    p = profile(slant_deg)
    n = len(p)
    half = W / 2.0

    verts = np.vstack(
        [
            np.column_stack([p[:, 0], np.full(n, -half), p[:, 1]]),
            np.column_stack([p[:, 0], np.full(n, half), p[:, 1]]),
        ]
    )
    c = p.mean(axis=0)
    verts = np.vstack([verts, [c[0], -half, c[1]], [c[0], half, c[1]]])
    c0, c1 = 2 * n, 2 * n + 1

    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j])
        faces.append([i, n + j, n + i])
        faces.append([c0, j, i])
        faces.append([c1, n + i, n + j])

    m = trimesh.Trimesh(vertices=verts, faces=np.asarray(faces), process=False)
    trimesh.repair.fix_normals(m)
    return m


def report(m: trimesh.Trimesh, slant_deg: float, out: Path) -> dict:
    lo, hi = m.bounds
    body_h = hi[2] - lo[2]
    projected = (hi[1] - lo[1]) * body_h
    conventional = W * H_TOP
    checks = {
        "slant_deg": slant_deg,
        "watertight": bool(m.is_watertight),
        "winding_consistent": bool(m.is_winding_consistent),
        "volume_m3": float(m.volume),
        "bbox_min": [float(v) for v in lo],
        "bbox_max": [float(v) for v in hi],
        "length_m": float(hi[0] - lo[0]),
        "width_m": float(hi[1] - lo[1]),
        "height_above_ground_m": float(hi[2]),
        "body_projected_frontal_area_m2": float(projected),
        "conventional_Aref_W_times_H_m2": float(conventional),
        "triangles": int(len(m.faces)),
    }
    m.export(out)
    return checks


def main() -> int:
    outdir = Path(sys.argv[1])
    outdir.mkdir(parents=True, exist_ok=True)
    ok = True
    for slant in (25.0, 35.0):
        m = build(slant)
        stl = outdir / f"ahmed_{int(slant)}.stl"
        c = report(m, slant, stl)
        print(f"--- {stl} ---")
        for k, v in c.items():
            print(f"  {k}: {v}")
        good = (
            c["watertight"]
            and c["winding_consistent"]
            and abs(c["length_m"] - L) < 1e-9
            and abs(c["width_m"] - W) < 1e-9
            and abs(c["height_above_ground_m"] - H_TOP) < 1e-9
            and c["volume_m3"] > 0
        )
        print(f"  GEOMETRY_CHECK: {'PASS' if good else 'FAIL'}")
        ok = ok and good
    print(f"ALL_GEOMETRY_CHECKS: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())