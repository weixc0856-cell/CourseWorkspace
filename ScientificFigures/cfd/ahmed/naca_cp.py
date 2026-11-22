"""Export NACA surface Cp vs x/c from a solved 2D case. Archive post-processing only.

The 2D plane is x-z (chord along x, LE at x=0, chord=1); alpha is imposed by the
freestream vector, so upper/lower is simply the sign of z. Points are duplicated
across the y-span, so one y-plane is taken.

Usage: python naca_cp.py <caseDir> <outCsv>
"""
import sys
from pathlib import Path

import numpy as np
import pyvista as pv

U_INF = 15.0


def main() -> int:
    case, out = Path(sys.argv[1]), Path(sys.argv[2])
    stub = case / "case.foam"
    if not stub.exists():
        stub.write_text("", encoding="utf-8")
    r = pv.OpenFOAMReader(str(stub))
    r.set_active_time_value(r.time_values[-1])
    r.cell_to_point_creation = True
    blk = r.read()
    foil = blk["boundary"]["aerofoil"]

    pts = np.asarray(foil.points)
    cp = np.asarray(foil.point_data["p"]) / (0.5 * U_INF**2)
    yplane = pts[:, 1].min()
    keep = np.isclose(pts[:, 1], yplane, atol=1e-8)
    x, z, cp = pts[keep, 0], pts[keep, 2], cp[keep]

    order = np.argsort(x)
    x, z, cp = x[order], z[order], cp[order]
    side = np.where(z >= 0.0, "upper", "lower")

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("x_over_c,z_over_c,Cp,side\n")
        for xi, zi, ci, si in zip(x, z, cp, side):
            fh.write(f"{xi:.8f},{zi:.8f},{ci:.8f},{si}\n")

    span = float(pts[:, 1].max() - pts[:, 1].min())
    print(f"wrote {out}  points={len(x)}  time={r.time_values[-1]}")
    print(f"  x/c range {x.min():.5f} .. {x.max():.5f}")
    print(f"  Cp range {cp.min():.4f} .. {cp.max():.4f}  (stagnation should approach +1)")
    print(f"  upper {int((side == 'upper').sum())}  lower {int((side == 'lower').sum())}")
    print(f"  MESH SPAN in y = {span:.6f} m  -> correct Aref for coefficients is chord*span = {1.0 * span:.6f} m^2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())