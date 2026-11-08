"""Slide 10 — forward pass, loss against the target, and backprop.

Rebuilt as three sequential zones on the process_flow band:
01 input + model -> 02 prediction -> 03 loss.
"""
from __future__ import annotations

import sys
from pathlib import Path

from manim import (
    LEFT,
    UP,
    Arrow,
    Create,
    DashedLine,
    FadeIn,
    Indicate,
    Line,
    Rectangle,
    RoundedRectangle,
    Scene,
    Text,
    VGroup,
    config,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.design_system import (  # noqa: E402
    ACCENT,
    BG,
    BODY,
    DIVIDER,
    GREEN,
    INK,
    MUTED,
    TYPE,
    WARM,
    x_at,
    y_at,
)

config.background_color = BG


def label(text: str, size: int = TYPE["label"], color: str = INK) -> Text:
    return Text(text, font="Arial", font_size=size, color=color)


def box(text: str, width: float = 2.0, height: float = 0.9, color: str = INK, size: int = 24) -> VGroup:
    rect = RoundedRectangle(
        corner_radius=0.1, width=width, height=height, stroke_color=color, stroke_width=2
    )
    return VGroup(rect, label(text, size).move_to(rect))


def kicker(text: str, x: float) -> Text:
    return label(text, TYPE["label"], MUTED).move_to([x, 1.75, 0], aligned_edge=LEFT)


class LossBackpropScene(Scene):
    def construct(self):
        title = label("Training: forward pass, loss, update", TYPE["heading_1"], INK)
        title.move_to([x_at(0.06), y_at(0.85), 0], aligned_edge=LEFT)
        self.play(FadeIn(title), run_time=0.5)

        # 01 input + model
        z1_kicker = kicker("01  input + model", -5.55)
        source = box("merci", 1.6, 0.9, INK, 22).move_to([-5.6, 0.7, 0])
        stack = box("encoder → decoder", 2.8, 1.1, INK, 21).move_to([-3.05, 0.7, 0])
        a1 = Arrow([-4.78, 0.7, 0], [-4.48, 0.7, 0], buff=0.03, color=INK, stroke_width=2.6)
        a2 = Arrow([-1.62, 0.7, 0], [-1.05, 0.7, 0], buff=0.03, color=INK, stroke_width=2.6)
        zone1 = VGroup(z1_kicker, source, stack, a1, a2)
        self.play(FadeIn(zone1, shift=0.08 * UP), run_time=1.0)

        # 02 prediction
        z2_kicker = kicker("02  prediction", -0.75)
        base_y = -1.55
        names = ["thanks", "merci", "the", "a", "you"]
        heights = [0.9, 1.5, 1.2, 0.8, 0.7]
        xs = [-0.6 + index * 0.82 for index in range(5)]
        bars = VGroup()
        bar_labels = VGroup()
        for name, height, x in zip(names, heights, xs):
            bar = Rectangle(
                width=0.58, height=height, stroke_width=0, fill_color=ACCENT, fill_opacity=0.9
            )
            bar.move_to([x, base_y + height / 2, 0])
            bars.add(bar)
            bar_labels.add(label(name, 18, MUTED).move_to([x, base_y - 0.32, 0]))
        target = Rectangle(
            width=0.62, height=2.5, stroke_color=GREEN, stroke_width=2.6, fill_opacity=0
        ).move_to([xs[0], base_y + 1.25, 0])
        target_label = label("target: thanks = 1", 18, GREEN).move_to([1.05, 1.3, 0])
        gap = VGroup(
            Line(
                [xs[0] - 0.42, base_y + heights[0], 0],
                [xs[0] - 0.42, base_y + 2.5, 0],
                color=WARM,
                stroke_width=2.2,
            ),
            Line(
                [xs[0] - 0.5, base_y + heights[0], 0],
                [xs[0] - 0.34, base_y + heights[0], 0],
                color=WARM,
                stroke_width=2.2,
            ),
            Line(
                [xs[0] - 0.5, base_y + 2.5, 0],
                [xs[0] - 0.34, base_y + 2.5, 0],
                color=WARM,
                stroke_width=2.2,
            ),
        )
        gap_label = label("gap", 18, WARM).move_to([xs[0] - 0.35, base_y + 2.72, 0])
        zone2 = VGroup(z2_kicker, bars, bar_labels, target_label)
        self.play(FadeIn(zone2, shift=0.08 * UP), run_time=0.9)
        self.play(Create(target), Create(gap), FadeIn(gap_label), run_time=1.0)

        # 03 loss
        z3_kicker = kicker("03  loss", 4.1)
        loss = label("loss = 2.3", 40, WARM).move_to([5.0, 0.6, 0])
        zone3 = VGroup(z3_kicker, loss)
        self.play(FadeIn(zone3, shift=0.08 * UP), run_time=0.8)
        self.play(Indicate(loss, color=WARM, scale_factor=1.06), run_time=0.6)

        # backprop below the visual band
        down = DashedLine([4.2, -0.2, 0], [4.2, -2.15, 0], color=WARM, stroke_width=2.2, dash_length=0.12)
        across = DashedLine(
            [4.2, -2.15, 0], [-3.0, -2.15, 0], color=WARM, stroke_width=2.2, dash_length=0.12
        )
        into = Arrow(
            [-3.0, -2.15, 0],
            [-3.0, -0.25, 0],
            buff=0,
            color=WARM,
            stroke_width=2.4,
            max_tip_length_to_length_ratio=0.1,
        )
        update = label("update weights", TYPE["body"], WARM).move_to([0.6, -2.45, 0])
        self.play(Create(down), Create(across), run_time=0.8)
        self.play(Create(into), FadeIn(update), run_time=0.6)
        self.play(Indicate(stack, color=WARM, scale_factor=1.04), run_time=0.7)

        divider = Line([x_at(0.06), -2.72, 0], [x_at(0.94), -2.72, 0], color=DIVIDER, stroke_width=1.5)
        caption = label(
            "same forward pass; training adds the target and the loss", TYPE["caption"], BODY
        ).move_to([x_at(0.06), -3.02, 0], aligned_edge=LEFT)
        self.play(Create(divider), FadeIn(caption), run_time=0.6)
        self.wait(1.1)
