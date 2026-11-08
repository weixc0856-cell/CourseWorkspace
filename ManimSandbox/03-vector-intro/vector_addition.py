"""80-second vector-addition slice.

Visual direction: direction-addition.json. Dark grid, one spatial move per beat,
no slide chrome. No audio.
"""
from __future__ import annotations

import numpy as np
from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
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
    config,
)

config.background_color = "#0B1220"

BG = "#0B1220"
INK = "#E8EEF7"
MUTED = "#8494A8"
A = "#4CC2FF"
B = "#FF8A5B"
RESULT = "#5BE3B0"


def p(x: float, y: float) -> np.ndarray:
    return np.array([x, y, 0.0])


def m(tex: str, size: int = 34, color: str = INK) -> MathTex:
    return MathTex(tex, font_size=size, color=color)


def card(content, buff: float = 0.14):
    return VGroup(
        BackgroundRectangle(
            content,
            color=BG,
            fill_opacity=0.94,
            stroke_color=MUTED,
            stroke_width=0.6,
            buff=buff,
        ),
        content,
    )


class VectorAdditionScene(MovingCameraScene):
    def construct(self) -> None:
        grid = NumberPlane(
            x_range=[-8, 8, 1],
            y_range=[-5, 5, 1],
            background_line_style={"stroke_color": MUTED, "stroke_opacity": 0.16, "stroke_width": 1},
            axis_config={"stroke_color": MUTED, "stroke_opacity": 0.55, "stroke_width": 2},
        )
        self.camera.frame.set_width(16).move_to(p(1.0, 1.0))
        self.play(FadeIn(grid), run_time=1.0)
        self.wait(2.0)

        kicker = Text("Vector addition", font="Arial", font_size=24, color=MUTED).move_to(p(-6.2, 4.15))
        self.play(FadeIn(kicker), run_time=0.5)

        origin = p(0, 0)
        a_end = p(3, 2)
        b_end = p(1, 3)

        a_arrow = Arrow(origin, a_end, buff=0, color=A, stroke_width=6, max_tip_length_to_length_ratio=0.10)
        b_arrow = Arrow(origin, b_end, buff=0, color=B, stroke_width=6, max_tip_length_to_length_ratio=0.12)
        a_label = m(r"\mathbf a", 32, A).move_to(p(3.35, 1.25))
        b_label = m(r"\mathbf b", 30, B).move_to(p(0.55, 3.2))
        self.play(GrowArrow(a_arrow), FadeIn(a_label), run_time=1.4)
        self.play(GrowArrow(b_arrow), FadeIn(b_label), run_time=1.4)
        self.play(self.camera.frame.animate.set_width(14).move_to(p(1.0, 1.2)), run_time=6.0)
        self.play(FadeOut(kicker), run_time=0.4)
        self.wait(7.6)

        # s2: b's tail travels to a's tip
        b_clone = b_arrow.copy()
        trail_dot = Dot(origin, color=B, radius=0.055)
        trail = DashedLine(origin, origin, color=B, stroke_width=2)
        self.play(FadeIn(trail_dot), run_time=0.3)
        self.play(
            b_clone.animate.shift(a_end - origin),
            trail_dot.animate.shift(a_end - origin),
            run_time=2.6,
        )
        self.play(
            self.camera.frame.animate.set_width(15).move_to(p(1.6, 1.5)),
            run_time=2.6,
        )
        moved = card(m(r"\mathbf b\ \text{moved to the tip}", 24, B).move_to(p(5.1, -1.9)))
        self.play(FadeIn(moved), run_time=0.7)
        self.wait(8.0)

        # s3: resultant closes the triangle
        result = Arrow(origin, p(4, 5), buff=0, color=RESULT, stroke_width=7, max_tip_length_to_length_ratio=0.08)
        result_label = card(m(r"\mathbf a+\mathbf b=(4,5)", 26, RESULT).move_to(p(5.1, 0.2)))
        self.play(GrowArrow(result), run_time=1.4)
        self.play(FadeIn(result_label), run_time=0.7)
        para_b = DashedLine(b_end, p(4, 5), color=MUTED, stroke_width=1.5)
        para_a = DashedLine(a_end, p(4, 5), color=MUTED, stroke_width=1.5)
        self.play(Create(para_b), Create(para_a), run_time=0.8)
        components = card(m(r"=(3+1,\ 2+3)", 22, INK).move_to(p(5.1, -0.7)))
        self.play(FadeIn(components), run_time=0.6)
        self.play(self.camera.frame.animate.shift(RIGHT * 0.2), run_time=6.0)
        self.wait(9.0)

        # s4: commutative order — a travels to b's tip
        self.play(
            FadeOut(b_clone), FadeOut(moved), FadeOut(result), FadeOut(result_label),
            FadeOut(components), FadeOut(para_b), FadeOut(para_a), FadeOut(trail_dot),
            run_time=0.6,
        )
        self.play(FadeOut(a_arrow), FadeOut(a_label), run_time=0.4)
        a_clone = Arrow(origin, a_end, buff=0, color=A, stroke_width=6, max_tip_length_to_length_ratio=0.10)
        a_clone.shift(b_end)
        a_clone_label = m(r"\mathbf a", 30, A).move_to(p(4.3, 4.2))
        self.play(GrowArrow(a_clone), FadeIn(a_clone_label), run_time=1.8)
        result2 = Arrow(origin, p(4, 5), buff=0, color=RESULT, stroke_width=7, max_tip_length_to_length_ratio=0.08)
        self.play(GrowArrow(result2), run_time=1.2)
        endpoint = Dot(p(4, 5), color=RESULT, radius=0.10)
        self.play(FadeIn(endpoint), run_time=0.4)
        commute = card(m(r"\mathbf a+\mathbf b=\mathbf b+\mathbf a", 26, RESULT).move_to(p(5.0, 0.5)))
        self.play(FadeIn(commute), run_time=0.7)
        self.play(self.camera.frame.animate.set_width(16).move_to(p(1.2, 1.3)), run_time=4.5)
        self.wait(8.0)

        # s5: hold the finished triangle
        self.play(self.camera.frame.animate.set_width(16.5).move_to(p(1.0, 1.2)), run_time=5.0)
        self.wait(6.0)
