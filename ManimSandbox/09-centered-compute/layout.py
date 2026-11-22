"""Shared helpers for the centered-compute acts (09-centered-compute).

Composition contract (owner's bar, 2026-11-22):
- every element centered on a symmetric grid; masthead centered top,
  caption centered bottom; diagram = ONE balanced lockup.
- type sizes at 1080p: title 56, section labels 30, matrix numbers 34,
  caption 24, eyebrow 20 (letterspaced). Safe margin >= 96 px.
- color discipline: paper bg, ink text, BLUE = input family, TEAL = results,
  ORANGE = the single active element, MUTED = inactive. No rainbow.
- every displayed number comes from numpy (C = A @ B). Nothing hardcoded.

Render (run from ManimSandbox in a subshell):
  uv run manim render -r 1920,1080 --fps 30 \
    --media_dir <content_root>/build/_shared/centered-compute/media \
    09-centered-compute/act1.py Act1
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.design_system import (  # noqa: E402
    BG, SURFACE, INK, BODY, MUTED, DIVIDER, ORANGE, BLUE, TEAL, NAVY,
)

from manim import RoundedRectangle, Text, VGroup, config  # noqa: E402

config.background_color = BG

PX = 135.0             # px per manim unit at 1920x1080
SAFE_Y = 4.0 - 96.0 / PX      # 3.289 top/bottom bound for ink
SAFE_X = 7.1111 - 96.0 / PX   # 6.400 left/right bound

# ----------------------------------------------------------------- the data
A = np.array([[1, 2, 0], [0, 1, 3], [2, 0, 1]])
B = np.array([[1, 0, 2], [3, 1, 0], [0, 2, 1]])
C = A @ B
assert list(int(v) for v in C.flatten()) == [7, 2, 2, 3, 7, 3, 2, 2, 5]

N = 3
SERIAL_STEPS = int(C.size)            # 9 dot-products done one after another
WAVE_STEPS = N + N - 1                # 3 MAC rounds + 2 skew = 5 wavefronts
MACS = SERIAL_STEPS * N               # 27 multiply-accumulates in the product
assert (SERIAL_STEPS, WAVE_STEPS, MACS) == (9, 5, 27)


def txt(s: str, size: int = 24, color: str = INK, weight: str = "NORMAL") -> Text:
    return Text(s, font="Arial", font_size=size, color=color, weight=weight)


def caps(s: str, size: int = 20, color: str = MUTED,
         weight: str = "BOLD") -> Text:
    """Small-caps eyebrow with real letterspacing (Pango has none)."""
    spaced = "   ".join(" ".join(w) for w in s.split())
    return Text(spaced, font="Arial", font_size=size, color=color, weight=weight)


def panel(w: float, h: float, x: float, y: float, stroke: str = DIVIDER,
          fill: str = SURFACE, opacity: float = 0.65,
          stroke_w: float = 1.8) -> RoundedRectangle:
    p = RoundedRectangle(corner_radius=0.11, width=w, height=h,
                         stroke_color=stroke, stroke_width=stroke_w)
    p.set_fill(fill, opacity).move_to([x, y, 0.0])
    return p


def chip(value: int, color: str, size: int = 26, half: float = 0.185
         ) -> VGroup:
    body = RoundedRectangle(corner_radius=0.06, width=2 * half + 0.11,
                            height=2 * half + 0.07, stroke_width=0)
    body.set_fill(color, 1.0)
    lab = Text(str(int(value)), font="Arial", font_size=size, color="#FFFFFF",
               weight="BOLD").move_to(body.get_center() + np.array([0, 0.01, 0]))
    return VGroup(body, lab)


def centered(*items) -> VGroup:
    g = VGroup(*items)
    g.move_to([0, g.get_center()[1], 0])   # keeps caller's y, forces x=0
    return g
