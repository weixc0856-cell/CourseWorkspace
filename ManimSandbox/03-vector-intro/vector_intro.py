"""Three-minute vector animation. No narration, no audio; visual only."""
from __future__ import annotations

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Angle,
    Arrow,
    Axes,
    BackgroundRectangle,
    Create,
    DashedLine,
    Dot,
    FadeIn,
    FadeOut,
    Indicate,
    Line,
    MathTex,
    ReplacementTransform,
    Scene,
    Text,
    VGroup,
    Wait,
    Write,
    config,
)

config.background_color = "#FFFFFF"

INK = "#14213D"
MUTED = "#5C677D"
ACCENT = "#0077B6"
WARM = "#E76F51"
GREEN = "#2A9D8F"


def title(text: str, size: int = 60) -> Text:
    return Text(text, font="Arial", font_size=size, color=INK)


def math(tex: str, size: int = 42, color: str = INK) -> MathTex:
    return MathTex(tex, font_size=size, color=color)


def panel(content, buff: float = 0.12):
    """Opaque white card so formulas stay readable over axes/grid."""
    return VGroup(
        BackgroundRectangle(content, color="#FFFFFF", fill_opacity=1.0, buff=buff),
        content,
    )


class VectorIntroScene(Scene):
    def beat(self, *args, **kwargs) -> None:
        # No voice-over: hold each state long enough to read it. Call Scene.play
        # directly so the hold does not recurse through an overridden play().
        Scene.play(self, *args, **kwargs)
        Scene.play(self, Wait(run_time=3.42))

    def construct(self) -> None:
        # 0:00–0:12 — title
        heading = title("Vectors, Visually", 76).shift(UP * 1.1)
        sub = Text("direction · length · combination", font="Arial", font_size=30, color=MUTED)
        sub.next_to(heading, DOWN, buff=0.35)
        self.beat(FadeIn(heading), FadeIn(sub), run_time=1.0)
        self.wait(3.0)
        self.beat(FadeOut(heading), FadeOut(sub), run_time=0.8)

        # 0:12–0:40 — coordinates and one vector
        axes = Axes(
            x_range=[-4, 7, 1],
            y_range=[-3, 6, 1],
            x_length=8.4,
            y_length=7.2,
            axis_config={"color": MUTED, "stroke_width": 2, "include_numbers": True, "font_size": 22},
        ).shift(LEFT * 2.1 + DOWN * 0.25)
        axis_labels = axes.get_axis_labels(math("x", 28, MUTED), math("y", 28, MUTED))
        self.beat(Create(axes), FadeIn(axis_labels), run_time=1.1)

        origin = axes.c2p(0, 0)
        a_end = axes.c2p(3, 2)
        a_line = Line(origin, a_end, color=ACCENT, stroke_width=5)
        a_arrow = Arrow(origin, a_end, buff=0, color=ACCENT, stroke_width=5, max_tip_length_to_length_ratio=0.12)
        a_label = math(r"\mathbf a=(3,2)", 38, ACCENT).next_to(a_end, RIGHT, buff=0.22)
        self.beat(Create(a_line), FadeIn(a_label), run_time=1.0)
        self.beat(ReplacementTransform(a_line, a_arrow), run_time=0.7)

        dx = DashedLine(origin, axes.c2p(3, 0), color=MUTED, stroke_width=2)
        dy = DashedLine(axes.c2p(3, 0), a_end, color=MUTED, stroke_width=2)
        self.beat(Create(dx), Create(dy), run_time=0.8)
        x_label = math("3", 32, WARM).next_to(Line(origin, axes.c2p(3, 0)), DOWN, buff=0.18)
        y_label = math("2", 32, WARM).next_to(Line(axes.c2p(3, 0), a_end), RIGHT, buff=0.18)
        self.beat(FadeIn(x_label), FadeIn(y_label), run_time=0.5)

        length_content = math(r"|\mathbf a|=\sqrt{3^2+2^2}=\sqrt{13}", 34, INK).shift(RIGHT * 2.0 + UP * 1.35)
        length = panel(length_content)
        self.beat(FadeIn(length), run_time=1.2)
        self.wait(3.2)

        # 0:40–0:56 — direction + length are both data
        note1 = Text("direction + length", font="Arial", font_size=30, color=MUTED).shift(RIGHT * 2.1 + DOWN * 0.2)
        note2 = Text("both matter", font="Arial", font_size=34, color=INK).next_to(note1, DOWN, buff=0.25)
        self.beat(FadeIn(note1), FadeIn(note2), run_time=0.6)
        self.beat(Indicate(a_arrow, color=WARM, scale_factor=1.05), run_time=1.2)
        self.wait(2.2)

        # 0:56–1:28 — addition, tip to tail
        self.beat(FadeOut(length), FadeOut(note1), FadeOut(note2), FadeOut(x_label), FadeOut(y_label), run_time=0.6)
        section = Text("1 · Add vectors", font="Arial", font_size=26, color=ACCENT).to_corner(UP + LEFT).shift(DOWN * 0.3)
        self.beat(FadeIn(section), run_time=0.5)

        b_end = axes.c2p(1, 3)
        b_arrow = Arrow(origin, b_end, buff=0, color=WARM, stroke_width=5, max_tip_length_to_length_ratio=0.12)
        b_label = math(r"\mathbf b=(1,3)", 34, WARM).next_to(b_end, LEFT, buff=0.18)
        self.beat(Create(b_arrow), FadeIn(b_label), run_time=0.9)

        b_copy_end = axes.c2p(4, 5)
        b_copy = Arrow(a_end, b_copy_end, buff=0, color=WARM, stroke_width=5, max_tip_length_to_length_ratio=0.12)
        b_copy_label = math(r"\mathbf b", 30, WARM).next_to(b_copy, RIGHT, buff=0.12)
        self.beat(Create(b_copy), FadeIn(b_copy_label), run_time=0.9)

        result_end = axes.c2p(4, 5)
        result_arrow = Arrow(origin, result_end, buff=0, color=GREEN, stroke_width=6, max_tip_length_to_length_ratio=0.10)
        result_label = math(r"\mathbf a+\mathbf b=(4,5)", 36, GREEN).next_to(result_end, RIGHT, buff=0.18)
        self.beat(Create(result_arrow), FadeIn(result_label), run_time=1.0)

        para1 = DashedLine(b_end, result_end, color=MUTED, stroke_width=2)
        para2 = DashedLine(a_end, result_end, color=MUTED, stroke_width=2)
        self.beat(Create(para1), Create(para2), run_time=0.8)

        sum_formula_content = math(r"\mathbf a+\mathbf b=(3+1,\,2+3)=(4,5)", 30).shift(RIGHT * 1.8 + DOWN * 2.1)
        sum_formula = panel(sum_formula_content)
        self.beat(FadeIn(sum_formula), run_time=1.2)
        self.wait(3.2)

        # 1:28–1:44 — commutativity
        swap_content = math(r"\mathbf b+\mathbf a=\mathbf a+\mathbf b", 34, GREEN).shift(RIGHT * 1.8 + DOWN * 2.85)
        swap = panel(swap_content)
        self.beat(FadeIn(swap), run_time=1.0)
        self.beat(Indicate(result_arrow, color=GREEN, scale_factor=1.04), run_time=1.2)
        self.wait(2.4)

        # 1:44–2:16 — scalar multiplication
        self.beat(
            FadeOut(b_arrow), FadeOut(b_label), FadeOut(b_copy), FadeOut(b_copy_label),
            FadeOut(result_arrow), FadeOut(result_label), FadeOut(para1), FadeOut(para2),
            FadeOut(sum_formula), FadeOut(swap), FadeOut(a_arrow), FadeOut(a_label),
            run_time=0.8,
        )
        section2 = Text("2 · Scale a vector", font="Arial", font_size=26, color=ACCENT).to_corner(UP + LEFT).shift(DOWN * 0.3)
        self.beat(ReplacementTransform(section, section2), run_time=0.5)

        a2_end = axes.c2p(6, 4)
        a2 = Arrow(origin, a2_end, buff=0, color=GREEN, stroke_width=6, max_tip_length_to_length_ratio=0.08)
        a2_label = math(r"2\mathbf a=(6,4)", 34, GREEN).next_to(a2_end, RIGHT, buff=0.16)
        a_neg_end = axes.c2p(-3, -2)
        a_neg = Arrow(origin, a_neg_end, buff=0, color=WARM, stroke_width=5, max_tip_length_to_length_ratio=0.12)
        a_neg_label = math(r"-\mathbf a=(-3,-2)", 32, WARM).next_to(a_neg_end, LEFT, buff=0.16)
        self.beat(Create(a2), FadeIn(a2_label), run_time=0.9)
        self.beat(Create(a_neg), FadeIn(a_neg_label), run_time=0.9)

        scale_formula_content = math(r"|\lambda\mathbf a|=|\lambda|\,|\mathbf a|", 32).shift(RIGHT * 1.8 + DOWN * 1.0)
        scale_formula = panel(scale_formula_content)
        self.beat(FadeIn(scale_formula), run_time=1.1)
        self.wait(3.2)

        # 2:16–2:48 — dot product / projection
        self.beat(
            FadeOut(a2), FadeOut(a2_label), FadeOut(a_neg), FadeOut(a_neg_label),
            FadeOut(scale_formula), FadeOut(section2), run_time=0.7,
        )
        section3 = Text("3 · Dot product", font="Arial", font_size=26, color=ACCENT).to_corner(UP + LEFT).shift(DOWN * 0.3)
        self.beat(FadeIn(section3), run_time=0.5)

        a_end = axes.c2p(3, 2)
        b_end = axes.c2p(1, 3)
        a_arrow = Arrow(origin, a_end, buff=0, color=ACCENT, stroke_width=5, max_tip_length_to_length_ratio=0.12)
        b_arrow = Arrow(origin, b_end, buff=0, color=WARM, stroke_width=5, max_tip_length_to_length_ratio=0.12)
        a_tag = math(r"\mathbf a", 32, ACCENT).next_to(a_end, DOWN + RIGHT, buff=0.14)
        b_tag = math(r"\mathbf b", 32, WARM).next_to(b_end, UP + LEFT, buff=0.14)
        self.beat(Create(a_arrow), Create(b_arrow), FadeIn(a_tag), FadeIn(b_tag), run_time=0.9)

        proj_point = axes.c2p(27 / 13, 18 / 13)
        proj_line = DashedLine(b_end, proj_point, color=MUTED, stroke_width=2)
        proj_dot = Dot(proj_point, color=GREEN, radius=0.06)
        proj_mark = math(r"\mathrm{proj}_{\mathbf a}\mathbf b", 24, GREEN).next_to(proj_point, DOWN + LEFT, buff=0.12)
        self.beat(Create(proj_line), FadeIn(proj_dot), FadeIn(proj_mark), run_time=0.8)

        angle = Angle(
            Line(origin, a_end),
            Line(origin, b_end),
            radius=0.55,
            color=GREEN,
            stroke_width=2,
        )
        theta = math(r"\theta", 30, GREEN).next_to(angle, RIGHT, buff=0.05)
        self.beat(Create(angle), FadeIn(theta), run_time=0.7)

        dot_numbers = panel(math(r"3\cdot1+2\cdot3=9", 30).shift(RIGHT * 1.9 + UP * 0.8))
        dot_formula = panel(
            math(r"\mathbf a\cdot\mathbf b=|\mathbf a||\mathbf b|\cos\theta", 30).shift(
                RIGHT * 1.9 + DOWN * 0.2
            )
        )
        self.beat(FadeIn(dot_numbers), run_time=0.8)
        self.beat(FadeIn(dot_formula), run_time=1.1)
        self.wait(3.8)

        # 2:48–3:00 — recap
        self.beat(
            FadeOut(a_arrow), FadeOut(b_arrow), FadeOut(a_tag), FadeOut(b_tag),
            FadeOut(proj_line), FadeOut(proj_dot), FadeOut(proj_mark),
            FadeOut(angle), FadeOut(theta), FadeOut(dot_numbers), FadeOut(dot_formula),
            FadeOut(section3), FadeOut(axes), FadeOut(axis_labels), FadeOut(dx), FadeOut(dy),
            run_time=0.4,
        )
        recap_title = title("Three moves", 64).shift(UP * 1.4)
        recap = VGroup(
            Text("add  ·  tip to tail", font="Arial", font_size=36, color=ACCENT),
            Text("scale  ·  stretch or flip", font="Arial", font_size=36, color=GREEN),
            Text("dot  ·  projection × length", font="Arial", font_size=36, color=WARM),
        ).arrange(DOWN, buff=0.45, aligned_edge=LEFT).shift(DOWN * 0.1)
        self.beat(FadeIn(recap_title), run_time=0.5)
        for line in recap:
            self.beat(FadeIn(line, shift=RIGHT * 0.3), run_time=0.5)
        self.wait(2.0)
        self.beat(FadeOut(recap_title), FadeOut(recap), run_time=0.6)
