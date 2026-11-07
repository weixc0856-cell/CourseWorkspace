from __future__ import annotations

from manim import (
    BLUE,
    ORANGE,
    Create,
    FadeIn,
    RoundedRectangle,
    Scene,
    Text,
    UP,
    Write,
)


class SmokeScene(Scene):
    """R1-1: smallest real Manim render used to validate the engine."""

    def construct(self) -> None:
        title = Text("R1 engine smoke", font="Arial", font_size=64).shift(UP * 2.0)
        box = RoundedRectangle(
            width=7.2,
            height=1.8,
            corner_radius=0.18,
            color=ORANGE,
            stroke_width=4,
        )
        label = Text("Manim render OK", font="Arial", font_size=42).move_to(box)

        self.play(FadeIn(title), run_time=0.6)
        self.play(Create(box), run_time=0.8)
        self.play(Write(label), run_time=0.8)
        self.play(title.animate.set_color(BLUE).shift(UP * 0.25), run_time=0.6)
        self.wait(1.0)
