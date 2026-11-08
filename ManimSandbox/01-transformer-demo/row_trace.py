from __future__ import annotations

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Arrow,
    Create,
    FadeIn,
    Line,
    Rectangle,
    Scene,
    Text,
    VGroup,
    config,
)

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.scene_checks import enforce
from common.design_system import BG, BLUE, INK, MUTED, ORANGE, PURPLE, TEAL  # noqa: E402

config.background_color = BG

TEXT = INK


def label(value: str, size: int = 36, color: str = TEXT) -> Text:
    return Text(value, font="Arial", font_size=size, color=color)


def matrix_box(name: str, size: float = 2.1) -> VGroup:
    outer = Rectangle(width=size, height=size, stroke_color=MUTED, stroke_width=3)
    grid = VGroup()
    for step in (1, 2, 3):
        dx = -size / 2 + step * size / 4
        dy = size / 2 - step * size / 4
        grid.add(
            Line(
                outer.get_center() + UP * (size / 2) + RIGHT * dx,
                outer.get_center() + DOWN * (size / 2) + RIGHT * dx,
                stroke_width=1.5,
                color=MUTED,
            )
        )
        grid.add(
            Line(
                outer.get_center() + LEFT * (size / 2) + UP * dy,
                outer.get_center() + RIGHT * (size / 2) + UP * dy,
                stroke_width=1.5,
                color=MUTED,
            )
        )
    caption = label(name, 30).next_to(outer, DOWN, buff=0.25)
    return VGroup(outer, grid, caption)


class RowTraceScene(Scene):
    """X · W_Q = Q preserves row order; the same holds for K and V."""

    def construct(self) -> None:
        title = label("One matmul per projection", 52).to_edge(UP, buff=0.6)
        self.play(FadeIn(title), run_time=0.5)

        x = matrix_box("X").shift(LEFT * 5.0 + DOWN * 0.2)
        w = matrix_box("W_Q").shift(LEFT * 1.0 + DOWN * 0.2)
        q = matrix_box("Q").shift(RIGHT * 3.0 + DOWN * 0.2)
        for box in (x, w, q):
            self.play(Create(box[0]), FadeIn(box[2]), run_time=0.5)
            self.play(Create(box[1]), run_time=0.4)

        sign1 = label("×", 44, MUTED).move_to((x.get_right() + w.get_left()) / 2)
        sign2 = label("=", 44, MUTED).move_to((w.get_right() + q.get_left()) / 2)
        self.play(FadeIn(sign1), FadeIn(sign2), run_time=0.4)

        row_bar = Rectangle(
            width=2.1, height=2.1 / 4, stroke_width=0, fill_color=ORANGE, fill_opacity=0.35,
        )
        row_bar.move_to(x[0].get_top() + DOWN * (2.1 / 8), aligned_edge=UP)
        self.play(FadeIn(row_bar), run_time=0.4)
        self.play(
            row_bar.animate.move_to(q[0].get_top() + DOWN * (2.1 / 8), aligned_edge=UP),
            run_time=1.4,
        )

        note = VGroup(
            label("row i of X  →  row i of Q", 30, MUTED),
            label("the weights change the representation, not the order", 26, MUTED),
        ).arrange(DOWN, buff=0.2).to_edge(DOWN, buff=0.62)
        self.play(FadeIn(note), run_time=0.6)
        self.wait(2.0)
        enforce(self)
