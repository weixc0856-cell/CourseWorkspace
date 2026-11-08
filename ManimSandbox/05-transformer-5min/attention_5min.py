"""Five-minute continuous animation for the Transformer calibration lesson.

The scene is authored against the measured narration timeline (12 segments,
292.38 s).  Each beat consumes exactly the segment's wall-clock span so the
visual changes line up with what the narrator is saying.
"""

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
    FadeOut,
    Indicate,
    LaggedStart,
    Line,
    MoveAlongPath,
    Rectangle,
    ReplacementTransform,
    RoundedRectangle,
    Scene,
    Text,
    VGroup,
    Write,
    config,
    linear,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.scene_checks import enforce  # noqa: E402
from common.design_system import BG, BLUE, INK, MUTED, ORANGE, PURPLE, TEAL  # noqa: E402

config.background_color = BG

TEXT = INK


def label(value: str, size: int = 32, color: str = TEXT) -> Text:
    return Text(value, font="Arial", font_size=size, color=color)


def token_row(words: list[str], y: float = 1.55) -> VGroup:
    boxes = VGroup()
    for word in words:
        box = RoundedRectangle(
            width=1.85, height=0.85, corner_radius=0.1,
            stroke_color=MUTED, stroke_width=2,
        )
        box.add(label(word, 26).move_to(box))
        boxes.add(box)
    boxes.arrange(RIGHT, buff=0.22).move_to(UP * y)
    return boxes


def halo(box) -> Rectangle:
    return Rectangle(
        width=box.width + 0.28, height=box.height + 0.28,
        stroke_color=ORANGE, stroke_width=4,
    ).move_to(box)


def block(name: str, color: str, width: float = 1.7, height: float = 0.95) -> VGroup:
    rect = RoundedRectangle(
        width=width, height=height, corner_radius=0.1,
        stroke_color=color, stroke_width=3,
    )
    rect.add(label(name, 22, color).move_to(rect))
    return rect


def moving_dots(path, count: int = 4) -> VGroup:
    dots = VGroup()
    for index in range(count):
        dot = Rectangle(width=0.09, height=0.09, stroke_width=0, fill_color=ORANGE, fill_opacity=0.85)
        dot.move_to(path.point_from_proportion(index / max(1, count)))
        dots.add(dot)
    return dots


