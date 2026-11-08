from __future__ import annotations

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
    Rectangle,
    RoundedRectangle,
    Scene,
    Text,
    VGroup,
)

TEXT = "#1A1A1A"
MUTED = "#595959"


def label(value: str, size: int = 32, color: str = TEXT) -> Text:
    return Text(value, font="Arial", font_size=size, color=color)


def block(name: str, color: str, width: float = 1.5, height: float = 1.1) -> VGroup:
    rect = RoundedRectangle(
        width=width, height=height, corner_radius=0.1,
        stroke_color=color, stroke_width=3,
    )
    rect.add(label(name, 24, color).move_to(rect))
    return rect


class HeadSplitMergeScene(Scene):
    """Several attention heads run in parallel, then concat and mix."""

    def construct(self) -> None:
        title = label("Multi-head: several views, one output", 50).to_edge(UP, buff=0.55)
        self.play(FadeIn(title), run_time=0.5)

        qkv = VGroup(
            block("Q", "#2F6DB3"),
            block("K", "#2F8F6B"),
            block("V", "#B3478A"),
        ).arrange(DOWN, buff=0.3).shift(LEFT * 6.0)
        self.play(LaggedStart(*[Create(item) for item in qkv], lag_ratio=0.15), run_time=0.9)

        heads = VGroup()
        for index in range(3):
            head = VGroup(
                block(f"head {index + 1}", ORANGE, 1.7, 0.7),
                Rectangle(width=1.7, height=1.1, stroke_color=MUTED, stroke_width=1.5),
            ).arrange(DOWN, buff=0.2)
            head.add(label("attention", 18, MUTED).move_to(head[1]))
            heads.add(head)
        heads.arrange(DOWN, buff=0.3).shift(LEFT * 2.2)
        arrows = VGroup()
        for head in heads:
            arrows.add(
                Arrow(qkv.get_right() + RIGHT * 0.1, head[0].get_left() + LEFT * 0.1,
                      buff=0.1, stroke_width=2.5, color=MUTED)
            )
        self.play(LaggedStart(*[Create(arrow) for arrow in arrows], lag_ratio=0.15), run_time=0.8)
        self.play(LaggedStart(*[FadeIn(head) for head in heads], lag_ratio=0.18), run_time=0.9)

        concat = Rectangle(
            width=1.0, height=3.4, stroke_color=ORANGE, stroke_width=3,
        ).shift(RIGHT * 1.4)
        concat.add(label("concat", 22, ORANGE).rotate(90 * 3.14159 / 180).move_to(concat))
        mix = block("W_O", ORANGE, 1.4, 1.1).shift(RIGHT * 3.4)
        output = block("output", "#2F6DB3", 1.5, 1.1).shift(RIGHT * 5.6)
        self.play(FadeIn(concat), run_time=0.5)
        self.play(
            LaggedStart(
                *[Create(Arrow(head.get_right(), concat.get_left(), buff=0.1, stroke_width=2.5, color=MUTED)) for head in heads],
                lag_ratio=0.15,
            ),
            run_time=0.7,
        )
        self.play(FadeIn(mix), Create(Arrow(concat.get_right(), mix.get_left(), buff=0.1, stroke_width=3, color=ORANGE)), run_time=0.6)
        self.play(FadeIn(output), Create(Arrow(mix.get_right(), output.get_left(), buff=0.1, stroke_width=3, color=ORANGE)), run_time=0.6)

        note = label("each head keeps its own learned projections", 26, MUTED).to_edge(DOWN, buff=0.45)
        self.play(FadeIn(note), run_time=0.5)
        self.wait(2.0)
