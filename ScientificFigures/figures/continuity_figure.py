"""POC: SymPy derivation -> LaTeX, Matplotlib + SciencePlots -> SVG/PDF/PNG.

Run from the repository root:
  uv run --project ScientificFigures python ScientificFigures/figures/continuity_figure.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import sympy as sp
import scienceplots  # noqa: F401 - registers the styles

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)


def style() -> None:
    # SciencePlots' default "science" style assumes a full LaTeX install.
    # "no-latex" keeps the paper-like layout while using Matplotlib mathtext.
    try:
        plt.style.use(["science", "no-latex"])
    except OSError:
        plt.style.use("default")
    plt.rcParams.update(
        {
            "figure.dpi": 160,
            "savefig.dpi": 320,
            "font.family": "DejaVu Sans",
            "mathtext.fontset": "stix",
            "axes.unicode_minus": False,
        }
    )


def derive_continuity() -> dict:
    x, t, u, rho = sp.symbols("x t u rho", real=True)
    continuity = sp.Eq(sp.Derivative(rho, t) + sp.Derivative(rho * u, x), 0)
    steady = continuity.subs(sp.Derivative(rho, t), 0)
    incompressible = steady.subs(rho, sp.Symbol("rho_0", positive=True))
    reduced = sp.simplify(incompressible.lhs)
    return {
        "continuity": sp.latex(continuity),
        "steady": sp.latex(steady),
        "incompressible": sp.latex(sp.Eq(reduced, 0)),
    }


def velocity_figure() -> tuple[Path, Path, Path]:
    y = np.linspace(-1.0, 1.0, 400)
    velocity = 1.0 - y**2

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.plot(velocity, y, color="#0077B6", linewidth=2.2, label="plane Poiseuille")
    ax.fill_betweenx(y, 0, velocity, color="#0077B6", alpha=0.10)
    ax.axvline(0, color="#5C677D", linewidth=0.8)
    ax.set_xlabel("streamwise velocity  $u/U_{\\max}$")
    ax.set_ylabel("wall-normal position  $y/h$")
    ax.set_title("A parabolic velocity profile")
    ax.set_xlim(0, 1.08)
    ax.set_ylim(-1.05, 1.05)
    ax.text(
        0.08,
        0.72,
        r"$u(y)=U_{\max}\left(1-\frac{y^2}{h^2}\right)$",
        fontsize=15,
        color="#14213D",
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85, "pad": 4},
    )
    ax.legend(loc="lower right", frameon=False)
    fig.tight_layout()

    svg = OUT / "continuity_velocity.svg"
    pdf = OUT / "continuity_velocity.pdf"
    png = OUT / "continuity_velocity.png"
    fig.savefig(svg, format="svg", bbox_inches="tight")
    fig.savefig(pdf, format="pdf", bbox_inches="tight")
    fig.savefig(png, format="png", bbox_inches="tight", dpi=320)
    plt.close(fig)
    return svg, pdf, png


def main() -> None:
    style()
    formulas = derive_continuity()
    (OUT / "continuity_derivation.tex").write_text(
        "\n".join(
            [
                r"\begin{align}",
                r"\frac{\partial \rho}{\partial t}+\frac{\partial(\rho u)}{\partial x}&=0 \\",
                formulas["steady"] + r" \\",
                formulas["incompressible"],
                r"\end{align}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    svg, pdf, png = velocity_figure()
    print("derivation:", OUT / "continuity_derivation.tex")
    print("svg:", svg)
    print("pdf:", pdf)
    print("png:", png)


if __name__ == "__main__":
    main()
