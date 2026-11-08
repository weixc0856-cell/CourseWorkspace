"""90-second vector visual-direction slice.

Design intent lives in direction.json; this file is the renderer. The camera,
composition, motion order and on-screen text follow that direction rather than
a slide deck.
"""
from __future__ import annotations

import numpy as np
from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Angle,
    Arrow,
    BackgroundRectangle,
    Create,
    DashedLine,
    Dot,
    FadeIn,
    FadeOut,
    GrowArrow,
    Line,
    MathTex,
    MovingCameraScene,
    NumberPlane,
    Text,
    Transform,
    VGroup,
    Write,
    config,
)

config.background_color = "#FFFFFF"

INK = "#14213D"
MUTED = "#5C677D"
ACCENT = "#0077B6"
WARM = "#E76F51"
GREEN = "#2A9D8F"


def p(x: float, y: float) -> np.ndarray:
    return np.array([x, y, 0.0])


def m(tex: str, size: int = 34, color: str = INK) -> MathTex:
    return MathTex(tex, font_size=size, color=color)


def panel(content, buff: float = 0.12):
    return VGroup(
        BackgroundRectangle(content, color="#FFFFFF", fill_opacity=1.0, buff=buff),
        content,
    )


class VectorDirectionScene(MovingCameraScene):
    def construct(self) -> None:
        # --- s1: establish a vector as displacement -------------------------
        grid = NumberPlane(
            x_range=[-8, 8, 1],
            y_range=[-5, 5, 1],
            background_line_style={"stroke_opacity": 0.07, "stroke_width": 1},
            axis_config={"stroke_opacity": 0.35, "stroke_width": 2},
        )
        x_label = m("x", 28, MUTED).move_to(p(7.6, -0.35))
        y_label = m("y", 28, MUTED).move_to(p(-0.35, 4.7))
        title = Text("Vectors, visually", font="Arial", font_size=30, color=MUTED).move_to(p(-5.7, 4.2))
        self.camera.frame.set_width(16)
        self.play(FadeIn(grid), FadeIn(x_label), FadeIn(y_label), run_time=1.0)
        self.play(FadeIn(title), run_time=0.5)
        self.wait(4.0)

        origin = p(0, 0)
        a_end = p(3, 2)
        a_arrow = Arrow(origin, a_end, buff=0, color=ACCENT, stroke_width=6, max_tip_length_to_length_ratio=0.10)
        a_label = m(r"\mathbf a", 34, ACCENT).move_to(p(3.35, 1.2))
        self.play(GrowArrow(a_arrow), FadeIn(a_label), run_time=1.6)
        self.play(
            self.camera.frame.animate.set_width(13).move_to(p(0.8, 1.2)),
            run_time=2.4,
        )
        self.play(self.camera.frame.animate.shift(RIGHT * 0.25), run_time=5.0)
        self.wait(2.0)

        # --- s2: components and magnitude ----------------------------------
        self.play(FadeOut(title), run_time=0.4)
        dx = DashedLine(origin, p(3, 0), color=MUTED, stroke_width=2)
        dy = DashedLine(p(3, 0), a_end, color=MUTED, stroke_width=2)
        x3 = m("3", 28, WARM).next_to(Line(origin, p(3, 0)), DOWN, buff=0.16)
        y2 = m("2", 28, WARM).next_to(Line(p(3, 0), a_end), RIGHT, buff=0.16)
        self.play(Create(dx), Create(dy), run_time=0.8)
        self.play(FadeIn(x3), FadeIn(y2), run_time=0.5)

        comp = panel(m(r"\mathbf a=(3,2)", 32, ACCENT).move_to(p(3.6, 3.2)))
        mag = panel(m(r"|\mathbf a|=\sqrt{3^2+2^2}=\sqrt{13}", 28, INK).move_to(p(3.2, 2.45)))
        self.play(FadeIn(comp), run_time=0.7)
        self.play(FadeIn(mag), run_time=0.7)
        self.play(a_arrow.animate.set_color(GREEN), run_time=0.8)
        self.play(a_arrow.animate.set_color(ACCENT), run_time=0.8)
        self.play(self.camera.frame.animate.shift(LEFT * 0.2), run_time=6.0)
        self.wait(3.0)

        # --- s3: addition as a spatial action ------------------------------
        self.play(FadeOut(comp), FadeOut(mag), FadeOut(x3), FadeOut(y2), FadeOut(dx), FadeOut(dy), run_time=0.5)
        b_end = p(1, 3)
        b_arrow = Arrow(origin, b_end, buff=0, color=WARM, stroke_width=5, max_tip_length_to_length_ratio=0.12)
        b_label = m(r"\mathbf b", 30, WARM).next_to(b_end, LEFT, buff=0.16)
        self.play(GrowArrow(b_arrow), FadeIn(b_label), run_time=1.1)

        # The actual move: a copy of b travels from the origin to a's tip.
        b_clone = b_arrow.copy()
        self.play(b_clone.animate.shift(a_end), run_time=1.4)
        self.wait(0.6)

        result_end = p(4, 5)
        result = Arrow(origin, result_end, buff=0, color=GREEN, stroke_width=6, max_tip_length_to_length_ratio=0.09)
        result_label = panel(m(r"\mathbf a+\mathbf b=(4,5)", 26, GREEN).move_to(p(5.7, 4.4)))
        self.play(GrowArrow(result), FadeIn(result_label), run_time=1.2)
        para1 = DashedLine(b_end, result_end, color=MUTED, stroke_width=1.5)
        para2 = DashedLine(a_end, result_end, color=MUTED, stroke_width=1.5)
        self.play(Create(para1), Create(para2), run_time=0.8)
        self.play(
            self.camera.frame.animate.set_width(15).move_to(p(1.6, 1.6)),
            run_time=1.6,
        )
        sum_formula = panel(m(r"\mathbf a+\mathbf b=(3+1,\,2+3)", 24, INK).move_to(p(4.8, 0.5)))
        swap_formula = panel(m(r"\mathbf b+\mathbf a=\mathbf a+\mathbf b", 24, GREEN).move_to(p(4.8, -0.2)))
        self.play(FadeIn(sum_formula), run_time=0.6)
        self.play(FadeIn(swap_formula), run_time=0.6)
        self.play(self.camera.frame.animate.shift(RIGHT * 0.3), run_time=6.0)
        self.wait(3.0)

        # --- s4: scalar multiplication as continuous stretch/flip ----------
        self.play(
            FadeOut(b_arrow), FadeOut(b_label), FadeOut(b_clone),
            FadeOut(result), FadeOut(result_label), FadeOut(para1), FadeOut(para2),
            FadeOut(sum_formula), FadeOut(swap_formula), run_time=0.6,
        )
        self.play(self.camera.frame.animate.set_width(18).move_to(p(0, 0)), run_time=1.2)
        a2 = Arrow(origin, p(6, 4), buff=0, color=GREEN, stroke_width=6, max_tip_length_to_length_ratio=0.08)
        a2_label = m(r"2\mathbf a", 30, GREEN).next_to(p(6, 4), RIGHT, buff=0.16)
        self.play(Transform(a_arrow, a2), Transform(a_label, a2_label), run_time=1.8)
        self.wait(1.0)

        a_neg = Arrow(origin, p(-3, -2), buff=0, color=WARM, stroke_width=6, max_tip_length_to_length_ratio=0.12)
        a_neg_label = m(r"-\mathbf a", 30, WARM).next_to(p(-3, -2), LEFT, buff=0.16)
        self.play(Transform(a_arrow, a_neg), Transform(a_label, a_neg_label), run_time=1.8)
        scale_formula = panel(m(r"|\lambda\mathbf a|=|\lambda|\,|\mathbf a|", 28, INK).move_to(p(3.0, -3.2)))
        self.play(FadeIn(scale_formula), run_time=0.7)
        self.play(self.camera.frame.animate.shift(LEFT * 0.25), run_time=5.0)
        self.wait(2.0)

        # --- s5: dot product as projection ---------------------------------
        self.play(FadeOut(a_arrow), FadeOut(a_label), FadeOut(scale_formula), run_time=0.5)
        self.play(self.camera.frame.animate.set_width(14).move_to(p(1.0, 0.6)), run_time=1.2)
        a_arrow = Arrow(origin, a_end, buff=0, color=ACCENT, stroke_width=5, max_tip_length_to_length_ratio=0.12)
        b_arrow = Arrow(origin, b_end, buff=0, color=WARM, stroke_width=5, max_tip_length_to_length_ratio=0.12)
        self.play(GrowArrow(a_arrow), GrowArrow(b_arrow), run_time=1.2)

        proj = p(27 / 13, 18 / 13)
        drop = DashedLine(b_end, proj, color=GREEN, stroke_width=2)
        proj_dot = Dot(proj, color=GREEN, radius=0.07)
        proj_line = DashedLine(origin, proj, color=GREEN, stroke_width=3)
        proj_label = m(r"\mathrm{proj}_{\mathbf a}\mathbf b", 20, GREEN).move_to(p(1.5, -0.45))
        self.play(Create(drop), FadeIn(proj_dot), Create(proj_line), FadeIn(proj_label), run_time=1.0)

        angle = Angle(Line(origin, a_end), Line(origin, b_end), radius=0.55, color=GREEN, stroke_width=2)
        theta = m(r"\theta", 26, GREEN).next_to(angle, RIGHT, buff=0.04)
        self.play(Create(angle), FadeIn(theta), run_time=0.7)

        dot_numbers = panel(m(r"3\cdot1+2\cdot3=9", 22, INK).move_to(p(5.7, 3.1)))
        dot_formula = panel(m(r"\mathbf a\cdot\mathbf b=|\mathbf a||\mathbf b|\cos\theta", 26, INK).move_to(p(3.3, 1.55)))
        self.play(FadeIn(dot_numbers), run_time=0.6)
        self.play(FadeIn(dot_formula), run_time=0.7)
        self.play(self.camera.frame.animate.shift(RIGHT * 0.2), run_time=5.0)
        self.wait(2.0)

        # Hold the complete projection picture; a slow camera pull-back is the
        # final motion (no blank tail).
        self.play(self.camera.frame.animate.set_width(16).move_to(p(0.5, 0.5)), run_time=4.0)
        self.wait(11.0)
        self.play(
            FadeOut(dot_numbers), FadeOut(dot_formula), FadeOut(proj_label),
            FadeOut(theta), FadeOut(angle), FadeOut(grid), FadeOut(x_label), FadeOut(y_label),
            FadeOut(a_arrow), FadeOut(b_arrow), FadeOut(drop), FadeOut(proj_dot),
            FadeOut(proj_line), run_time=0.4,
        )
