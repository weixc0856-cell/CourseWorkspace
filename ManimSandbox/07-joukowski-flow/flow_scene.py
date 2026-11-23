"""Joukowski airfoil potential flow -- a data-driven Manim scene.

Reads flow.npz (computed by flow_field.py from the analytic complex potential).
Every curve here is sampled from the equations; the airfoil outline is the
conformal map of a circle, the streamlines are RK4 trajectories of the real
velocity field. Nothing is hand-drawn.

Three-beat rhythm (hook -> deconstruct -> reconstruct), spotlight rule,
causal delay, damped camera dolly. Render:
  uv run manim render -r 1920,1080 --fps 30 \
    --media_dir <content_root>/build/_shared/joukowski-flow/media \
    07-joukowski-flow/flow_scene.py JoukowskiFlow
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from manim import (
    DOWN, LEFT, RIGHT, UP, Arrow, Dot, Ellipse, FadeIn, FadeOut, GrowArrow,
    ImageMobject, MathTex, MovingCameraScene, Polygon, Text, VGroup, Write,
    config,
)
from manim.utils.rate_functions import ease_in_out_cubic, ease_out_cubic, smooth

import os
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.design_system import BG, INK, MUTED, ORANGE, BLUE, TEAL, TYPE

config.background_color = BG
HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get("COURSEWORKSPACE_CONTENT_ROOT")
           or HERE.parent.parent / "content_data") / "build/_shared/joukowski-flow"

# data extent x:[-3,5] y:[-2.6,2.6] -> manim units
K = 1.30
CX, CY = 0.0, -0.30


def M(pt):
    return np.array([(float(pt[0]) - 1.0) * K + CX, float(pt[1]) * K + CY, 0.0])


def txt(s, size=24, color=INK, weight="NORMAL"):
    return Text(s, font="Arial", font_size=size, color=color, weight=weight)


class JoukowskiFlow(MovingCameraScene):
    def construct(self):
        d = np.load(OUT / "flow.npz", allow_pickle=True)
        foil = d["foil"]
        streams = list(d["streams"])
        stag = d["stag"]
        te = d["te"]
        p = d["params"]
        Gamma, Cl, cp_min = float(p[7]), float(p[9]), float(p[10])

        self.clock = 0.0
        self.camera.frame.set_width(14.2222).move_to([CX, CY, 0])

        cloud = ImageMobject(str(OUT / "cp_cloud.png")).set_width(8 * K)
        cloud.move_to([CX, CY, 0])
        body = Polygon(*[M(q) for q in foil[::3]], stroke_color=INK, stroke_width=2,
                       fill_opacity=0)
        slines = VGroup(*[
            VMobject_line(s) for s in streams
        ])

        # particles advecting along the real velocity field
        particles = VGroup()
        for j, s in enumerate(streams):
            if j % 2 == 0 and len(s) > 30:
                col = ORANGE if 0.1 < s[0][1] < 1.3 else BLUE
                particles.add(make_particle(s, (j * 0.37) % 1.0, 1.7 + (j % 5) * 0.18, col))

        eyebrow = txt("POTENTIAL FLOW  ·  JOUKOWSKI AIRFOIL", 18, MUTED).move_to([-4.6, 3.3, 0]).align_to([-6.6, 0, 0], LEFT)
        headline = txt("Why does a wing lift?", 44, INK, "BOLD").move_to([-3.0, 2.8, 0]).align_to([-6.6, 0, 0], LEFT)

        # ---------------------------------------------------- beat 1: hook
        self.beat(FadeIn(cloud), run_time=0.8)
        self.beat(FadeIn(body), FadeIn(eyebrow), FadeIn(headline, shift=DOWN * 0.12), run_time=0.8)
        self.beat(*[FadeIn(sl, shift=RIGHT * 0.1) for sl in slines[:8]], run_time=0.5)
        self.beat(*[FadeIn(sl) for sl in slines[8:]], FadeIn(particles), run_time=0.7)
        self.play(self.camera.frame.animate.set_width(13.4).move_to([CX, -0.2, 0]),
                  run_time=1.8, rate_func=ease_in_out_cubic)
        self.clock += 1.8
        self.beat(run_time=1.2)

        # ------------------------------------------- beat 2: deconstruct
        # dim everything, spotlight the upper-surface suction
        hi = [sl for sl, s in zip(slines, streams) if 0.1 < s[0][1] < 1.3]
        lo = [sl for sl in slines if sl not in hi]
        self.beat(
            cloud.animate.set_opacity(0.22),
            *[sl.animate.set_stroke(opacity=0.10) for sl in lo],
            *[sl.animate.set_stroke(color=ORANGE, width=2.6, opacity=0.95) for sl in hi],
            FadeOut(headline), FadeOut(eyebrow),
            run_time=0.9,
        )
        self.play(self.camera.frame.animate.set_width(10.5).move_to([-1.2, 0.2, 0]),
                  run_time=1.8, rate_func=ease_in_out_cubic)
        self.clock += 1.8
        # causal chain: fast flow -> low pressure -> number -> equation
        spot = Ellipse(width=2.6, height=1.5, color=ORANGE, stroke_width=2,
                       fill_color=ORANGE, fill_opacity=0.10).move_to(M([-1.55, 0.55]))
        self.beat(FadeIn(spot), run_time=0.4)
        lab_fast = txt("flow speeds up over the top", 22, INK).move_to(M([-1.2, 1.7]))
        self.beat(FadeIn(lab_fast, shift=DOWN * 0.08), run_time=0.4)
        lab_cp = MathTex(r"C_p = %.2f" % cp_min, font_size=34, color=BLUE).move_to(M([-1.5, 1.15]))
        self.beat(Write(lab_cp), run_time=0.5)
        f_cp = MathTex(r"C_p = 1 - \left(\frac{V}{U}\right)^2", font_size=32, color=INK)
        f_cp.move_to([2.4, 1.9, 0])
        self.beat(FadeIn(f_cp, shift=LEFT * 0.1), run_time=0.6)
        # stagnation + Kutta markers
        stag_dot = Dot(M(stag), radius=0.06, color=INK).set_stroke(BG, width=2)
        stag_lab = MathTex(r"C_p=+1", font_size=26, color=INK).next_to(stag_dot, DOWN, buff=0.18)
        te_dot = Dot(M(te), radius=0.05, color=TEAL).set_stroke(BG, width=2)
        te_lab = txt("Kutta: smooth exit", 20, TEAL).next_to(te_dot, RIGHT, buff=0.15)
        self.beat(FadeIn(stag_dot), FadeIn(stag_lab), FadeIn(te_dot), FadeIn(te_lab), run_time=0.7)
        f_w = MathTex(r"w(\zeta)=U\!\left(\zeta+\frac{R^2}{\zeta}\right)+\frac{i\Gamma}{2\pi}\ln\zeta",
                      font_size=26, color=INK).move_to([1.7, 1.0, 0])
        self.beat(Write(f_w), run_time=0.9)
        gamma_lab = MathTex(r"\Gamma = %.3f" % Gamma, font_size=28, color=ORANGE).next_to(f_w, DOWN, buff=0.25)
        self.beat(FadeIn(gamma_lab), run_time=0.5)
        self.beat(run_time=1.0)

        # ------------------------------------------- beat 3: reconstruct
        self.beat(
            cloud.animate.set_opacity(1.0),
            *[sl.animate.set_stroke(color=INK, width=1.5, opacity=0.45) for sl in slines],
            FadeOut(spot), FadeOut(lab_fast), FadeOut(lab_cp), FadeOut(f_cp),
            FadeOut(f_w), FadeOut(gamma_lab), FadeOut(stag_lab), FadeOut(te_lab),
            run_time=0.9,
        )
        self.play(self.camera.frame.animate.set_width(12.8).move_to([CX, -0.2, 0]),
                  run_time=1.8, rate_func=ease_in_out_cubic)
        self.clock += 1.8
        lift = Arrow(M([0.1, 0.35]), M([0.1, 1.7]), color=ORANGE, stroke_width=7,
                     max_tip_length_to_length_ratio=0.16)
        lift_lab = txt("LIFT", 22, ORANGE, "BOLD").next_to(lift, RIGHT, buff=0.2)
        cl_eq = MathTex(r"C_L = %.2f" % Cl, font_size=46, color=INK).move_to([4.6, 1.4, 0])
        kj = MathTex(r"L' = \rho\, U\, \Gamma", font_size=34, color=INK).next_to(cl_eq, DOWN, buff=0.3)
        kj_note = txt("Kutta–Joukowski theorem", 19, MUTED).next_to(kj, DOWN, buff=0.18)
        self.beat(GrowArrow(lift), FadeIn(lift_lab), run_time=0.8)
        self.beat(Write(cl_eq), run_time=0.7)
        self.beat(FadeIn(kj), FadeIn(kj_note), run_time=0.6)
        source = txt("Schematic · analytic potential flow (inviscid). No external source.",
                     17, MUTED).move_to([0, -3.55, 0])
        self.beat(FadeIn(source), run_time=0.5)
        self.beat(run_time=2.2)

        if self.clock < 22:
            self.wait(22 - self.clock)
            self.clock = 22.0

    def beat(self, *anims, run_time=1.0, rate_func=smooth):
        if anims:
            self.play(*anims, run_time=run_time, rate_func=rate_func)
        else:
            self.wait(run_time)
        self.clock += run_time


def VMobject_line(s):
    from manim import VMobject
    v = VMobject(stroke_color=INK, stroke_width=1.5, stroke_opacity=0.45)
    v.set_points_as_corners([M(q) for q in s[::3]])
    return v


def make_particle(stream, offset, speed, color):
    pts = np.array([M(q) for q in stream])
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    dot = Dot(pts[0], radius=0.045, color=color)
    state = {"s": offset * total}

    def upd(m, dt):
        state["s"] = (state["s"] + dt * speed) % total
        s = state["s"]
        i = int(np.searchsorted(cum, s) - 1)
        i = min(max(i, 0), len(pts) - 2)
        f = (s - cum[i]) / max(seg[i], 1e-9)
        m.move_to(pts[i] * (1 - f) + pts[i + 1] * f)

    dot.add_updater(upd)
    return dot