"""Frame-sequence renderer for CFD explainer shots.

Given a solved case directory and a shot definition (camera path keyframes,
layer toggles, duration, fps), writes numbered PNG frames plus a JSON sidecar:

  * world + per-frame pixel position for every tracked label anchor
    (stagnation point, separation-line midpoint, base centre, recirculation tail);
  * per-frame pick of the actor actually under the anchor pixel, so a label can
    be faded out when the feature is occluded and so a checker can verify the
    anchor lands on the feature it names;
  * marker displacement/speed samples for the mean-field pathline proof;
  * camera keyframes and measured feature values.

Everything physical is solver-derived: separation line only from wss_x = 0 on
upstream-facing slant cells, recirculation from a point-data Ux contour, Cp
colormap centred on zero. Markers are advected along steady-field pathlines in
slow motion; the sidecar records the slow-motion factor so nothing claims
unsteady vortex shedding.

Usage:
    python -I shot_render.py --shot <shot.json> [--frames 0-N] [--fast] [--out <dir>]

Camera interpolation is cosine-eased piecewise between keyframes; shot configs
must keep one dominant move (the renderer asserts total camera speed is smooth
by construction and records per-frame deltas).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pyvista as pv
import vtk
from vtk.util import numpy_support as nps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flowfield import load, pathlines, screen_xy  # noqa: E402

BACKGROUND = (14, 18, 24)  # #0e1218 studio floor
U_INF = 40.0


class ScenePoints:
    """Fast in-place update of the polydata that VTK actually renders.

    pyvista copies the PolyData we hand it, so editing our object does nothing;
    we must mutate the mapper's own input (verified on this stack: 2757 px of
    marker dots move per frame with this path).
    """

    def __init__(self, actor):
        self.pd = actor.mapper.GetInput()
        self.speed_arr = self.pd.GetPointData().GetArray("speed")

    def set(self, pts, spd):
        vp = vtk.vtkPoints()
        vp.SetData(nps.numpy_to_vtk(np.ascontiguousarray(pts, np.float64), deep=True))
        self.pd.SetPoints(vp)
        if self.speed_arr is not None and spd is not None:
            nps.vtk_to_numpy(self.speed_arr)[:] = spd
            self.speed_arr.Modified()
        self.pd.GetPointData().Modified()
        self.pd.Modified()


# --------------------------------------------------------------------------- #
# native face fields: p/area per patch FACE, read with cell_to_point off.
# The converted (point) arrays smooth the base mean from -0.1118 to -0.1016;
# the spec number on screen must come from the native face distribution.
# --------------------------------------------------------------------------- #
def face_fields(case_dir: Path) -> dict:
    stub = case_dir / "case.foam"
    r = pv.OpenFOAMReader(str(stub))
    r.set_active_time_value(r.time_values[-1])
    r.cell_to_point_creation = False
    patch = None
    block = r.read()["boundary"]
    patch = None
    for name in block.keys():
        if any(k in name.lower() for k in ("body", "ahmed", "car", "wall")) and block[name].n_cells > 500:
            patch = block[name]
            break
    n = np.asarray(patch.cell_normals)
    cc = patch.cell_centers().points
    area = patch.compute_cell_sizes(length=False, volume=False, area=True).cell_data["Area"]
    p_face = np.asarray(patch.cell_data["p"]) / (0.5 * U_INF**2)
    return {"n": n, "cc": cc, "area": area, "cp_face": p_face, "n_cells": patch.n_cells}


# --------------------------------------------------------------------------- #
# features -- all measured from the solution, per the hard-won rules in
# ahmed_still.py (they encode what is a *real* separation line and what is not)
# --------------------------------------------------------------------------- #
@dataclass
class Features:
    sep: pv.PolyData | None
    sep_mid: np.ndarray
    recirc: pv.PolyData | None
    recirc_tail: np.ndarray
    recirc_extent_m: float
    base_centre: np.ndarray
    base_cp_mean: float          # FACE mean over the 958 base faces: the headline (-0.1118)
    base_cp_point_mean: float    # smoothed point mean (-0.1016), never on screen unlabelled
    base_cp_area_mean: float     # area-weighted face mean (-0.1024), reference
    base_n_faces: int
    base_area_m2: float
    stagnation: np.ndarray
    stagnation_cp: float
    body: pv.DataSet
    sep_length_m: float
    underbody: np.ndarray | None = None
    rear_top_edge: np.ndarray | None = None
    slant_top_edge: np.ndarray | None = None
    geom: dict = field(default_factory=dict)
    notes: dict = field(default_factory=dict)


def extract_features(c, ff: dict) -> Features:
    m, body = c.mesh, c.body
    n, cc = ff["n"], ff["cc"]

    # base: vertical faces aft of the slant (n_x ~ +-1, x past the rear edge)
    base_mask = (np.abs(n[:, 0]) > 0.9) & (cc[:, 0] > cc[:, 0].max() - 0.009)
    base_centre = cc[base_mask].mean(axis=0)
    # spec policy 2026-11-22: the headline base Cp is the FACE mean over the
    # native base-face distribution (-0.1118 at 25 deg), the same array
    # drag_breakdown.py integrates to the solver's pressure force. The
    # area-weighted and point-smoothed means are recorded but do not go on
    # screen; using the converted point arrays would silently return -0.1016.
    base_cp = float(ff["cp_face"][base_mask].mean())
    base_cp_area = float((ff["cp_face"][base_mask] * ff["area"][base_mask]).sum()
                         / ff["area"][base_mask].sum())
    base = body.extract_cells(base_mask)
    base_cp_point = float((base.point_data["p"] / (0.5 * U_INF**2)).mean())
    base_area = float(ff["area"][base_mask].sum())
    base_nf = int(base_mask.sum())

    # separation line: wss_x = 0 on upstream-facing slant cells only
    body.point_data["wssx"] = body.point_data["wallShearStress"][:, 0]
    slant_mask = (np.abs(n[:, 2]) > 0.25) & (cc[:, 0] > 0.80) & (cc[:, 0] < 1.043) & (cc[:, 2] > 0.19)
    slant = body.extract_cells(slant_mask)
    sep = slant.contour(isosurfaces=[0.0], scalars="wssx")
    sep_mid = None
    sep_length = 0.0
    if sep.n_points:
        # the contour arrives as short fragments; the anchor is the mean of the
        # points nearest the symmetry plane -- those sit on the top line of the
        # separation, the one the narration refers to, and are on orange pixels
        sp = np.asarray(sep.points)
        order = np.argsort(np.abs(sp[:, 1]))[:8]
        sep_mid = sp[order].mean(axis=0)
        total = 0.0
        for i in range(sep.n_cells):
            pts = np.asarray(sep.get_cell(i).points)
            if len(pts) > 1:
                total += float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
        sep_length = total

    # recirculation: point-data contour of Ux = -0.5 in the near wake
    bp = np.asarray(body.points)
    x_rear = float(bp[:, 0].max())
    wake = m.clip_box((x_rear + 0.016, 3.5, -0.6, 0.6, 0.06, 0.9), invert=False)
    recirc = wake.contour(isosurfaces=[-0.5], scalars="Ux")
    extent = 0.0
    rec_tail = None
    if recirc.n_points:
        rx = recirc.points[:, 0]
        extent = float(rx.max() - x_rear)
        tail_mask = rx > rx.max() - 0.02
        rec_tail = recirc.points[tail_mask].mean(axis=0)

    # stagnation: max Cp on the body front (front is at x=0 for this build)
    cp = body.point_data["Cp"]
    front = bp[:, 0] < 0.012
    idx = int(np.argmax(np.where(front, cp, -99.0)))
    stag = bp[idx]
    stag_cp = float(cp[idx])

    # underbody: lowest FRONT point -- ground clearance is part of the argument
    zmin = float(bp[:, 2].min())
    cand = bp[(bp[:, 2] < zmin + 0.002) & (np.abs(bp[:, 1]) < 0.02)]
    ub = cand[int(np.argmin(cand[:, 0]))] if len(cand) else bp[int(np.argmin(bp[:, 2]))]

    # rear top edge: the topmost point on the vertical base face at centreline
    sel = (bp[:, 0] > x_rear - 0.0025) & (np.abs(bp[:, 1]) < 0.02)
    rear_top = bp[sel][int(np.argmax(bp[sel][:, 2]))] if sel.any() else None
    # slant top edge: roof/rear-window junction on the centreline -- where the
    # adverse pressure gradient starts (Cp min measured just downstream)
    sel2 = (np.abs(bp[:, 1]) < 0.012) & (bp[:, 2] > 0.284)
    slant_top = bp[sel2][int(np.argmax(bp[sel2][:, 0]))] if sel2.any() else None

    geom = {
        "length_m": round(x_rear - float(bp[:, 0].min()), 4),
        "height_total_m": round(float(bp[:, 2].max()), 4),
        "width_m": round(float(bp[:, 1].max() - bp[:, 1].min()), 4),
        "ground_clearance_m": round(float(bp[:, 2].min()), 4),
        "slenderness_LH": round((x_rear - float(bp[:, 0].min())) / float(bp[:, 2].max()), 3),
        "rear_edge_x_m": round(x_rear, 4),
    }

    return Features(sep, sep_mid, recirc, rec_tail, extent, base_centre, base_cp,
                    base_cp_point, base_cp_area, base_nf, base_area, stag, stag_cp,
                    body, sep_length, underbody=ub, geom=geom,
                    rear_top_edge=rear_top, slant_top_edge=slant_top)


# --------------------------------------------------------------------------- #
# camera path: cosine-eased piecewise between keyframes
# --------------------------------------------------------------------------- #
def _ease(u: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * min(max(u, 0.0), 1.0))


def camera_at(keys: list[dict], t: float):
    t = min(max(t, keys[0]["t"]), keys[-1]["t"])
    i = 0
    while i < len(keys) - 2 and t > keys[i + 1]["t"]:
        i += 1
    k0, k1 = keys[i], keys[i + 1]
    u = _ease((t - k0["t"]) / max(k1["t"] - k0["t"], 1e-9))
    pos = (1 - u) * np.array(k0["pos"], float) + u * np.array(k1["pos"], float)
    focal = (1 - u) * np.array(k0["focal"], float) + u * np.array(k1["focal"], float)
    up = (1 - u) * np.array(k0.get("up", [0, 0, 1]), float) + u * np.array(k1.get("up", [0, 0, 1]), float)
    fov = (1 - u) * k0.get("fov", keys[0].get("fov", 30.0)) + u * k1.get("fov", keys[0].get("fov", 30.0))
    return pos, focal, np.asarray(up), float(fov)


# --------------------------------------------------------------------------- #
# projection re-implementation for the independent checker
# --------------------------------------------------------------------------- #
def project_manual(cam: dict, xyz, width=1920, height=1080):
    """Look-at + vertical-FOV perspective projection in pure numpy.

    cam: {pos, focal, up, fov_deg}. Returns (u, v_px, in_front). Matches
    flowfield.screen_xy only if VTK's camera convention is what we assume --
    the checker treats a mismatch > 2 px as a failure, which is the point.
    """
    pos = np.array(cam["pos"], float)
    focal = np.array(cam["focal"], float)
    up = np.array(cam["up"], float)
    w = focal - pos
    w /= np.linalg.norm(w)                      # view direction
    zc = -w
    xc = np.cross(up, zc)
    xn = np.linalg.norm(xc)
    if xn < 1e-9:
        return None
    xc /= xn
    yc = np.cross(zc, xc)
    v = np.array(xyz, float) - pos
    cv = np.array([v @ xc, v @ yc, v @ zc])
    if cv[2] >= -1e-9:
        return None
    tan = math.tan(math.radians(cam["fov"]) / 2.0)
    ndc_y = (cv[1] / -cv[2]) / tan
    ndc_x = (cv[0] / -cv[2]) / (tan * (width / height))
    u = (ndc_x * 0.5 + 0.5) * width
    vy = (1.0 - (ndc_y * 0.5 + 0.5)) * height
    return float(u), float(vy)


# --------------------------------------------------------------------------- #
# renderer
# --------------------------------------------------------------------------- #
def render_shot(shot: dict, frames: list[int], fast: bool = False) -> Path:
    case_dir = Path(shot["case"])
    out_dir = Path(shot["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    fps = float(shot["fps"])
    duration = float(shot["duration"])
    n_total = int(round(duration * fps))
    slow = float(shot.get("slow_motion_factor", 20.0))
    layers = shot.get("layers", {})
    cp_clim = list(shot.get("cp_clim", [-0.6, 0.6]))

    t0 = time.time()
    c = load(case_dir, u_inf=U_INF)
    ff = face_fields(case_dir)
    feats = extract_features(c, ff)
    m = c.mesh
    print(f"[{shot['shot']}] load+features {time.time()-t0:.1f}s  "
          f"sep_len={feats.sep_length_m:.3f} m  recirc_extent={feats.recirc_extent_m:.3f} m  "
          f"base Cp(face)={feats.base_cp_mean:.4f} (area)={feats.base_cp_area_mean:.4f} "
          f"(point)={feats.base_cp_point_mean:.4f}  stag Cp={feats.stagnation_cp:.3f}")

    pv.OFF_SCREEN = True
    p = pv.Plotter(off_screen=True, window_size=(1920, 1080))
    p.set_background("#0e1218")

    if layers.get("ground", True):
        ground = p.add_mesh(
            pv.Plane(center=(1.2, 0, 0), direction=(0, 0, 1), i_size=9, j_size=6),
            color="#242c36", roughness=0.95, name="ground")
        ground.SetPickable(0)
    body_actor = p.add_mesh(feats.body, scalars="Cp", cmap="RdBu_r", clim=cp_clim,
                            show_scalar_bar=False, smooth_shading=True, name="body")
    if layers.get("recirc", True) and feats.recirc is not None and feats.recirc.n_points:
        rec = p.add_mesh(feats.recirc, color="#6fa8d6", opacity=0.30, smooth_shading=True,
                         name="recirc")
        rec.SetPickable(1)
    else:
        rec = None
    if layers.get("separation", True) and feats.sep is not None and feats.sep.n_points:
        sep_actor = p.add_mesh(feats.sep, color="#e8733b", line_width=7,
                               render_lines_as_tubes=True, name="separation")
        sep_actor.SetPickable(1)
    else:
        sep_actor = None

    # ---- pathlines (mean-field) + markers
    seed_cfg = shot.get("seeds", {})
    far = np.array([[seed_cfg.get("far_x", -0.6), y, z]
                    for z in np.linspace(*seed_cfg.get("far_z", [0.07, 0.40]), 13)
                    for y in np.linspace(*seed_cfg.get("far_y", [-0.17, 0.17]), 11)])
    rake = np.array([[seed_cfg.get("rake_x", 0.55), y, z]
                     for z in np.linspace(0.292, 0.36, 9)
                     for y in np.linspace(-0.16, 0.16, 9)])
    seeds = pv.PolyData(np.vstack([far, rake]))
    pl = pathlines(m, seeds, max_length=float(shot.get("max_pathline_length", 6.0)))
    if layers.get("pathlines", True):
        # NB: do NOT pass name= here -- pyvista DROPS each actor added under a
        # name already in use (_probe_namebug.py: 224 named adds leave 1 actor).
        for pts in pl.points:
            sp = p.add_mesh(pv.Spline(pts, max(len(pts) // 3, 10)), color="#9fb0c4",
                             line_width=2, opacity=0.40)
            sp.SetPickable(0)
    rng = np.random.default_rng(int(shot.get("seed_rng", 7)))
    phase = np.array([rng.uniform(0, t[-1]) for t in pl.travel])
    keep = [i for i, t in enumerate(pl.travel) if t[-1] > 0]
    cloud_pos, cloud_spd = pl.markers(0.0, phase)
    cloud = pv.PolyData(cloud_pos)
    cloud.point_data["speed"] = cloud_spd
    if layers.get("markers", True):
        markers_actor = p.add_mesh(cloud, scalars="speed", cmap="autumn", clim=(0, 45),
                                   render_points_as_spheres=True, point_size=10,
                                   show_scalar_bar=False, name="markers")
        markers_actor.SetPickable(0)
        scene_pts = ScenePoints(markers_actor)
    else:
        markers_actor = None
        scene_pts = None

    # independent velocity field for the proof: nearest-mesh-vertex speed via
    # a vtkStaticPointLocator (pyvista 0.49 has no batch API here and there is
    # no scipy in this env), NOT the streamline-integration samples -- ties
    # marker displacement to the raw solved field
    mesh_U = np.asarray(m.point_data["U"])
    _loc = vtk.vtkStaticPointLocator()
    _loc.SetDataSet(m)
    _loc.BuildLocator()

    def nearest_ids(points):
        return np.asarray([_loc.FindClosestPoint([float(p[0]), float(p[1]), float(p[2])])
                           for p in np.asarray(points, float)])

    if not fast and shot.get("antialias", "off") == "ssaa":
        # NB: with ssaa ON vtkPropPicker silently returns nothing on this GL
        # stack (_probe_ssaa.py), so production runs AA off -- the approved
        # ahmed25_v3.png was produced through the same screenshot path.
        p.enable_anti_aliasing("ssaa")

    # ---- anchors
    anchors = []
    for a_def in shot["anchors"]:
        world = feats.__dict__[a_def["feature"]]
        if world is None:
            print(f"WARNING anchor {a_def['name']}: feature missing, skipped")
            continue
        expected = set(a_def["expected_actors"])
        anchors.append({**a_def, "world": [float(x) for x in world], "expected": expected})

    picker = vtk.vtkPropPicker()
    # actor identity via id(pv.Actor): verified in _probe_pick4.py that the
    # picker hands back the same wrapper pyvista registered. NOTE the
    # mapper.GetInput() shortcut is NOT safe -- consecutive calls return the
    # most-recently-created wrapper, which silently mislabels every actor.
    scene_ids = {}
    for act_, nm_ in ((body_actor, "body"), (rec, "recirc"), (sep_actor, "separation"),
                      (markers_actor, "markers")):
        if act_ is not None:
            scene_ids[id(act_)] = nm_

    def pick_state(u, v, world):
        if not (0 <= u < 1920 and 0 <= v < 1080):
            return None, None
        if not picker.Pick(float(u), float(1080 - v), 0.0, p.renderer):
            return None, None
        act = picker.GetActor()
        if act is None:
            return None, None
        name = scene_ids.get(id(act), "other")
        dp = np.array(picker.GetPickPosition(), float)
        depth_delta = float(np.linalg.norm(dp - pos) - np.linalg.norm(np.array(world) - pos))
        return name, depth_delta
    sidecar = {
        "kind": "cfd_shot_sidecar",
        "version": 1,
        "mode": "vtk",
        "shot": shot["shot"],
        "case": str(case_dir),
        "fps": fps,
        "duration": duration,
        "n_frames": n_total,
        "width": 1920,
        "height": 1080,
        "background_rgb": list(BACKGROUND),
        "cp_clim": cp_clim,
        "slow_motion_factor": slow,
        "u_inf": U_INF,
        "field_note": shot.get("field_note",
                              "steady RANS mean field; markers are mean-field pathline tracers in slow motion"),
        "source_line": shot["source_line"],
        "headline": shot["headline"],
        "callouts": shot["callouts"],
        "camera_keys": shot["camera"]["keys"],
        "camera_easing": "cosine piecewise-linear",
        "features_measured": {
            "separation_line_length_m": round(feats.sep_length_m, 4),
            "recirc_extent_behind_base_m": round(feats.recirc_extent_m, 4),
            "base_cp_face_mean": round(feats.base_cp_mean, 4),
            "base_cp_area_mean": round(feats.base_cp_area_mean, 4),
            "base_cp_point_mean": round(feats.base_cp_point_mean, 4),
            "base_n_faces": feats.base_n_faces,
            "base_area_m2": round(feats.base_area_m2, 4),
            "stagnation_cp": round(feats.stagnation_cp, 4),
            "geom": feats.geom,
        },
        "anchors": [{k: v for k, v in a.items() if k != "expected"} | {"expected_actors": sorted(a["expected"])}
                    for a in anchors],
        "frames": [],
        "marker_proof": [],
    }
    # 21-point RdBu_r sample so the Remotion colour bar matches the VTK LUT
    import matplotlib

    cmapobj = matplotlib.colormaps["RdBu_r"]
    ts = np.linspace(0, 1, 21)
    sidecar["cp_bar_stops"] = [[round(cp_clim[0] + (cp_clim[1] - cp_clim[0]) * float(t), 4),
                                 [int(round(x * 255)) for x in cmapobj(float(t))[:3]]]
                                for t in ts]

    keys = shot["camera"]["keys"]
    proof_stride = int(shot.get("proof_stride_frames", 2))
    sampled_marker_ids = list(range(0, len(keep), max(1, len(keep) // 9)))[:10]

    if "formula" in shot:
        sidecar["formula"] = shot["formula"]

    # vtkPropPicker on this offscreen GL stack ABORTS unless the window has
    # completed at least one real swap -- a screenshot primes it (verified in
    # _probe_pick3.py: pick-only run dies, pick-after-screenshot returns the
    # actor). The priming file is deleted after the loop.
    p.screenshot(str(out_dir / "_prime.png"))

    t_render0 = time.time()
    for f in frames:
        t = f / fps
        pos, focal, up, fov = camera_at(keys, t)
        p.camera.position = tuple(pos)
        p.camera.focal_point = tuple(focal)
        p.camera.view_up = tuple(up / np.linalg.norm(up))
        p.camera.view_angle = fov
        p.reset_camera_clipping_range()
        tau = t / slow
        if scene_pts is not None:
            q, s = pl.markers(tau, phase)
            scene_pts.set(q, s)
        p.render()

        fr = {"f": f, "camera": {"pos": [round(x, 5) for x in pos],
                                 "focal": [round(x, 5) for x in focal],
                                 "up": [round(x, 5) for x in up / np.linalg.norm(up)],
                                 "fov": round(fov, 3)},
              "anchors": {}, "pick": {}}
        for a in anchors:
            u, v = screen_xy(p, a["world"], 1080)
            fr["anchors"][a["name"]] = [round(u, 2), round(v, 2)]
            name, dz = pick_state(u, v, a["world"])
            # on_feature: right actor AND the pick surface within the anchor's
            # depth window. Default +/-5 cm; the base anchor gets a one-sided
            # window so the translucent recirc bubble in front of it (picked
            # actor recirc, ~0.2 m closer) does not blank the label
            # (_probe_pick4.py showed the raw pick can't tell these apart).
            lo, hi = a.get("pick_depth", (-0.05, 0.05))
            ok = bool(name in a["expected"]) and dz is not None and lo <= dz <= hi
            fr["pick"][a["name"]] = {"actor": name, "on_feature": ok,
                                      "depth_delta_m": None if dz is None else round(dz, 4)}
        sidecar["frames"].append(fr)

        # marker proof: consecutive-frame chord/(speed*dt_sim) for sampled markers
        # marker proof: per-FRAME travel (dt = 1/fps/slow) chord vs v*dt from
        # the streamline's own sampled speeds -- the spec quantity, and small
        # enough dt that even wake curvature keeps chord~arc within 2%.
        # Recorded once per second; mesh-locator speed is kept as a
        # DIAGNOSTIC only (nearest-vertex sampling in the millimetres-thick
        # wall layer and inside the solid makes it useless as a gate).
        if f % 30 == 0:
            dt_sim = 1.0 / fps / slow
            q0, s0 = pl.markers(tau, phase)
            q1, s1 = pl.markers(tau + dt_sim, phase)
            ids = [mid for mid in sampled_marker_ids if mid < len(q0)]
            if ids:
                A0 = q0[ids]; A1 = q1[ids]
                i0 = nearest_ids(A0)
                i1 = nearest_ids(A1)
                for k, mid in enumerate(ids):
                    dvec = A1[k] - A0[k]
                    chord = float(np.linalg.norm(dvec))
                    v_avg = 0.5 * (float(s0[mid]) + float(s1[mid]))
                    u0 = mesh_U[i0[k]]; u1 = mesh_U[i1[k]]
                    mv = 0.5 * (float(np.linalg.norm(u0)) + float(np.linalg.norm(u1)))
                    if chord > 1e-5:
                        dn = dvec / chord
                        n0 = max(float(np.linalg.norm(u0)), 1e-9)
                        n1 = max(float(np.linalg.norm(u1)), 1e-9)
                        ang = max(
                            math.degrees(math.acos(max(-1.0, min(1.0, float(dn @ (u0 / n0)))))),
                            math.degrees(math.acos(max(-1.0, min(1.0, float(dn @ (u1 / n1)))))))
                    else:
                        ang = 0.0
                    T_i = float(pl.travel[keep[mid]][-1])
                    ph = float(phase[keep[mid]])
                    wrapped = math.floor((tau + ph) / T_i) != math.floor((tau + dt_sim + ph) / T_i)
                    sidecar["marker_proof"].append({
                        "marker": mid, "f0": f, "f1": f + 1,
                        "p0": [round(x, 5) for x in A0[k]], "p1": [round(x, 5) for x in A1[k]],
                        "v0": round(float(s0[mid]), 3), "v1": round(float(s1[mid]), 3),
                        "dt_sim": dt_sim, "chord_m": round(chord, 5),
                        "ratio": round(chord / max(v_avg * dt_sim, 1e-12), 4),
                        "mesh_ratio": round(chord / max(mv * dt_sim, 1e-12), 4),
                        "angle_deg": round(ang, 2), "wrapped": bool(wrapped),
                    })
        p.screenshot(str(out_dir / f"frame_{f:05d}.png"))

    (out_dir / "_prime.png").unlink(missing_ok=True)
    sidecar["render_seconds"] = round(time.time() - t_render0, 1)
    (out_dir / "anchors.json").write_text(json.dumps(sidecar), encoding="utf-8")
    print(f"[{shot['shot']}] rendered {len(frames)} frames in {sidecar['render_seconds']}s -> {out_dir}")
    return out_dir


def retune_windows(shot: dict) -> None:
    """Update callout/headline/formula windows in an existing sidecar without
    re-rendering frames -- the pick data is frame-identical, only the text
    schedule changes. Also re-derives on_feature from the SAVED actor + depth
    evidence against the (possibly updated) expected_actors/pick_depth: the
    rule is applied to already-recorded VTK picks, nothing is fabricated."""
    out = Path(shot["out_dir"]) / "anchors.json"
    sc = json.loads(out.read_text(encoding="utf-8"))
    for key in ("callouts", "headline"):
        sc[key] = shot[key]
    if "field_note" in shot:
        sc["field_note"] = shot["field_note"]
    if "formula" in shot:
        sc["formula"] = shot["formula"]
    if "anchors" in shot and sc.get("mode") != "plot":
        spec = {a["name"]: a for a in shot["anchors"]}
        # merge rule fields INTO the stored anchor entries -- never replace
        # them: the stored entries carry the feature world coordinates
        for entry in sc["anchors"]:
            s_ = spec.get(entry["name"])
            if s_ is not None:
                entry["expected_actors"] = s_["expected_actors"]
                entry["pick_depth"] = s_.get("pick_depth", [-0.05, 0.05])
        for fr in sc["frames"]:
            for name, pk in fr["pick"].items():
                a = spec.get(name)
                if a is None:
                    continue
                lo, hi = a.get("pick_depth", [-0.05, 0.05])
                actor = pk.get("actor")
                dz = pk.get("depth_delta_m")
                pk["on_feature"] = bool(actor in set(a["expected_actors"])
                                        and dz is not None and lo <= dz <= hi)
    out.write_text(json.dumps(sc), encoding="utf-8")
    print(f"[retune] {shot['shot']}: windows + pick rules updated in {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", required=True)
    ap.add_argument("--frames", default=None, help="subset like 0-12 for probes")
    ap.add_argument("--out", default=None)
    ap.add_argument("--fast", action="store_true", help="no SSAA (quality probes only)")
    ap.add_argument("--windows-only", action="store_true",
                    help="rewrite callout/headline/formula schedule in existing sidecar")
    args = ap.parse_args()
    shot = json.loads(Path(args.shot).read_text(encoding="utf-8"))
    if args.out:
        shot["out_dir"] = args.out
    if args.windows_only:
        retune_windows(shot)
        return
    if args.frames:
        a, b = args.frames.split("-")
        fr = list(range(int(a), int(b) + 1))
    else:
        fr = list(range(int(round(shot["duration"] * shot["fps"]))))
    mode = shot.get("mode", "vtk")
    if mode == "plot":
        render_plot_shot(shot, fr)
    else:
        render_shot(shot, fr, fast=args.fast)


# --------------------------------------------------------------------------- #
# plot mode: centreline Cp curve extracted from the body patch (Segment A).
# Curve, axes, units and every number come from the solved field; the shot is
# labelled steady RANS by the source line. No drag coefficient appears.
# --------------------------------------------------------------------------- #
def extract_centerline(body, base_face_cp: float) -> dict:
    """Surface chain in the symmetry plane: stagnation -> over the nose -> roof
    -> slant -> down the base. All coordinates and values are mesh points.
    base_face_cp is the native face-mean base Cp from face_fields (displayed).

    Sign convention: OpenFOAM's wallShearStress is nut*dU/dn with the patch
    normal pointing INTO the wall, so the stored x-component is the NEGATIVE
    of the true fluid-side wall shear (the attached roof stores ~-2.5; after
    negation u* = sqrt(tau/rho) ~ 1.6 m/s gives a sane Cf). We report
    tau_w,x in the fluid convention: wss_true = -wssx. The zero contour is
    sign-invariant, so the 3D separation-line extraction is unaffected.
    """
    pts = np.asarray(body.points)
    cp = body.point_data["Cp"]
    if "wssx" not in body.point_data:
        body.point_data["wssx"] = body.point_data["wallShearStress"][:, 0]
    wss_true = -np.asarray(body.point_data["wssx"], float)
    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
    near = np.abs(y) < 6e-3
    x_rear = float(x.max())
    x_base = x_rear - 0.002  # vertical rear face

    # 1) front face from stagnation upward (a handful of vertices -- per-point)
    front = np.where(near & (x < 0.012))[0]
    stag_i = front[int(np.argmax(cp[front]))]
    up = front[z[front] >= z[stag_i]]
    up = up[np.argsort(z[up])]
    P0 = pts[up]
    c0, w0 = cp[up], wss_true[up]

    # 2) over the hood, roof and slant: MEAN of the surface points per x bin.
    #    z > 0.07 drops the underbody column that shares every x bin; 6 mm
    #    bins keep the leading-edge suction peak (-1.58) that 10 mm bins wash
    #    out, while averaging away the two-vertices-per-bin zigzag (verified:
    #    roof sigma 0.043 physical vs 0.15 sawtooth on raw picks).
    bins = [i for i in (np.where(near & (x >= bx) & (x < bx + 0.0065) & (z > 0.07))[0]
                        for bx in np.arange(0.012, x_base - 0.004, 0.006)) if len(i)]
    prof_x = np.array([pts[i, 0].mean() for i in bins])
    prof_z = np.array([pts[i, 2].mean() for i in bins])
    prof_cp = np.array([cp[i].mean() for i in bins])
    prof_wss = np.array([wss_true[i].mean() for i in bins])

    # 3) down the vertical base
    base = np.where(near & (x >= x_base))[0]
    base = base[np.argsort(-z[base])]
    Pb, cb, wb = pts[base], cp[base], wss_true[base]

    # stitch one continuous arc-length chain: front vertices, bin centroids,
    # base vertices -- all in walking order, no double-counted transition pts
    D = np.vstack([P0,
                   np.column_stack([prof_x, np.zeros_like(prof_x), prof_z]),
                   Pb])
    s_ = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(D, axis=0), axis=1))])
    xs_ = D[:, 0]
    cp_ = np.concatenate([c0, prof_cp, cb])
    wss_ = np.concatenate([w0, prof_wss, wb])

    # the suction peak lives at the front top edge (x~0.066), so the search
    # window starts right after the front stagnation face
    roof = (xs_ > 0.03) & (xs_ < 0.80)
    peak_i = int(np.argmin(np.where(roof, cp_, 9e9)))
    mid_i = int(np.argmin(np.abs(xs_ - 0.55)))
    slant = xs_ > 0.84
    neg_idx = np.where(slant & (wss_ < 0.0))[0]
    sep_i = int(neg_idx[0]) if len(neg_idx) else int(np.argmax(slant))
    base_i = np.where(xs_ >= x_base)[0]
    return {
        "s": s_, "cp": cp_, "xs": xs_, "wssx": wss_,
        "stagnation": (float(s_[0]), float(cp_[0])),
        "roof_peak": (float(s_[peak_i]), float(cp_[peak_i])),
        "mid_roof": (float(s_[mid_i]), float(cp_[mid_i])),
        "separation": (float(s_[sep_i]), float(cp_[sep_i])),
        "base_mid": (float(s_[base_i[len(base_i) // 2]]), float(cp_[base_i[len(base_i) // 2]])),
        "base_mean_cp": float(cp_[base_i].mean()),
        "base_face_cp": base_face_cp,
        "s_total": float(s_[-1]),
        "n": int(len(s_)),
    }


def render_plot_shot(shot: dict, frames: list[int]) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    case_dir = Path(shot["case"])
    out_dir = Path(shot["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    fps = float(shot["fps"])
    duration = float(shot["duration"])
    n_total = int(round(duration * fps))
    r0, r1 = shot.get("reveal_frames", [int(0.05 * n_total), int(0.72 * n_total)])
    plot_opt = shot.get("plot", {})

    W, H = 1920, 1080
    ink, grid = "#cfd8e3", "#2a3442"
    curve_col, steel = "#7fb3e0", "#6fa8d6"
    focus_col = "#e8733b"

    if plot_opt.get("kind") == "force_split":
        fig, payload = _build_force_chart(shot, W, H, ink, grid, steel, focus_col)
    else:
        c = load(case_dir, u_inf=U_INF)
        ff = face_fields(case_dir)
        base_mask = (np.abs(ff["n"][:, 0]) > 0.9) & (ff["cc"][:, 0] > ff["cc"][:, 0].max() - 0.009)
        base_face_cp = float(ff["cp_face"][base_mask].mean())
        cl = extract_centerline(c.body, base_face_cp)
        print(f"[{shot['shot']}] centreline pts={cl['n']} s_total={cl['s_total']:.3f} "
              f"stag={cl['stagnation'][1]:.3f} peak={cl['roof_peak'][1]:.3f} "
              f"base_face_cp={cl['base_face_cp']:.4f}")
        fig, ax, ax2, payload = _build_cp_axes(shot, cl, W, H, ink, grid, curve_col,
                                                steel, focus_col, plot_opt)

    def reveal_frac(f):
        if f <= r0:
            return 0.0
        return _ease((f - r0) / max(r1 - r0, 1)) if f < r1 else 1.0

    def draw(frac):
        for a in fig.axes:
            a.clear()
        payload["style"]()
        payload["draw"](frac)
        fig.canvas.draw()

    # static anchor pixels: draw once fully revealed, transform, done
    draw(1.0)
    sidecar = {
        "kind": "cfd_shot_sidecar", "version": 1, "mode": "plot",
        "shot": shot["shot"], "case": str(case_dir),
        "fps": fps, "duration": duration, "n_frames": n_total,
        "width": W, "height": H, "background_rgb": list(BACKGROUND),
        "cp_clim": None, "slow_motion_factor": None, "u_inf": U_INF,
        "field_note": shot.get("field_note", payload["field_note"]),
        "source_line": shot["source_line"], "headline": shot["headline"],
        "callouts": shot["callouts"], "camera_keys": None,
        "features_measured": payload["features_measured"],
        "anchors": [], "frames": [], "marker_proof": [],
        "reveal_frames": [r0, r1], "cp_bar_stops": None,
    }
    sidecar["anchors"] = []
    for a_def in shot["anchors"]:
        u, v = payload["anchor_px"](a_def["name"])
        sidecar["anchors"].append({"name": a_def["name"],
                                   "world": list(payload["anchor_world"](a_def["name"])),
                                   "px_static": [float(u), float(v)],
                                   "expected_actors": ["curve"]})

    last_static = None
    for f in frames:
        frac = reveal_frac(f)
        png = out_dir / f"frame_{f:05d}.png"
        if frac >= 1.0 and last_static is not None and last_static != f - 1:
            import shutil
            shutil.copyfile(out_dir / f"frame_{last_static:05d}.png", png)
        else:
            draw(frac)
            fig.savefig(str(png), facecolor=fig.get_facecolor())
            last_static = f
        fr = {"f": f, "camera": None, "anchors": {}, "pick": {}}
        for a in sidecar["anchors"]:
            fr["anchors"][a["name"]] = [round(v, 2) for v in a["px_static"]]
            on = frac >= payload["reveal_at"](a["name"])
            fr["pick"][a["name"]] = {"actor": "curve" if on else None, "on_feature": bool(on)}
        sidecar["frames"].append(fr)

    (out_dir / "anchors.json").write_text(json.dumps(sidecar), encoding="utf-8")
    print(f"[{shot['shot']}] plot frames written -> {out_dir} ({len(frames)} frames)")
    return out_dir


def _build_cp_axes(shot, cl, W, H, ink, grid, curve_col, steel, focus_col, opt):
    """Cp(s) centreline trace. Layout contract (owner review 2026-11-22):
    the axes block stays above the source line; the quoted base FACE MEAN
    (-0.1118, a different quantity from the centreline curve) is drawn as an
    explicit dashed level so no label ever quotes a value the curve does not
    show; plain-text axis labels (mathtext stacked ∞ badly under ^2)."""
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    fig.patch.set_facecolor("#0e1218")
    show_wss = bool(opt.get("wss_strip", False))
    if show_wss:
        # main axis top 0.845 (screen y=167) keeps the rotated ylabel clear of
        # the headline block; strip sits above the source row (~886) and the
        # subtitle band (>=930). (owner review 2026-11-22.)
        ax = fig.add_axes((0.115, 0.50, 0.815, 0.345))
        ax2 = fig.add_axes((0.115, 0.315, 0.815, 0.13), sharex=ax)
    else:
        ax = fig.add_axes((0.115, 0.26, 0.815, 0.585))
        ax2 = None

    x_base = float(np.max(cl["xs"])) - 0.002
    lo_ = min(-1.0, cl["roof_peak"][1] - 0.15)
    level = cl["base_face_cp"]
    bi = np.where(cl["xs"] >= x_base)[0]
    s_level_mid = float(cl["s"][bi[len(bi) // 2]]) if len(bi) else cl["s_total"]

    def style():
        for a in fig.axes:
            a.set_facecolor("#0e1218")
            for sp in a.spines.values():
                sp.set_color("#4a5568")
            a.tick_params(colors=ink, labelsize=22)
        ax.grid(True, color=grid, linewidth=1, alpha=0.8)
        ax.set_ylabel("Cp = p / (½U∞²)", color=ink, fontsize=26)
        ax.axhline(0.0, color="#7b8794", linestyle="--", linewidth=2)
        ax.set_xlim(-0.03, cl["s_total"] * 1.04)
        ax.set_ylim(lo_, 1.25)
        if ax2 is not None:
            ax2.grid(True, color=grid, linewidth=1, alpha=0.6)
            ax2.axhline(0.0, color="#7b8794", linewidth=2)
            ax2.set_xlabel("s  —  centreline arc length from stagnation [m]",
                           color=ink, fontsize=24)
            ax2.set_ylabel("τw,x/ρ  [m²/s²]", color=ink, fontsize=22)
            wmin = float(np.min(cl["wssx"]))
            wmax = float(np.max(cl["wssx"]))
            ax2.set_ylim(min(-0.5, wmin * 1.15), max(0.5, wmax * 1.15))
        else:
            ax.set_xlabel("s  —  centreline arc length from stagnation [m]",
                          color=ink, fontsize=26)

    def draw(frac):
        style()
        k = max(2, int(round(frac * (len(cl["s"]) - 1))) + 1)
        ax.plot(cl["s"][:k], cl["cp"][:k], color=curve_col, linewidth=4.5, zorder=3)
        bmask = np.where(cl["xs"][:k] >= x_base)[0]
        if len(bmask) > 1:
            # centreline base trace stays steel: it is NOT the face mean
            ax.plot(cl["s"][bmask], cl["cp"][bmask], color=steel, linewidth=5.0, zorder=4)
        if not show_wss and frac > 0.93 and len(bmask) > 1:
            # explicit marked level for the quoted face mean (owner review):
            # drawn across the slant+base span where the centreline curve sits
            # visibly below it; the numeric identity lives in the tracked
            # Remotion label, which points AT this line -- no in-figure text
            # to collide with the curve.
            ax.plot([cl["s_total"] * 0.78, cl["s_total"]], [level, level],
                    color=focus_col, linewidth=3.0, linestyle=(0, (7, 5)), zorder=4)
        for nm in ("stagnation", "roof_peak", "mid_roof", "separation"):
            if nm == "mid_roof" and not any(cd["anchor"] == "mid_roof" for cd in shot["callouts"]):
                continue
            sx, sv = cl[nm]
            if sx <= cl["s"][k - 1] + 1e-9:
                col = focus_col if (show_wss and nm == "separation") else "#ffffff"
                ax.plot([sx], [sv], "o", color=col, ms=10, mec="#0e1218", mew=2, zorder=5)
        if show_wss:
            ax2.plot(cl["s"][:k], cl["wssx"][:k], color=steel, linewidth=3)
            ax2.fill_between(cl["s"][:k], cl["wssx"][:k], 0.0,
                             where=np.asarray(cl["wssx"][:k]) < 0,
                             color=focus_col, alpha=0.30, interpolate=True)

    def anchor_px(name):
        if name == "base_plateau":
            y = level if not show_wss else cl["base_mid"][1]
            fx, fy = ax.transData.transform((s_level_mid, y))
        else:
            fx, fy = ax.transData.transform(cl[name])
        return float(fx), float(H - fy)

    def anchor_world(name):
        if name == "base_plateau":
            y = level if not show_wss else cl["base_mid"][1]
            return (s_level_mid, 0.0, y)
        return (cl[name][0], 0.0, cl[name][1])

    def reveal_at(name):
        if name == "base_plateau" and not show_wss:
            return 0.93
        key = "base_mid" if name == "base_plateau" else name
        s_ = cl[key][0]
        return s_ / max(cl["s_total"], 1e-9)

    fm = {
        "stagnation_cp": round(cl["stagnation"][1], 4),
        "roof_peak_cp": round(cl["roof_peak"][1], 4),
        "mid_roof_cp": round(cl["mid_roof"][1], 4),
        "separation_cp": round(cl["separation"][1], 4),
        "separation_s_m": round(cl["separation"][0], 4),
        "base_cp_face_mean": round(cl["base_face_cp"], 4),
        "base_cp_centreline_mid": round(cl["base_mid"][1], 4),
        "s_total_m": round(cl["s_total"], 4),
    }
    return fig, ax, ax2, {
        "style": style, "draw": draw, "anchor_px": anchor_px,
        "anchor_world": anchor_world, "reveal_at": reveal_at,
        "features_measured": fm,
        "field_note": ("steady RANS mean field · curve: centreline trace · "
                       "Cp = p/(½U∞²), dimensionless · τ strip: fluid-side wall shear")
        if show_wss else
        ("steady RANS mean field · curve: centreline trace, dashed level: base face mean · "
         "Cp = p/(½U∞²), dimensionless"),
    }


def _build_force_chart(shot, W, H, ink, grid, steel, focus_col):
    """Drag split bars. Values are transcribed verbatim from the shot config,
    whose data_source names the solver output file they were read from."""
    import matplotlib.pyplot as plt

    d = shot["chart_data"]
    items = d["items"]
    xmax = d["axis"]["xmax"]
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    fig.patch.set_facecolor("#0e1218")
    ax = fig.add_axes((0.26, 0.34, 0.55, 0.42))

    ys = np.arange(len(items))[::-1]
    vals = [it["value"] for it in items]
    cols = [focus_col if it.get("focus") else steel for it in items]

    def style():
        ax.set_facecolor("#0e1218")
        for sp in ax.spines.values():
            sp.set_color("#4a5568")
        ax.tick_params(colors=ink, labelsize=22)
        ax.grid(True, axis="x", color=grid, linewidth=1, alpha=0.8)
        ax.set_xlabel(f"drag force [{d['unit']}]", color=ink, fontsize=26)
        ax.set_xlim(0, xmax)
        ax.set_ylim(-0.8, len(items) - 0.2)
        ax.set_yticks(ys)
        ax.set_yticklabels([it["label"] for it in items], color=ink, fontsize=26)

    def draw(frac):
        style()
        for i, it in enumerate(items):
            ax.barh(ys[i], it["value"] * frac, height=0.46, color=cols[i], zorder=3)
            if frac > 0.97:
                ax.text(it["value"] + xmax * 0.02, ys[i],
                        f"{it['value']:.2f} N · {it['pct']:.2f}%",
                        va="center", color=ink, fontsize=24, zorder=4)
        if frac > 0.97 and d.get("caveat"):
            # two wrapped lines below the axis: the split is Ahmed-specific,
            # the car-typical figure is a textbook range, never a constant
            lines = d["caveat"].split("|")
            for j, ln in enumerate(lines):
                ax.text(0.0, -0.24 - 0.085 * j, ln, transform=ax.transAxes,
                        color="#8fa0b3", fontsize=22, va="top")

    def anchor_px(name):
        for i, it in enumerate(items):
            if it["name"] == name:
                fx, fy = ax.transData.transform((it["value"], ys[i]))
                return float(fx), float(H - fy)
        raise KeyError(name)

    def anchor_world(name):
        for it in items:
            if it["name"] == name:
                return (it["value"], 0.0, 0.0)
        raise KeyError(name)

    def reveal_at(name):
        for it in items:
            if it["name"] == name:
                return it["value"] / xmax
        return 0.0

    fm = {it["name"] + "_N": it["value"] for it in items}
    fm["total_N"] = d["total"]
    return fig, {
        "style": style, "draw": draw, "anchor_px": anchor_px,
        "anchor_world": anchor_world, "reveal_at": reveal_at,
        "features_measured": fm,
        "field_note": f"data bar · values from {d.get('data_source', 'solver forces output')} (spec section 2)",
    }


if __name__ == "__main__":
    main()
