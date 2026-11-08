"""Course design tokens shared by Manim scenes.

Mirrors the layout system in CourseControl: 1920x1080 canvas, 96 px safe
margin, process_flow / principle_diagram regions. Keep values in sync with
CourseControl/src/course_control/layout/library.py.
"""
from __future__ import annotations

BG = "#FFFFFF"
INK = "#14213D"
BODY = "#252525"
MUTED = "#5C677D"
ACCENT = "#0077B6"
WARM = "#E76F51"
GREEN = "#2A9D8F"
DIVIDER = "#E8E8E8"

CANVAS_W = 1920
CANVAS_H = 1080
SAFE_MARGIN = 96
FRAME_W = 14.2222
FRAME_H = 8.0

# Manim font sizes tuned for 1080p; the same hierarchy as the design tokens.
TYPE = {
    "display": 46,
    "heading_1": 40,
    "heading_2": 30,
    "body": 26,
    "label": 22,
    "caption": 24,
}


def x_at(fraction: float) -> float:
    return (fraction - 0.5) * FRAME_W


def y_at(fraction: float) -> float:
    return (fraction - 0.5) * FRAME_H


def region(x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
    """Normalised layout region -> (center_x, center_y, width, height) in units."""
    return (x_at(x + w / 2), y_at(y + h / 2), w * FRAME_W, h * FRAME_H)


# process_flow template regions (normalised, bottom-left origin).
TITLE_REGION = (0.06, 0.80, 0.88, 0.10)
MAIN_REGION = (0.06, 0.20, 0.88, 0.54)
CAPTION_REGION = (0.06, 0.09, 0.88, 0.07)
