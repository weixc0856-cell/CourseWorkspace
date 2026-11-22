"""Honest convergence / validation summary for an Ahmed body case.

Usage: python analyze.py <caseDir> [--window 200]
"""

import json
import re
import sys
from pathlib import Path

import numpy as np

TARGETS = {25: 0.299, 35: None}
RHO_INF = 1.225
U_INF = 40.0
AREF = 0.112


def force_coeffs(case: Path):
    hits = sorted(case.glob("postProcessing/forceCoeffs*/*/coefficient.dat"))
    if not hits:
        hits = sorted(case.glob("postProcessing/forceCoeffs*/*/coefficients.dat"))
    if not hits:
        return None, None
    path = hits[-1]
    header, rows = None, []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("#"):
            header = line
            continue
        if line.strip():
            rows.append([float(v) for v in line.split()])
    if not rows:
        return path, None
    cols = (header or "").lstrip("#").split()
    data = np.asarray(rows)
    return path, (cols, data)


def grep_first(path: Path, pattern: str):
    if not path.exists():
        return None
    m = re.search(pattern, path.read_text(encoding="utf-8", errors="replace"))
    return m.group(1) if m else None


def main() -> int:
    case = Path(sys.argv[1])
    window = 200
    if "--window" in sys.argv:
        window = int(sys.argv[sys.argv.index("--window") + 1])

    out = {"case": str(case)}
    slant = int(re.search(r"ahmed(\d+)", case.name).group(1))
    out["slant_deg"] = slant

    path, parsed = force_coeffs(case)
    out["coefficient_file"] = str(path) if path else None
    if parsed:
        cols, data = parsed
        t = data[:, 0]
        i_cd = cols.index("Cd") if "Cd" in cols else 1
        i_cl = cols.index("Cl") if "Cl" in cols else 4
        cd, cl = data[:, i_cd], data[:, i_cl]
        n = min(window, len(cd))
        tail = cd[-n:]
        half = max(1, n // 2)
        m1, m2 = tail[:half].mean(), tail[half:].mean()
        out.update(
            {
                "iterations_logged": int(t[-1]),
                "window": int(n),
                "Cd_mean": float(tail.mean()),
                "Cd_std": float(tail.std()),
                "Cd_min": float(tail.min()),
                "Cd_max": float(tail.max()),
                "Cd_drift_pct": float(100.0 * (m2 - m1) / abs(m1)) if m1 else None,
                "Cl_mean": float(cl[-n:].mean()),
                "Cd_last": float(cd[-1]),
            }
        )
        tgt = TARGETS.get(slant)
        if tgt:
            out["experiment_Cd"] = tgt
            out["delta_vs_experiment_pct"] = float(100.0 * (tail.mean() - tgt) / tgt)
        out["converged_by_drift_rule"] = bool(abs(out["Cd_drift_pct"]) < 0.5)

    cm = case / "log.checkMesh"
    out["cells"] = grep_first(cm, r"cells:\s+(\d+)")
    out["non_ortho"] = grep_first(cm, r"Mesh non-orthogonality Max:\s+([\d.]+)")
    out["skewness"] = grep_first(cm, r"Max skewness =\s+([\d.]+)")
    out["mesh_ok"] = "Mesh OK." in cm.read_text(encoding="utf-8", errors="replace") if cm.exists() else False
    failed = grep_first(cm, r"Failed (\d+) mesh checks")
    out["failed_mesh_checks"] = int(failed) if failed else 0
    if cm.exists():
        out["mesh_check_failures"] = [
            ln.strip() for ln in cm.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip().startswith("***")
        ]

    yp = case / "log.yPlus"
    yplus_src = None
    for cand in (case / "log.yPlus", case / "log.simpleFoam"):
        if not cand.exists():
            continue
        txt = cand.read_text(encoding="utf-8", errors="replace")
        blocks = re.findall(
            r"patch\s+(\w+)\s+y\+\s*:\s*min\s*=\s*([\d.eE+-]+),\s*max\s*=\s*([\d.eE+-]+),\s*average\s*=\s*([\d.eE+-]+)",
            txt,
        )
        if blocks and any(float(b[2]) > 0 for b in blocks):
            last = blocks[-2:] if len(blocks) >= 2 else blocks
            out["yPlus"] = [
                {"patch": b[0], "min": float(b[1]), "max": float(b[2]), "avg": float(b[3])}
                for b in last
            ]
            yplus_src = cand.name
            break
    out["yPlus_source"] = yplus_src

    fhits = sorted(case.glob("postProcessing/forces*/*/force.dat"))
    if not fhits:
        fhits = sorted(case.glob("postProcessing/forces*/*/forces.dat"))
    if fhits:
        rows = [
            [float(v) for v in ln.replace("(", " ").replace(")", " ").split()]
            for ln in fhits[-1].read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip() and not ln.startswith("#")
        ]
        if rows:
            a = np.asarray(rows[-1:])
            out["forces_sample_time"] = float(a[0, 0])
            # v2512 force.dat: time total(x y z) pressure(x y z) viscous(x y z)
            tot = float(a[:, 1].mean())
            p_drag, v_drag = float(a[:, 4].mean()), float(a[:, 7].mean())
            out["forces_file"] = str(fhits[-1])
            out["total_drag_N"] = tot
            out["pressure_drag_N"] = p_drag
            out["viscous_drag_N"] = v_drag
            out["pressure_share_pct"] = float(100.0 * p_drag / tot) if tot else None
            out["drag_closure_error_pct"] = (
                float(100.0 * (p_drag + v_drag - tot) / tot) if tot else None
            )
            out["Cd_from_forces"] = tot / (0.5 * RHO_INF * U_INF**2 * AREF)

    sf = case / "log.simpleFoam"
    if sf.exists():
        lines = sf.read_text(encoding="utf-8", errors="replace").splitlines()
        res = [ln.strip() for ln in lines if "Solving for" in ln][-6:]
        out["final_residual_lines"] = res
        out["foam_end"] = next((ln for ln in reversed(lines) if "End" in ln or "Finalising" in ln), None)

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())