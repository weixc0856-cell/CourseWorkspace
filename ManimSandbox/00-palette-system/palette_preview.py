"""One-frame reference sheet for the painting palettes.

Render a still::

    uv run manim render -s -r 1920,1080 \
      --media_dir ../build/palette-preview/media 00-palette-system/palette_preview.py PalettePreview
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Line,
    Scene,
    Square,
    Text,
    VGroup,
    config,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import palettes  # noqa: E402

config.background_color = palettes.palette("editorial").paper


def label(text: str, size: int, color: str, weight: str = "NORMAL") -> Text:
    return Text(text, font="Arial", font_size=size, color=color, weight=weight)


def cjk(text: str, size: int, color: str) -> Text:
    return Text(text, font="Microsoft YaHei", font_size=size, color=color)


class PalettePreview(Scene):
    def construct(self) -> None:
        keys = palettes.keys()
        top = 3.35
        step = 0.9
        for index, key in enumerate(keys):
            item = palettes.palette(key)
            y = top - index * step

            background = Square(0.5).set_fill(item.paper, 1).set_stroke(item.divider, 1.2)
            name = label(key, 15, item.ink, "BOLD")
            chinese = cjk(item.label, 11, item.muted)
            names = VGroup(name, chinese).arrange(DOWN, buff=0.02, aligned_edge=LEFT)
            identity = VGroup(background, names).arrange(RIGHT, buff=0.14)

            family = VGroup()
            for colour_name, value in item.family.items():
                chip = Square(0.30).set_fill(value, 1).set_stroke(item.divider, 0.8)
                tag = label(value.lstrip("#"), 10, item.muted).next_to(chip, DOWN, buff=0.03)
                family.add(VGroup(chip, tag))
            family.arrange(RIGHT, buff=0.12)

            ink = label("Aa body", 13, item.ink)
            focus_line = Line(LEFT, RIGHT, color=item.focus, stroke_width=3).scale(0.24)
            focus_line.next_to(ink, DOWN, buff=0.08).align_to(ink, LEFT)
            support_line = Line(LEFT, RIGHT, color=item.support, stroke_width=3).scale(0.24)
            support_line.next_to(focus_line, DOWN, buff=0.03).align_to(ink, LEFT)
            muted = label("secondary", 9, item.muted).next_to(support_line, DOWN, buff=0.03).align_to(ink, LEFT)
            roles = VGroup(ink, focus_line, support_line, muted)

            meta = label(
                f"ink {palettes.contrast(item.ink, item.paper):.1f}:1\n"
                f"focus {palettes.contrast(item.focus, item.paper):.1f}:1",
                9,
                item.muted,
            )

            row = VGroup(identity, family, roles, meta).arrange(RIGHT, buff=0.45)
            row.move_to([0, y, 0])
            row.align_to(np.array([-6.8, y, 0]), LEFT)
            self.add(row)
        self.wait(0.1)
