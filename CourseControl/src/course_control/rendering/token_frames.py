"""Compare two one-frame colour references cell by cell.

The Remotion and Manim proofs read the same ``swatch-layout.json`` and the same
brand tokens, then draw identical rectangles.  This module samples the centre
of every cell (and the background corner) and reports the delta; it does not
grade aesthetics.  A drift beyond ``tolerance`` is a mismatch, not a warning.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

DEFAULT_TOLERANCE = 3


class TokenFrameError(ValueError):
    pass


def load_layout(path: Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise TokenFrameError(f"swatch layout not found: {path}")
    try:
        layout = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TokenFrameError(f"cannot read swatch layout {path}: {exc}") from exc
    for key in ("width", "height", "columns", "cell", "gap", "origin", "keys"):
        if key not in layout:
            raise TokenFrameError(f"swatch layout is missing {key!r}")
    if not layout["keys"]:
        raise TokenFrameError("swatch layout has no keys")
    return layout


def cells(layout: dict) -> list[dict]:
    cell_w = int(layout["cell"]["w"])
    cell_h = int(layout["cell"]["h"])
    step_x = cell_w + int(layout["gap"])
    step_y = cell_h + int(layout["gap"])
    result = []
    for index, key in enumerate(layout["keys"]):
        col = index % int(layout["columns"])
        row = index // int(layout["columns"])
        result.append(
            {
                "key": key,
                "x": int(layout["origin"]["x"]) + col * step_x,
                "y": int(layout["origin"]["y"]) + row * step_y,
                "w": cell_w,
                "h": cell_h,
            }
        )
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open(path: Path, layout: dict) -> Image.Image:
    path = Path(path)
    if not path.is_file():
        raise TokenFrameError(f"frame not found: {path}")
    try:
        image = Image.open(path).convert("RGB")
    except OSError as exc:
        raise TokenFrameError(f"cannot read frame {path}: {exc}") from exc
    expected = (int(layout["width"]), int(layout["height"]))
    if image.size != expected:
        raise TokenFrameError(f"{path} is {image.size[0]}x{image.size[1]}, expected {expected[0]}x{expected[1]}")
    return image


def _pixel(image: Image.Image, x: int, y: int) -> tuple[int, int, int]:
    return image.getpixel((x, y))


def _delta(a: tuple[int, int, int], b: tuple[int, int, int]) -> dict:
    channels = [abs(a[index] - b[index]) for index in range(3)]
    return {
        "a": list(a),
        "b": list(b),
        "channels": channels,
        "max": max(channels),
        "euclidean": round(sum(channel * channel for channel in channels) ** 0.5, 2),
    }


def compare_frames(
    frame_a: Path,
    frame_b: Path,
    layout: dict,
    *,
    tolerance: int = DEFAULT_TOLERANCE,
) -> dict:
    image_a = _open(frame_a, layout)
    image_b = _open(frame_b, layout)
    rows = []
    background = _delta(_pixel(image_a, 5, 5), _pixel(image_b, 5, 5))
    background["key"] = "background"
    rows.append(background)
    for cell in cells(layout):
        center_x = cell["x"] + cell["w"] // 2
        center_y = cell["y"] + cell["h"] // 2
        row = _delta(_pixel(image_a, center_x, center_y), _pixel(image_b, center_x, center_y))
        row["key"] = cell["key"]
        row["at"] = [center_x, center_y]
        rows.append(row)
    worst = max(rows, key=lambda row: row["max"])
    failed = [row for row in rows if row["max"] > tolerance]
    return {
        "schema_version": 1,
        "status": "PASS" if not failed else "FAIL",
        "tolerance": tolerance,
        "frame_a": str(frame_a),
        "frame_b": str(frame_b),
        "frame_a_sha256": _sha256(frame_a),
        "frame_b_sha256": _sha256(frame_b),
        "rows": rows,
        "failed": [row["key"] for row in failed],
        "worst": {"key": worst["key"], "max": worst["max"]},
    }
