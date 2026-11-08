"""Slide 8 — the decoder adds cross-attention to the encoder output.

White course palette, 11 s insert. Keeps the shared building blocks visible and
shows the new bridge from the encoder into the decoder's middle sub-layer.
"""
from __future__ import annotations

from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Create,
    CurvedArrow,
    FadeIn,
    Indicate,
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


def strip(text: str, width: float = 2.7, height: float = 0.42, color: str = INK, size: int = 18) -> VGroup:
    rect = RoundedRectangle(
        corner_radius=0.07, width=width, height=height, stroke_color=color, stroke_width=1.8
    )
    return VGroup(rect, label(text, size).move_to(rect))


class CrossAttentionFlowScene(Scene):
    def construct(self):
        title = label("The decoder adds cross-attention", 36).to_corner(UP + LEFT, buff=0.55)
        self.play(FadeIn(title), run_time=0.6)

        enc_x = -4.5
        enc_blocks = VGroup(
            *[
                strip("encoder layer", 2.5, 0.62, INK, 20).move_to([enc_x, y, 0])
                for y in (-0.9, -0.15, 0.6)
            ]
        )
        enc_tag = label("encoder", 22, MUTED).next_to(enc_blocks, UP, buff=0.18)
        source = VGroup(*[label(t, 20) for t in ("Je", "suis", "étudiant")]).arrange(RIGHT, buff=0.14)
        source.next_to(enc_blocks, DOWN, buff=0.45)
        src_tag = label("source", 18, MUTED).next_to(source, DOWN, buff=0.12)
        self.play(FadeIn(enc_blocks, shift=0.1 * UP), FadeIn(enc_tag), run_time=1.0)
        self.play(FadeIn(source), FadeIn(src_tag), run_time=0.8)

        dec_x = 2.9
        decoder = VGroup()
        highlights = VGroup()
        for block_y in (1.0, -1.1):
            self_attn = strip("masked self-attention").move_to([dec_x, block_y + 0.46, 0])
            cross = strip("cross-attention", color=ACCENT).move_to([dec_x, block_y, 0])
            ffn = strip("feed-forward").move_to([dec_x, block_y - 0.46, 0])
            decoder.add(self_attn, cross, ffn)
            highlights.add(cross)
        dec_tag = label("decoder", 22, MUTED).next_to(decoder, UP, buff=0.25)
        self.play(FadeIn(decoder, shift=0.1 * UP), FadeIn(dec_tag), run_time=1.2)
        self.play(Indicate(highlights, color=ACCENT, scale_factor=1.05), run_time=1.2)

        bridge_top = VGroup(
            CurvedArrow(
                [enc_x + 1.3, 0.75, 0],
                [dec_x - 1.45, 1.0, 0],
                angle=-0.7,
                color=ACCENT,
                stroke_width=2.4,
                tip_length=0.15,
            ),
            CurvedArrow(
                [enc_x + 1.3, 0.45, 0],
                [dec_x - 1.45, -1.1, 0],
                angle=-0.35,
                color=ACCENT,
                stroke_width=2.4,
                tip_length=0.15,
            ),
        )
        kv = label("K, V from the source", 22, ACCENT).move_to([-0.7, 1.75, 0])
        self.play(Create(bridge_top[0]), Create(bridge_top[1]), FadeIn(kv), run_time=1.8)

        out_arrow = CurvedArrow(
            [dec_x + 1.5, 1.0, 0],
            [dec_x + 2.9, 1.0, 0],
            angle=0.0,
            color=GREEN,
            stroke_width=2.6,
            tip_length=0.16,
        )
        out = label("thanks", 26, GREEN).next_to(out_arrow, RIGHT, buff=0.1)
        self.play(Create(out_arrow), FadeIn(out), run_time=0.9)
        caption = label("each new token looks back at the whole input", 21, MUTED)
        caption.to_corner(DOWN + LEFT, buff=0.5)
        self.play(FadeIn(caption), run_time=0.7)
        self.wait(1.4)
