from __future__ import annotations

import numpy as np
from manim import (
    DOWN,
    LEFT,
    ORANGE,
    RIGHT,
    UP,
    Arrow,
    Create,
    FadeIn,
    LaggedStart,
    ParametricFunction,
    Rectangle,
    Scene,
    Text,
    VGroup,
)

TEXT = "#1A1A1A"
MUTED = "#595959"


def label(value: str, size: int = 32, color: str = TEXT) -> Text:
    return Text(value, font="Arial", font_size=size, color=color)


class PositionAddScene(Scene):
    """Without recurrence, positions must be added explicitly."""

    def construct(self) -> None:
        title = label("Positional encoding: order returns", 50).to_edge(UP, buff=0.55)
        self.play(FadeIn(title), run_time=0.5)

        words = ["The", "animal", "didn't", "cross", "street"]
        embeddings = VGroup()
        heights = [1.0, 1.8, 0.8, 1.5, 1.1]
        for word, height in zip(words, heights):
            bar = Rectangle(
                width=0.55, height=height, stroke_width=0,
                fill_color="#2F6DB3", fill_opacity=0.7,
            )
            bar.move_to(DOWN * 2.4, aligned_edge=DOWN)
            embeddings.add(VGroup(bar, label(word, 18, MUTED).next_to(bar, DOWN, buff=0.15)))
        embeddings.arrange(RIGHT, buff=0.35).shift(DOWN * 1.0)
        self.play(LaggedStart(*[FadeIn(item) for item in embeddings], lag_ratio=0.12), run_time=0.9)

        curve = ParametricFunction(
            lambda t: np.array([t, 0.55 * np.sin(2.0 * t), 0]),
            t_range=[-2.7, 2.7],
            color=ORANGE,
            stroke_width=5,
        ).shift(UP * 1.6)
        curve_label = label("sin / cos at different frequencies", 24, ORANGE).next_to(curve, UP, buff=0.15)
        self.play(Create(curve), FadeIn(curve_label), run_time=1.2)

        plus = label("+", 56, MUTED).move_to(LEFT * 5.2 + UP * 0.4)
        arrows = VGroup(
            Arrow(embeddings.get_top() + UP * 0.1, embeddings.get_top() + UP * 0.7, buff=0.05, stroke_width=2.5, color=MUTED),
            Arrow(curve.get_bottom() + DOWN * 0.1, curve.get_bottom() + DOWN * 0.6, buff=0.05, stroke_width=2.5, color=ORANGE),
        )
        self.play(FadeIn(plus), LaggedStart(*[Create(arrow) for arrow in arrows], lag_ratio=0.2), run_time=0.8)

        output = VGroup()
        for index, (word, height) in enumerate(zip(words, heights)):
            bar = Rectangle(
                width=0.55, height=height + 0.25, stroke_width=0,
                fill_color=ORANGE, fill_opacity=0.55 + 0.08 * index,
            )
            bar.move_to(UP * 2.2, aligned_edge=DOWN)
            output.add(VGroup(bar, label(word, 18, MUTED).next_to(bar, DOWN, buff=0.15)))
        output.arrange(RIGHT, buff=0.35).shift(UP * 0.1)
        self.play(LaggedStart(*[FadeIn(item) for item in output], lag_ratio=0.12), run_time=0.9)

        summary = VGroup(
            label("embedding × word meaning", 24, MUTED),
            label("+ position signature", 24, MUTED),
            label("= input the layer can order", 24, ORANGE),
        ).arrange(DOWN, buff=0.15).to_edge(DOWN, buff=0.35)
        self.play(LaggedStart(*[FadeIn(line) for line in summary], lag_ratio=0.2), run_time=0.9)
        self.wait(2.0)
