"""Systolic array: how a chip computes C = A B (output-stationary dataflow).

Equation/data-driven: every position is computed from array indices, every
number on screen comes from numpy (C = A @ B). Nothing is hand-drawn.
Pattern reused from 03-vector-intro (beat/clock) and 07-joukowski-flow
(design-system tokens, MovingCameraScene, ease_in_out_cubic dollies).

Render:
  uv run manim render -r 1920,1080 --fps 30 \
    --media_dir <content_root>/build/_shared/systolic-array/media \
    08-systolic-array/scene.py SystolicArray
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.design_system import BG, SURFACE, INK, MUTED, DIVIDER, ORANGE, BLUE, TEAL

from manim import (
    DOWN, LEFT, RIGHT, UP, Arrow, BackgroundRectangle, FadeIn, FadeOut,
    MathTex, MovingCameraScene, RoundedRectangle, Text, Transform, VGroup,
    Write, config,
)
from manim.utils.rate_functions import ease_in_out_cubic, smooth

config.background_color = BG

# ----------------------------------------------------------------- the data
A = np.array([[1, 2, 0], [0, 1, 3], [2, 0, 1]])
B = np.array([[1, 0, 2], [3, 1, 0], [0, 2, 1]])
C = A @ B  # numpy is the single source of truth for every displayed number

N = 3
P = 1.50        # grid pitch
S = 1.32        # cell size
HS = S / 2
GX, GY = 0.0, -0.55
B_TOP, B_STEP = 2.62, 0.26    # B panel rows (tight, kept clear of header)
CH = 0.20                     # half size of a data chip


def row_y(i: int) -> float:
    return GY - (i - 1) * P


def cell_c(i: int, j: int) -> np.ndarray:
    return np.array([GX + (j - 1) * P, row_y(i), 0.0])


def a_pos(i: int, k: int) -> np.ndarray:
    return np.array([-4.20 + k * 0.55, row_y(i), 0.0])


def b_pos(k: int, j: int) -> np.ndarray:
    return np.array([GX + (j - 1) * P, B_TOP - k * B_STEP, 0.0])


def c_pos(i: int, j: int) -> np.ndarray:
    return np.array([3.55 + (j - 1) * 0.75, GY - (i - 1) * 0.90, 0.0])


def txt(s: str, size: int = 22, color: str = INK, weight: str = "NORMAL") -> Text:
    return Text(s, font="Arial", font_size=size, color=color, weight=weight)


def chip(value: int, color: str) -> VGroup:
    body = RoundedRectangle(corner_radius=0.07, width=2 * CH + 0.04,
                            height=2 * CH + 0.04, stroke_width=0)
    body.set_fill(color, 1.0)
    lab = Text(str(int(value)), font="Arial", font_size=18, color="#FFFFFF",
               weight="BOLD").move_to([0, 0.012, 0])
    return VGroup(body, lab)


class SystolicArray(MovingCameraScene):
    def construct(self) -> None:
        self.clock = 0.0
        self.camera.frame.set_width(14.2222).move_to([0.0, 0.02, 0.0])

        # ---------------------------------------------------------- headers
        eyebrow = txt("SYSTOLIC ARRAY  ·  OUTPUT-STATIONARY DATAFLOW", 15, MUTED)
        eyebrow.move_to([-6.50, 3.86, 0.0]).align_to([-6.50, 0, 0], LEFT)
        hl1 = txt("How a chip", 28, INK, "BOLD")
        hl1.move_to([-6.50, 3.54, 0.0]).align_to([-6.50, 0, 0], LEFT)
        hl2 = txt("multiplies matrices", 28, INK, "BOLD")
        hl2.move_to([-6.50, 3.10, 0.0]).align_to([-6.50, 0, 0], LEFT)
        eq = MathTex(r"C = A\,B", font_size=44, color=INK)
        eq.set_color_by_tex("A", ORANGE).set_color_by_tex("B", BLUE)
        eq.set_color_by_tex("C", TEAL)
        eq.move_to([5.45, 3.42, 0.0])
        caption = txt("each cell: multiply + accumulate", 21, MUTED)
        caption.move_to([2.60, -3.48, 0.0])

        # ------------------------------------------------------------ A / B
        self.a_nums = VGroup(*[
            Text(str(int(A[i, k])), font="Arial", font_size=26, color=INK)
            .move_to(a_pos(i, k))
            for i in range(N) for k in range(N)
        ])
        self.a_lab = txt("A", 24, ORANGE, "BOLD").move_to([-4.90, GY, 0.0])
        self.a_panel = BackgroundRectangle(self.a_nums, color=SURFACE,
                                           fill_opacity=0.75, stroke_width=1,
                                           stroke_color=DIVIDER,
                                           stroke_opacity=0.9, buff=0.24)

        self.b_nums = VGroup(*[
            Text(str(int(B[k, j])), font="Arial", font_size=23, color=INK)
            .move_to(b_pos(k, j))
            for k in range(N) for j in range(N)
        ])
        self.b_lab = txt("B", 24, BLUE, "BOLD").move_to([2.35, b_pos(1, 1)[1], 0.0])
        self.b_panel = BackgroundRectangle(self.b_nums, color=SURFACE,
                                           fill_opacity=0.75, stroke_width=1,
                                           stroke_color=DIVIDER,
                                           stroke_opacity=0.9, buff=0.16)

        # ------------------------------------------------------------- grid
        self.cells = VGroup()
        self.accs = VGroup()
        for i in range(N):
            for j in range(N):
                body = RoundedRectangle(corner_radius=0.11, width=S, height=S,
                                        stroke_color=DIVIDER, stroke_width=2)
                body.set_fill(SURFACE, 0.45).move_to(cell_c(i, j))
                ac = Text("0", font="Arial", font_size=32, color=INK).set_opacity(0.35)
                ac.move_to(cell_c(i, j) + np.array([0, 0.06, 0.0]))
                self.cells.add(body)
                self.accs.add(ac)

        # ---------------------------------------------------------- beat 1
        self.beat(FadeIn(self.cells), FadeIn(self.accs), FadeIn(self.a_panel),
                  FadeIn(self.a_nums), FadeIn(self.a_lab), FadeIn(self.b_panel),
                  FadeIn(self.b_nums), FadeIn(self.b_lab), run_time=0.7)
        self.beat(FadeIn(eyebrow), FadeIn(hl1), FadeIn(hl2, shift=DOWN * 0.08),
                  FadeIn(eq), FadeIn(caption), run_time=0.6)
        self.play(self.camera.frame.animate.set_width(14.15),
                  run_time=1.2, rate_func=ease_in_out_cubic)
        self.clock += 1.2

        # ------------------------------------------------------------ focus
        self.focus_pe(0, 0, with_eq=True)
        self.focus_pe(1, 1, with_eq=False)
        self.focus_pe(2, 2, with_eq=False)

        # ----------------------------------------------------------- reveal
        self.beat(self.cells.animate.set_opacity(1.0),
                  self.accs.animate.set_opacity(1.0), run_time=0.3)

        c_out = VGroup()
        c_panel = BackgroundRectangle(
            VGroup(*[Text(str(int(C[i, j])), font="Arial", font_size=27, color=TEAL)
                     .move_to(c_pos(i, j))
                     for i in range(N) for j in range(N)]),
            color=SURFACE, fill_opacity=0.9,
            stroke_width=1.5, stroke_color=TEAL, stroke_opacity=0.7, buff=0.32)
        c_lab = txt("C", 24, TEAL, "BOLD").move_to([5.05, GY - 0.45, 0.0])
        self.beat(FadeIn(c_panel), FadeIn(c_lab), run_time=0.3)

        # one wavefront per anti-diagonal: cell ticks to its C value and a
        # teal number drains out to the C panel
        for s_ in range(2 * N - 1):
            anims = []
            for i in range(N):
                j = s_ - i
                if 0 <= j < N:
                    idx = i * N + j
                    new = Text(str(int(C[i, j])), font="Arial", font_size=33,
                               color=TEAL, weight="BOLD")
                    new.move_to(self.accs[idx].get_center())
                    anims.append(Transform(self.accs[idx], new))
                    dn = Text(str(int(C[i, j])), font="Arial", font_size=27,
                              color=TEAL, weight="BOLD").move_to(c_pos(i, j))
                    shift = (c_pos(i, j) - self.accs[idx].get_center()) / 14.0
                    anims.append(FadeIn(dn, shift=shift))
                    c_out.add(dn)
            self.beat(*anims, run_time=0.45, rate_func=ease_in_out_cubic)

        self.beat(eq.animate.scale(1.18), run_time=0.55, rate_func=ease_in_out_cubic)
        self.play(self.camera.frame.animate.set_width(14.2222)
                  .move_to([0.0, 0.02, 0.0]),
                  run_time=0.9, rate_func=ease_in_out_cubic)
        self.clock += 0.9
        self.play(self.camera.frame.animate.set_width(14.08).move_to([0.22, 0.05, 0.0]),
                  run_time=1.1, rate_func=ease_in_out_cubic)
        self.clock += 1.1
        self.beat(run_time=1.0)

        target = 21.5
        if self.clock < target:
            self.wait(target - self.clock)
            self.clock = target
        if abs(self.clock - target) > 0.05:
            print(f"WARNING: clock={self.clock:.2f}s, expected {target:.2f}s")

    # ------------------------------------------------------------ one PE
    def focus_pe(self, i: int, j: int, with_eq: bool = False) -> None:
        idx = i * N + j
        center = cell_c(i, j)

        ring = RoundedRectangle(corner_radius=0.13, width=S + 0.14, height=S + 0.14,
                                stroke_color=ORANGE, stroke_width=4.5,
                                fill_color=ORANGE, fill_opacity=0.05)
        ring.move_to(center)
        ar = Arrow(center + np.array([-HS - 0.30, -0.16, 0.0]),
                   center + np.array([-HS - 0.04, -0.16, 0.0]),
                   buff=0, color=ORANGE, stroke_width=4,
                   max_tip_length_to_length_ratio=0.30)
        ab = Arrow(center + np.array([-0.16, HS + 0.30, 0.0]),
                   center + np.array([-0.16, HS + 0.04, 0.0]),
                   buff=0, color=BLUE, stroke_width=4,
                   max_tip_length_to_length_ratio=0.30)

        row_a = VGroup(*[self.a_nums[i * N + k] for k in range(N)])
        col_b = VGroup(*[self.b_nums[k * N + j] for k in range(N)])
        others = VGroup(*[self.cells[m] for m in range(N * N) if m != idx])
        others_acc = VGroup(*[self.accs[m] for m in range(N * N) if m != idx])
        cam = np.array([0.12 * (j - 1), 0.10 * (1 - i), 0.0]) + np.array([0.0, 0.02, 0.0])
        self.beat(FadeIn(ring), FadeIn(ar), FadeIn(ab),
                  others.animate.set_opacity(0.38),
                  others_acc.animate.set_opacity(0.25),
                  self.accs[idx].animate.set_opacity(1.0),
                  row_a.animate.set_color(ORANGE),
                  col_b.animate.set_color(BLUE),
                  self.camera.frame.animate.move_to(cam),
                  run_time=0.55, rate_func=ease_in_out_cubic)

        eq_terms = None
        if with_eq:
            terms = VGroup(
                MathTex(r"C_{%d%d}=" % (i, j), font_size=27, color=INK),
                *[MathTex(r"+\,{%d}{\cdot}%d" % (int(A[i, k]), int(B[k, j])),
                          font_size=27, color=MUTED) for k in range(N)],
                MathTex(r"=\,{%d}" % int(C[i, j]), font_size=27, color=TEAL),
            ).arrange(RIGHT, buff=0.11).move_to([-4.45, -3.48, 0.0])
            eq_panel = BackgroundRectangle(terms, color=SURFACE, fill_opacity=0.85,
                                           stroke_width=1, stroke_color=DIVIDER,
                                           stroke_opacity=0.9, buff=0.13)
            self.beat(FadeIn(eq_panel), Write(terms[0]), run_time=0.45)
            eq_terms = (eq_panel, terms)

        running = 0
        for k in range(N):
            ca = chip(int(A[i, k]), ORANGE)
            ca.move_to(center + np.array([-HS - 0.22, -0.16, 0.0]))
            cb = chip(int(B[k, j]), BLUE)
            cb.move_to(center + np.array([-0.16, HS + 0.22, 0.0]))
            # A chip streams in from the left; B chip follows ~0.12 s later
            self.beat(FadeIn(ca, shift=RIGHT * 0.08),
                      *[eq_terms[1][k + 1].animate.set_color(INK)] if eq_terms else [],
                      run_time=0.26)
            self.beat(FadeIn(cb, shift=DOWN * 0.08),
                      ca.animate.move_to(center + np.array([-HS + 0.34, -0.16, 0.0])),
                      run_time=0.30)
            running += int(A[i, k]) * int(B[k, j])
            acc_new = Text(str(running), font="Arial", font_size=32, color=INK,
                           weight="BOLD").move_to(self.accs[idx].get_center())
            self.beat(cb.animate.move_to(center + np.array([-0.16, HS - 0.30, 0.0])),
                      FadeOut(ca, scale=0.7),
                      Transform(self.accs[idx], acc_new),
                      run_time=0.32)
            self.beat(FadeOut(cb, scale=0.7), run_time=0.12)

        final = Text(str(int(C[i, j])), font="Arial", font_size=36, color=TEAL,
                     weight="BOLD").move_to(self.accs[idx].get_center())
        self.beat(Transform(self.accs[idx], final),
                  FadeOut(ring), FadeOut(ar), FadeOut(ab),
                  run_time=0.45, rate_func=ease_in_out_cubic)
        if eq_terms:
            # reveal the result term of the card, hold it, then release
            self.beat(FadeIn(eq_terms[1][4], shift=RIGHT * 0.05), run_time=0.45)
            self.beat(FadeOut(eq_terms[0]), FadeOut(eq_terms[1]), run_time=0.3)

    # ------------------------------------------------------------ plumbing
    def beat(self, *anims, run_time: float = 1.0, rate_func=smooth) -> None:
        if anims:
            self.play(*anims, run_time=run_time, rate_func=rate_func)
        else:
            self.wait(run_time)
        self.clock += run_time
