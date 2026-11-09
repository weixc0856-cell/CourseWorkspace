"""Five-minute Transformer lesson, authored as timed shots.

Architecture follows the 2-minute attention sample (`06-attention-3b1b`):

* ``MovingCameraScene`` -- the camera is a storytelling device, not a fixed frame.
* one shot per authored visual beat, ~8-12 s, never a bare ``wait`` while the
  narrator is speaking: leftover time is covered by a slow camera move.
* every content animation also carries a 1.4 %/s camera zoom (``play`` override),
  so the frame keeps changing even when only a small dot is moving; measured
  ``freezedetect`` below ~1.2 %/s still reports a frozen frame.
* the picture shares one clock with the voice. Segment starts, durations and the
  page end come from the measured narration
  (``build/05-transformer-5min/narration/narration.meta.json``). Shot boundaries
  inside a segment are authored fractions of that segment.
* every shot ends with ``check_now`` *before* anything is faded out, so
  ``STRICT_LAYOUT=1`` fails the render while the frame is full.

House style (docs/课程视觉风格指南.md, docs/配色规范.md) is kept: paper-white
background, Arial for prose, Computer Modern (``MathTex``) only for formulas,
semantic colours blue=query, teal=key, purple=value, orange=focus.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from manim import (
    BOLD,
    DOWN,
    LEFT,
    MEDIUM,
    ORIGIN,
    PI,
    RIGHT,
    UP,
    Arrow,
    Create,
    CurvedArrow,
    DashedLine,
    Dot,
    FadeIn,
    FadeOut,
    GrowArrow,
    GrowFromCenter,
    Indicate,
    LaggedStart,
    Line,
    ManimColor,
    MathTex,
    MovingCameraScene,
    Rectangle,
    ReplacementTransform,
    RoundedRectangle,
    Square,
    SurroundingRectangle,
    Text,
    Transform,
    ValueTracker,
    VGroup,
    Write,
    always_redraw,
    config,
    interpolate_color,
    linear,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.design_system import (  # noqa: E402
    BG,
    BLUE,
    DIVIDER,
    INK,
    MUTED,
    ORANGE,
    PURPLE,
    SURFACE,
    TEAL,
)
from common.scene_checks import check_now, enforce  # noqa: E402

config.background_color = BG

ROOT = Path(__file__).resolve().parents[2]
LESSON = "05-transformer-5min"
NARRATION_META = ROOT / "build" / LESSON / "narration" / "narration.meta.json"
TIMING_JSON = ROOT / "build" / LESSON / "timing.json"

FRAME_W = float(config.frame_width)
FRAME_H = float(config.frame_height)

TOKENS = ["The", "animal", "didn't", "cross", "street"]
FOCUS = 1

# Fallback clock: measured narration on 2026-11-09 (start, duration) per segment.
FALLBACK_SEGMENTS = [
    (0.00, 17.12),
    (17.72, 34.56),
    (52.88, 24.32),
    (77.70, 27.68),
    (105.83, 26.40),
    (132.68, 22.24),
    (155.42, 21.44),
    (177.46, 23.04),
    (201.00, 21.60),
    (223.10, 19.52),
    (243.12, 23.84),
    (267.46, 24.32),
]
FALLBACK_END = 292.38

# Authored cut points inside each narration segment (fractions of its duration).
SUBDIVISIONS: list[list[float]] = [
    [0.45],
    [0.33, 0.66],
    [0.55],
    [0.40, 0.70],
    [0.40, 0.72],
    [0.55],
    [0.50],
    [0.55],
    [0.55],
    [0.55],
    [0.55],
    [0.50],
]


# ---------------------------------------------------------------- primitives
def label(text: str, size: int = 24, color: str = INK, weight: str = "NORMAL") -> Text:
    return Text(text, font="Arial", font_size=size, color=color, weight=weight)


def heading(text: str, size: int = 36, color: str = INK) -> Text:
    return Text(text, font="Arial", font_size=size, color=color, weight="MEDIUM")


def math(tex: str, size: int = 38, color: str = INK) -> MathTex:
    return MathTex(tex, font_size=size, color=color)


def card(
    text: str,
    color: str = MUTED,
    width: float = 2.2,
    height: float = 0.8,
    size: int = 22,
    fill: str | None = None,
    fill_opacity: float = 0.0,
    stroke: float = 2.4,
) -> RoundedRectangle:
    rect = RoundedRectangle(
        width=width,
        height=height,
        corner_radius=0.10,
        stroke_color=color,
        stroke_width=stroke,
    )
    if fill is not None:
        rect.set_fill(fill, opacity=fill_opacity)
    rect.add(label(text, size, INK).move_to(rect))
    return rect


def token_row(
    words: list[str] | None = None,
    y: float = 1.55,
    width: float = 1.95,
    height: float = 0.85,
    size: int = 26,
    buff: float = 0.22,
) -> VGroup:
    boxes = VGroup()
    for word in words or TOKENS:
        box = RoundedRectangle(
            width=width,
            height=height,
            corner_radius=0.10,
            stroke_color=MUTED,
            stroke_width=2,
            stroke_opacity=0.75,
        )
        box.add(label(word, size, INK).move_to(box))
        boxes.add(box)
    boxes.arrange(RIGHT, buff=buff).move_to([0, y, 0])
    return boxes


def chip(text: str, color: str = MUTED, width: float = 1.1, height: float = 0.5) -> VGroup:
    rect = RoundedRectangle(
        width=width,
        height=height,
        corner_radius=0.08,
        stroke_color=color,
        stroke_width=1.8,
        stroke_opacity=0.8,
    )
    rect.add(label(text, 17, INK).move_to(rect))
    return rect


def ring(mob, color: str = ORANGE, width: float = 3.0, pad: float = 0.13) -> Rectangle:
    box = Rectangle(
        width=mob.width + 2 * pad,
        height=mob.height + 2 * pad,
        stroke_color=color,
        stroke_width=width,
    ).move_to(mob)
    return box


def arrow(start, end, color: str = MUTED, width: float = 2.4, opacity: float = 1.0, buff: float = 0.06) -> Arrow:
    return Arrow(
        start,
        end,
        buff=buff,
        stroke_width=width,
        color=color,
        stroke_opacity=opacity,
        fill_opacity=opacity,
        max_tip_length_to_length_ratio=0.09,
    )


def vector(origin, end, color: str, width: float = 4.4, opacity: float = 1.0) -> Arrow:
    return Arrow(
        origin,
        end,
        buff=0,
        color=color,
        stroke_width=width,
        stroke_opacity=opacity,
        fill_opacity=opacity,
        max_tip_length_to_length_ratio=0.12,
        max_stroke_width_to_length_ratio=80,
    )


def curved(start, end, color: str, rise: float = 0.55, width: float = 2.0, tip: float = 0.14) -> CurvedArrow:
    """Arc whose apex rises ``rise`` units, whether the chord is short or long."""
    start_v = np.array(start, dtype=float)
    end_v = np.array(end, dtype=float)
    chord = float(np.linalg.norm(end_v[:2] - start_v[:2]))
    # CurvedArrow bulges opposite to ArcBetweenPoints, and its sign convention flips
    # with travel direction. Measured: dx>0 needs a negative angle to rise.
    angle = -4 * np.arctan(2 * rise / max(chord, 0.05))
    if end_v[0] < start_v[0]:
        angle = -angle
    return CurvedArrow(
        start_v, end_v, angle=angle, color=color, stroke_width=width, tip_length=tip
    )


def heat(value: float, low: str = SURFACE, high: str = ORANGE) -> str:
    return interpolate_color(ManimColor(low), ManimColor(high), float(value))


def load_bounds() -> tuple[list[float], str]:
    """Absolute shot boundaries, and a human-readable clock source."""
    segments: list[tuple[float, float]] = []
    total = FALLBACK_END
    source = "fallback"
    meta = None
    if NARRATION_META.is_file():
        meta = json.loads(NARRATION_META.read_text(encoding="utf-8"))
    elif TIMING_JSON.is_file():
        meta = json.loads(TIMING_JSON.read_text(encoding="utf-8"))
    if meta:
        source = str(meta.get("source") or "")
        if "segments" in meta:
            raw = meta["segments"]
            if raw and "start_s" in raw[0]:
                segments = [(float(s["start_s"]), float(s["duration_s"])) for s in raw]
            else:
                segments = [(float(s["start"]), float(s["duration"])) for s in raw]
            total = float(meta.get("total") or (segments[-1][0] + segments[-1][1] + 0.6))
            if meta.get("pages"):
                total = float(meta["pages"][-1]["end_s"])
            source = "narration.meta.json"
    if len(segments) != len(SUBDIVISIONS):
        segments = list(FALLBACK_SEGMENTS)
        total = FALLBACK_END
        source = "fallback (segment count mismatch)"
    bounds = [0.0]
    for index, ((start, duration), cuts) in enumerate(zip(segments, SUBDIVISIONS)):
        for cut in cuts:
            bounds.append(round(start + cut * duration, 3))
        # the gap before the next segment belongs to the previous shot
        bounds.append(segments[index + 1][0] if index + 1 < len(segments) else total)
    return bounds, source


class AttentionFiveMinuteScene(MovingCameraScene):
    """Twelve narration segments, twenty-seven timed visual shots."""

    def construct(self) -> None:
        self.bounds, clock = load_bounds()
        print(f"[clock] {clock}: {len(self.bounds) - 1} shots, {self.bounds[-1]:.2f}s", flush=True)
        self.camera.frame.set(width=FRAME_W).move_to(ORIGIN)
        self.remove(self.camera.frame)

        self.title = VGroup()
        self.tokens = VGroup()
        self.cells: list[list[Square]] = []
        self.grid = VGroup()
        self.attn_card = VGroup()
        self.stack = VGroup()
        self.qkv = VGroup()
        self.vectors = VGroup()
        self.weights = VGroup()
        self.context = VGroup()
        self.head_cards = VGroup()
        self.arcs = VGroup()
        self.panels = VGroup()
        self.output = VGroup()

        self.shots = [
            self.shot_1a, self.shot_1b,
            self.shot_2a, self.shot_2b, self.shot_2c,
            self.shot_3a, self.shot_3b,
            self.shot_4a, self.shot_4b, self.shot_4c,
            self.shot_5a, self.shot_5b, self.shot_5c,
            self.shot_6a, self.shot_6b,
            self.shot_7a, self.shot_7b,
            self.shot_8a, self.shot_8b,
            self.shot_9a, self.shot_9b,
            self.shot_10a, self.shot_10b,
            self.shot_11a, self.shot_11b,
            self.shot_12a, self.shot_12b,
        ]
        for index, shot in enumerate(self.shots):
            shot()
            self.sync_to(index + 1)
        enforce(self)

    # ---------- clock and camera ----------
    def sync_to(self, index: int) -> None:
        """Cover leftover narration time with a camera move: the frame never freezes."""
        target = self.bounds[index]
        span = target - self.bounds[index - 1]
        used = self.renderer.time - self.bounds[index - 1]
        print(f"[timing] shot {index:02d}: {used:6.2f}s / {span:6.2f}s", flush=True)
        remaining = target - self.renderer.time
        if remaining > 0.08:
            self.wait(remaining)
        elif remaining < -0.12:
            print(f"[timing] shot {index} overran by {-remaining:.2f}s", flush=True)


    # ---------- motion helpers ----------
    def flow(self, path, seconds: float, count: int = 3, color: str = ORANGE, radius: float = 0.055) -> None:
        """Dots travelling along a path for the whole duration (no static frame)."""
        tracker = ValueTracker(0.0)
        dots = VGroup(
            *[
                always_redraw(
                    lambda off=i / count: Dot(
                        point=path.point_from_proportion((tracker.get_value() + off) % 1.0),
                        radius=radius,
                        color=color,
                        fill_opacity=0.9,
                        stroke_width=0,
                    )
                )
                for i in range(count)
            ]
        )
        self.add(tracker, dots)
        self.play(tracker.animate.set_value(1.0), run_time=seconds, rate_func=linear)
        self.remove(tracker, dots)

    def clear_all(self, run_time: float = 0.5, keep: tuple = ()) -> None:
        content = [
            mob
            for mob in self.mobjects
            if mob is not self.camera.frame and all(mob is not item for item in keep)
        ]
        if content:
            self.play(*[FadeOut(mob) for mob in content], run_time=run_time)

    def heading_at(self, text: str, size: int = 34, y: float = 3.18) -> Text:
        return heading(text, size).move_to([0, y, 0])

    # ================================================================ page 1
    def shot_1a(self) -> None:
        """The paper and its claim."""
        words = VGroup(
            *[
                Text(word, font="Arial", font_size=50, color=INK, weight=MEDIUM)
                for word in ("Attention", "Is", "All", "You", "Need")
            ]
        ).arrange(RIGHT, buff=0.26).move_to([0, 1.15, 0])
        rule = Line([-3.3, 0.35, 0], [3.3, 0.35, 0], color=ORANGE, stroke_width=3)
        source = label("Vaswani et al. · 2017 · arXiv:1706.03762", 22, MUTED).move_to([0, -0.2, 0])
        self.title = VGroup(words, rule, source)

        self.play(LaggedStart(*[FadeIn(w, shift=0.14 * UP) for w in words], lag_ratio=0.12), run_time=2.0)
        self.play(words[0].animate.set_color(ORANGE), run_time=0.8)
        self.play(GrowFromCenter(rule), run_time=0.9)
        self.play(FadeIn(source, shift=0.08 * UP), run_time=0.9)
        self.play(
            *[w.animate.set_opacity(0.35) for w in words[1:]],
            Indicate(words[0], color=ORANGE, scale_factor=1.08),
            run_time=1.2,
        )
        self.play(*[w.animate.set_opacity(1.0) for w in words[1:]], run_time=0.8)
        check_now(self, "1a")

    def shot_1b(self) -> None:
        """Sequence to sequence, and the three candidate mechanisms."""
        title, rule, source = self.title
        self.play(
            title.animate.scale(0.62).move_to([0, 3.25, 0]),
            rule.animate.set_opacity(0.0),
            FadeOut(source),
            run_time=0.9,
        )
        self.title = VGroup(title)

        src = card("source sequence", BLUE, 3.7, 0.85, 19).move_to([-4.1, 1.35, 0])
        dst = card("target sequence", TEAL, 3.7, 0.85, 19).move_to([4.1, 1.35, 0])
        link = arrow(src.get_right(), dst.get_left(), MUTED, 2.6, buff=0.15)
        self.play(FadeIn(src, shift=0.06 * UP), FadeIn(dst, shift=0.06 * UP), Create(link), run_time=1.5)
        self.flow(link, 1.2, count=3, color=ORANGE)

        # recurrence: a chain with a loop
        chain = VGroup(*[Square(0.38, stroke_color=MUTED, stroke_width=1.6) for _ in range(4)])
        chain.arrange(RIGHT, buff=0.34).move_to([-4.2, -1.35, 0])
        chain_links = VGroup(
            *[arrow(chain[i].get_right(), chain[i + 1].get_left(), MUTED, 1.6, buff=0.03) for i in range(3)]
        )
        loop = CurvedArrow(
            chain[2].get_top() + 0.18 * UP,
            chain[1].get_top() + 0.18 * UP,
            angle=-PI / 1.6,
            color=MUTED,
            stroke_width=1.6,
            tip_length=0.12,
        )
        recurrence = VGroup(chain, chain_links, loop)
        recurrence_label = label("recurrence", 18, MUTED).move_to([-4.2, -1.98, 0])

        # convolution: a 3x3 filter grid
        conv = VGroup()
        for row in range(3):
            for col in range(3):
                cell = Square(0.34, stroke_color=MUTED, stroke_width=1.4)
                cell.move_to([(col - 1) * 0.36, (1 - row) * 0.36 - 1.35, 0])
                conv.add(cell)
        conv_label = label("convolution", 18, MUTED).move_to([0, -1.98, 0])

        # attention: a hub with radiating links
        hub = VGroup(
            Square(0.44, stroke_color=ORANGE, stroke_width=2.4),
            *[
                Line(ORIGIN, 0.62 * np.array([np.cos(a), np.sin(a), 0]), stroke_color=ORANGE, stroke_width=1.8)
                for a in np.linspace(0, 2 * PI, 7)[:-1]
            ],
        ).move_to([4.2, -1.35, 0])
        attention_label = label("attention", 18, ORANGE).move_to([5.55, -1.2, 0])

        self.play(
            LaggedStart(
                Create(recurrence), Create(conv), FadeIn(hub),
                lag_ratio=0.18,
                run_time=2.0,
            ),
            FadeIn(recurrence_label), FadeIn(conv_label), FadeIn(attention_label),
        )

        cross_r = Line(
            chain.get_corner(DOWN + LEFT) + 0.12 * DOWN + 0.12 * LEFT,
            chain.get_corner(UP + RIGHT) + 0.12 * UP + 0.12 * RIGHT,
            color="#C75B55", stroke_width=4,
        )
        cross_c = Line(
            conv.get_corner(DOWN + LEFT), conv.get_corner(UP + RIGHT),
            color="#C75B55", stroke_width=4,
        )
        self.play(Create(cross_r), run_time=0.6)
        self.play(Create(cross_c), run_time=0.6)
        self.play(
            recurrence.animate.set_opacity(0.30),
            recurrence_label.animate.set_opacity(0.35),
            cross_r.animate.set_opacity(0.55),
            conv.animate.set_opacity(0.30),
            conv_label.animate.set_opacity(0.35),
            cross_c.animate.set_opacity(0.55),
            run_time=1.0,
        )
        glow = ring(hub, ORANGE, 2.4, 0.12)
        self.play(Create(glow), Indicate(hub, color=ORANGE, scale_factor=1.15), run_time=1.2)
        check_now(self, "1b")
        self.scene_parts = VGroup(src, dst, link, recurrence, recurrence_label, conv, conv_label,
                                  hub, attention_label, cross_r, cross_c, glow)

    def shot_2a(self) -> None:
        """Attention becomes the central mechanism."""
        parts = self.scene_parts
        src, dst, link = parts[0], parts[1], parts[2]
        recurrence, recurrence_label = parts[3], parts[4]
        conv, conv_label = parts[5], parts[6]
        hub, attention_label = parts[7], parts[8]
        cross_r, cross_c, glow = parts[9], parts[10], parts[11]

        self.play(
            FadeOut(src), FadeOut(dst), FadeOut(link),
            recurrence.animate.scale(0.62).move_to([-5.4, -1.5, 0]).set_opacity(0.22),
            recurrence_label.animate.scale(0.8).move_to([-5.4, -1.96, 0]).set_opacity(0.3),
            conv.animate.scale(0.62).move_to([5.4, -1.5, 0]).set_opacity(0.22),
            conv_label.animate.scale(0.8).move_to([5.4, -1.96, 0]).set_opacity(0.3),
            FadeOut(cross_r), FadeOut(cross_c),
            run_time=1.6,
        )

        big_hub = VGroup(
            Square(0.66, stroke_color=ORANGE, stroke_width=3),
            *[
                Line(ORIGIN, 0.92 * np.array([np.cos(a), np.sin(a), 0]), stroke_color=ORANGE, stroke_width=2.2)
                for a in np.linspace(0, 2 * PI, 9)[:-1]
            ],
        ).move_to([0, 0.45, 0])
        big_glow = ring(big_hub, ORANGE, 2.0, 0.10)
        self.play(
            ReplacementTransform(hub, big_hub),
            ReplacementTransform(glow, big_glow),
            attention_label.animate.scale(1.2).move_to([0, -1.15, 0]),
            run_time=1.8,
        )

        words = VGroup(*[chip(word, MUTED, 1.15, 0.5) for word in TOKENS])
        words.arrange(RIGHT, buff=0.20).move_to([0, 2.55, 0])
        fan = VGroup(
            *[
                arrow(w.get_bottom(), np.array([(index - 2) * 0.26, 1.44, 0.0]), MUTED, 1.8, buff=0.05)
                for index, w in enumerate(words)
            ]
        )
        self.play(LaggedStart(*[FadeIn(w, shift=0.08 * DOWN) for w in words], lag_ratio=0.12), run_time=1.4)
        self.play(LaggedStart(*[Create(a) for a in fan], lag_ratio=0.12), run_time=1.6)
        self.flow(fan[2], 2.2, count=3, color=ORANGE)
        self.play(
            LaggedStart(*[Indicate(a, color=ORANGE, scale_factor=1.03) for a in fan], lag_ratio=0.15),
            run_time=2.2,
        )
        check_now(self, "2a")

        self.attn_card = VGroup(big_hub, big_glow, words, fan, attention_label)
        self.dim_parts = VGroup(recurrence, recurrence_label, conv, conv_label)

    def shot_2b(self) -> None:
        """Attention carries the work in every layer."""
        card_hub, big_glow, words, fan, attention_label = self.attn_card
        self.play(
            FadeOut(fan), FadeOut(words), FadeOut(card_hub),
            FadeOut(big_glow), FadeOut(attention_label),
            run_time=1.0,
        )

        self.stack = VGroup()
        for index in range(6):
            layer = RoundedRectangle(
                width=3.8, height=0.56, corner_radius=0.08,
                stroke_color=MUTED, stroke_width=1.4, stroke_opacity=0.55,
            ).move_to([0, 2.45 - index * 0.74, 0])
            bar = Rectangle(
                width=1.05, height=0.24, stroke_width=0,
                fill_color=ORANGE, fill_opacity=0.85,
            ).move_to([layer.get_right()[0] - 0.72, layer.get_center()[1], 0])
            bar.add(label("attention", 15, BG).move_to(bar))
            layer.add(bar)
            layer.add(label(f"layer {index + 1}", 16, MUTED).move_to([layer.get_left()[0] + 0.72, layer.get_center()[1], 0]))
            self.stack.add(layer)

        self.play(LaggedStart(*[FadeIn(layer, shift=0.10 * LEFT) for layer in self.stack], lag_ratio=0.14), run_time=2.6)

        rail = Line(self.stack[0].get_top(), self.stack[-1].get_bottom(), color=MUTED, stroke_width=1.4)
        self.play(Create(rail), run_time=0.6)
        self.flow(rail, 4.2, count=3, color=BLUE, radius=0.06)

        self.play(
            LaggedStart(*[Indicate(layer[0], color=ORANGE, scale_factor=1.05) for layer in self.stack], lag_ratio=0.12),
            run_time=1.6,
        )
        self.play(Indicate(VGroup(*[layer[0] for layer in self.stack]), color=ORANGE, scale_factor=1.04), run_time=1.2)
        check_now(self, "2b")

    def shot_2c(self) -> None:
        """Not a loop, not a filter: attention is the core operation."""
        self.play(FadeOut(self.dim_parts), run_time=0.8)

        # the same operation sits in every layer: light the strips in order
        self.play(
            LaggedStart(*[Indicate(layer[0], color=ORANGE, scale_factor=1.06) for layer in self.stack], lag_ratio=0.16),
            run_time=4.2,
        )

        # the two rejected alternatives come back into the argument
        loop = CurvedArrow([-5.9, -0.5, 0], [-4.6, -0.1, 0], angle=-PI / 1.8, color=MUTED, stroke_width=1.8, tip_length=0.12)
        conv = VGroup(*[Square(0.24, stroke_color=MUTED, stroke_width=1.1) for _ in range(9)])
        conv.arrange_in_grid(3, 3, buff=0.05).move_to([5.3, -0.35, 0])
        loop_lab = label("recurrence", 16, MUTED).next_to(loop, DOWN, buff=0.10)
        conv_lab = label("convolution", 16, MUTED).next_to(conv, DOWN, buff=0.10)
        self.play(FadeIn(loop), FadeIn(loop_lab), run_time=0.8)
        self.play(FadeIn(conv), FadeIn(conv_lab), run_time=0.8)

        slash_l = Line(loop.get_corner(DOWN + LEFT), loop.get_corner(UP + RIGHT), color="#C75B55", stroke_width=3)
        slash_c = Line(conv.get_corner(DOWN + LEFT), conv.get_corner(UP + RIGHT), color="#C75B55", stroke_width=3)
        self.play(Create(slash_l), Create(slash_c), run_time=1.0)
        self.play(
            FadeOut(loop), FadeOut(conv), FadeOut(loop_lab), FadeOut(conv_lab),
            FadeOut(slash_l), FadeOut(slash_c),
            run_time=1.2,
        )
        self.play(
            Indicate(VGroup(*[layer[0] for layer in self.stack]), color=ORANGE, scale_factor=1.05),
            run_time=3.0,
        )
        check_now(self, "2c")

    # ================================================================ page 2
    def shot_3a(self) -> None:
        """Every word against every other word."""
        self.clear_all(0.5)
        title = self.heading_at("every word against every other word", 34)
        self.play(FadeIn(title, shift=0.1 * DOWN), run_time=0.9)

        self.tokens = token_row(TOKENS, y=1.95, width=2.05, height=0.92, size=27)
        self.play(LaggedStart(*[FadeIn(box, shift=0.05 * UP) for box in self.tokens], lag_ratio=0.10), run_time=1.2)
        self.focus_ring = ring(self.tokens[FOCUS], ORANGE, 3.0, 0.12)
        self.play(Create(self.focus_ring), run_time=0.6)

        arcs = VGroup()
        for index, box in enumerate(self.tokens):
            if index == FOCUS:
                continue
            arcs.add(
                curved(box.get_top() + 0.08 * UP, self.tokens[FOCUS].get_top() + 0.08 * RIGHT, TEAL, rise=0.52, width=2.0)
            )
        self.play(LaggedStart(*[Create(arc) for arc in arcs], lag_ratio=0.16), run_time=1.6)
        self.play(FadeOut(arcs), run_time=0.7)

        # pairwise grid
        self.grid = VGroup()
        self.cells = []
        for row in range(5):
            line = []
            for col in range(5):
                cell = Square(
                    0.64,
                    stroke_color=MUTED,
                    stroke_width=0.9,
                    stroke_opacity=0.6,
                    fill_color=SURFACE,
                    fill_opacity=0.55,
                ).move_to([(col - 2) * 0.69, -0.35 + (2 - row) * 0.69, 0])
                line.append(cell)
                self.grid.add(cell)
            self.cells.append(line)
        rows = VGroup(
            *[label(TOKENS[i], 15, MUTED).next_to(self.cells[i][0], LEFT, buff=0.12) for i in range(5)]
        )
        self.play(
            LaggedStart(
                *[FadeIn(self.cells[i][j], scale=0.9) for i in range(5) for j in range(5)],
                lag_ratio=0.025,
                run_time=2.2,
            ),
            FadeIn(rows),
        )
        row_box = SurroundingRectangle(VGroup(*self.cells[FOCUS]), color=ORANGE, buff=0.03, stroke_width=2.0)
        self.play(Create(row_box), Indicate(self.cells[FOCUS][FOCUS], color=ORANGE, scale_factor=1.2), run_time=1.0)
        self.play(
            LaggedStart(
                *[Indicate(VGroup(*self.cells[row]), color=ORANGE, scale_factor=1.02) for row in range(5)],
                lag_ratio=0.2,
            ),
            run_time=1.5,
        )
        col_box = SurroundingRectangle(
            VGroup(*[self.cells[row][FOCUS] for row in range(5)]), color=TEAL, buff=0.03, stroke_width=1.8
        )
        self.play(Create(col_box), run_time=1.0)
        self.play(Indicate(self.cells[FOCUS][FOCUS], color=ORANGE, scale_factor=1.2), run_time=1.0)
        check_now(self, "3a")
        self.grid_extras = VGroup(rows, row_box, col_box, title)

    def shot_3b(self) -> None:
        """The comparison is built from three learned projections."""
        rows, row_box, col_box, title = self.grid_extras
        self.play(FadeOut(row_box), FadeOut(col_box), FadeOut(self.focus_ring), run_time=0.6)
        self.play(
            self.grid.animate.scale(0.55).move_to([-4.6, -1.9, 0]).set_opacity(0.35),
            FadeOut(rows), FadeOut(title),
            run_time=1.2,
        )

        self.qkv = VGroup(
            card("query", BLUE, 2.2, 0.78, 21),
            card("key", TEAL, 2.2, 0.78, 21),
            card("value", PURPLE, 2.2, 0.78, 21),
        ).arrange(RIGHT, buff=0.5).move_to([0.6, -1.55, 0])
        source = self.tokens[FOCUS]
        fans = VGroup(
            *[arrow(source.get_bottom(), item.get_top(), MUTED, 2.0, buff=0.08) for item in self.qkv]
        )
        self.play(LaggedStart(*[Create(a) for a in fans], lag_ratio=0.18), run_time=2.6)
        self.play(LaggedStart(*[FadeIn(item, shift=0.08 * UP) for item in self.qkv], lag_ratio=0.18), run_time=2.6)
        self.qkv_fans = fans
        self.play(
            LaggedStart(*[Indicate(item, color=ORANGE, scale_factor=1.05) for item in self.qkv], lag_ratio=0.2),
            run_time=1.8,
        )
        self.play(Indicate(source, color=ORANGE, scale_factor=1.1), run_time=2.0)
        check_now(self, "3b")

    def shot_4a(self) -> None:
        """Every word emits a query, a key and a value."""
        self.play(
            FadeOut(self.qkv[0]), FadeOut(self.qkv[1]), FadeOut(self.qkv[2]),
            FadeOut(self.qkv_fans), FadeOut(self.grid),
            run_time=0.8,
        )

        self.play(
            LaggedStart(
                *[box.animate.move_to([box.get_center()[0], 2.35, 0]) for box in self.tokens],
                lag_ratio=0.05,
                run_time=1.0,
            )
        )
        lanes = VGroup()
        lane_labels = VGroup()
        for text, color, y in (("Q", BLUE, 0.65), ("K", TEAL, -0.30), ("V", PURPLE, -1.25)):
            lane = Line([-5.35, y, 0], [5.35, y, 0], color=color, stroke_width=1.6, stroke_opacity=0.55)
            lanes.add(lane)
            lane_labels.add(label(text, 24, color, BOLD).move_to([-6.0, y, 0]))
        self.play(LaggedStart(*[Create(lane) for lane in lanes], lag_ratio=0.2), run_time=1.4)
        self.play(FadeIn(lane_labels), run_time=0.8)

        drops = VGroup()
        for row_index, (lane, color) in enumerate(zip(lanes, (BLUE, TEAL, PURPLE))):
            for col_index, box in enumerate(self.tokens):
                drop = Dot(
                    point=[box.get_center()[0], lane.get_center()[1], 0],
                    radius=0.075,
                    color=color,
                    fill_opacity=0.9,
                    stroke_width=0,
                )
                drops.add(drop)
        self.play(LaggedStart(*[FadeIn(d, scale=0.6) for d in drops], lag_ratio=0.035), run_time=3.2)
        self.play(
            LaggedStart(*[Indicate(lab, color=lab.get_color(), scale_factor=1.12) for lab in lane_labels], lag_ratio=0.25),
            run_time=1.5,
        )
        self.play(
            LaggedStart(
                *[
                    Indicate(VGroup(*drops[index * 5:(index + 1) * 5]), color=color, scale_factor=1.15)
                    for index, color in enumerate((BLUE, TEAL, PURPLE))
                ],
                lag_ratio=0.3,
            ),
            run_time=1.8,
        )
        check_now(self, "4a")
        self.lanes = lanes
        self.drops = drops
        self.lane_labels = lane_labels

    def shot_4b(self) -> None:
        """What each of the three vectors means."""
        self.play(
            FadeOut(self.lanes), FadeOut(self.drops), FadeOut(self.lane_labels),
            self.tokens.animate.scale(0.62).move_to([0, 3.08, 0]),
            run_time=0.9,
        )
        self.sentence = self.tokens

        origin = np.array([-4.4, 0.2, 0.0])
        q_end = origin + 3.2 * np.array([np.cos(np.deg2rad(45)), np.sin(np.deg2rad(45)), 0])
        k_end = origin + 3.2 * np.array([np.cos(np.deg2rad(-10)), np.sin(np.deg2rad(-10)), 0])
        v_end = origin + 3.2 * np.array([np.cos(np.deg2rad(-40)), np.sin(np.deg2rad(-40)), 0])
        q_arrow = vector(origin, q_end, BLUE, 5.2)
        k_arrow = vector(origin, k_end, TEAL, 5.2)
        v_arrow = vector(origin, v_end, PURPLE, 5.2)
        q_lab = math(r"\vec{q}", 40, BLUE).next_to(q_end, RIGHT, buff=0.14)
        k_lab = math(r"\vec{k}", 40, TEAL).next_to(k_end, RIGHT, buff=0.14)
        v_lab = math(r"\vec{v}", 40, PURPLE).next_to(v_end, RIGHT, buff=0.14)
        self.vectors = VGroup(q_arrow, k_arrow, v_arrow, q_lab, k_lab, v_lab)
        self.play(
            LaggedStart(
                GrowArrow(q_arrow), FadeIn(q_lab),
                GrowArrow(k_arrow), FadeIn(k_lab),
                GrowArrow(v_arrow), FadeIn(v_lab),
                lag_ratio=0.25,
                run_time=2.4,
            )
        )

        notes = VGroup(
            label("what this word is looking for", 21, MUTED).move_to([2.2, 1.35, 0]),
            label("what this word offers to others", 21, MUTED).move_to([2.2, 0.15, 0]),
            label("the information that is passed on", 21, MUTED).move_to([2.2, -1.15, 0]),
        )
        for note, vec in zip(notes, (q_arrow, k_arrow, v_arrow)):
            self.play(Indicate(vec, color=vec.get_color(), scale_factor=1.05), FadeIn(note, shift=0.06 * UP), run_time=1.3)
        self.play(Indicate(self.vectors, color=INK, scale_factor=1.03), run_time=1.0)
        check_now(self, "4b")
        self.role_notes = notes

    def shot_4c(self) -> None:
        """The projections are learned, so relevance can be adjusted."""
        self.play(FadeOut(self.role_notes), FadeOut(self.vectors), run_time=0.6)

        token = chip("animal", ORANGE, 1.5, 0.55).move_to([-5.6, 0.1, 0])
        matrices = VGroup(
            math(r"W_Q", 30, BLUE), math(r"W_K", 30, TEAL), math(r"W_V", 30, PURPLE),
        ).arrange(DOWN, buff=0.72).move_to([-3.6, 0.1, 0])
        base = np.array([-2.4, 0.1, 0.0])
        feeds = VGroup(
            *[arrow(token.get_right(), m.get_left(), MUTED, 1.6, buff=0.10) for m in matrices]
        )
        self.play(FadeIn(token), LaggedStart(*[FadeIn(m) for m in matrices], lag_ratio=0.15), run_time=1.0)
        self.play(LaggedStart(*[Create(a) for a in feeds], lag_ratio=0.12), run_time=1.0)

        # projection directions that can be re-aimed: the "learned" part
        angle = ValueTracker(0.0)

        def q_dir():
            a = np.deg2rad(32 + 16 * angle.get_value())
            return base + 2.3 * np.array([np.cos(a), np.sin(a), 0])

        def k_dir():
            a = np.deg2rad(-18 - 12 * angle.get_value())
            return base + 2.3 * np.array([np.cos(a), np.sin(a), 0])

        def v_dir():
            a = np.deg2rad(-55 + 14 * angle.get_value())
            return base + 2.3 * np.array([np.cos(a), np.sin(a), 0])

        q_arrow = always_redraw(lambda: vector(base, q_dir(), BLUE, 4.2))
        k_arrow = always_redraw(lambda: vector(base, k_dir(), TEAL, 4.2))
        v_arrow = always_redraw(lambda: vector(base, v_dir(), PURPLE, 4.2))
        aim = VGroup(
            *[arrow(m.get_right(), base, MUTED, 1.4, buff=0.04) for m in matrices]
        )
        self.play(LaggedStart(*[Create(a) for a in aim], lag_ratio=0.15), run_time=0.8)
        self.add(angle, q_arrow, k_arrow, v_arrow)
        self.play(angle.animate.set_value(1.0), run_time=2.0)
        self.play(angle.animate.set_value(0.0), run_time=1.0)

        self.play(
            LaggedStart(*[Indicate(m, color=m.get_color(), scale_factor=1.1) for m in matrices], lag_ratio=0.15),
            run_time=1.6,
        )
        static = VGroup(
            vector(base, q_dir(), BLUE, 4.2),
            vector(base, k_dir(), TEAL, 4.2),
            vector(base, v_dir(), PURPLE, 4.2),
        )
        self.remove(angle, q_arrow, k_arrow, v_arrow)
        self.add(static)
        self.play(Indicate(static, color=INK, scale_factor=1.04), run_time=0.7)
        check_now(self, "4c")
        self.learned_parts = VGroup(token, matrices, feeds, aim, static)

    # ================================================================ page 2 · scoring
    def shot_5a(self) -> None:
        """A query scored against a key."""
        self.clear_all(0.5, keep=(self.sentence,))

        plane = Line([-6.2, 0, 0], [6.2, 0, 0], color=DIVIDER, stroke_width=1)
        self.play(FadeIn(plane), run_time=0.4)

        origin = np.array([-3.4, -1.5, 0.0])
        q_vec = 3.1 * np.array([np.cos(np.deg2rad(35)), np.sin(np.deg2rad(35)), 0])
        q_end = origin + q_vec
        q_arrow = vector(origin, q_end, BLUE, 5.0)
        q_lab = math(r"\vec{q}", 40, BLUE).next_to(q_end, RIGHT, buff=0.15)
        self.play(GrowArrow(q_arrow), FadeIn(q_lab), run_time=1.0)

        angle = ValueTracker(np.deg2rad(-4))
        k_len = 2.7

        def k_end():
            a = angle.get_value()
            return origin + k_len * np.array([np.cos(a), np.sin(a), 0.0])

        k_arrow = always_redraw(lambda: vector(origin, k_end(), TEAL, 4.6))
        k_lab = always_redraw(lambda: math(r"\vec{k}", 38, TEAL).next_to(k_end(), RIGHT, buff=0.12))

        def foot():
            kv = k_end() - origin
            u = kv / np.linalg.norm(kv)
            return origin + np.dot(q_vec, u) * u

        shadow = always_redraw(lambda: Line(origin, foot(), color=ORANGE, stroke_width=11, stroke_opacity=0.25))
        drop = always_redraw(
            lambda: DashedLine(q_end, foot(), color=ORANGE, stroke_width=1.8, dash_length=0.1)
        )
        self.play(FadeIn(k_arrow), FadeIn(k_lab), FadeIn(shadow), FadeIn(drop), run_time=0.8)

        formula = math(r"\vec{q}\cdot\vec{k}\;=\;|\vec{q}|\,|\vec{k}|\cos\theta", 34).move_to([3.3, 2.4, 0])
        self.play(FadeIn(formula, scale=0.98), run_time=1.0)
        scaled = math(r"\text{scaled: }\frac{\vec{q}\cdot\vec{k}}{\sqrt{d_k}}", 26, MUTED).move_to([3.3, 1.62, 0])
        self.play(FadeIn(scaled, shift=0.05 * UP), run_time=0.8)

        readout = VGroup(
            math(r"\vec{q}\cdot\vec{k}=", 30),
            math(f"{score_at(q_vec, k_len, angle.get_value()):.1f}", 30, ORANGE),
        ).arrange(RIGHT, buff=0.1).move_to([3.4, -1.25, 0])

        self.play(FadeIn(readout), run_time=0.4)
        steps = [0.35, 0.62, 0.86, 1.0]
        for step_value in steps:
            target = np.deg2rad(-4 + 44 * step_value)
            number = math(f"{score_at(q_vec, k_len, target):.1f}", 30, ORANGE).move_to(readout[1])
            self.play(
                angle.animate.set_value(target),
                Transform(readout[1], number),
                run_time=0.85,
            )
        self.play(Indicate(readout[1], color=ORANGE, scale_factor=1.25), run_time=1.1)
        check_now(self, "5a")

    def shot_5b(self) -> None:
        """Repeat the comparison for every word: a full score matrix."""
        self.clear_all(0.5, keep=(self.sentence,))

        title = self.heading_at("one row of scores per word", 32)
        self.play(FadeIn(title, shift=0.1 * DOWN), run_time=0.9)

        # the same sentence strip expands back into the matrix headers
        self.tokens = self.sentence
        self.play(self.tokens.animate.scale(1 / 0.62).move_to([0, 2.40, 0]), run_time=1.0)

        rng = np.random.default_rng(11)
        scores = rng.uniform(0.05, 1.0, (5, 5))
        scores[FOCUS] = [0.16, 0.86, 0.12, 0.44, 0.22]
        for row in range(5):
            scores[row][row] = max(scores[row][row], 0.55)
        self.scores = scores

        self.cells = []
        self.grid = VGroup()
        for row in range(5):
            line = []
            for col in range(5):
                value = float(scores[row][col])
                cell = Square(
                    0.64,
                    stroke_color=MUTED,
                    stroke_width=0.8,
                    stroke_opacity=0.35,
                ).move_to([(col - 2) * 0.69, -0.35 + (2 - row) * 0.69, 0])
                cell.set_fill(heat(value), opacity=0.15 + 0.85 * value)
                line.append(cell)
                self.grid.add(cell)
            self.cells.append(line)

        rows = VGroup(
            *[label(TOKENS[i], 15, MUTED).next_to(self.cells[i][0], LEFT, buff=0.12) for i in range(5)]
        )

        self.play(
            LaggedStart(
                *[FadeIn(self.cells[i][j], scale=0.9) for i in range(5) for j in range(5)],
                lag_ratio=0.022,
                run_time=2.2,
            ),
            FadeIn(rows),
        )
        row_box = SurroundingRectangle(VGroup(*self.cells[FOCUS]), color=ORANGE, buff=0.035, stroke_width=2.0)
        self.play(Create(row_box), run_time=0.8)
        self.play(
            LaggedStart(
                *[Indicate(VGroup(*self.cells[row]), color=ORANGE, scale_factor=1.02) for row in range(5)],
                lag_ratio=0.2,
            ),
            run_time=1.6,
        )
        check_now(self, "5b")
        self.score_extras = VGroup(title, rows, row_box)

    def shot_5c(self) -> None:
        """Normalise the scores into weights."""
        title, rows, row_box = self.score_extras
        self.play(FadeOut(row_box), run_time=0.5)
        others = [cell for index, row in enumerate(self.cells) if index != FOCUS for cell in row]
        self.play(
            FadeOut(title), FadeOut(rows),
            *[FadeOut(cell) for cell in others],
            run_time=0.6,
        )

        base = -0.95
        xs = [-4.4, -2.2, 0.0, 2.2, 4.4]
        raw = self.scores[FOCUS]
        weights = np.exp(raw * 2.6)
        weights = weights / weights.sum()
        bars = VGroup()
        bar_labels = VGroup()
        for x, token in zip(xs, TOKENS):
            bar = Rectangle(width=0.90, height=0.02, stroke_width=0, fill_color=ORANGE, fill_opacity=0.85)
            bar.move_to([x, base + 0.01, 0], aligned_edge=DOWN)
            bars.add(bar)
            bar_labels.add(label(token, 17, MUTED).move_to([x, base - 0.30, 0]))
        row_cells = VGroup(*self.cells[FOCUS])
        self.play(
            ReplacementTransform(row_cells, bars), FadeIn(bar_labels), FadeOut(self.tokens),
            run_time=1.2,
        )

        grown = VGroup()
        for x, value in zip(xs, raw):
            height = max(0.06, float(value) * 2.6)
            bar = Rectangle(width=0.72, height=height, stroke_width=0, fill_color=ORANGE, fill_opacity=0.55)
            bar.move_to([x, base + height / 2, 0])
            grown.add(bar)
        self.play(Transform(bars, grown), run_time=1.4)

        normalised = VGroup()
        for x, value in zip(xs, weights):
            height = max(0.06, float(value) * 3.3)
            bar = Rectangle(width=0.72, height=height, stroke_width=0, fill_color=ORANGE, fill_opacity=0.9)
            bar.move_to([x, base + height / 2, 0])
            normalised.add(bar)
        self.play(Transform(bars, normalised), run_time=1.6)

        formula = math(
            r"\mathrm{softmax}(\vec{s})_i=\frac{e^{s_i}}{\sum_j e^{s_j}}", 32
        ).move_to([3.5, 2.2, 0])
        self.play(FadeIn(formula, scale=0.98), run_time=1.0)

        top = int(np.argmax(weights))
        pct = MathTex(rf"{weights[top]*100:.0f}\%", font_size=26, color=ORANGE)
        pct.next_to(bars[top], UP, buff=0.1)
        self.play(FadeIn(pct, shift=0.06 * UP), run_time=0.5)
        self.play(
            LaggedStart(*[Indicate(bar, color=ORANGE, scale_factor=1.06) for bar in bars], lag_ratio=0.1),
            run_time=1.1,
        )
        check_now(self, "5c")
        self.weight_bars = bars
        self.weight_formula = formula
        self.weight_pct = pct

    # ================================================================ page 2 · mixing
    def shot_6a(self) -> None:
        """Weighted sum of value vectors."""
        self.clear_all(0.5)

        title = self.heading_at("weighted sum of the value vectors", 32)
        self.play(FadeIn(title, shift=0.1 * DOWN), run_time=0.9)

        origin = np.array([-4.2, -1.35, 0.0])
        angles = np.linspace(18, 162, 5)
        full = VGroup()
        for token, angle, weight in zip(TOKENS, angles, self.weights_vector()):
            a = np.deg2rad(angle)
            tip = origin + 2.7 * np.array([np.cos(a), np.sin(a), 0.0])
            full.add(vector(origin, tip, PURPLE, 3.2, opacity=0.40 + 0.55 * float(weight)))
        self.play(LaggedStart(*[GrowArrow(a) for a in full], lag_ratio=0.12), run_time=1.6)

        cursor = origin.copy()
        chain = VGroup()
        for angle, weight in zip(angles, self.weights_vector()):
            a = np.deg2rad(angle)
            step = 4.6 * float(weight) * np.array([np.cos(a), np.sin(a), 0.0])
            seg = vector(cursor, cursor + step, ORANGE, 3.6)
            chain.add(seg)
            cursor = cursor + step
        self.play(LaggedStart(*[GrowArrow(s) for s in chain], lag_ratio=0.28), run_time=3.4)

        context = vector(origin, cursor, INK, 6.0)
        context_label = label("context", 24, INK).next_to(cursor, UP, buff=0.20)
        self.play(GrowArrow(context), FadeIn(context_label), run_time=1.2)

        formula = math(r"\text{context}=\sum_i w_i\,\vec{v}_i", 34).move_to([3.5, 2.2, 0])
        self.play(FadeIn(formula, scale=0.98), run_time=1.4)

        self.play(
            LaggedStart(*[Indicate(seg, color=ORANGE, scale_factor=1.03) for seg in chain], lag_ratio=0.15),
            run_time=1.5,
        )
        check_now(self, "6a")
        self.context = VGroup(context, context_label, title, formula)
        self.mix_parts = VGroup(full, chain)

    def weights_vector(self) -> np.ndarray:
        raw = self.scores[FOCUS]
        weights = np.exp(raw * 2.6)
        return weights / weights.sum()

    def shot_6b(self) -> None:
        """The new representation is a blend, built in one layer."""
        self.play(
            FadeOut(self.context[1]), FadeOut(self.context[2]),
            FadeOut(self.context[3]), FadeOut(self.mix_parts),
            run_time=0.6,
        )
        context = self.context[0]
        self.play(context.animate.scale(0.55).move_to([-3.0, 0.1, 0]), run_time=1.0)

        self.tokens = token_row(TOKENS, y=1.9, width=1.85, height=0.8, size=24)
        self.play(LaggedStart(*[FadeIn(b, shift=0.06 * UP) for b in self.tokens], lag_ratio=0.08), run_time=1.3)

        arcs = VGroup()
        for index, box in enumerate(self.tokens):
            if index == FOCUS:
                continue
            arcs.add(
                curved(box.get_top() + 0.08 * UP, self.tokens[FOCUS].get_top() + 0.08 * LEFT, ORANGE, rise=0.55, width=1.8, tip=0.12)
            )
        self.play(LaggedStart(*[Create(a) for a in arcs], lag_ratio=0.16), run_time=3.0)

        fresh = card("new representation", ORANGE, 3.2, 0.8, 20).move_to([3.9, 0.05, 0])
        link = arrow(context.get_right(), fresh.get_left(), ORANGE, 2.4, buff=0.12)
        self.play(FadeIn(fresh, shift=0.08 * UP), Create(link), run_time=1.2)
        self.play(
            LaggedStart(*[Indicate(a, color=ORANGE, scale_factor=1.04) for a in arcs], lag_ratio=0.18),
            run_time=2.0,
        )
        self.play(Indicate(link, color=ORANGE, scale_factor=1.06), run_time=1.0)
        check_now(self, "6b")

    # ================================================================ page 2 · roles
    def shot_7a(self) -> None:
        """Two roles: where to look, and what to bring back."""
        outgoing = [mob for mob in self.mobjects if mob is not self.camera.frame]

        title = self.heading_at("two roles, one operation", 32)

        left = RoundedRectangle(
            width=5.2, height=2.3, corner_radius=0.10,
            stroke_color=BLUE, stroke_width=2.2, stroke_opacity=0.65,
        ).move_to([-3.4, 0.25, 0])
        left_title = label("where to look", 22, BLUE).move_to([-3.4, 1.0, 0])
        left_marks = VGroup(
            math(r"\vec{q}", 34, BLUE).move_to([-4.9, 0.15, 0]),
            math(r"\vec{k}", 34, TEAL).move_to([-3.7, 0.15, 0]),
            math(r"\cdot", 34, MUTED).move_to([-4.3, 0.15, 0]),
            label("weights", 20, MUTED).move_to([-2.3, 0.15, 0]),
        )
        left_group = VGroup(left, left_title, left_marks)

        right = RoundedRectangle(
            width=4.4, height=2.3, corner_radius=0.10,
            stroke_color=PURPLE, stroke_width=2.2, stroke_opacity=0.65,
        ).move_to([4.0, 0.25, 0])
        right_title = label("what to bring back", 22, PURPLE).move_to([4.0, 1.0, 0])
        right_marks = VGroup(
            math(r"\vec{v}", 34, PURPLE).move_to([3.0, 0.15, 0]),
            label("values", 20, MUTED).move_to([4.4, 0.15, 0]),
        )
        right_group = VGroup(right, right_title, right_marks)

        # cross-fade: the previous diagram leaves while the new title arrives
        self.play(*[FadeOut(mob) for mob in outgoing], FadeIn(title, shift=0.1 * DOWN), run_time=0.9)
        self.play(FadeIn(left_group, shift=0.08 * UP), run_time=1.2)
        self.play(FadeIn(right_group, shift=0.08 * UP), run_time=1.2)

        pipe = arrow(left.get_right(), right.get_left(), ORANGE, 3.2, buff=0.12)
        self.play(Create(pipe), run_time=0.9)
        self.flow(pipe, 2.5, count=3, color=ORANGE, radius=0.07)

        self.play(Indicate(left_group, color=BLUE, scale_factor=1.02), run_time=0.9)
        self.play(Indicate(right_group, color=PURPLE, scale_factor=1.02), run_time=0.9)
        check_now(self, "7a")
        self.roles = VGroup(title, left_group, right_group, pipe)

    def shot_7b(self) -> None:
        """Each word scores every other word, then builds a new representation."""
        outgoing = [mob for mob in self.mobjects if mob is not self.camera.frame]

        title = self.heading_at("the core of query, key and value", 32)

        words = token_row(TOKENS, y=2.65, width=1.5, height=0.55, size=18)
        self.play(*[FadeOut(mob) for mob in outgoing], FadeIn(title, shift=0.1 * DOWN), run_time=0.9)
        self.play(LaggedStart(*[FadeIn(w, shift=0.04 * DOWN) for w in words], lag_ratio=0.06), run_time=1.0)

        row_scores = VGroup()
        row_weights = VGroup()
        for index, token in enumerate(TOKENS):
            box = RoundedRectangle(
                width=1.5, height=0.55, corner_radius=0.06,
                stroke_color=ORANGE if index == FOCUS else MUTED,
                stroke_width=1.6 if index == FOCUS else 1.0,
                stroke_opacity=0.85 if index == FOCUS else 0.45,
            ).move_to([(index - 2) * 1.55, 1.75, 0])
            box.add(label(token, 17, INK if index == FOCUS else MUTED).move_to(box))
            row_scores.add(box)
        for index, value in enumerate(self.weights_vector()):
            box = RoundedRectangle(
                width=1.5, height=0.55, corner_radius=0.06,
                stroke_color=ORANGE, stroke_width=1.2, stroke_opacity=0.55,
            ).move_to([(index - 2) * 1.55, 0.65, 0])
            box.set_fill(ORANGE, opacity=0.10 + 0.55 * float(value))
            box.add(label(f"{value:.2f}", 17, INK).move_to(box))
            row_weights.add(box)
        self.play(LaggedStart(*[FadeIn(b) for b in row_scores], lag_ratio=0.08), run_time=1.2)
        self.play(LaggedStart(*[FadeIn(b) for b in row_weights], lag_ratio=0.08), run_time=1.2)

        outs = VGroup()
        for index, value in enumerate(self.weights_vector()):
            box = RoundedRectangle(
                width=1.5, height=0.55, corner_radius=0.06,
                stroke_color=PURPLE, stroke_width=1.2, stroke_opacity=0.55,
            ).move_to([(index - 2) * 1.55, -0.45, 0])
            box.set_fill(PURPLE, opacity=0.10 + 0.55 * float(value))
            box.add(label(f"v{index + 1}", 17, INK).move_to(box))
            outs.add(box)
        self.play(LaggedStart(*[FadeIn(b) for b in outs], lag_ratio=0.08), run_time=1.2)

        merge = VGroup(
            *[arrow(b.get_bottom(), [b.get_center()[0] * 0.35, -1.05, 0], MUTED, 1.4, buff=0.04) for b in outs]
        )
        result = label("new representation", 21, ORANGE).move_to([0, -1.42, 0])
        self.play(LaggedStart(*[Create(a) for a in merge], lag_ratio=0.06), run_time=1.3)
        self.play(FadeIn(result, shift=0.06 * UP), run_time=0.8)
        self.flow(merge[2], 2.1, count=3, color=ORANGE, radius=0.05)
        check_now(self, "7b")

    # ================================================================ page 3 · multi-head
    def shot_8a(self) -> None:
        """One computation becomes several, in parallel."""
        self.clear_all(0.5)

        title = self.heading_at("multi-headed attention: several in parallel", 32)
        self.play(FadeIn(title, shift=0.1 * DOWN), run_time=0.9)

        words = token_row(TOKENS, y=2.6, width=1.45, height=0.5, size=17)
        self.play(LaggedStart(*[FadeIn(w, shift=0.04 * DOWN) for w in words], lag_ratio=0.06), run_time=1.0)

        single = card("self-attention", ORANGE, 3.2, 0.9, 22).move_to([0, 0.35, 0])
        self.play(FadeIn(single, scale=0.9), run_time=1.0)

        self.head_cards = VGroup()
        for index in range(3):
            head = card(f"head {index + 1}", ORANGE, 2.9, 0.75, 20)
            head.move_to([-3.6 + index * 3.6, -1.3, 0])
            self.head_cards.add(head)
        self.play(
            ReplacementTransform(single, self.head_cards[0]),
            LaggedStart(*[FadeIn(h, shift=0.10 * DOWN) for h in self.head_cards[1:]], lag_ratio=0.25),
            run_time=2.6,
        )

        fan = VGroup(
            *[
                arrow([head.get_center()[0], 2.30, 0], head.get_top(), MUTED, 1.8, buff=0.05)
                for head in self.head_cards
            ]
        )
        self.play(LaggedStart(*[Create(a) for a in fan], lag_ratio=0.07), run_time=2.2)
        self.play(LaggedStart(*[Indicate(a, color=ORANGE, scale_factor=1.05) for a in fan], lag_ratio=0.15), run_time=2.0)

        self.play(
            LaggedStart(*[Indicate(h, color=ORANGE, scale_factor=1.05) for h in self.head_cards], lag_ratio=0.2),
            run_time=1.5,
        )
        check_now(self, "8a")
        self.head_fan = fan

    def shot_8b(self) -> None:
        """The parallel structure is what the name points to."""
        self.play(FadeOut(self.head_fan), run_time=0.6)
        self.play(
            self.head_cards.animate.arrange(RIGHT, buff=1.1).move_to([0, -0.2, 0]),
            run_time=1.6,
        )
        for head in self.head_cards:
            head.add(
                math(r"\vec{q},\vec{k},\vec{v}", 22, MUTED).next_to(head, DOWN, buff=0.22)
            )
        self.play(
            LaggedStart(*[FadeIn(head[-1], shift=0.05 * UP) for head in self.head_cards], lag_ratio=0.2),
            run_time=1.3,
        )

        bracket = VGroup(
            Line([-5.3, 0.30, 0], [-5.3, 0.58, 0], color=MUTED, stroke_width=1.6),
            Line([-5.3, 0.58, 0], [5.3, 0.58, 0], color=MUTED, stroke_width=1.6),
            Line([5.3, 0.58, 0], [5.3, 0.30, 0], color=MUTED, stroke_width=1.6),
        )
        self.play(Create(bracket), run_time=1.0)

        feeds = VGroup(
            *[arrow([head.get_center()[0], 2.30, 0], head.get_top(), MUTED, 1.6, buff=0.06) for head in self.head_cards]
        )
        self.play(LaggedStart(*[Create(a) for a in feeds], lag_ratio=0.0), run_time=1.4)
        self.flow(feeds[1], 2.2, count=3, color=ORANGE, radius=0.05)
        self.play(
            LaggedStart(*[Indicate(head, color=ORANGE, scale_factor=1.05) for head in self.head_cards], lag_ratio=0.15),
            run_time=1.4,
        )
        check_now(self, "8b")

    def shot_9a(self) -> None:
        """Each head can emphasise a different relationship."""
        self.clear_all(0.5)

        self.tokens = token_row(TOKENS, y=1.55, width=1.8, height=0.72, size=21)
        self.play(LaggedStart(*[FadeIn(b, shift=0.05 * UP) for b in self.tokens], lag_ratio=0.08), run_time=1.2)

        pairings = [(FOCUS, 0, BLUE), (FOCUS, 2, TEAL), (FOCUS, 3, PURPLE)]
        self.arcs = VGroup()
        for src, dst, color in pairings:
            arc = curved(
                self.tokens[src].get_top() + 0.08 * UP,
                self.tokens[dst].get_top() + 0.08 * UP,
                color,
                rise=0.50,
                width=2.2,
            )
            self.arcs.add(arc)
        labels = VGroup(
            label("head 1", 19, BLUE).move_to([self.tokens[0].get_center()[0], 2.95, 0]),
            label("head 2", 19, TEAL).move_to([self.tokens[2].get_center()[0], 2.95, 0]),
            label("head 3", 19, PURPLE).move_to([self.tokens[3].get_center()[0], 2.95, 0]),
        )
        self.play(FadeIn(labels), run_time=0.6)
        for arc, lab, color, target in zip(self.arcs, labels, (BLUE, TEAL, PURPLE), (0, 2, 3)):
            self.play(Create(arc), Indicate(lab, color=color, scale_factor=1.1), run_time=1.8)
            self.play(Indicate(self.tokens[target], color=color, scale_factor=1.1), run_time=0.6)
        self.play(
            LaggedStart(*[Indicate(a, color=a.get_color(), scale_factor=1.06) for a in self.arcs], lag_ratio=0.25),
            run_time=1.6,
        )
        check_now(self, "9a")
        self.arc_labels = labels

    def shot_9b(self) -> None:
        """All views at once."""
        self.play(
            *[Indicate(arc, color=arc.get_color(), scale_factor=1.04) for arc in self.arcs],
            run_time=1.6,
        )
        for keep in range(3):
            self.play(
                *[arc.animate.set_opacity(1.0 if index == keep else 0.22) for index, arc in enumerate(self.arcs)],
                run_time=1.5,
            )
        self.play(*[arc.animate.set_opacity(1.0) for arc in self.arcs], run_time=1.5)
        self.play(
            LaggedStart(*[Indicate(lab, color=lab.get_color(), scale_factor=1.1) for lab in self.arc_labels], lag_ratio=0.25),
            run_time=1.4,
        )
        check_now(self, "9b")

    def shot_10a(self) -> None:
        """The benefit: the layer can focus on more than one pattern."""
        self.clear_all(0.5)

        title = self.heading_at("more patterns to work with", 32)
        self.play(FadeIn(title, shift=0.1 * DOWN), run_time=0.9)

        patterns = [
            [0.10, 0.62, 0.08, 0.12, 0.08],
            [0.08, 0.10, 0.62, 0.12, 0.08],
            [0.06, 0.08, 0.10, 0.66, 0.10],
        ]
        colors = [BLUE, TEAL, PURPLE]
        self.panels = VGroup()
        for head, (values, color) in enumerate(zip(patterns, colors)):
            cx = -4.3 + head * 4.3
            frame = RoundedRectangle(
                width=3.5, height=2.15, corner_radius=0.08,
                stroke_color=color, stroke_width=1.6, stroke_opacity=0.6,
            ).move_to([cx, -0.15, 0])
            bars = VGroup()
            base_y = frame.get_bottom()[1] + 0.12
            for index, value in enumerate(values):
                height = max(0.06, value * 2.5)
                bar = Rectangle(
                    width=0.42, height=height, stroke_width=0,
                    fill_color=color, fill_opacity=0.8,
                ).move_to([cx + (index - 2) * 0.52, base_y + height / 2, 0])
                bars.add(bar)
            head_label = label(f"head {head + 1}", 19, color).next_to(frame, UP, buff=0.10)
            self.panels.add(VGroup(frame, bars, head_label))
        self.play(LaggedStart(*[FadeIn(p, shift=0.08 * DOWN) for p in self.panels], lag_ratio=0.25), run_time=2.8)
        self.play(
            LaggedStart(*[Indicate(p, color=p[2].get_color(), scale_factor=1.02) for p in self.panels], lag_ratio=0.2),
            run_time=1.6,
        )
        peaks = VGroup(*[p[1][int(np.argmax([b.height for b in p[1]]))] for p in self.panels])
        self.play(
            LaggedStart(*[Indicate(bar, color=bar.get_color(), scale_factor=1.12) for bar in peaks], lag_ratio=0.3),
            run_time=2.6,
        )
        check_now(self, "10a")

    def shot_10b(self) -> None:
        """Several computations at the same time."""
        for panel in self.panels:
            bars = panel[1]
            self.play(
                LaggedStart(*[Indicate(bar, color=bar.get_color(), scale_factor=1.08) for bar in bars], lag_ratio=0.12),
                run_time=1.5,
            )
        self.play(
            LaggedStart(*[Indicate(p[0], color=p[2].get_color(), scale_factor=1.03) for p in self.panels], lag_ratio=0.15),
            run_time=1.4,
        )
        guide = Line([-6.0, -1.55, 0], [6.0, -1.55, 0], color=MUTED, stroke_width=1.2)
        self.play(Create(guide), run_time=0.8)
        self.play(
            LaggedStart(*[Indicate(p, color=p[2].get_color(), scale_factor=1.04) for p in self.panels], lag_ratio=0.0),
            run_time=1.6,
        )
        check_now(self, "10b")

    def shot_11a(self) -> None:
        """Concatenate and project the heads into one output."""
        self.clear_all(0.5)

        title = self.heading_at("concatenate, project, combine", 32)
        self.play(FadeIn(title, shift=0.1 * DOWN), run_time=0.9)

        colors = [BLUE, TEAL, PURPLE]
        heads = VGroup(*[card(f"head {i + 1}", colors[i], 2.1, 0.62, 19) for i in range(3)])
        heads.arrange(DOWN, buff=0.3).move_to([-5.1, -0.4, 0])
        self.play(LaggedStart(*[FadeIn(h, shift=0.06 * RIGHT) for h in heads], lag_ratio=0.15), run_time=1.4)

        concat = RoundedRectangle(
            width=0.7, height=2.6, corner_radius=0.08,
            stroke_color=ORANGE, stroke_width=2.4,
        ).move_to([-1.7, -0.4, 0])
        links = VGroup(*[arrow(h.get_right(), concat.get_left(), MUTED, 1.8, buff=0.08) for h in heads])
        self.play(Create(concat), LaggedStart(*[Create(a) for a in links], lag_ratio=0.1), run_time=1.5)

        mix_box = RoundedRectangle(
            width=1.5, height=1.0, corner_radius=0.10,
            stroke_color=ORANGE, stroke_width=2.4,
        ).move_to([0.7, -0.4, 0])
        mix_label = math(r"W_O", 32, ORANGE).move_to(mix_box)
        mix = VGroup(mix_box, mix_label)
        to_mix = arrow(concat.get_right(), mix.get_left(), ORANGE, 2.6, buff=0.08)
        self.play(FadeIn(mix), Create(to_mix), run_time=1.0)

        output = card("output", INK, 1.9, 0.9, 20).move_to([4.0, -0.4, 0])
        to_out = arrow(mix.get_right(), output.get_left(), ORANGE, 2.6, buff=0.08)
        self.play(FadeIn(output), Create(to_out), run_time=1.0)
        dims = math(r"h\cdot d_v \to d_{model}", 22, MUTED).move_to([1.0, -1.15, 0])
        self.play(FadeIn(dims, shift=0.04 * UP), run_time=0.6)

        path = VGroup(to_mix, to_out)
        self.flow(to_mix, 1.8, count=3, color=ORANGE, radius=0.06)
        self.flow(to_out, 1.8, count=3, color=ORANGE, radius=0.06)

        self.play(Indicate(output, color=ORANGE, scale_factor=1.12), run_time=1.6)
        check_now(self, "11a")
        self.output = VGroup(heads, concat, links, mix, to_mix, output, to_out, title, mix_label)

    def shot_11b(self) -> None:
        """The single representation is a merge of several views."""
        heads, concat, links, mix, to_mix, output, to_out, title, mix_label = self.output
        self.play(FadeOut(title), run_time=0.6)
        self.play(
            FadeOut(heads), FadeOut(links), FadeOut(concat), FadeOut(to_mix),
            mix.animate.move_to([-2.2, -0.4, 0]),
            output.animate.move_to([3.2, -0.4, 0]),
            to_out.animate.put_start_and_end_on([-0.9, -0.4, 0], [2.25, -0.4, 0]),
            run_time=1.2,
        )

        stem = Line([3.2, -0.86, 0], [3.2, -1.10, 0], color=MUTED, stroke_width=1.6)
        segments = VGroup()
        for index, color in enumerate((BLUE, TEAL, PURPLE)):
            bar = Rectangle(width=0.72, height=0.34, stroke_width=0, fill_color=color, fill_opacity=0.85)
            bar.move_to([3.2 + (index - 1) * 0.78, -1.30, 0])
            segments.add(bar)
        self.play(Create(stem), LaggedStart(*[FadeIn(s, shift=0.06 * UP) for s in segments], lag_ratio=0.2), run_time=1.4)
        self.play(Indicate(output, color=INK, scale_factor=1.05), run_time=1.0)
        self.play(
            LaggedStart(*[Indicate(s, color=s.get_color(), scale_factor=1.06) for s in segments], lag_ratio=0.2),
            run_time=1.6,
        )
        homes = [bar.get_center().copy() for bar in segments]
        self.play(
            *[bar.animate.move_to(homes[index] + 0.45 * UP * (index - 1)) for index, bar in enumerate(segments)],
            run_time=1.8,
        )
        self.play(*[bar.animate.move_to(homes[index]) for index, bar in enumerate(segments)], run_time=1.4)
        self.play(output.animate.set_color(ORANGE), run_time=0.7)
        self.play(output.animate.set_color(INK), run_time=0.7)
        check_now(self, "11b")
        self.segments = segments

    # ================================================================ page 3 · recap
    def shot_12a(self) -> None:
        """Two things to keep: parallel, then combined."""
        self.clear_all(0.5)

        title = self.heading_at("two things to keep in mind", 34)
        self.play(FadeIn(title, shift=0.1 * DOWN), run_time=0.9)

        one_title = label("1 · heads operate in parallel", 24, INK).move_to([0, 1.95, 0])
        cards = VGroup(*[card(f"head {i + 1}", (BLUE, TEAL, PURPLE)[i], 1.6, 0.58, 18) for i in range(3)])
        cards.arrange(RIGHT, buff=0.3).move_to([0, 1.1, 0])
        self.play(FadeIn(one_title, shift=0.06 * UP), run_time=0.8)
        self.play(LaggedStart(*[FadeIn(c, shift=0.05 * DOWN) for c in cards], lag_ratio=0.18), run_time=1.4)

        two_title = label("2 · outputs are combined", 24, INK).move_to([0, 0.0, 0])
        self.play(FadeIn(two_title, shift=0.06 * UP), run_time=0.8)

        chips = VGroup(*[chip(f"head {i + 1}", (BLUE, TEAL, PURPLE)[i], 1.5, 0.32) for i in range(3)])
        chips.arrange(DOWN, buff=0.12).move_to([-1.6, -1.05, 0])
        concat = Rectangle(
            width=0.28, height=1.25, stroke_color=ORANGE, stroke_width=2.2,
        ).move_to([0.35, -1.05, 0])
        merge = VGroup(*[arrow(c.get_right(), concat.get_left(), MUTED, 1.6, buff=0.05) for c in chips])
        output = card("one output", ORANGE, 2.1, 0.62, 19).move_to([3.2, -1.05, 0])
        final = arrow(concat.get_right(), output.get_left(), ORANGE, 2.6, buff=0.06)

        self.play(LaggedStart(*[FadeIn(c, shift=0.05 * RIGHT) for c in chips], lag_ratio=0.12), run_time=1.2)
        self.play(LaggedStart(*[Create(a) for a in merge], lag_ratio=0.1), run_time=1.2)
        self.play(Create(concat), Create(final), FadeIn(output, shift=0.06 * UP), run_time=1.4)

        self.play(Indicate(VGroup(concat, output), color=ORANGE, scale_factor=1.05), run_time=1.1)
        for chip_obj, color in zip(chips, (BLUE, TEAL, PURPLE)):
            self.play(Indicate(chip_obj, color=color, scale_factor=1.1), run_time=0.5)
        check_now(self, "12a")
        self.recap = VGroup(title, one_title, cards, two_title, chips, concat, merge, output, final)

    def shot_12b(self) -> None:
        """More heads, more capacity: the closing claim."""
        self.clear_all(0.5)

        title = Text("several heads, more capacity", font="Arial", font_size=44, color=INK, weight=MEDIUM)
        title.move_to([0, 2.7, 0])
        self.play(FadeIn(title, shift=0.10 * UP), run_time=1.2)

        def pair(x: float) -> VGroup:
            left = chip("animal", MUTED, 1.55, 0.55).move_to([x - 0.95, 0.10, 0])
            right = chip("street", MUTED, 1.55, 0.55).move_to([x + 0.95, 0.10, 0])
            return VGroup(left, right)

        left_pair = pair(-4.0)
        single_label = label("one head", 22, MUTED).move_to([-4.0, 1.62, 0])
        single_arc = curved(
            left_pair[0].get_top() + 0.06 * UP, left_pair[1].get_top() + 0.06 * UP,
            MUTED, rise=0.55, width=2.2,
        )
        self.play(FadeIn(left_pair, shift=0.06 * UP), FadeIn(single_label, shift=0.05 * UP), run_time=1.0)
        self.play(Create(single_arc), run_time=0.9)

        right_pair = pair(4.0)
        multi_label = label("several heads", 22, ORANGE).move_to([4.0, 1.62, 0])
        multi_arcs = VGroup()
        for index, color in enumerate((BLUE, TEAL, PURPLE)):
            multi_arcs.add(
                curved(
                    right_pair[0].get_top() + 0.06 * UP,
                    right_pair[1].get_top() + 0.06 * UP,
                    color,
                    rise=0.40 + 0.24 * index,
                    width=2.0,
                )
            )
        self.play(FadeIn(right_pair, shift=0.06 * UP), FadeIn(multi_label, shift=0.05 * UP), run_time=1.0)
        self.play(LaggedStart(*[Create(a) for a in multi_arcs], lag_ratio=0.25), run_time=2.2)
        for arc, color in zip(multi_arcs, (BLUE, TEAL, PURPLE)):
            self.play(Indicate(arc, color=color, scale_factor=1.06), run_time=1.0)

        closing = label("several heads, working together, give the layer more capacity", 22, INK).move_to([0, -1.42, 0])
        self.play(FadeIn(closing, shift=0.06 * UP), run_time=1.0)

        source = label("Vaswani et al., 2017", 18, MUTED).move_to([0, -1.85, 0])
        self.play(FadeIn(source), run_time=0.8)
        check_now(self, "12b")


def score_at(q_vec: np.ndarray, k_len: float, angle: float) -> float:
    kv = k_len * np.array([np.cos(angle), np.sin(angle), 0.0])
    return float(np.dot(q_vec, kv))
