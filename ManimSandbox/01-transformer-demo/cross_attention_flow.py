"""Slide 8 — the decoder adds cross-attention to the encoder output.

Rebuilt against the process_flow layout: full-width stage, larger blocks,
title band, dedicated caption band.
"""
from __future__ import annotations

import sys
from pathlib import Path

from manim import (
    LEFT,
    RIGHT,
    UP,
    Create,
    CurvedArrow,
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
from common.design_system import (  # noqa: E402
    BG,
    BODY,
    DIVIDER,
    INK,
    MUTED,
    ORANGE,
    PURPLE,
    TEAL,
    TYPE,
    x_at,
    y_at,
)

config.background_color = BG


def label(text: str, size: int = TYPE["label"], color: str = INK) -> Text:
    return Text(text, font="Arial", font_size=size, color=color)


def strip(text: str, width: float = 3.6, height: float = 0.5, color: str = INK, size: int = 20) -> VGroup:
    rect = RoundedRectangle(
        corner_radius=0.07, width=width, height=height, stroke_color=color, stroke_width=1.8
    )
    return VGroup(rect, label(text, size).move_to(rect))


class CrossAttentionFlowScene(Scene):
    def construct(self):
        title = label("The decoder adds cross-attention", TYPE["heading_1"], INK)
        title.move_to([x_at(0.06), y_at(0.85), 0], aligned_edge=LEFT)
        self.play(FadeIn(title), run_time=0.5)

        enc_x = -4.0
        enc_blocks = VGroup(
            *[strip("encoder layer", 3.2, 0.85, INK, 24).move_to([enc_x, y, 0]) for y in (-1.2, 0.0, 1.2)]
        )
        enc_tag = label("encoder", TYPE["body"], MUTED).move_to([enc_x, 1.82, 0])
        source = VGroup(*[label(t, TYPE["body"], INK) for t in ("Je", "suis", "étudiant")]).arrange(
            RIGHT, buff=0.2
        )
        source.move_to([enc_x, -2.02, 0])
        src_tag = label("source", TYPE["label"], MUTED).move_to([enc_x, -2.32, 0])
        self.play(FadeIn(enc_blocks, shift=0.1 * UP), FadeIn(enc_tag), run_time=0.9)
        self.play(FadeIn(source), FadeIn(src_tag), run_time=0.5)

        dec_x = 2.8
        decoder = VGroup()
        highlights = VGroup()
        for block_y in (0.9, -1.2):
            for offset, text, color in (
                (0.6, "masked self-attention", INK),
                (0.0, "cross-attention", ORANGE),
                (-0.6, "feed-forward", INK),
            ):
                cell = strip(text, 3.6, 0.5, color).move_to([dec_x, block_y + offset, 0])
                decoder.add(cell)
                if text == "cross-attention":
                    highlights.add(cell)
        dec_tag = label("decoder", TYPE["body"], MUTED).move_to([dec_x, 2.02, 0])
        self.play(FadeIn(decoder, shift=0.1 * UP), FadeIn(dec_tag), run_time=1.0)
        self.play(Indicate(highlights, color=ORANGE, scale_factor=1.03), run_time=0.9)

        bridge = VGroup(
            CurvedArrow(
                [-2.35, 1.05, 0],
                [0.95, 1.5, 0],
                angle=-0.55,
                color=TEAL,
                stroke_width=3.0,
                tip_length=0.16,
            ),
            CurvedArrow(
                [-2.35, 0.6, 0],
                [0.95, -1.2, 0],
                angle=-0.28,
                color=TEAL,
                stroke_width=3.0,
                tip_length=0.16,
            ),
        )
        kv = label("K, V from the source", TYPE["body"], TEAL).move_to([-0.55, 1.92, 0])
        self.play(Create(bridge[0]), Create(bridge[1]), FadeIn(kv), run_time=1.5)

        out_arrow = CurvedArrow(
            [4.65, 0.9, 0],
            [5.65, 0.9, 0],
            angle=0.0,
            color=PURPLE,
            stroke_width=2.8,
            tip_length=0.16,
        )
        out = label("thanks", TYPE["body"], PURPLE).move_to([5.85, 0.9, 0], aligned_edge=LEFT)
        self.play(Create(out_arrow), FadeIn(out), run_time=0.8)

        divider = Line([x_at(0.06), -2.62, 0], [x_at(0.94), -2.62, 0], color=DIVIDER, stroke_width=1.5)
        caption = label(
            "each new token looks back at the whole input", TYPE["caption"], BODY
        ).move_to([x_at(0.06), -2.95, 0], aligned_edge=LEFT)
        self.play(Create(divider), FadeIn(caption), run_time=0.6)
        self.play(Indicate(highlights, color=ORANGE, scale_factor=1.03), run_time=0.8)
        self.wait(1.0)
