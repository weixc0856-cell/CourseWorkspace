from __future__ import annotations

import sys
from pathlib import Path

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Arrow,
    Create,
    FadeIn,
    LaggedStart,
    Line,
    Rectangle,
    RoundedRectangle,
    Scene,
    Text,
    VGroup,
    Write,
    config,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.scene_checks import enforce
from common.design_system import BG, BLUE, INK, MUTED, ORANGE, PURPLE, TEAL  # noqa: E402

config.background_color = BG

TEXT = INK
ORANGE_HEX = ORANGE


def label(value: str, size: int = 36, color: str = TEXT) -> Text:
    return Text(value, font="Arial", font_size=size, color=color)


class QkvFanoutScene(Scene):
    """A token fans out into query/key/value and produces a context vector."""

    def construct(self) -> None:
        title = label("Query · Key · Value", 52).to_edge(UP, buff=0.6)
        self.play(FadeIn(title), run_time=0.5)

        words = ["The", "animal", "didn't", "cross", "street"]
        boxes = VGroup()
        for word in words:
            box = RoundedRectangle(
                width=2.0, height=0.9, corner_radius=0.12,
                stroke_color=MUTED, stroke_width=2,
            )
            box.add(label(word, 28).move_to(box))
            boxes.add(box)
        boxes.arrange(RIGHT, buff=0.28).shift(UP * 1.6)
        self.play(LaggedStart(*[Create(box) for box in boxes], lag_ratio=0.12), run_time=1.2)

        target = boxes[1]
        halo = Rectangle(
            width=2.25, height=1.1, stroke_color=ORANGE_HEX, stroke_width=4,
        ).move_to(target)
        self.play(Create(halo), run_time=0.5)
        self.wait(0.3)

        projections = VGroup()
        for name, color in (("Q", BLUE), ("K", TEAL), ("V", PURPLE)):
            block = RoundedRectangle(
                width=1.8, height=1.1, corner_radius=0.12,
                stroke_color=color, stroke_width=3,
            )
            block.add(label(f"{name} vector", 24, color).move_to(block))
            projections.add(block)
        projections.arrange(DOWN, buff=0.45).shift(LEFT * 4.6 + DOWN * 1.1)
        arrows = VGroup()
        for block in projections:
            arrows.add(
                Arrow(
                    target.get_bottom() + DOWN * 0.05,
                    block.get_top() + UP * 0.05,
                    buff=0.1, stroke_width=3, color=MUTED,
                )
            )
        self.play(LaggedStart(*[Create(arrow) for arrow in arrows], lag_ratio=0.2), run_time=0.8)
        self.play(LaggedStart(*[FadeIn(block) for block in projections], lag_ratio=0.2), run_time=0.8)

        score_title = label("attention scores for “animal”", 28, MUTED).shift(RIGHT * 1.7 + UP * 0.2)
        self.play(FadeIn(score_title), run_time=0.4)
        scores = [0.18, 0.62, 0.12, 0.30, 0.08]
        bars = VGroup()
        for word, score in zip(words, scores):
            bar = Rectangle(
                width=0.6, height=score * 2.2,
                stroke_width=0, fill_color=ORANGE_HEX, fill_opacity=0.75,
            )
            bar.move_to(RIGHT * 1.7 + DOWN * 1.9, aligned_edge=DOWN)
            bar.shift(RIGHT * (len(bars) - 2) * 0.95)
            bars.add(bar)
        bar_labels = VGroup()
        for word, bar in zip(words, bars):
            bar_labels.add(label(word, 18, MUTED).next_to(bar, DOWN, buff=0.15))
        self.play(LaggedStart(*[Create(bar) for bar in bars], lag_ratio=0.12), run_time=1.0)
        self.play(FadeIn(bar_labels), run_time=0.5)

        context = RoundedRectangle(
            width=2.2, height=1.0, corner_radius=0.12,
            stroke_color=ORANGE_HEX, stroke_width=4,
        )
        context.add(label("context vector", 20, ORANGE_HEX).move_to(context))
        context.shift(RIGHT * 5.3 + DOWN * 1.75)
        self.play(FadeIn(context), run_time=0.5)
        self.play(
            Create(Arrow(bars.get_right(), context.get_left(), buff=0.2, stroke_width=3, color=ORANGE_HEX)),
            run_time=0.6,
        )

        summary = VGroup(
            label("Q · K decide where to look", 28, MUTED),
            label("V is what gets passed back", 28, MUTED),
        ).arrange(DOWN, buff=0.18).to_edge(DOWN, buff=0.62)
        self.play(FadeIn(summary), run_time=0.6)
        self.wait(2.0)
        enforce(self)
