"""80-second vector-addition case study (R3).

Design: ManimSandbox/03-vector-intro/direction-addition-v2.json

Five continuous shots, no slides, no audio, no 3D. The benchmark is the
3Blue1Brown visual language: one persistent world, motivated camera moves,
objects that keep their identity, and equations written rather than pasted.
"""
from __future__ import annotations

import numpy as np
from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    ArcBetweenPoints,
    Arrow,
    BackgroundRectangle,
    Circle,
    Create,
    DashedVMobject,
    Dot,
    FadeIn,
    FadeOut,
    Flash,
    GrowArrow,
    Indicate,
    Line,
    MathTex,
    MovingCameraScene,
    NumberPlane,
    Text,
    VGroup,
    Write,
    always_redraw,
    config,
)
from manim.utils.rate_functions import ease_in_out_cubic, ease_out_cubic, ease_out_quad, smooth

config.background_color = "#0B1220"

BG = "#0B1220"
INK = "#E8EEF7"
MUTED = "#8494A8"
A = "#4CC2FF"
B = "#FF8A5B"
RESULT = "#5BE3B0"


def p(x: float, y: float) -> np.ndarray:
    return np.array([x, y, 0.0])


def m(tex: str, size: int = 30, color: str = INK) -> MathTex:
    return MathTex(tex, font_size=size, color=color)


def t(text: str, size: int = 24, color: str = INK) -> Text:
    return Text(text, font="Arial", font_size=size, color=color)


def panel(content, buff: float = 0.12):
    return BackgroundRectangle(
        content, color=BG, fill_opacity=0.88, stroke_opacity=0.0, buff=buff
    )


def headline(lines, x=-2.30, y=3.55, size=32):
    group = VGroup(*[t(line, size, INK) for line in lines])
    group.arrange(DOWN, buff=0.10, aligned_edge=LEFT).move_to(p(x, y))
    return group


def arrow(start, end, color, width: float = 6.0, opacity: float = 1.0):
    return Arrow(
        start, end, buff=0, color=color, stroke_width=width,
        max_tip_length_to_length_ratio=0.11, stroke_opacity=opacity, fill_opacity=opacity,
    )


def tick(mid: np.ndarray, vec: np.ndarray, color=MUTED) -> Line:
    unit = vec / np.linalg.norm(vec)
    perp = np.array([-unit[1], unit[0], 0.0])
    return Line(mid - perp * 0.13, mid + perp * 0.13, color=color, stroke_width=2.5)


