"""Measure the horizontal centre of every content band in a brand still.

Usage:
    uv run --project CourseControl python scripts/brand-centers.py <png> [max_delta_px]

The end card must keep every band on the frame's vertical axis (x = width/2).
Trailing letter-spacing and left-aligned taglines are the usual culprits; this
script reports the ink bounding box, not the CSS box, so it sees both.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def bands(path: Path, threshold: int = 12):
    image = Image.open(path).convert("RGB")
    width, height = image.size
    background = image.getpixel((4, 4))
    pixels = image.load()

    rows: list[tuple[int, int] | None] = []
    for y in range(height):
        xs = [
            x
            for x in range(width)
            if max(abs(pixels[x, y][i] - background[i]) for i in range(3)) > threshold
        ]
        rows.append((min(xs), max(xs)) if xs else None)

    found: list[tuple[int, int]] = []
    start: int | None = None
    for y, span in enumerate(rows + [None]):
        if span and start is None:
            start = y
        if not span and start is not None:
            found.append((start, y - 1))
            start = None

    result = []
    for y0, y1 in found:
        xs = [
            x
            for y in range(y0, y1 + 1)
            if rows[y]
            for x in range(rows[y][0], rows[y][1] + 1)
            if max(abs(pixels[x, y][i] - background[i]) for i in range(3)) > threshold
        ]
        if not xs:
            continue
        result.append(
            {
                "y0": y0,
                "y1": y1,
                "x0": min(xs),
                "x1": max(xs),
                "center_x": (min(xs) + max(xs)) / 2,
            }
        )
    return width, height, result


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    tolerance = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    width, height, found = bands(path)
    axis = width / 2
    failed = False
    print(f"{path.name}: {width}x{height}, axis {axis:.1f}px, tolerance {tolerance}px")
    for index, band in enumerate(found):
        delta = band["center_x"] - axis
        status = "ok" if abs(delta) <= tolerance else "OFF"
        failed = failed or abs(delta) > tolerance
        print(
            f"band {index}: y {band['y0']}-{band['y1']}  "
            f"x {band['x0']}-{band['x1']}  "
            f"center_x {band['center_x']:.2f}  delta {delta:+.2f}  {status}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
