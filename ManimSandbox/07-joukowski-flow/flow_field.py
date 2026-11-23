"""Potential flow past a Joukowski airfoil -- equation-driven, zero hand-drawn paths.

Analytic complex potential (uniform stream + doublet + vortex) around a cylinder
in the zeta-plane, mapped through z = zeta + a^2/zeta. Circulation is fixed by the
Kutta condition so the flow leaves the sharp trailing edge smoothly. Every curve
in the picture is sampled from these equations; nothing is sketched by hand.

Outputs:
  cp_static.png   journal-style Cp contour + streamlines + body mask (300 dpi)
  cp_cloud.png    bare Cp cloud + body, exact data extent, for Manim compositing
  flow.npz        grid fields, foil polygon, streamlines, stagnation, parameters
cp_static.png / cp_cloud.png go to the content root (<content_root>/build/_shared/joukowski-flow/);
flow.npz is written to OUT alongside the images (all products live in the content root).

Run:  uv run python 07-joukowski-flow/flow_field.py
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.collections import LineCollection
from matplotlib.path import Path as MplPath

HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get("COURSEWORKSPACE_CONTENT_ROOT")
           or HERE.parent.parent / "content_data") / "build/_shared/joukowski-flow"
OUT.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------- parameters
a = 1.0                      # Joukowski parameter; trailing edge at z = 2a
eps = 0.10                   # thickness offset
eta = 0.06                   # camber offset
alpha_deg = 6.0
U = 1.0
alpha = np.deg2rad(alpha_deg)

zeta0 = -eps + 1j * eta
R = abs(a - zeta0)                       # circle passes through zeta = a -> sharp TE
beta = np.arctan2(eta, a + eps)
Gamma = 4 * np.pi * U * R * np.sin(alpha + beta)   # Kutta condition


def dW_dzeta(zeta):
    d = zeta - zeta0
    return U * (np.exp(-1j * alpha) - R**2 * np.exp(1j * alpha) / d**2) \
        + 1j * Gamma / (2 * np.pi * d)


def joukowski(zeta):
    return zeta + a**2 / zeta


def velocity_z(z):
    s = np.sqrt(z**2 - 4 * a**2 + 0j)
    z1, z2 = (z + s) / 2, (z - s) / 2
    zeta = np.where(np.abs(z1 - zeta0) >= np.abs(z2 - zeta0), z1, z2)
    dz_dzeta = 1 - a**2 / zeta**2
    with np.errstate(divide="ignore", invalid="ignore"):
        return dW_dzeta(zeta) / dz_dzeta          # = u - i v


# ----------------------------------------------------------------- airfoil body
theta = np.linspace(0, 2 * np.pi, 1200)
foil_c = joukowski(zeta0 + R * np.exp(1j * theta))
foil = np.column_stack([foil_c.real, foil_c.imag])
# rotate so the polygon starts at the trailing edge and runs counter-clockwise
te_idx = int(np.argmax(foil[:, 0]))
foil = np.roll(foil, -te_idx, axis=0)
foil_path = MplPath(foil)

# ----------------------------------------------------------------- grid field
nx, ny = 600, 420
x = np.linspace(-3.0, 5.0, nx)
y = np.linspace(-2.6, 2.6, ny)
X, Y = np.meshgrid(x, y)
W = velocity_z(X + 1j * Y)
u = np.ma.masked_where(foil_path.contains_points(np.column_stack([X.ravel(), Y.ravel()])).reshape(X.shape), W.real)
v = np.ma.masked_where(u.mask, -W.imag)
Cp = np.ma.masked_where(u.mask, 1 - (np.abs(W) / U) ** 2)

# ----------------------------------------------------------------- stagnation
zeta_s = zeta0 - R * np.exp(1j * (2 * alpha + beta))   # front stagnation (physical)
z_s = joukowski(zeta_s)
stag = np.array([z_s.real, z_s.imag])
te = np.array([2 * a, 0.0])

# ----------------------------------------------------------------- streamlines
def trace(seed, dt=0.02, nmax=1400):
    p = np.array(seed, dtype=float)
    pts = [p.copy()]
    for _ in range(nmax):
        def vel(q):
            w = complex(velocity_z(complex(q[0], q[1])))
            return np.array([w.real, -w.imag])
        k1 = vel(p)
        if not np.all(np.isfinite(k1)) or np.linalg.norm(k1) < 1e-6:
            break
        k2 = vel(p + 0.5 * dt * k1)
        k3 = vel(p + 0.5 * dt * k2)
        k4 = vel(p + dt * k3)
        step = dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        p = p + step
        if p[0] > 4.9 or abs(p[1]) > 2.55 or foil_path.contains_point(p):
            break
        pts.append(p.copy())
    return np.array(pts)

seeds = [[-2.9, yy] for yy in np.linspace(-2.2, 2.2, 26)]
streams = [trace(s) for s in seeds]
streams = [s for s in streams if len(s) > 8]

# ----------------------------------------------------------------- verification
chord = 2 * a - foil[:, 0].min()
Cl = 2 * Gamma / (U * chord)
Cl_thin = 2 * np.pi * (alpha + beta)
cp_min = float(Cp.min())
# Kutta check: Cp just above / below the trailing edge should converge
def cp_near(pt):
    return float(1 - abs(complex(velocity_z(complex(pt[0], pt[1])))) ** 2 / U**2)
cp_te_up = cp_near([1.985, 0.012])
cp_te_lo = cp_near([1.985, -0.012])

print("=== Joukowski potential flow -- verification ===")
print(f"alpha={alpha_deg} deg  eps={eps}  eta={eta}  R={R:.4f}  beta={np.rad2deg(beta):.3f} deg")
print(f"Gamma (Kutta) = {Gamma:.5f}")
print(f"chord = {chord:.4f}")
print(f"Cl = 2*Gamma/(U*c) = {Cl:.5f}   thin-airfoil 2*pi*(alpha+beta) = {Cl_thin:.5f}")
print(f"min Cp (suction peak) = {cp_min:.4f}")
print(f"front stagnation z = ({stag[0]:.4f}, {stag[1]:.4f})  (Cp should be +1)")
print(f"Cp near TE upper={cp_te_up:.4f}  lower={cp_te_lo:.4f}  (Kutta: finite & close)")
print(f"streamlines traced: {len(streams)}")

# ----------------------------------------------------------------- static figure
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 13,
    "axes.linewidth": 0.8,
})
fig, ax = plt.subplots(figsize=(12.8, 8.32), dpi=300)
fig.patch.set_facecolor("white")
norm = TwoSlopeNorm(vmin=cp_min, vcenter=0.0, vmax=1.0)
cf = ax.contourf(X, Y, Cp, levels=60, cmap="RdBu_r", norm=norm, antialiased=True)
ax.add_collection(LineCollection(streams, colors=(0, 0, 0, 0.5), linewidths=0.8, zorder=3))
for j, s in enumerate(streams):
    if len(s) > 24:
        i = int((0.40 + 0.42 * ((j * 0.61803398875) % 1.0)) * (len(s) - 1))
        ax.annotate("", xy=s[i], xytext=s[i - 1],
                    arrowprops=dict(arrowstyle="-|>", color=(0, 0, 0, 0.6),
                                    lw=0.8, mutation_scale=9), zorder=3)
ax.fill(foil[:, 0], foil[:, 1], color="#3A3F45", zorder=5)
ax.plot(foil[:, 0], foil[:, 1], color="#1A1D21", lw=1.0, zorder=6)
ax.plot(*stag, "o", ms=7, mfc="white", mec="#1A1D21", mew=1.4, zorder=7)
ax.annotate("stagnation  Cp = +1", stag, xytext=(stag[0] - 0.4, stag[1] - 0.85),
            fontsize=12, ha="right",
            arrowprops=dict(arrowstyle="-", color="#1A1D21", lw=0.9))
ax.plot(*te, "s", ms=6, mfc="white", mec="#1A1D21", mew=1.3, zorder=7)
ax.annotate("sharp trailing edge (Kutta)", te, xytext=(te[0] + 0.25, te[1] + 0.9),
            fontsize=12, ha="left",
            arrowprops=dict(arrowstyle="-", color="#1A1D21", lw=0.9))
# suction peak marker
iy, ix = np.unravel_index(np.ma.argmin(Cp), Cp.shape)
ax.plot(X[iy, ix], Y[iy, ix], "^", ms=7, mfc="white", mec="#1A1D21", mew=1.3, zorder=7)
ax.annotate(f"suction peak  Cp = {cp_min:.2f}", (X[iy, ix], Y[iy, ix]),
            xytext=(X[iy, ix] - 0.2, Y[iy, ix] + 0.8), fontsize=12, ha="center",
            arrowprops=dict(arrowstyle="-", color="#1A1D21", lw=0.9))
cb = fig.colorbar(cf, ax=ax, shrink=0.82, pad=0.02)
cb.set_label("Pressure coefficient  $C_p = 1 - (V/U)^2$", fontsize=13)
ax.set_xlim(-3, 5)
ax.set_ylim(-2.6, 2.6)
ax.set_aspect("equal")
ax.set_xlabel("x / a")
ax.set_ylabel("y / a")
ax.set_title(f"Potential flow past a Joukowski airfoil   "
             f"$\\alpha={alpha_deg:.0f}^\\circ$,  $\\Gamma={Gamma:.3f}$,  $C_L={Cl:.3f}$",
             fontsize=15, pad=12)
ax.text(0.012, 0.02,
        "Analytic complex potential + Kutta condition.  Inviscid model: no separation or viscous effects.",
        transform=ax.transAxes, fontsize=10.5, color="#333",
        bbox=dict(facecolor="white", alpha=0.85, edgecolor="none", boxstyle="round,pad=0.3"))
fig.tight_layout()
fig.savefig(OUT / "cp_static.png", dpi=300, facecolor="white")
plt.close(fig)

# ----------------------------------------------------------------- bare cloud for Manim
fig2, ax2 = plt.subplots(figsize=(8.0, 5.2), dpi=220)
fig2.subplots_adjust(left=0, right=1, top=1, bottom=0)
ax2.set_position([0, 0, 1, 1])
ax2.contourf(X, Y, Cp, levels=60, cmap="RdBu_r", norm=norm, antialiased=True)
ax2.fill(foil[:, 0], foil[:, 1], color="#3A3F45", zorder=5)
ax2.set_xlim(-3, 5)
ax2.set_ylim(-2.6, 2.6)
ax2.axis("off")
fig2.savefig(OUT / "cp_cloud.png", dpi=220, facecolor="#FBFAF7", pad_inches=0)
plt.close(fig2)

# ----------------------------------------------------------------- cache
np.savez_compressed(
    OUT / "flow.npz",
    X=X, Y=Y, u=np.ma.filled(u, np.nan), v=np.ma.filled(v, np.nan),
    Cp=np.ma.filled(Cp, np.nan), foil=foil, stag=stag, te=te,
    streams=np.array(streams, dtype=object),
    params=np.array([a, eps, eta, alpha_deg, U, R, beta, Gamma, chord, Cl, cp_min]),
)
print(f"saved: cp_static.png, cp_cloud.png -> {OUT}; flow.npz -> {OUT}")