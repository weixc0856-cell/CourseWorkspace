"""06-attention-sample · shot 2: query/key geometry (long_take).

15 s, one continuous shot. q fixed, k rotates from 12° to 68°; the angle arc and
the projection are recomputed from the vectors, not keyframed by hand. One
motivated camera push. No cuts, no randomness.
"""
from __future__ import annotations

import numpy as np
from manim import (
    DOWN,
    LEFT,
    UP,
    RIGHT,
    UP,
    Arc,
    Create,
    DashedLine,
    Dot,
    FadeIn,
    FadeOut,
    Line,
    MathTex,
    MovingCameraScene,
    NumberPlane,
    Text,
    ValueTracker,
    config,
    always_redraw,
)

config.background_color = "#F6F1E7"

INK = "#1D1B17"
MUTED = "#7C756B"
ACCENT = "#D97757"
TEAL = "#4C7A6A"
GRID = "#D9D1C3"


class AttentionGeometry(MovingCameraScene):
    def construct(self) -> None:
        plane = NumberPlane(
            x_range=(-7, 7, 1),
            y_range=(-4, 4, 1),
            background_line_style={
                "stroke_color": GRID,
                "stroke_width": 1,
                "stroke_opacity": 0.55,
            },
            axis_config={"stroke_color": GRID, "stroke_width": 2},
        )
        self.add(plane)

        title = Text("一个词，就是一个方向（二维示意）", font="Microsoft YaHei", color=INK, font_size=36)
        title.to_corner(UP + LEFT, buff=0.8)
        self.add(title)

        origin = np.array(plane.c2p(0, 0))
        q_angle = np.deg2rad(48)
        q_tip = np.array(plane.c2p(4.8 * np.cos(q_angle), 4.8 * np.sin(q_angle)))
        k_angle = ValueTracker(np.deg2rad(12))

        def k_tip() -> np.ndarray:
            a = k_angle.get_value()
            return np.array(plane.c2p(4.6 * np.cos(a), 4.6 * np.sin(a)))

        q_arrow = Line(origin, q_tip, color=TEAL, stroke_width=7)
        q_dot = Dot(q_tip, color=TEAL, radius=0.09)
        q_label = Text("查询 q", font="Microsoft YaHei", color=TEAL, font_size=34)
        q_label.next_to(q_dot, LEFT, buff=0.2)

        k_arrow = always_redraw(lambda: Line(origin, k_tip(), color=ACCENT, stroke_width=7))
        k_dot = always_redraw(lambda: Dot(k_tip(), color=ACCENT, radius=0.09))
        k_label = always_redraw(
            lambda: Text("键 k", font="Microsoft YaHei", color=ACCENT, font_size=34)
            .next_to(k_tip(), RIGHT, buff=0.18)
        )

        def projection() -> DashedLine:
            tip = k_tip()
            unit = tip / np.linalg.norm(tip)
            foot = origin + unit * np.dot(q_tip - origin, unit)
            return DashedLine(q_tip, foot, color=MUTED, stroke_width=2, dash_length=0.12)

        proj = always_redraw(projection)

        def angle_arc() -> Arc:
            low, high = sorted((q_angle, k_angle.get_value()))
            return Arc(
                radius=1.05,
                start_angle=low,
                angle=high - low,
                arc_center=origin,
                color=INK,
                stroke_width=3,
            )

        arc = always_redraw(angle_arc)

        formula = MathTex(
            r"\vec{q}\cdot\vec{k}=|\vec{q}|\,|\vec{k}|\cos\theta", color=INK, font_size=64
        )
        formula.scale(0.75)
        formula.move_to(plane.c2p(-2.2, -0.9))

        self.play(Create(q_arrow), FadeIn(q_dot, q_label), run_time=1.2)
        self.play(Create(k_arrow), FadeIn(k_dot, k_label), run_time=1.2)
        self.play(Create(arc), Create(proj), run_time=0.8)
        self.play(FadeIn(formula), run_time=0.8)
        self.play(
            FadeOut(title),
            self.camera.frame.animate.scale(0.90).move_to(plane.c2p(1.0, 0.9)),
            run_time=2.2,
        )
        self.play(
            k_angle.animate.set_value(np.deg2rad(68)),
            run_time=7.0,
            rate_func=lambda t: t,
        )
        self.wait(1.8)