class VectorAdditionV2(MovingCameraScene):
    def construct(self) -> None:
        self.clock = 0.0
        self.camera.frame.set_width(14).move_to(p(1.5, 1.9))

        grid = NumberPlane(
            x_range=[-8, 8, 1], y_range=[-5, 6, 1],
            background_line_style={"stroke_color": MUTED, "stroke_opacity": 0.13, "stroke_width": 1},
            axis_config={"stroke_color": MUTED, "stroke_opacity": 0.40, "stroke_width": 2},
        )
        origin = p(0, 0)
        a_end = p(3, 2)
        b_end = p(1, 3)
        b_vec = b_end - origin
        result_end = b_end + (a_end - origin)

        kicker = t("Vector addition", 20, MUTED).move_to(p(-3.0, 4.65))
        headline1 = headline(["How do we add", "two vectors?"], y=3.5)
        sub1 = t("tail to tail, for now", 22, MUTED).move_to(p(-2.30, 1.95))
        a = arrow(origin, a_end, A)
        b = arrow(origin, b_end, B)
        a_label = m(r"\vec{a}", 30, A).move_to(p(3.3, 1.9))
        b_label = m(r"\vec{b}", 30, B).move_to(p(1.55, 2.72))
        origin_mark = VGroup(Dot(origin, color=MUTED, radius=0.045), t("O", 18, MUTED).move_to(p(-0.22, -0.22)))
        target = Line(origin, p(3.98, 4.82), color=MUTED, stroke_width=2, stroke_opacity=0.25)
        unknown = t("?", 44, MUTED).move_to(p(4.02, 4.98))
        known = VGroup(
            panel(VGroup(
                m(r"\vec{a}=(3,2)", 24, A),
                m(r"\vec{b}=(1,3)", 24, B),
            ).arrange(DOWN, buff=0.18, aligned_edge=LEFT).move_to(p(5.5, 1.45))),
            m(r"\vec{a}=(3,2)", 24, A).move_to(p(5.5, 1.63)),
            m(r"\vec{b}=(1,3)", 24, B).move_to(p(5.5, 1.05)),
        )
        given = t("given", 17, MUTED).move_to(p(5.5, 2.28))

        # ---------------------------------------------------------------- s1
        self.beat(FadeIn(grid), run_time=0.8)
        self.beat(FadeIn(kicker), FadeIn(headline1, shift=DOWN * 0.15), run_time=0.8)
        self.beat(GrowArrow(a), run_time=1.2)
        self.beat(GrowArrow(b), run_time=1.2)
        self.beat(FadeIn(a_label), FadeIn(b_label), FadeIn(origin_mark), FadeIn(sub1), run_time=0.6)
        self.beat(Create(target), run_time=1.0)
        self.beat(FadeIn(unknown, shift=UP * 0.1), FadeIn(known), FadeIn(given), run_time=0.6)
        self.play(
            self.camera.frame.animate.set_width(12.5).move_to(p(1.75, 2.1)),
            run_time=1.8, rate_func=ease_in_out_cubic,
        )
        self.clock += 1.8

        # ---------------------------------------------------------------- s2
        self.beat(
            FadeOut(headline1), FadeOut(sub1), FadeOut(target), FadeOut(unknown),
            FadeOut(known), FadeOut(given), FadeOut(kicker),
            b.animate.set_opacity(0.18), b_label.animate.set_opacity(0.32),
            run_time=0.8,
        )
        b_copy = arrow(origin, b_end, B)
        tail = always_redraw(lambda: VGroup(
            Circle(radius=0.11, color=B, stroke_width=2).move_to(b_copy.get_start()),
            Dot(b_copy.get_start(), color=B, radius=0.05),
        ))
        copy_label = always_redraw(lambda: VGroup(
            m(r"\vec{b}", 26, B),
            t("copy", 16, MUTED),
        ).arrange(DOWN, buff=0.02).move_to(b_copy.get_start() + p(0.55, 0.55)))
        trail = DashedVMobject(ArcBetweenPoints(origin, a_end, angle=-0.70), num_dashes=22)
        trail.set_stroke(color=B, width=2.5, opacity=0.62)
        self.beat(
            FadeIn(b_copy), FadeIn(tail), FadeIn(copy_label),
            self.camera.frame.animate.set_width(11.4).move_to(p(2.4, 2.15)),
            run_time=0.6,
        )
        self.play(
            b_copy.animate.shift(a_end),
            Create(trail),
            self.camera.frame.animate.set_width(10.9).move_to(p(2.9, 2.3)),
            run_time=3.0, rate_func=ease_in_out_cubic,
        )
        self.clock += 3.0
        join_ring = VGroup(
            Circle(radius=0.23, color=RESULT, stroke_width=3).set_fill(RESULT, opacity=0.12).move_to(a_end),
            Dot(a_end, color=RESULT, radius=0.07),
        )
        join_text = t("tail meets tip", 19, INK).move_to(p(3.95, 1.18))
        self.beat(
            FadeOut(tail), Flash(a_end, color=RESULT, flash_radius=0.32, num_lines=10, line_length=0.14),
            a_label.animate.move_to(p(2.55, 1.35)),
            run_time=0.8,
        )
        self.beat(FadeIn(join_ring), FadeIn(join_text), run_time=1.0)
        # same length / same direction proof marks
        proof_tick_b = tick(b_vec / 2, b_vec, MUTED)
        proof_tick_c = tick(a_end + b_vec / 2, b_vec, MUTED)
        proof = VGroup(
            t("same length", 20, B),
            t("same direction", 20, B),
        ).arrange(DOWN, buff=0.06, aligned_edge=LEFT).move_to(p(5.15, 2.35))
        self.beat(Create(proof_tick_b), Create(proof_tick_c), FadeIn(proof, shift=LEFT * 0.15), run_time=2.0)
        self.beat(Indicate(b_copy, color=B, scale_factor=1.04), run_time=1.6)
        self.beat(run_time=1.4)
        self.play(
            self.camera.frame.animate.set_width(10.2).move_to(p(3.0, 2.45)),
            run_time=2.0, rate_func=ease_in_out_cubic,
        )
        self.clock += 2.0
        self.beat(
            FadeOut(proof), FadeOut(proof_tick_b), FadeOut(proof_tick_c),
            run_time=1.0,
        )
        self.beat(Indicate(join_ring, color=RESULT, scale_factor=1.2), run_time=1.6)
        self.beat(run_time=1.4)
        self.play(
            FadeOut(trail), FadeOut(tail), FadeOut(copy_label),
            self.camera.frame.animate.set_width(12.5).move_to(p(2.0, 2.2)),
            run_time=3.0, rate_func=ease_in_out_cubic,
        )
        self.clock += 3.0
        self.beat(run_time=3.8)
        # clock at 32.0

        # ---------------------------------------------------------------- s3
        headline3 = headline(["Close the", "triangle"], y=3.5)
        sub3 = t("the diagonal is the sum", 21, MUTED).move_to(p(-2.15, 1.65))
        result = arrow(origin, result_end, RESULT, width=7)
        result_ring = VGroup(
            Circle(radius=0.18, color=RESULT, stroke_width=2.5).set_fill(RESULT, opacity=0.10).move_to(result_end),
            Dot(result_end, color=RESULT, radius=0.07),
        )
        para1 = Line(b_end, result_end, color=MUTED, stroke_width=1.4, stroke_opacity=0.55)
        para2 = Line(a_end, result_end, color=MUTED, stroke_width=1.4, stroke_opacity=0.55)
        f1a = m(r"\vec{a}+\vec{b}=(4,5)", 29, RESULT).move_to(p(5.75, 3.72))
        f1b = m(r"=(3+1,\ 2+3)", 23, INK).move_to(p(5.95, 3.08))
        F1 = VGroup(panel(f1a), f1a)
        F2 = VGroup(panel(f1b), f1b)
        self.beat(
            FadeIn(headline3), FadeIn(sub3),
            FadeOut(join_ring), FadeOut(join_text), FadeOut(b_copy.tip),
            GrowArrow(result), run_time=1.6, rate_func=ease_out_cubic,
        )
        self.beat(Create(para1), Create(para2), FadeIn(result_ring), run_time=0.8)
        self.beat(Flash(result_end, color=RESULT, flash_radius=0.38, num_lines=12, line_length=0.18), run_time=1.2)
        self.beat(FadeIn(F1[0]), Write(F1[1]), run_time=1.2)
        self.beat(FadeIn(F2[0]), Write(F2[1]), run_time=1.2)
        self.play(
            self.camera.frame.animate.set_width(12.6).move_to(p(2.0, 2.25)),
            run_time=2.0, rate_func=ease_in_out_cubic,
        )
        self.clock += 2.0
        self.beat(Indicate(result, color=RESULT, scale_factor=1.03), run_time=1.6)
        self.beat(run_time=1.4)
        self.play(
            self.camera.frame.animate.set_width(12.2).move_to(p(2.15, 2.4)),
            run_time=3.0, rate_func=ease_in_out_cubic,
        )
        self.clock += 3.0
        self.beat(Indicate(result_ring, color=RESULT, scale_factor=1.12), run_time=1.4)
        self.beat(run_time=1.6)
        self.beat(run_time=1.5)
        self.beat(Indicate(result_ring, color=RESULT, scale_factor=1.08), run_time=1.0)
        self.beat(run_time=0.5)
        # clock at 52.0

        # ---------------------------------------------------------------- s4
        headline4 = headline(["Same sum,", "different order"], y=3.9)
        def route_legend(color1, color2, label, y):
            first = Line(p(-3.90, y), p(-3.62, y), color=color1, stroke_width=6)
            second = Line(p(-3.62, y), p(-3.34, y), color=color2, stroke_width=6)
            return VGroup(first, second, t(label, 20, INK).next_to(second, RIGHT, buff=0.18))

        leg1 = route_legend(B, A, "Route 1: b, then a", 1.65)
        leg2 = route_legend(A, B, "Route 2: a, then b", 1.05)
        self.beat(
            FadeOut(headline3), FadeOut(sub3),
            FadeIn(headline4),
            a.animate.set_opacity(0.28), a_label.animate.set_opacity(0.28),
            b_copy.animate.set_opacity(0.22),
            b.animate.set_opacity(0.95), b_label.animate.set_opacity(0.95),
            run_time=0.8,
        )
        a_copy = Line(origin, a_end, color=A, stroke_width=6, stroke_opacity=1.0)
        self.beat(FadeIn(a_copy), run_time=0.6)
        self.play(
            a_copy.animate.shift(b_end),
            self.camera.frame.animate.set_width(12.8).move_to(p(2.0, 2.2)),
            run_time=2.6, rate_func=ease_in_out_cubic,
        )
        self.clock += 2.6
        self.beat(Flash(b_end, color=A, flash_radius=0.24, num_lines=8, line_length=0.12), run_time=0.4)
        result2 = arrow(origin, result_end, RESULT, width=7)
        self.beat(GrowArrow(result2), run_time=1.2, rate_func=ease_out_cubic)
        self.beat(Flash(result_end, color=RESULT, flash_radius=0.38, num_lines=12, line_length=0.16), run_time=1.2)
        f3 = m(r"\vec{a}+\vec{b}=\vec{b}+\vec{a}", 24, RESULT).move_to(p(-2.3, -0.75))
        F3 = VGroup(panel(f3), f3)
        self.beat(FadeIn(F3[0]), Write(F3[1]), run_time=1.2)
        self.beat(FadeIn(leg1, shift=RIGHT * 0.12), FadeIn(leg2, shift=RIGHT * 0.12), run_time=1.4)
        self.play(
            self.camera.frame.animate.set_width(13.0).move_to(p(1.9, 2.15)),
            run_time=1.2, rate_func=ease_in_out_cubic,
        )
        self.clock += 1.2
        self.beat(Indicate(a_copy, color=A, scale_factor=1.03), run_time=1.2)
        self.beat(Indicate(b, color=B, scale_factor=1.04), run_time=1.2)
        self.beat(run_time=1.0)
        self.play(
            self.camera.frame.animate.shift(RIGHT * 0.15 + UP * 0.05),
            run_time=2.0, rate_func=smooth,
        )
        self.clock += 2.0
        self.beat(run_time=2.0)
        # clock at 70.0

        # ---------------------------------------------------------------- s5
        headline5 = headline(["One picture,", "three facts"], y=3.95)
        bullets = VGroup(
            t("1   Tip-to-tail adds vectors", 22, INK),
            t("2   The diagonal is the sum", 22, INK),
            t("3   Order does not change it", 22, INK),
        ).arrange(DOWN, buff=0.22, aligned_edge=LEFT).move_to(p(-2.05, 1.35))
        self.beat(FadeOut(leg1), FadeOut(leg2), FadeOut(headline4), run_time=0.5)
        self.beat(FadeIn(headline5), run_time=0.5)
        self.play(
            FadeOut(F2[0]), FadeOut(F2[1]),
            F1.animate.move_to(p(6.0, 1.55)),
            F3.animate.move_to(p(6.0, 0.55)),
            b_copy.animate.set_opacity(0.14),
            a_copy.animate.set_opacity(0.16),
            b.animate.set_opacity(0.22), b_label.animate.set_opacity(0.30),
            self.camera.frame.animate.set_width(13.0).move_to(p(1.6, 2.15)),
            run_time=1.4, rate_func=ease_in_out_cubic,
        )
        self.clock += 1.4
        self.beat(run_time=0.8)
        self.beat(FadeIn(bullets[0], shift=RIGHT * 0.15), run_time=1.2)
        self.beat(FadeIn(bullets[1], shift=RIGHT * 0.15), run_time=1.2)
        self.beat(FadeIn(bullets[2], shift=RIGHT * 0.15), run_time=1.2)
        self.play(
            self.camera.frame.animate.shift(LEFT * 0.08 + DOWN * 0.03),
            run_time=1.5, rate_func=smooth,
        )
        self.clock += 1.5
        self.beat(run_time=1.7)
        end_clock = self.clock
        if end_clock < 80:
            self.wait(80 - end_clock)
            self.clock = 80.0
        if abs(self.clock - 80) > 0.05:
            print(f"WARNING: clock={self.clock:.2f}s, expected 80.00s")

    def beat(self, *anims, run_time: float = 1.0, rate_func=smooth) -> None:
        if anims:
            self.play(*anims, run_time=run_time, rate_func=rate_func)
        else:
            self.wait(run_time)
        self.clock += run_time
