"""Slide 7 — residual bypass and layer normalization.

White course palette, 10 s insert. One encoder sub-layer wrapper is shown, then
repeated once for the feed-forward sub-layer.
"""
from __future__ import annotations

import sys
from pathlib import Path

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Create,
    FadeIn,
    Indicate,
    Line,
    RoundedRectangle,
    Scene,
    Text,
    VGroup,
    config,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.scene_checks import enforce
from common.design_system import BG, INK, MUTED, ORANGE, TEAL  # noqa: E402

config.background_color = BG


def label(text: str, size: int = 26, color: str = INK) -> Text:
    return Text(text, font="Arial", font_size=size, color=color)


def block(text: str, width: float = 3.2, height: float = 0.72, color: str = INK) -> VGroup:
    rect = RoundedRectangle(
        corner_radius=0.1, width=width, height=height, stroke_color=color, stroke_width=2
    )
    return VGroup(rect, label(text, 24).move_to(rect))


def plus(color: str = ORANGE) -> VGroup:
    circle = RoundedRectangle(
        corner_radius=0.35, width=0.42, height=0.42, stroke_color=color, stroke_width=2
    )
    sign = label("+", 30, color).move_to(circle)
    return VGroup(circle, sign)


class ResidualBypassScene(Scene):
    def construct(self):
        title = label("Residual + layer norm", 32).to_corner(UP + LEFT, buff=0.55)
        note = label("one wrapper around every sub-layer", 22, MUTED).to_corner(DOWN + LEFT, buff=0.5)
        x = 0.4

        attn = block("self-attention").move_to([x, -1.9, 0])
        plus1 = plus().move_to([x, -0.8, 0])
        ln1 = block("layer norm", 2.6, 0.6, TEAL).move_to([x, 0.25, 0])
        ffn = block("feed-forward").move_to([x, 1.25, 0])
        plus2 = plus().move_to([x, 2.3, 0])
        ln2 = block("layer norm", 2.6, 0.6, TEAL).move_to([x, 3.3, 0])

        inp = Line([x, -3.35, 0], [x, -2.3, 0], color=INK, stroke_width=3)
        arrow = label("x", 24).next_to(inp, LEFT, buff=0.15)

        def bypass(y_from: float, y_to: float) -> VGroup:
            rail = x - 2.55
            return VGroup(
                Line([x - 1.62, y_from, 0], [rail, y_from, 0], color=ORANGE, stroke_width=2),
                Line([rail, y_from, 0], [rail, y_to, 0], color=ORANGE, stroke_width=2),
                Line([rail, y_to, 0], [x - 0.24, y_to, 0], color=ORANGE, stroke_width=2),
            )

        self.play(FadeIn(title), FadeIn(note), run_time=0.6)
        self.play(Create(inp), FadeIn(arrow), run_time=0.7)
        self.play(FadeIn(attn, shift=0.1 * UP), run_time=0.6)
        self.play(Create(bypass(-1.5, -0.8)), FadeIn(plus1), run_time=1.0)
        self.play(Indicate(plus1, color=ORANGE), run_time=0.5)
        self.play(Create(Line([x, -0.5, 0], [x, -0.05, 0], color=INK, stroke_width=3)),
                  FadeIn(ln1), run_time=0.6)
        self.play(FadeIn(ffn, shift=0.1 * UP), run_time=0.6)
        self.play(Create(bypass(1.6, 2.3)), FadeIn(plus2), run_time=1.0)
        self.play(Indicate(plus2, color=ORANGE), run_time=0.5)
        self.play(Create(Line([x, 2.6, 0], [x, 3.0, 0], color=INK, stroke_width=3)),
                  FadeIn(ln2), run_time=0.6)
        bracket = VGroup(
            Line([x + 2.0, -2.4, 0], [x + 2.55, -2.4, 0], color=TEAL, stroke_width=2),
            Line([x + 2.55, -2.4, 0], [x + 2.55, 3.6, 0], color=TEAL, stroke_width=2),
            Line([x + 2.55, 3.6, 0], [x + 2.0, 3.6, 0], color=TEAL, stroke_width=2),
        )
        tag = label("repeat in every block", 22, TEAL).next_to(bracket, RIGHT, buff=0.15)
        self.play(Create(bracket), FadeIn(tag), run_time=1.0)
        self.wait(1.4)
        enforce(self)
