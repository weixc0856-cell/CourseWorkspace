"""Act 2 — Serial vs parallel: why a GPU is fast (centered two-panel act).

Composition: centered masthead; two EQUAL panels mirrored about x=0 with
section labels above each and content rows on shared baselines inside each;
below both, a centered two-row quantitative convergence and one centered
conclusion + caption. ORANGE = the single active element (serial unit, and
the array's current wavefront ring), TEAL = the result family, MUTED =
inactive paper, ink = text.

Truth model (one shared cycle clock; 27 cycles = the whole race):
- serial: one dot-product unit. Each of the 9 outputs needs 3 multiply-
  accumulate cycles -> the product takes 27 MAC cycles.
- systolic: 9 cells wired as a 3x3 array. Cell (i,j) starts at cycle
  max(i,j)+1 and finishes 3 cycles later -> array done at cycle 2*3-1 = 5.
- 27 / 5 = 5.4x. Every number on screen is computed from numpy.

Render (from ManimSandbox, in a subshell):
  uv run manim render -r 1920,1080 --fps 30 \
    --media_dir <content_root>/build/_shared/centered-compute/media \
    09-centered-compute/act2.py Act2
"""
from __future__ import annotations

import numpy as np

from layout import (A, B, C, N, ORANGE, BLUE, TEAL, INK, MUTED, DIVIDER,
                    SURFACE, BG, MACS, WAVE_STEPS, SERIAL_STEPS, txt, caps,
                    panel)

from manim import (
    DOWN, RIGHT, FadeIn, FadeOut, MathTex, MovingCameraScene, RoundedRectangle,
    Transform, VGroup, config,
)
from manim.utils.rate_functions import ease_in_out_cubic

config.background_color = BG

# --------------------------------------------------------------- composition
EYEBROW_Y, TITLE_Y = 3.16, 2.59
HEAD_Y = 1.92
PANEL_W, PANEL_H, PANEL_Y = 5.3, 2.75, 0.255
PANEL_L, PANEL_R = -2.85, 2.85

BOX_W, BOX_H, BOX_Y = 3.0, 0.88, 0.62            # serial MAC unit
PX2, SX2 = 0.52, 0.46                             # mini-grid pitch / cell
GRID_C = np.array([PANEL_R, 0.74, 0.0])

CYCLE_Y, CNT_Y = -0.34, -0.86
STAT_Y, STATLBL_Y = -1.62, -2.12
CONCL_Y, CAP_Y = -2.62, -3.08


def mcell(i: int, j: int) -> np.ndarray:
    return GRID_C + np.array([(j - 1) * PX2, (1 - i) * PX2, 0.0])


