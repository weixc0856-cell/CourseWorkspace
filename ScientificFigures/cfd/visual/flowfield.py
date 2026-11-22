"""Flow-field loading and pathline animation from a solved OpenFOAM case.

Everything here is derived from the solver output. No hand-drawn geometry, no
synthetic fields. For a steady RANS solution, pathlines coincide with streamlines,
so markers advected along them at the local speed are a faithful visualisation of
the MEAN field -- not of instantaneous turbulence.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyvista as pv
import vtk


@dataclass
class Case:
    mesh: pv.DataSet
    body: pv.DataSet | None
    u_inf: float
    cp_clim: tuple[float, float]
    time: float


def load(case_dir: Path, u_inf: float, time_index: int = -1) -> Case:
    stub = case_dir / "case.foam"
    if not stub.exists():
        stub.write_text("", encoding="utf-8")
    reader = pv.OpenFOAMReader(str(stub))
    reader.set_active_time_value(reader.time_values[time_index])
    reader.cell_to_point_creation = True
    block = reader.read()
    mesh = block["internalMesh"]

    # incompressible simpleFoam stores kinematic pressure p [m^2/s^2], p_inf = 0
    mesh.point_data["Cp"] = mesh.point_data["p"] / (0.5 * u_inf**2)
    mesh.point_data["Umag"] = np.linalg.norm(mesh.point_data["U"], axis=1)
    mesh.point_data["Ux"] = mesh.point_data["U"][:, 0]

    body = None
    if "boundary" in block.keys():
        for name in block["boundary"].keys():
            if any(k in name.lower() for k in ("body", "ahmed", "car", "wall")):
                patch = block["boundary"][name]
                if patch.n_cells > 500:
                    patch.point_data["Cp"] = patch.point_data["p"] / (0.5 * u_inf**2)
                    body = patch
                    break

    cp = mesh.point_data["Cp"]
    lo, hi = np.percentile(cp, [2, 98])
    span = max(abs(lo), abs(hi))
    return Case(mesh, body, u_inf, (-span, span), float(reader.time_values[time_index]))


@dataclass
class Pathlines:
    points: list[np.ndarray]
    travel: list[np.ndarray]
    speed: list[np.ndarray]

    def markers(self, t: float, phase: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        """Positions and speeds of one marker per pathline at travel time t."""
        pos, spd = [], []
        for i, (pts, tc) in enumerate(zip(self.points, self.travel)):
            if tc[-1] <= 0:
                continue
            offset = 0.0 if phase is None else float(phase[i])
            tau = (t + offset) % tc[-1]
            j = int(np.searchsorted(tc, tau))
            j = min(max(j, 1), len(tc) - 1)
            w = (tau - tc[j - 1]) / max(tc[j] - tc[j - 1], 1e-12)
            pos.append(pts[j - 1] + w * (pts[j] - pts[j - 1]))
            spd.append(self.speed[i][j - 1] + w * (self.speed[i][j] - self.speed[i][j - 1]))
        return np.asarray(pos), np.asarray(spd)


def pathlines(mesh: pv.DataSet, seed: pv.PolyData, max_length: float) -> Pathlines:
    lines = mesh.streamlines_from_source(
        seed, vectors="U", max_length=max_length, integration_direction="forward", terminal_speed=1e-8
    )
    out = Pathlines([], [], [])
    for i in range(lines.n_cells):
        cell = lines.get_cell(i)
        pts = np.asarray(cell.points)
        if len(pts) < 3:
            continue
        if "U" in lines.point_data:
            spd = np.linalg.norm(np.asarray(lines.point_data["U"])[list(cell.point_ids)], axis=1)
        else:
            sampled = pv.PolyData(pts).sample(mesh)
            spd = np.linalg.norm(sampled.point_data["U"], axis=1)
        ds = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        v = 0.5 * (spd[:-1] + spd[1:])
        dt = ds / np.maximum(v, 1e-6)
        out.points.append(pts)
        out.travel.append(np.concatenate([[0.0], np.cumsum(dt)]))
        out.speed.append(spd)
    return out


def screen_xy(plotter: pv.Plotter, xyz: tuple[float, float, float], height: int) -> tuple[float, float]:
    """Project a world point to pixel coordinates so labels can track geometry."""
    coord = vtk.vtkCoordinate()
    coord.SetCoordinateSystemToWorld()
    coord.SetValue(*xyz)
    x, y = coord.GetComputedDisplayValue(plotter.renderer)[:2]
    return float(x), float(height - y)