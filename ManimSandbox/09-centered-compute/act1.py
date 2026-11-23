"""Act 1 — How a chip multiplies matrices (centered systolic-array redesign).

Composition: one symmetric cross lockup on a shared grid — B matrix floats
above the array (columns aligned to the array columns), A matrix card at left,
C result card at right (rows aligned to the array rows), PE grid centered on
the frame axis; centered masthead (eyebrow + title) on top; hero equation
C = A B and caption centered below. Everything is axis-symmetric about x=0;
static full-frame composition so the 96 px safe margin holds every frame.
BLUE = input family, ORANGE = the single active element, TEAL = results,
MUTED = inactive. Every number comes from numpy.

Dataflow truth: output-stationary. Cell (i,j) accumulates its 3-term dot
product over 3 MAC rounds; start skew is max(i,j), so the array finishes in
N + (N-1) = 5 wavefront cycles and C drains in readiness order (3 waves).

Render (from ManimSandbox, in a subshell):
  uv run manim render -r 1920,1080 --fps 30 \
    --media_dir <content_root>/build/_shared/centered-compute/media \
    09-centered-compute/act1.py Act1
"""
from __future__ import annotations

import numpy as np

from layout import (A, B, C, N, ORANGE, BLUE, TEAL, INK, MUTED, DIVIDER,
                    SURFACE, BG, txt, caps, panel, chip)

from manim import (
    DOWN, RIGHT, Arrow, FadeIn, FadeOut, MathTex, Scene, RoundedRectangle,
    Transform, VGroup, config,
)
from manim.utils.rate_functions import ease_in_out_cubic

config.background_color = BG

# --------------------------------------------------------------- composition
P, S = 0.90, 0.74                 # PE pitch / cell size (units; 135 px/unit)
HS = S / 2
EDGE = P + HS                     # 1.27 array half-extent
GX, GY = 0.0, -0.60
ROW_Y = [GY + (1 - i) * P for i in range(N)]     # 0.30, -0.60, -1.50
COL_X = [GX + (j - 1) * P for j in range(N)]     # -0.90, 0, 0.90

EYEBROW_Y, TITLE_Y = 3.155, 2.58
B_ROWS = [1.93, 1.51, 1.09]       # k=0 top row; pitch 0.42 (fs 32 clears)

A_CARD_C = -(EDGE + 0.42 + 0.715)          # -2.405
C_CARD_C = -A_CARD_C
CARD_W, CARD_H = 1.43, 2.365
A_PITCH, C_PITCH = 0.48, 0.48
A_XS = [A_CARD_C + (k - 1) * A_PITCH for k in range(N)]
C_XS = [C_CARD_C + (j - 1) * C_PITCH for j in range(N)]
EQ_Y, CAP_Y = -2.29, -2.77

FS_NUM, FS_CAPTION, FS_EQ = 32, 24, 54

CHIP_L = np.array([-(S / 2) - 0.02, -0.03, 0.0])   # chip at cell left edge
CHIP_T = np.array([-0.02, (S / 2) + 0.02, 0.0])    # chip at cell top edge


def cell_c(i: int, j: int) -> np.ndarray:
    return np.array([COL_X[j], ROW_Y[i], 0.0])


