from __future__ import annotations

import numpy as np
from manim import (
    DOWN,
    LEFT,
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
    config,
)

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.scene_checks import enforce
from common.design_system import BG, BLUE, INK, MUTED, ORANGE, PURPLE, TEAL  # noqa: E402

config.background_color = BG

TEXT = INK


def label(value: str, size: int = 32, color: str = TEXT) -> Text:
    return Text(value, font="Arial", font_size=size, color=color)


class PositionAddScene(Scene):
    """Without recurrence, positions must be added explicitly."""

    def construct(self) -> None:
        title = label("Positional encoding: order returns", 50).to_edge(UP, buff=0.55)
        self.play(FadeIn(title), run_time=0.5)

        words = ["The", "animal", "didn't", "cross", "street"]
        heights = [1.0, 1.8, 0.8, 1.5, 1.1]
        baseline = -1.5
        x_step = 0.95
        embeddings = VGroup()
        output = VGroup()
        for index, (word, height) in enumerate(zip(words, heights)):
            x = (index - 2) * x_step
            bar = Rectangle(
                width=0.55, height=height, stroke_width=0,
                fill_color=BLUE, fill_opacity=0.7,
            )
            bar.move_to(RIGHT * x + UP * (baseline + height / 2))
            embeddings.add(bar)
            total = Rectangle(
                width=0.55, height=height + 0.3, stroke_width=2,
                stroke_color=ORANGE, fill_color=ORANGE, fill_opacity=0.0,
            )
            total.move_to(RIGHT * x + UP * (baseline + (height + 0.3) / 2))
            cap = Rectangle(
                width=0.55, height=0.3, stroke_width=0,
                fill_color=ORANGE, fill_opacity=0.92,
            )
            cap.move_to(RIGHT * x + UP * (baseline + height + 0.15))
            output.add(VGroup(total, cap))

        labels = VGroup(*[
            label(word, 18, MUTED).move_to(RIGHT * (index - 2) * x_step + UP * (baseline - 0.22))
            for index, word in enumerate(words)
        ])
        self.play(LaggedStart(*[FadeIn(item) for item in embeddings], lag_ratio=0.1), run_time=0.9)
        self.play(FadeIn(labels), run_time=0.4)

        curve = ParametricFunction(
            lambda t: np.array([t, 0.45 * np.sin(2.0 * t), 0]),
            t_range=[-2.7, 2.7],
            color=ORANGE,
            stroke_width=5,
        ).shift(UP * 1.7)
        curve_label = label(
            "position signature: sin / cos at different frequencies", 22, ORANGE
        ).next_to(curve, UP, buff=0.15)
        self.play(Create(curve), FadeIn(curve_label), run_time=1.2)

        role_pos = label("position", 22, ORANGE).move_to(LEFT * 4.2 + UP * 1.7)
        role_emb = label("embedding", 22, INK).move_to(LEFT * 4.2 + DOWN * 1.2)
        plus = label("+", 40, MUTED).move_to(LEFT * 4.2 + UP * 0.2)
        self.play(FadeIn(role_pos), FadeIn(role_emb), FadeIn(plus), run_time=0.4)
        self.play(LaggedStart(*[FadeIn(item) for item in output], lag_ratio=0.1), run_time=0.9)

        summary = VGroup(
            label("embedding × word meaning", 22, MUTED),
            label("+ position signature", 22, ORANGE),
            label("= input the layer can order", 22, INK),
        ).arrange(DOWN, buff=0.15).to_edge(DOWN, buff=0.62)
        self.play(LaggedStart(*[FadeIn(line) for line in summary], lag_ratio=0.2), run_time=0.9)
        self.wait(2.0)
        enforce(self)
