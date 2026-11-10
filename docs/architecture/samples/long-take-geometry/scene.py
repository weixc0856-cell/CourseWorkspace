"""Validation sample 1: long-take geometric evolution (Manim).

8 s, one shot, continuous transformation of k; q fixed. One motivated camera
push. No cuts, no randomness, no wall-clock state.
"""
from __future__ import annotations

import numpy as np
from manim import (
    DOWN,
    RIGHT,
    UP,
    Arc,
    Create,
    DashedLine,
    Dot,
    FadeIn,
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


class LongTakeGeometry(MovingCameraScene):
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

        title = Text("注意力先把词变成方向", font="Microsoft YaHei", color=INK, font_size=44)
        title.to_edge(UP, buff=0.45)
        self.add(title)

        origin = np.array(plane.c2p(0, 0))
        q_angle = np.deg2rad(48)
        q_tip = np.array(plane.c2p(5.2 * np.cos(q_angle), 5.2 * np.sin(q_angle)))
        k_angle = ValueTracker(np.deg2rad(12))

        def k_tip() -> np.ndarray:
            a = k_angle.get_value()
            return np.array(plane.c2p(4.8 * np.cos(a), 4.8 * np.sin(a)))

        q_arrow = Line(origin, q_tip, color=TEAL, stroke_width=7)
        q_dot = Dot(q_tip, color=TEAL, radius=0.09)
        q_label = Text("q", font="Microsoft YaHei", color=TEAL, font_size=40)
        q_label.next_to(q_dot, UP, buff=0.18)

        k_arrow = always_redraw(lambda: Line(origin, k_tip(), color=ACCENT, stroke_width=7))
        k_dot = always_redraw(lambda: Dot(k_tip(), color=ACCENT, radius=0.09))
        k_label = always_redraw(
            lambda: Text("k", font="Microsoft YaHei", color=ACCENT, font_size=40).next_to(
                k_tip(), RIGHT, buff=0.18
            )
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
        formula.to_corner(DOWN + RIGHT, buff=0.55)

        self.play(Create(q_arrow), FadeIn(q_dot, q_label), run_time=0.9)
        self.play(Create(k_arrow), FadeIn(k_dot, k_label), run_time=0.9)
        self.play(Create(arc), Create(proj), run_time=0.7)
        self.play(FadeIn(formula), run_time=0.6)

        # One motivated camera push: the angle opens; the frame follows it.
        self.play(
            self.camera.frame.animate.scale(0.78).move_to(plane.c2p(1.1, 1.0)),
            run_time=2.2,
        )
        self.play(
            k_angle.animate.set_value(np.deg2rad(68)),
            run_time=3.0,
            rate_func=lambda t: t,
        )
        self.wait(0.5)
