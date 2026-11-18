"""One-frame colour reference shared with the Remotion proof.

Render a still::

    uv run manim render -s -r 1920,1080 \
      --media_dir ../build/token-swatch/media \
      00-token-swatch/token_swatch.py TokenSwatch

The cells use ``common.design_system`` constants, the Manim copy of the brand
tokens.  A pixel at the same cell is compared with the Remotion frame by
``course-control token-frames-check``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from manim import Rectangle, Scene, config

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import design_system as ds  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LAYOUT = json.loads((ROOT / "shared" / "design-tokens" / "swatch-layout.json").read_text(encoding="utf-8"))

COLORS = {
    "paper": ds.BG,
    "surface": ds.SURFACE,
    "ink": ds.INK,
    "text": ds.BODY,
    "muted": ds.MUTED,
    "border": ds.DIVIDER,
    "orange": ds.ORANGE,
    "navy": ds.NAVY,
    "blue": ds.BLUE,
    "teal": ds.TEAL,
    "purple": ds.PURPLE,
    "red": ds.RED,
    "flow": ds.FLOW,
}

# The canvas background is part of the brand proof, not a render default.
config.background_color = COLORS["paper"]

# 1920x1080 with Manim's 14.2222x8 frame is 135 px per scene unit.
PX_PER_UNIT = 135.0
FRAME_W = 1920.0


def to_scene(px: float, py_top: float) -> tuple[float, float]:
    """Convert a top-left pixel point to Manim scene units."""
    x = (px - FRAME_W / 2) / PX_PER_UNIT
    y = (540.0 - py_top) / PX_PER_UNIT
    return x, y


class TokenSwatch(Scene):
    def construct(self) -> None:
        self.camera.background_color = COLORS["paper"]
        cell_w = LAYOUT["cell"]["w"]
        cell_h = LAYOUT["cell"]["h"]
        step_x = cell_w + LAYOUT["gap"]
        step_y = cell_h + LAYOUT["gap"]
        for index, key in enumerate(LAYOUT["keys"]):
            col = index % LAYOUT["columns"]
            row = index // LAYOUT["columns"]
            left = LAYOUT["origin"]["x"] + col * step_x
            top = LAYOUT["origin"]["y"] + row * step_y
            center = to_scene(left + cell_w / 2, top + cell_h / 2)
            rect = Rectangle(
                width=cell_w / PX_PER_UNIT,
                height=cell_h / PX_PER_UNIT,
                fill_color=COLORS[key],
                fill_opacity=1.0,
                stroke_width=0,
            )
            rect.move_to([center[0], center[1], 0])
            self.add(rect)
        self.wait(0.1)
