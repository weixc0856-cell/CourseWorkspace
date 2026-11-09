from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import palettes  # noqa: E402


class PaletteTest(unittest.TestCase):
    def test_all_palettes_present(self) -> None:
        self.assertEqual(
            palettes.keys(),
            ["editorial", "qinglv", "yanlan", "taohua", "hetang", "qiushan", "yebo", "xueyi"],
        )

    def test_each_painting_has_four_colours(self) -> None:
        for key in palettes.PAINTINGS:
            with self.subTest(key=key):
                _, family, *_ = palettes.PAINTINGS[key]
                self.assertEqual(len(family), 4)
                for value in family.values():
                    self.assertRegex(value, r"^#[0-9A-F]{6}$")

    def test_accessibility_gates(self) -> None:
        for key in palettes.keys():
            with self.subTest(key=key):
                item = palettes.palette(key)
                self.assertGreaterEqual(
                    palettes.contrast(item.ink, item.paper), 7.0, "body text needs 7:1"
                )
                self.assertGreaterEqual(
                    palettes.contrast(item.focus, item.paper), 3.0, "graphics need 3:1"
                )
                self.assertGreaterEqual(
                    palettes.contrast(item.support, item.paper), 3.0, "graphics need 3:1"
                )
                self.assertGreaterEqual(
                    palettes.contrast(item.muted, item.paper), 4.5, "secondary text needs 4.5:1"
                )

    def test_roles_are_distinct(self) -> None:
        for key in palettes.PAINTINGS:
            with self.subTest(key=key):
                item = palettes.palette(key)
                self.assertEqual(len({item.paper, item.ink, item.focus, item.support}), 4)
                self.assertNotEqual(item.focus.lower(), item.support.lower())

    def test_divider_sits_between_paper_and_ink(self) -> None:
        for key in palettes.PAINTINGS:
            with self.subTest(key=key):
                item = palettes.palette(key)
                paper = palettes.luminance(item.paper)
                divider = palettes.luminance(item.divider)
                ink = palettes.luminance(item.ink)
                self.assertLess(divider, paper)
                self.assertGreater(divider, ink)

    def test_report_shape(self) -> None:
        data = palettes.report("qinglv")
        for field in ("paper", "ink", "focus", "support", "ink_contrast", "family"):
            self.assertIn(field, data)
        self.assertEqual(data["key"], "qinglv")

    def test_unknown_palette_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            palettes.palette("nope")


if __name__ == "__main__":
    unittest.main()
