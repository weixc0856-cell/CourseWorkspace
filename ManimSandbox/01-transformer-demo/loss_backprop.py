"""Slide 10 — forward pass, loss against the target, and backprop.

White course palette, 11 s insert. Toy translation 'merci' -> 'thanks'.
"""
from __future__ import annotations

from manim import (
    DOWN,
    LEFT,
    RIGHT,
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

BG = "#FFFFFF"
INK = "#14213D"
MUTED = "#5C677D"
ACCENT = "#0077B6"
WARM = "#E76F51"
GREEN = "#2A9D8F"

config.background_color = BG


def label(text: str, size: int = 24, color: str = INK) -> Text:
    return Text(text, font="Arial", font_size=size, color=color)


def box(text: str, width: float = 2.2, height: float = 0.75, color: str = INK) -> VGroup:
    rect = RoundedRectangle(
        corner_radius=0.1, width=width, height=height, stroke_color=color, stroke_width=2
    )
    return VGroup(rect, label(text, 22).move_to(rect))


class LossBackpropScene(Scene):
    def construct(self):
        title = label("Training: forward pass, loss, update", 34).to_corner(UP + LEFT, buff=0.55)
        self.play(FadeIn(title), run_time=0.6)

        source = box("merci", 1.9, 0.7).move_to([-5.4, 0.55, 0])
        stack = box("encoder → decoder", 3.4, 0.9).move_to([-2.4, 0.55, 0])
        a1 = Arrow([-4.4, 0.55, 0], [-3.9, 0.55, 0], buff=0.05, color=INK, stroke_width=2.4)
        a2 = Arrow([-0.65, 0.55, 0], [-0.15, 0.55, 0], buff=0.05, color=INK, stroke_width=2.4)
        self.play(FadeIn(source), Create(a1), FadeIn(stack), Create(a2), run_time=1.2)

        # model distribution
        base_y = -1.9
        names = ["thanks", "merci", "the", "a", "you"]
        heights = [0.55, 0.85, 0.7, 0.5, 0.45]
        xs = [-0.2 + i * 0.78 for i in range(5)]
        bars = VGroup()
        labels = VGroup()
        for name, height, x in zip(names, heights, xs):
            bar = Rectangle(
                width=0.52, height=height, stroke_width=0, fill_color=ACCENT, fill_opacity=0.85
            )
            bar.move_to([x, base_y + height / 2, 0])
            bars.add(bar)
            labels.add(label(name, 15, MUTED).move_to([x, base_y - 0.3, 0]))
        dist_caption = label("model distribution", 20, MUTED).move_to([1.4, 1.35, 0])
        self.play(
            FadeIn(bars, shift=0.1 * UP), FadeIn(labels), FadeIn(dist_caption), run_time=1.1
        )

        target = Rectangle(
            width=0.52, height=1.95, stroke_color=GREEN, stroke_width=2.4, fill_opacity=0
        ).move_to([xs[0], base_y + 1.95 / 2, 0])
        target_label = label("target: thanks = 1", 20, GREEN).move_to([0.6, 1.75, 0])
        self.play(Create(target), FadeIn(target_label), run_time=0.9)

        gap = VGroup(
            Line([xs[0] - 0.34, base_y + heights[0], 0], [xs[0] - 0.34, base_y + 1.95, 0], color=WARM, stroke_width=2),
            Line([xs[0] - 0.42, base_y + heights[0], 0], [xs[0] - 0.26, base_y + heights[0], 0], color=WARM, stroke_width=2),
            Line([xs[0] - 0.42, base_y + 1.95, 0], [xs[0] - 0.26, base_y + 1.95, 0], color=WARM, stroke_width=2),
        )
        gap_label = label("gap", 18, WARM).next_to(gap, LEFT, buff=0.1)
        self.play(Create(gap), FadeIn(gap_label), run_time=0.8)

        loss = label("loss = 2.3", 30, WARM).move_to([4.6, 0.55, 0])
        self.play(FadeIn(loss, shift=0.1 * LEFT), run_time=0.7)
        self.play(Indicate(loss, color=WARM), run_time=0.5)

        back = DashedLine([4.2, 0.05, 0], [-2.5, -0.2, 0], color=WARM, stroke_width=2.2, dash_length=0.12)
        back_tip = Arrow([-2.5, -0.2, 0], [-2.5, 0.05, 0], buff=0, color=WARM, stroke_width=2.2,
                         max_tip_length_to_length_ratio=0.35)
        update = label("update weights", 20, WARM).move_to([1.2, -0.55, 0])
        self.play(Create(back), FadeIn(back_tip), FadeIn(update), run_time=1.3)

        caption = label("same forward pass; training adds the target and the loss", 20, MUTED)
        caption.to_corner(DOWN + LEFT, buff=0.45)
        self.play(FadeIn(caption), run_time=0.7)
        self.wait(1.4)