class AttentionFiveMinuteScene(Scene):
    """Twelve beats, one continuous animation."""

    def wait_remaining(self, used: float, duration: float, tail: float = 0.0) -> None:
        remaining = duration - used - tail
        if remaining < 0:
            print(f"[timing] beat overran by {-remaining:.2f}s", flush=True)
        else:
            self.wait(remaining)

    def mark(self, name: str) -> None:
        print(f"[timing] {name}: {self.renderer.time:.3f}", flush=True)

    def fade(self, *mobjects) -> None:
        flat = []

        def walk(mob) -> None:
            if isinstance(mob, VGroup):
                for child in mob:
                    walk(child)
            else:
                flat.append(mob)

        for mob in mobjects:
            walk(mob)
        unique = []
        seen = set()
        for mob in flat:
            if id(mob) not in seen:
                seen.add(id(mob))
                unique.append(mob)
        self.play(*[FadeOut(mob) for mob in unique], run_time=1.0)
        self.remove(*unique)

    def construct(self) -> None:
        # beat durations come from narration.meta.json; each starts at the
        # next segment's start (pauses are kept inside the previous beat).
        beats = [17.72, 35.16, 24.82, 28.13, 26.85, 22.74, 22.04, 23.54, 22.10, 20.02, 24.34, 24.92]

        # ---------------------------------------------------------------- 1
        title = label("Attention Is All You Need", 50).to_edge(UP, buff=0.85)
        subtitle = label("2017 · arXiv:1706.03762", 24, MUTED).next_to(title, DOWN, buff=0.2)
        words = ["The", "animal", "didn't", "cross", "street"]
        tokens = token_row(words)
        target = tokens[1]
        ring = halo(target)
        arcs = VGroup()
        for box in tokens:
            if box is target:
                continue
            arcs.add(
                Arrow(
                    target.get_bottom() + DOWN * 0.05,
                    box.get_bottom() + DOWN * 0.05,
                    buff=0.05, stroke_width=2.2, color=MUTED,
                    max_tip_length_to_length_ratio=0.06,
                )
            )
        used = 0.0
        for anim, rt in (
            (FadeIn(title), 0.8),
            (Write(subtitle), 0.7),
            (LaggedStart(*[Create(box) for box in tokens], lag_ratio=0.12), 2.0),
            (Create(ring), 0.6),
            (LaggedStart(*[Create(arc) for arc in arcs], lag_ratio=0.12), 2.0),
            (ring.animate.set_stroke(width=7), 0.8),
            (ring.animate.set_stroke(width=4), 0.8),
            (arcs.animate.set_color(ORANGE), 1.0),
            (arcs.animate.set_color(MUTED), 1.0),
        ):
            self.play(anim, run_time=rt)
            used += rt
        mid = label("sequence → sequence", 32, MUTED).shift(DOWN * 0.4)
        self.play(
            *[FadeOut(mob) for mob in (*tokens, ring, *arcs)],
            FadeIn(mid),
            run_time=1.2,
        )
        used += 1.2
        self.wait_remaining(used, beats[0], tail=1.0)
        self.mark("beat1")
        self.fade(mid)

        # ---------------------------------------------------------------- 2
        small_title = title.animate.scale(0.55).to_edge(UP, buff=0.6).set_opacity(0.75)
        self.play(small_title, FadeOut(subtitle), run_time=1.2)
        used = 1.2
        source = block("source sentence", BLUE, 2.5, 1.0).shift(LEFT * 4.4 + UP * 1.2)
        target_box = block("target sentence", PURPLE, 2.5, 1.0).shift(RIGHT * 4.4 + UP * 1.2)
        line = Arrow(source.get_right(), target_box.get_left(), buff=0.2, stroke_width=3, color=MUTED)
        self.play(Create(source), Create(target_box), Create(line), run_time=2.0)
        used += 2.0
        rnn = block("RNN", MUTED, 1.9, 1.0).shift(LEFT * 3.4 + DOWN * 0.9)
        loop = Arrow(rnn.get_right(), rnn.get_top(), buff=0.1, stroke_width=2.5, color=MUTED)
        self.play(Create(rnn), Create(loop), run_time=1.2)
        used += 1.2
        cross1 = Line(rnn.get_corner(DOWN + LEFT), rnn.get_corner(UP + RIGHT), color=ORANGE, stroke_width=5)
        self.play(Create(cross1), run_time=0.8)
        used += 0.8
        cnn = VGroup()
        for row in range(2):
            for col in range(3):
                cell = Rectangle(width=0.42, height=0.42, stroke_color=MUTED, stroke_width=1.5)
                cell.move_to(LEFT * 0.1 + RIGHT * col * 0.45 + DOWN * (0.95 + row * 0.45))
                cnn.add(cell)
        cnn_label = label("CNN", 22, MUTED).next_to(cnn, DOWN, buff=0.18)
        self.play(FadeIn(cnn), FadeIn(cnn_label), run_time=1.2)
        used += 1.2
        cross2 = Line(cnn.get_corner(DOWN + LEFT), cnn.get_corner(UP + RIGHT), color=ORANGE, stroke_width=5)
        self.play(Create(cross2), run_time=0.8)
        used += 0.8
        attention = block("attention", ORANGE, 2.4, 1.0).shift(RIGHT * 3.4 + DOWN * 0.9)
        attention_line = Arrow(source.get_bottom(), attention.get_top(), buff=0.15, stroke_width=3, color=ORANGE)
        self.play(FadeIn(attention), Create(attention_line), run_time=1.2)
        used += 1.2
        claim = label("attention alone carries the sequence modelling", 24, MUTED).to_edge(DOWN, buff=0.75)
        self.play(FadeIn(claim), run_time=0.8)
        used += 0.8
        dots = moving_dots(line)
        self.add(dots)
        self.play(
            *[MoveAlongPath(dot, line, rate_func=linear) for dot in dots],
            run_time=10.0,
        )
        used += 10.0
        self.wait_remaining(used, beats[1], tail=1.0)
        self.mark("beat2")
        self.fade(
            source, target_box, line, rnn, loop, cross1, cnn, cnn_label, cross2,
            attention, attention_line, claim, dots, title,
        )
        used = 1.0

        # ---------------------------------------------------------------- 3
        tokens = token_row(words, y=1.8)
        ring = halo(tokens[1])
        spread = VGroup()
        for index, box in enumerate(tokens):
            if box is tokens[1]:
                continue
            spread.add(Arrow(tokens[1].get_top(), box.get_top(), buff=0.08, stroke_width=2, color=TEAL))
        self.play(LaggedStart(*[Create(box) for box in tokens], lag_ratio=0.1), run_time=1.8)
        used = 1.8
        self.play(Create(ring), run_time=0.6)
        used += 0.6
        self.play(LaggedStart(*[Create(arrow) for arrow in spread], lag_ratio=0.12), run_time=2.2)
        used += 2.2
        note = label("every word compares with every other word", 24, MUTED).to_edge(DOWN, buff=0.75)
        self.play(FadeIn(note), run_time=0.8)
        used += 0.8
        dots = moving_dots(spread[0], 3)
        self.add(dots)
        self.play(*[MoveAlongPath(dot, spread[0], rate_func=linear) for dot in dots], run_time=8.0)
        used += 8.0
        self.wait_remaining(used, beats[2], tail=1.0)
        self.mark("beat3")
        self.fade(tokens, ring, spread, note, dots)
        used = 1.0

        # ---------------------------------------------------------------- 4
        tokens = token_row(["The", "animal", "didn't", "cross", "street"], y=2.2)
        target = tokens[1]
        ring = halo(target)
        qkv = VGroup(
            block("Q  what it seeks", BLUE, 3.0, 0.8),
            block("K  what it offers", TEAL, 3.0, 0.8),
            block("V  what it passes on", PURPLE, 3.0, 0.8),
        ).arrange(DOWN, buff=0.3).shift(LEFT * 4.3 + DOWN * 0.8)
        fans = VGroup()
        for item in qkv:
            fans.add(Arrow(target.get_left(), item.get_right(), buff=0.12, stroke_width=2.5, color=MUTED))
        self.play(LaggedStart(*[Create(box) for box in tokens], lag_ratio=0.08), run_time=1.4)
        used = 1.4
        self.play(Create(ring), run_time=0.5)
        used += 0.5
        self.play(
            LaggedStart(*[Create(arrow) for arrow in fans], lag_ratio=0.18),
            LaggedStart(*[FadeIn(item) for item in qkv], lag_ratio=0.18),
            run_time=3.0,
        )
        used += 3.0
        role_note = label("three learned projections from the same token", 24, MUTED).to_edge(DOWN, buff=0.75)
        self.play(FadeIn(role_note), run_time=0.8)
        used += 0.8
        dots = moving_dots(fans[0], 3)
        self.add(dots)
        self.play(*[MoveAlongPath(dot, fans[0], rate_func=linear) for dot in dots], run_time=10.0)
        used += 10.0
        self.wait_remaining(used, beats[3], tail=1.0)
        self.mark("beat4")
        self.fade(tokens, ring, qkv, fans, role_note, dots)
        used = 1.0

        # ---------------------------------------------------------------- 5
        title5 = label("Q · K → scores → weights", 40).to_edge(UP, buff=0.55)
        self.play(FadeIn(title5), run_time=0.8)
        used = 0.8
        scores = [0.18, 0.82, 0.12, 0.38, 0.08]
        bars = VGroup()
        for index, score in enumerate(scores):
            bar = Rectangle(
                width=0.65, height=0.01,
                stroke_width=0, fill_color=ORANGE, fill_opacity=0.8,
            )
            bar.move_to(LEFT * 4.0 + RIGHT * index * 1.6 + DOWN * 2.1, aligned_edge=DOWN)
            bars.add(bar)
        words5 = ["The", "animal", "didn't", "cross", "street"]
        bar_labels = VGroup(*[label(word, 18, MUTED).next_to(bar, DOWN, buff=0.12) for word, bar in zip(words5, bars)])
        self.play(LaggedStart(*[Create(bar) for bar in bars], lag_ratio=0.1), run_time=1.5)
        used += 1.5
        self.play(
            *[bar.animate.stretch_to_fit_height(max(score * 4.8, 0.01), about_edge=DOWN) for bar, score in zip(bars, scores)],
            run_time=3.0,
        )
        used += 3.0
        self.play(FadeIn(bar_labels), run_time=0.8)
        used += 0.8
        score_note = label("query · key similarity", 24, MUTED).to_edge(DOWN, buff=0.75)
        self.play(FadeIn(score_note), run_time=0.7)
        used += 0.7
        total = sum(scores)
        weights = [score / total for score in scores]
        self.play(
            *[bar.animate.stretch_to_fit_height(max(weight * 4.8, 0.01), about_edge=DOWN) for bar, weight in zip(bars, weights)],
            run_time=3.0,
        )
        used += 3.0
        weight_note = label("softmax → weights that sum to 1", 24, MUTED).to_edge(DOWN, buff=0.75)
        self.play(FadeOut(score_note), FadeIn(weight_note), run_time=0.8)
        used += 0.8
        self.play(Indicate(bars, scale_factor=1.04), run_time=2.0)
        used += 2.0
        self.wait_remaining(used, beats[4], tail=1.0)
        self.mark("beat5")
        self.fade(title5, bars, bar_labels, score_note, weight_note)
        used = 1.0

        # ---------------------------------------------------------------- 6
        title6 = label("weighted sum of V", 40).to_edge(UP, buff=0.55)
        vblocks = VGroup()
        for index, weight in enumerate(weights):
            item = block(f"V{index + 1}", PURPLE, 0.9, 0.65).shift(
                LEFT * 5.2 + RIGHT * index * 1.15 + DOWN * 0.6
            )
            item.set_opacity(0.35 + 0.65 * weight)
            vblocks.add(item)
        context = block("new representation", ORANGE, 3.2, 1.0).shift(RIGHT * 4.2 + DOWN * 0.6)
        streams = VGroup()
        for item in vblocks:
            streams.add(Arrow(item.get_right(), context.get_left(), buff=0.1, stroke_width=2.4, color=ORANGE))
        self.play(FadeIn(title6), LaggedStart(*[FadeIn(item) for item in vblocks], lag_ratio=0.1), run_time=1.4)
        used = 1.4
        self.play(LaggedStart(*[Create(arrow) for arrow in streams], lag_ratio=0.1), run_time=2.0)
        used += 2.0
        self.play(FadeIn(context), run_time=1.0)
        used += 1.0
        dots = moving_dots(streams[1], 4)
        self.add(dots)
        self.play(*[MoveAlongPath(dot, streams[1], rate_func=linear) for dot in dots], run_time=8.0)
        used += 8.0
        note6 = label("the output blends information from the words it attended to", 24, MUTED).to_edge(DOWN, buff=0.75)
        self.play(FadeIn(note6), run_time=0.8)
        used += 0.8
        self.play(Indicate(vblocks, scale_factor=1.06), run_time=2.0)
        used += 2.0
        self.wait_remaining(used, beats[5], tail=1.0)
        self.mark("beat6")
        self.fade(title6, vblocks, context, streams, note6, dots)
        used = 1.0

        # ---------------------------------------------------------------- 7
        title7 = label("the separation of roles", 40).to_edge(UP, buff=0.55)
        qk = block("Q · K  decide where to look", BLUE, 5.6, 1.0).shift(UP * 0.7)
        vv = block("V  decides what to bring back", PURPLE, 5.6, 1.0).shift(DOWN * 0.7)
        self.play(FadeIn(title7), FadeIn(qk), run_time=1.2)
        used = 1.2
        self.play(FadeIn(vv), run_time=1.0)
        used += 1.0
        self.play(Indicate(qk, scale_factor=1.04), run_time=2.0)
        used += 2.0
        self.play(Indicate(vv, scale_factor=1.04), run_time=2.0)
        used += 2.0
        note7 = label("each word scores itself against every other word", 24, MUTED).to_edge(DOWN, buff=0.75)
        self.play(FadeIn(note7), run_time=0.8)
        used += 0.8
        self.wait_remaining(used, beats[6], tail=1.0)
        self.mark("beat7")
        self.fade(title7, qk, vv, note7)
        used = 1.0

        # ---------------------------------------------------------------- 8
        title8 = label("Multi-head: several views, one output", 40).to_edge(UP, buff=0.55)
        base = block("self-attention", ORANGE, 3.2, 0.9).shift(LEFT * 4.4)
        heads = VGroup()
        for index in range(3):
            head = VGroup(
                block(f"head {index + 1}", ORANGE, 2.0, 0.55),
                Rectangle(width=2.0, height=0.75, stroke_color=MUTED, stroke_width=1.5),
            ).arrange(DOWN, buff=0.12)
            head.add(label("attention", 16, MUTED).move_to(head[1]))
            head.shift(RIGHT * 0.8 + UP * (1.6 - index * 1.6))
            heads.add(head)
        fan = VGroup(*[Arrow(base.get_right(), head.get_left(), buff=0.1, stroke_width=2.2, color=MUTED) for head in heads])
        self.play(FadeIn(title8), FadeIn(base), run_time=1.2)
        used = 1.2
        self.play(LaggedStart(*[Create(arrow) for arrow in fan], lag_ratio=0.15), run_time=1.8)
        used += 1.8
        self.play(LaggedStart(*[FadeIn(head) for head in heads], lag_ratio=0.15), run_time=2.0)
        used += 2.0
        note8 = label("run several self-attention computations in parallel", 24, MUTED).to_edge(DOWN, buff=0.75)
        self.play(FadeIn(note8), run_time=0.8)
        used += 0.8
        dots = moving_dots(fan[0], 3)
        self.add(dots)
        self.play(*[MoveAlongPath(dot, fan[0], rate_func=linear) for dot in dots], run_time=8.0)
        used += 8.0
        self.wait_remaining(used, beats[7], tail=1.0)
        self.mark("beat8")
        self.fade(title8, base, heads, fan, note8, dots)
        used = 1.0

        # ---------------------------------------------------------------- 9
        title9 = label("each head can emphasise a different relationship", 36).to_edge(UP, buff=0.55)
        words9 = token_row(["The", "animal", "didn't", "cross", "street"], y=1.5)
        arcs9 = VGroup()
        colors = [BLUE, TEAL, PURPLE]
        targets = [0, 2, 4]
        for head_index, color in zip(range(3), colors):
            target_index = targets[head_index]
            arcs9.add(
                Arrow(
                    words9[1].get_top(), words9[target_index].get_top(),
                    buff=0.08, stroke_width=2.2, color=color,
                    max_tip_length_to_length_ratio=0.06,
                )
            )
        self.play(FadeIn(title9), LaggedStart(*[Create(box) for box in words9], lag_ratio=0.1), run_time=1.8)
        used = 1.8
        self.play(LaggedStart(*[Create(arc) for arc in arcs9], lag_ratio=0.2), run_time=2.4)
        used += 2.4
        note9 = label("one head, one relationship pattern", 24, MUTED).to_edge(DOWN, buff=0.75)
        self.play(FadeIn(note9), run_time=0.8)
        used += 0.8
        dots = moving_dots(arcs9[0], 3)
        self.add(dots)
        self.play(*[MoveAlongPath(dot, arcs9[0], rate_func=linear) for dot in dots], run_time=8.0)
        used += 8.0
        self.wait_remaining(used, beats[8], tail=1.0)
        self.mark("beat9")
        self.fade(title9, words9, arcs9, note9, dots)
        used = 1.0

        # --------------------------------------------------------------- 10
        title10 = label("more heads, more relationship patterns", 36).to_edge(UP, buff=0.55)
        lanes = VGroup()
        for index, color in enumerate(colors):
            lane = Rectangle(width=8.0, height=0.45, stroke_color=color, stroke_width=2)
            lane.shift(UP * (1.2 - index * 1.1))
            lanes.add(lane)
            for dot_index in range(6):
                dot = Rectangle(width=0.16, height=0.16, stroke_width=0, fill_color=color, fill_opacity=0.75)
                dot.move_to(lane.get_left() + RIGHT * (0.6 + dot_index * 1.1))
                lanes.add(dot)
        self.play(FadeIn(title10), LaggedStart(*[FadeIn(item) for item in lanes], lag_ratio=0.03), run_time=2.0)
        used = 2.0
        note10 = label("the layer keeps several attention computations alive at once", 24, MUTED).to_edge(DOWN, buff=0.75)
        self.play(FadeIn(note10), run_time=0.8)
        used += 0.8
        self.play(Indicate(lanes, scale_factor=1.02), run_time=3.0)
        used += 3.0
        self.wait_remaining(used, beats[9], tail=1.0)
        self.mark("beat10")
        self.fade(title10, lanes, note10)
        used = 1.0

        # --------------------------------------------------------------- 11
        title11 = label("concatenate, project, combine", 36).to_edge(UP, buff=0.55)
        heads11 = VGroup(*[block(f"head {index + 1}", ORANGE, 1.8, 0.7) for index in range(3)]).arrange(DOWN, buff=0.25).shift(LEFT * 5.4)
        concat = Rectangle(width=0.8, height=3.2, stroke_color=ORANGE, stroke_width=3).shift(LEFT * 2.0)
        mix = block("W_O", ORANGE, 1.5, 1.0).shift(RIGHT * 0.2)
        output = block("output", BLUE, 1.8, 1.0).shift(RIGHT * 3.0)
        merge = VGroup(*[Arrow(head.get_right(), concat.get_left(), buff=0.1, stroke_width=2.2, color=MUTED) for head in heads11])
        self.play(FadeIn(title11), LaggedStart(*[FadeIn(head) for head in heads11], lag_ratio=0.1), run_time=1.6)
        used = 1.6
        self.play(LaggedStart(*[Create(arrow) for arrow in merge], lag_ratio=0.1), run_time=1.8)
        used += 1.8
        self.play(FadeIn(concat), run_time=0.6)
        used += 0.6
        concat_mix = Arrow(concat.get_right(), mix.get_left(), buff=0.1, stroke_width=2.6, color=ORANGE)
        self.play(FadeIn(mix), Create(concat_mix), run_time=1.2)
        used += 1.2
        mix_output = Arrow(mix.get_right(), output.get_left(), buff=0.1, stroke_width=2.6, color=ORANGE)
        self.play(FadeIn(output), Create(mix_output), run_time=1.2)
        used += 1.2
        dots = moving_dots(merge[1], 3)
        self.add(dots)
        self.play(*[MoveAlongPath(dot, merge[1], rate_func=linear) for dot in dots], run_time=8.0)
        used += 8.0
        self.wait_remaining(used, beats[10], tail=1.0)
        self.mark("beat11")
        self.fade(title11, heads11, concat, mix, output, merge, dots, concat_mix, mix_output)
        used = 1.0

        # --------------------------------------------------------------- 12
        title12 = label("the transformer in one picture", 40).to_edge(UP, buff=0.55)
        recap_heads = VGroup(
            *[block(f"head {index + 1}", ORANGE, 1.5, 0.55) for index in range(3)]
        ).arrange(RIGHT, buff=0.35).shift(LEFT * 3.7 + UP * 1.3)
        recap_concat = Rectangle(
            width=0.55, height=1.6, stroke_color=ORANGE, stroke_width=3,
        ).shift(RIGHT * 0.6 + UP * 1.3)
        recap_output = block("output", BLUE, 1.8, 0.9).shift(RIGHT * 3.4 + UP * 1.3)
        recap_merge = Arrow(
            recap_heads.get_right(), recap_concat.get_left(),
            buff=0.08, stroke_width=2.2, color=MUTED,
        )
        recap_final = Arrow(recap_concat.get_right(), recap_output.get_left(), buff=0.08, stroke_width=2.4, color=ORANGE)
        recap_note = label("concatenate + project", 22, MUTED).shift(UP * 0.15)
        line1 = label("heads operate in parallel", 30, TEAL).shift(DOWN * 0.65)
        line2 = label("their outputs are combined", 30, ORANGE).shift(DOWN * 1.35)
        final = label("attention is the core operation", 26, MUTED).shift(DOWN * 2.05)

        self.play(FadeIn(title12), run_time=0.8)
        used = 0.8
        self.play(LaggedStart(*[FadeIn(head) for head in recap_heads], lag_ratio=0.12), run_time=1.4)
        used += 1.4
        self.play(Create(recap_merge), run_time=1.2)
        used += 1.2
        self.play(FadeIn(recap_concat), FadeIn(recap_output), Create(recap_final), run_time=1.2)
        used += 1.2
        self.play(FadeIn(recap_note), run_time=0.7)
        used += 0.7
        self.play(FadeIn(line1), run_time=0.8)
        used += 0.8
        self.play(FadeIn(line2), run_time=0.8)
        used += 0.8
        self.play(FadeIn(final), run_time=0.8)
        used += 0.8
        recap_dots = moving_dots(recap_merge, 3)
        self.add(recap_dots)
        self.play(*[MoveAlongPath(dot, recap_merge, rate_func=linear) for dot in recap_dots], run_time=4.0)
        used += 4.0
        self.play(Indicate(line1, scale_factor=1.04), run_time=2.0)
        used += 2.0
        self.play(Indicate(line2, scale_factor=1.04), run_time=2.0)
        used += 2.0
        self.wait_remaining(used, beats[11], tail=0.85)
        self.mark("beat12")
        self.fade(
            title12, recap_heads, recap_concat, recap_output, recap_merge,
            recap_final, recap_note, line1, line2, final, recap_dots,
        )
        self.mark("end")
        enforce(self)
