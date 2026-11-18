from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from course_control.rendering.token_frames import (
    TokenFrameError,
    cells,
    compare_frames,
    load_layout,
)

WORKSPACE = Path(__file__).resolve().parents[2]
LAYOUT = WORKSPACE / "shared" / "design-tokens" / "swatch-layout.json"

COLORS = {
    "paper": (251, 250, 247),
    "surface": (243, 241, 234),
    "ink": (37, 42, 49),
    "text": (46, 51, 56),
    "muted": (107, 114, 128),
    "border": (227, 224, 215),
    "orange": (232, 115, 59),
    "blue": (74, 130, 184),
    "teal": (66, 166, 154),
    "purple": (122, 111, 176),
    "red": (199, 91, 85),
    "navy": (18, 50, 74),
    "flow": (168, 198, 222),
}


def draw(path: Path, layout: dict, override: str | None = None) -> None:
    image = Image.new("RGB", (layout["width"], layout["height"]), COLORS["paper"])
    drawer = ImageDraw.Draw(image)
    for cell in cells(layout):
        color = COLORS[cell["key"]]
        if cell["key"] == override:
            color = (0, 0, 0)
        drawer.rectangle(
            [cell["x"], cell["y"], cell["x"] + cell["w"] - 1, cell["y"] + cell["h"] - 1],
            fill=color,
        )
    image.save(path)


class TokenFrameTest(unittest.TestCase):
    def setUp(self):
        self.layout = load_layout(LAYOUT)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_identical_frames_pass(self):
        first = self.root / "a.png"
        second = self.root / "b.png"
        draw(first, self.layout)
        draw(second, self.layout)
        report = compare_frames(first, second, self.layout)
        self.assertEqual(report["status"], "PASS", report["failed"])
        self.assertEqual(report["worst"]["max"], 0)

    def test_one_drifted_cell_fails(self):
        first = self.root / "a.png"
        second = self.root / "b.png"
        draw(first, self.layout)
        draw(second, self.layout, override="orange")
        report = compare_frames(first, second, self.layout)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("orange", report["failed"])

    def test_wrong_size_is_an_error(self):
        first = self.root / "a.png"
        Image.new("RGB", (640, 360), (0, 0, 0)).save(first)
        second = self.root / "b.png"
        draw(second, self.layout)
        with self.assertRaises(TokenFrameError):
            compare_frames(first, second, self.layout)

    def test_missing_frame_is_an_error(self):
        with self.assertRaises(TokenFrameError):
            compare_frames(self.root / "missing.png", self.root / "x.png", self.layout)

    def test_layout_cells_cover_every_key(self):
        cells_ = cells(self.layout)
        self.assertEqual([cell["key"] for cell in cells_], self.layout["keys"])
        self.assertTrue(all(cell["x"] >= 0 and cell["y"] >= 0 for cell in cells_))

    def test_bad_layout_is_reported(self):
        path = self.root / "layout.json"
        path.write_text(json.dumps({"width": 1920}), encoding="utf-8")
        with self.assertRaises(TokenFrameError):
            load_layout(path)


if __name__ == "__main__":
    unittest.main()