class Act2(MovingCameraScene):
    def construct(self) -> None:
        self.clock = 0.0
        self.rings = VGroup()
        self.camera.frame.set_width(14.2222).move_to([0.0, 0.0, 0.0])

        # ------------------------------------------------------------- masthead
        eyebrow = caps("SERIAL  VS  PARALLEL").move_to([0, EYEBROW_Y, 0])
        title = txt("Why a GPU is fast", 54, INK, "BOLD") \
            .move_to([0, TITLE_Y, 0])

        # --------------------------------------------------------------- panels
        p_l = panel(PANEL_W, PANEL_H, PANEL_L, PANEL_Y)
        p_r = panel(PANEL_W, PANEL_H, PANEL_R, PANEL_Y)
        head_l = txt("SERIAL · ONE UNIT", 28, MUTED, "BOLD") \
            .move_to([PANEL_L, HEAD_Y, 0])
        head_r = txt("SYSTOLIC · 3×3 GRID", 28, MUTED, "BOLD") \
            .move_to([PANEL_R, HEAD_Y, 0])

        self.mbox = RoundedRectangle(corner_radius=0.12, width=BOX_W,
                                     height=BOX_H, stroke_color=MUTED,
                                     stroke_width=3, fill_color=SURFACE,
                                     fill_opacity=0.8).move_to(
            [PANEL_L, BOX_Y, 0])
        self.meq = MathTex(r"C_{ij} \;=\; \cdot", font_size=40, color=INK)
        self.meq.move_to(self.mbox.get_center())

        self.mbodies, self.maccs = VGroup(), VGroup()
        for i in range(N):
            for j in range(N):
                body = RoundedRectangle(corner_radius=0.07, width=SX2,
                                        height=SX2, stroke_color=DIVIDER,
                                        stroke_width=2)
                body.set_fill(SURFACE, 0.5).move_to(mcell(i, j))
                ghost = txt("·", 26, MUTED).set_opacity(0.5) \
                    .move_to(mcell(i, j))
                self.mbodies.add(body)
                self.maccs.add(ghost)

        # cycle rows + big counters on shared baselines
        self.cyc_l = txt("cycle 0 / %d" % MACS, 26, MUTED) \
            .move_to([PANEL_L, CYCLE_Y, 0])
        self.cyc_r = txt("cycle 0 / %d" % WAVE_STEPS, 26, MUTED) \
            .move_to([PANEL_R, CYCLE_Y, 0])
        self.n_l = txt("0", 44, INK, "BOLD").move_to([PANEL_L - 0.28, CNT_Y, 0])
        self.n_l_tot = txt("/ %d" % SERIAL_STEPS, 30, MUTED) \
            .move_to([PANEL_L + 0.22, CNT_Y, 0])
        self.n_r = txt("0", 44, INK, "BOLD").move_to([PANEL_R - 0.28, CNT_Y, 0])
        self.n_r_tot = txt("/ %d" % WAVE_STEPS, 30, MUTED) \
            .move_to([PANEL_R + 0.22, CNT_Y, 0])

        # ------------------------------------------------ convergence + outro
        stat_l = self.stat_block(PANEL_L, "%d" % MACS, "serial MAC cycles",
                                 INK)
        stat_r = self.stat_block(PANEL_R, "%d" % WAVE_STEPS,
                                 "wavefront cycles", TEAL)
        concl = self.conclusion()
        caption = txt("one shared clock · 9 dot-products × 3 MACs = 27 "
                      "· array done in 3 + 3 − 1 = 5", 24, MUTED) \
            .move_to([0, CAP_Y, 0])

        # -------------------------------------------------------------- beats
        self.beat(FadeIn(eyebrow), FadeIn(title, shift=DOWN * 0.06),
                  run_time=1.0)
        self.beat(FadeIn(p_l), FadeIn(p_r), FadeIn(head_l), FadeIn(head_r),
                  run_time=0.8)
        self.beat(FadeIn(self.mbox), FadeIn(self.meq),
                  FadeIn(self.mbodies), FadeIn(self.maccs), run_time=0.7)
        self.beat(FadeIn(self.cyc_l), FadeIn(self.cyc_r),
                  FadeIn(self.n_l), FadeIn(self.n_l_tot),
                  FadeIn(self.n_r), FadeIn(self.n_r_tot), run_time=0.6)
        self.beat(run_time=0.7)

        # --------------------------------------------------- race: 27 cycles
        cur_dp = -1
        for cyc in range(1, MACS + 1):
            anims = [self.morph(self.cyc_l, "cycle %d / %d" % (cyc, MACS), 26)]
            if cyc % 3 == 0:
                cur_dp += 1
                i, j = divmod(cur_dp, N)
                parts = sum(int(A[i, k]) * int(B[k, j]) for k in range(N))
                assert parts == int(C[i, j])
                new = MathTex(r"C_{%d%d} \;=\; %d" % (i, j, parts),
                              font_size=40, color=INK).move_to(
                    self.mbox.get_center())
                anims.append(Transform(self.meq, new))
                anims.append(self.morph(self.n_l, "%d" % (cur_dp + 1), 44,
                                        INK, "BOLD"))
            if cyc <= WAVE_STEPS:
                anims.append(self.morph(self.cyc_r,
                                        "cycle %d / %d" % (cyc, WAVE_STEPS), 26))
                anims += self.wave_beat(cyc)
                anims.append(self.morph(self.n_r, "%d" % cyc, 44, INK, "BOLD"))
            self.beat(*anims, run_time=0.35)

        # both panels settled: array idle since cycle 5, serial now done
        self.beat(*self.stamp_done(), run_time=0.45)
        self.beat(run_time=0.5)

        # ------------------------------------------------------ convergence
        self.beat(FadeIn(stat_l, shift=DOWN * 0.06), run_time=0.55)
        self.beat(FadeIn(stat_r, shift=DOWN * 0.06), FadeIn(concl),
                  run_time=0.75)
        self.beat(FadeIn(caption), run_time=0.5)

        # -------------------------------------------------------------- outro
        self.beat(run_time=0.8)
        self.beat(concl.animate.scale(1.06), run_time=0.6)
        self.beat(run_time=max(0.0, 22.0 - self.clock))
        print(f"Act2 clock {self.clock:.2f}s cycles={MACS} waves={WAVE_STEPS}")

    # ----------------------------------------------------------------- pieces
    def stat_block(self, x: float, num: str, label: str,
                   color: str) -> VGroup:
        n = txt(num, 52, color, "BOLD").move_to([x, STAT_Y, 0])
        lb = txt(label.upper(), 24, MUTED).move_to([x, STATLBL_Y, 0])
        return VGroup(n, lb)

    def conclusion(self) -> VGroup:
        rate = MACS / WAVE_STEPS                     # 27/5 = 5.4
        pre = txt("the same %d multiply-accumulates," % MACS, 34, INK)
        mid = txt("%g× fewer cycles" % rate, 34, TEAL, "BOLD")
        return VGroup(pre, mid).arrange(RIGHT, buff=0.16).move_to(
            [0, CONCL_Y, 0])

    def wave_beat(self, cyc: int):
        """Ring cells that START this cycle; teal cells that FINISH it."""
        anims = []
        starting = [(i, j) for i in range(N) for j in range(N)
                    if max(i, j) + 1 == cyc]
        finishing = [(i, j) for i in range(N) for j in range(N)
                     if max(i, j) + 3 == cyc]
        new_rings = VGroup()
        for (i, j) in starting:
            r = RoundedRectangle(corner_radius=0.08, width=SX2 + 0.09,
                                 height=SX2 + 0.09, stroke_color=ORANGE,
                                 stroke_width=3.5, fill_color=ORANGE,
                                 fill_opacity=0.07).move_to(mcell(i, j))
            new_rings.add(r)
            idx = i * N + j
            anims.append(self.mbodies[idx].animate.set_fill(ORANGE, 0.10))
        anims.append(FadeOut(self.rings))
        anims.append(FadeIn(new_rings))
        self.rings = new_rings
        for (i, j) in finishing:
            idx = i * N + j
            val = txt(str(int(C[i, j])), 28, TEAL, "BOLD") \
                .move_to(self.maccs[idx].get_center())
            anims.append(Transform(self.maccs[idx], val))
            anims.append(self.mbodies[idx].animate.set_fill(TEAL, 0.14))
        return anims

    def stamp_done(self):
        stamp = txt("ARRAY DONE · CYCLE 5", 24, TEAL, "BOLD")
        box = RoundedRectangle(corner_radius=0.09, width=stamp.width + 0.34,
                               height=stamp.height + 0.20, stroke_color=TEAL,
                               stroke_width=2.5, fill_color=BG,
                               fill_opacity=0.95)
        stamp.move_to([PANEL_R, CYCLE_Y, 0])
        box.move_to(stamp.get_center())
        self.done = VGroup(box, stamp)
        return [FadeOut(self.cyc_r), FadeIn(self.done)]

    def morph(self, target, s: str, size: int, color=INK,
              weight="NORMAL"):
        new = txt(s, size, color, weight).move_to(target.get_center())
        return Transform(target, new)

    def beat(self, *anims, run_time: float = 1.0,
             rate_func=ease_in_out_cubic) -> None:
        if anims:
            self.play(*anims, run_time=run_time, rate_func=rate_func)
        else:
            self.wait(run_time)
        self.clock += run_time
