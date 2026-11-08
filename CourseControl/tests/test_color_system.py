from __future__ import annotations

import re
import unittest
from pathlib import Path

from course_control.director.planners import default_style
from course_control.layout import DESIGN

WORKSPACE = Path(__file__).resolve().parents[2]
MANIM_TOKENS = WORKSPACE / "ManimSandbox" / "common" / "design_system.py"


def _luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    channels = [int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(foreground: str, background: str) -> float:
    a, b = _luminance(foreground), _luminance(background)
    high, low = max(a, b), min(a, b)
    return (high + 0.05) / (low + 0.05)


class ColorSystemTest(unittest.TestCase):
    def test_text_colors_pass_aa_on_paper(self):
        for color in (DESIGN.ink, DESIGN.body, DESIGN.muted):
            self.assertGreaterEqual(contrast(color, DESIGN.background), 4.5, color)

    def test_semantic_colors_are_graphics_safe(self):
        for color in (DESIGN.accent, DESIGN.blue, DESIGN.teal, DESIGN.purple, DESIGN.red):
            self.assertGreaterEqual(contrast(color, DESIGN.background), 2.7, color)

    def test_default_theme_is_light(self):
        self.assertGreater(_luminance(DESIGN.background), 0.8)
        self.assertGreater(_luminance(DESIGN.surface), 0.7)

    def test_director_semantics_cover_transformer_roles(self):
        style = default_style()
        for role in ("query", "key", "value", "result", "mask", "attention", "loss"):
            self.assertIn(role, style.color_semantics)
        self.assertEqual(style.color_semantics["query"], DESIGN.blue)
        self.assertEqual(style.color_semantics["key"], DESIGN.teal)
        self.assertEqual(style.color_semantics["value"], DESIGN.purple)
        self.assertEqual(style.color_semantics["attention"], DESIGN.accent)
        self.assertEqual(style.color_semantics["loss"], DESIGN.red)

    def test_manim_tokens_match_design_system(self):
        text = MANIM_TOKENS.read_text(encoding="utf-8")
        expected = {
            "BG": DESIGN.background,
            "SURFACE": DESIGN.surface,
            "INK": DESIGN.ink,
            "BODY": DESIGN.body,
            "MUTED": DESIGN.muted,
            "ORANGE": DESIGN.accent,
            "NAVY": DESIGN.navy,
            "BLUE": DESIGN.blue,
            "TEAL": DESIGN.teal,
            "PURPLE": DESIGN.purple,
            "RED": DESIGN.red,
            "FLOW": DESIGN.flow,
            "DIVIDER": DESIGN.divider,
        }
        for name, value in expected.items():
            match = re.search(rf'^{name} = "(#[0-9A-Fa-f]{{6}})"', text, flags=re.M)
            self.assertIsNotNone(match, name)
            self.assertEqual(match.group(1).upper(), value.upper(), name)


if __name__ == "__main__":
    unittest.main()