class Act1(Scene):
    def construct(self) -> None:
        self.clock = 0.0
        self.ring = None

        # ------------------------------------------------------------ masthead
        eyebrow = caps("SYSTOLIC ARRAY  ·  DATAFLOW").move_to([0, EYEBROW_Y, 0])
        title = txt("How a chip multiplies matrices", 54, INK, "BOLD") \
            .move_to([0, TITLE_Y, 0])

        # -------------------------------------------------------------- array
        self.bodies, self.accs = VGroup(), VGroup()
        for i in range(N):
            for j in range(N):
                body = RoundedRectangle(corner_radius=0.10, width=S, height=S,
                                        stroke_color=DIVIDER, stroke_width=2)
                body.set_fill(SURFACE, 0.5).move_to(cell_c(i, j))
                ghost = txt("0", 34, INK).set_opacity(0.30).move_to(cell_c(i, j))
                self.bodies.add(body)
                self.accs.add(ghost)

        # ------------------------------------------------------------- A / B / C
        self.a_card = panel(CARD_W, CARD_H, A_CARD_C, GY)
        self.c_card = panel(CARD_W, CARD_H, C_CARD_C, GY)

        self.a_nums = VGroup()
        self.a_rows = VGroup(*[VGroup() for _ in range(N)])
        for i in range(N):
            for k in range(N):
                t = txt(str(int(A[i, k])), FS_NUM, BLUE).move_to(
                    [A_XS[k], ROW_Y[i], 0.0])
                self.a_nums.add(t)
                self.a_rows[i].add(t)

        self.b_nums = VGroup()
        self.b_cols = VGroup(*[VGroup() for _ in range(N)])
        for k in range(N):
            for j in range(N):
                t = txt(str(int(B[k, j])), FS_NUM, BLUE).move_to(
                    [COL_X[j], B_ROWS[k], 0.0])
                self.b_nums.add(t)
                self.b_cols[j].add(t)

        self.c_dots = VGroup(*[
            txt("·", 36, MUTED).set_opacity(0.55)
            .move_to([C_XS[j], ROW_Y[i], 0.0])
            for i in range(N) for j in range(N)])
        self.c_vals = VGroup()

        self.arr_a = VGroup(*[
            Arrow([A_CARD_C + CARD_W / 2 + 0.06, ROW_Y[i], 0],
                  [-EDGE - 0.06, ROW_Y[i], 0],
                  buff=0, stroke_width=4, color=BLUE, stroke_opacity=0.75,
                  max_tip_length_to_length_ratio=0.30)
            for i in range(N)])
        self.arr_b = VGroup(*[
            Arrow([COL_X[j], B_ROWS[2] - 0.1725 - 0.02, 0],
                  [COL_X[j], GY + EDGE + 0.04, 0],
                  buff=0, stroke_width=4, color=BLUE, stroke_opacity=0.75,
                  max_tip_length_to_length_ratio=0.35)
            for j in range(N)])
        self.arr_c = VGroup(*[
            Arrow([EDGE + 0.06, ROW_Y[i], 0],
                  [C_CARD_C - CARD_W / 2 - 0.06, ROW_Y[i], 0],
                  buff=0, stroke_width=4, color=TEAL, stroke_opacity=0.0,
                  max_tip_length_to_length_ratio=0.30)
            for i in range(N)])

        eq = MathTex(r"C \;=\; A\,B", font_size=FS_EQ, color=INK)
        eq.set_color_by_tex("A", BLUE).set_color_by_tex("B", BLUE)
        eq.set_color_by_tex("C", TEAL)
        eq.move_to([0, EQ_Y, 0])
        caption = txt("output-stationary — each cell holds its output and "
                      "accumulates it in place", FS_CAPTION, MUTED) \
            .move_to([0, CAP_Y, 0])

        # ------------------------------------------------------------- reveals
        self.beat(FadeIn(eyebrow), FadeIn(title, shift=DOWN * 0.06),
                  run_time=0.9)
        self.beat(FadeIn(self.bodies), FadeIn(self.accs), run_time=0.8)
        self.beat(FadeIn(self.a_card), FadeIn(self.a_nums),
                  FadeIn(self.c_card), FadeIn(self.c_dots), run_time=0.6)
        self.beat(FadeIn(self.b_nums), FadeIn(self.arr_a), FadeIn(self.arr_b),
                  run_time=0.6)
        self.beat(FadeIn(eq), FadeIn(caption), run_time=0.7)
        self.beat(run_time=0.6)

        # ------------------------------------------ spotlight one PE at a time
        self.focus_pe(0, 0, t_chip=0.30, t_out=0.30, t_tick=0.28)
        self.focus_pe(1, 1, t_chip=0.24, t_out=0.24, t_tick=0.24)
        self.focus_pe(2, 2, t_chip=0.20, t_out=0.22, t_tick=0.20)

        # every cell has been doing the same — restore, then finish the six
        self.beat(FadeOut(self.ring),
                  self.bodies.animate.set_opacity(1.0),
                  self.accs.animate.set_opacity(1.0),
                  self.a_nums.animate.set_opacity(1.0),
                  self.b_nums.animate.set_opacity(1.0),
                  run_time=0.45)
        self.beat(run_time=0.5)

        done = {(0, 0), (1, 1), (2, 2)}
        for skew in (1, 2):
            anims = []
            for i in range(N):
                for j in range(N):
                    if max(i, j) == skew and (i, j) not in done:
                        idx = i * N + j
                        new = txt(str(int(C[i, j])), 34, INK) \
                            .move_to(self.accs[idx].get_center())
                        anims.append(Transform(self.accs[idx], new))
            self.beat(*anims, run_time=0.55)
        self.beat(run_time=0.5)

        # ------------------------------------------------- drain, wavefronts
        self.beat(self.arr_c.animate.set_stroke(opacity=0.85), run_time=0.15)
        for skew in (0, 1, 2):
            anims = [FadeOut(self.c_dots)] if skew == 0 else []
            for i in range(N):
                for j in range(N):
                    if max(i, j) != skew:
                        continue
                    idx = i * N + j
                    tgt = np.array([C_XS[j], ROW_Y[i], 0.0])
                    src = self.accs[idx].get_center()
                    val = txt(str(int(C[i, j])), 32, TEAL, "BOLD").move_to(tgt)
                    self.c_vals.add(val)
                    anims.append(FadeIn(val, shift=(tgt - src) * 0.30))
                    anims.append(self.accs[idx].animate.set_opacity(0.20))
                    anims.append(self.bodies[idx].animate.set_opacity(0.20))
            self.beat(*anims, run_time=0.6)

        # --------------------------------------------------------------- outro
        self.beat(run_time=0.7)
        self.beat(eq.animate.scale(1.07),
                  self.c_vals.animate.scale(1.05), run_time=0.6)
        self.beat(run_time=max(0.0, 22.0 - self.clock))
        print(f"Act1 clock {self.clock:.2f}s")

    # --------------------------------------------------------------- spotlight
    def focus_pe(self, i: int, j: int, t_chip: float, t_out: float,
                 t_tick: float) -> None:
        idx = i * N + j
        c = cell_c(i, j)
        ring = RoundedRectangle(corner_radius=0.12, width=S + 0.13,
                                height=S + 0.13, stroke_color=ORANGE,
                                stroke_width=5, fill_color=ORANGE,
                                fill_opacity=0.05).move_to(c)
        others = [m for m in range(N * N) if m != idx]
        dim_cells = VGroup(*[self.bodies[m] for m in others])
        dim_accs = VGroup(*[self.accs[m] for m in others])
        dim_a = VGroup(*[m for r in range(N) if r != i for m in self.a_rows[r]])
        dim_b = VGroup(*[m for cc in range(N) if cc != j
                         for m in self.b_cols[cc]])
        anims = [FadeIn(ring)]
        if self.ring is not None:
            anims.append(FadeOut(self.ring))
        self.beat(*anims,
                  dim_cells.animate.set_opacity(0.30),
                  dim_accs.animate.set_opacity(0.30),
                  dim_a.animate.set_opacity(0.30),
                  dim_b.animate.set_opacity(0.30),
                  run_time=0.35)
        self.ring = ring

        running = 0
        for k in range(N):
            ca = chip(int(A[i, k]), BLUE, size=22, half=0.15)
            ca.move_to(c + CHIP_L)
            cb = chip(int(B[k, j]), BLUE, size=22, half=0.15)
            cb.move_to(c + CHIP_T)
            self.beat(FadeIn(ca, shift=RIGHT * 0.14), run_time=t_chip)
            self.beat(FadeIn(cb, shift=DOWN * 0.14), run_time=t_chip)
            running += int(A[i, k]) * int(B[k, j])
            acc_new = txt(str(running), 34, ORANGE, "BOLD") \
                .move_to(self.accs[idx].get_center())
            self.beat(Transform(self.accs[idx], acc_new), run_time=t_tick)
            self.beat(FadeOut(ca, scale=0.7), FadeOut(cb, scale=0.7),
                      run_time=t_out)

        final = txt(str(int(C[i, j])), 34, TEAL, "BOLD") \
            .move_to(self.accs[idx].get_center())
        self.beat(Transform(self.accs[idx], final), run_time=0.4)

    # ---------------------------------------------------------------- plumbing
    def beat(self, *anims, run_time: float = 1.0) -> None:
        if anims:
            self.play(*anims, run_time=run_time, rate_func=ease_in_out_cubic)
        else:
            self.wait(run_time)
        self.clock += run_time
