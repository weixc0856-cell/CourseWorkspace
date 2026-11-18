"""Compare a two-engine colour proof against the brand tokens.

The Remotion and Manim proofs read the same ``swatch-layout.json`` and the same
``tokens.json``, then draw identical rectangles.  This module checks three
things at every sample point:

1. the two frames agree with each other;
2. each frame agrees with the expected token colour;
3. the layout geometry keeps every sample point inside the canvas.

Point 2 is what makes a blank frame fail: two blank frames agree, but they do
not carry the palette.  A drift beyond ``tolerance`` is a mismatch, not a
warning.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

DEFAULT_TOLERANCE = 3
BACKGROUND_POINT = (5, 5)


class TokenFrameError(ValueError):
    pass


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_int(value, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TokenFrameError(f"layout {name} must be an integer")
    return value


def _validate_geometry(layout: dict) -> None:
    width = _as_int(layout["width"], "width")
    height = _as_int(layout["height"], "height")
    columns = _as_int(layout["columns"], "columns")
    if width <= 10 or height <= 10:
        raise TokenFrameError("canvas must be larger than the 5 px background sample")
    if columns <= 0:
        raise TokenFrameError("layout columns must be greater than zero")
    cell = layout["cell"]
    if not isinstance(cell, dict):
        raise TokenFrameError("layout cell must be an object")
    cell_w = _as_int(cell.get("w"), "cell.w")
    cell_h = _as_int(cell.get("h"), "cell.h")
    if cell_w <= 0 or cell_h <= 0:
        raise TokenFrameError("cell width and height must be greater than zero")
    gap = _as_int(layout["gap"], "gap")
    if gap < 0:
        raise TokenFrameError("gap must not be negative")
    origin = layout["origin"]
    if not isinstance(origin, dict):
        raise TokenFrameError("layout origin must be an object")
    origin_x = _as_int(origin.get("x"), "origin.x")
    origin_y = _as_int(origin.get("y"), "origin.y")
    if origin_x < 0 or origin_y < 0:
        raise TokenFrameError("origin must not be negative")
    keys = layout["keys"]
    if not isinstance(keys, list) or not keys:
        raise TokenFrameError("layout has no keys")
    if any(not isinstance(key, str) or not key for key in keys):
        raise TokenFrameError("layout keys must be non-empty strings")
    if len(set(keys)) != len(keys):
        raise TokenFrameError("layout keys must be unique")
    if "paper" in keys:
        raise TokenFrameError(
            "paper is the canvas background, not a swatch; remove it from keys"
        )
    if BACKGROUND_POINT[0] >= width or BACKGROUND_POINT[1] >= height:
        raise TokenFrameError("background sample point is outside the canvas")

    step_x = cell_w + gap
    step_y = cell_h + gap
    for index, key in enumerate(keys):
        col = index % columns
        row = index // columns
        left = origin_x + col * step_x
        top = origin_y + row * step_y
        if left + cell_w > width or top + cell_h > height:
            raise TokenFrameError(
                f"cell {key!r} runs outside the {width}x{height} canvas"
            )


def load_layout(path: Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise TokenFrameError(f"swatch layout not found: {path}")
    try:
        layout = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TokenFrameError(f"cannot read swatch layout {path}: {exc}") from exc
    if not isinstance(layout, dict):
        raise TokenFrameError("swatch layout must be an object")
    for key in ("width", "height", "columns", "cell", "gap", "origin", "keys"):
        if key not in layout:
            raise TokenFrameError(f"swatch layout is missing {key!r}")
    _validate_geometry(layout)
    return layout


def _parse_hex(value, key: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        raise TokenFrameError(f"token {key!r} is not a #RRGGBB colour: {value!r}")
    try:
        channels = tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))
    except ValueError as exc:
        raise TokenFrameError(f"token {key!r} is not a #RRGGBB colour: {value!r}") from exc
    return channels  # type: ignore[return-value]


def load_tokens(path: Path) -> dict[str, tuple[int, int, int]]:
    path = Path(path)
    if not path.is_file():
        raise TokenFrameError(f"tokens file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TokenFrameError(f"cannot read tokens {path}: {exc}") from exc
    colors = data.get("colors") if isinstance(data, dict) else None
    if not isinstance(colors, dict):
        raise TokenFrameError("tokens file has no colors object")
    return {key: _parse_hex(value, key) for key, value in colors.items()}


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
        raise TokenFrameError(
            f"{path} is {image.size[0]}x{image.size[1]}, expected {expected[0]}x{expected[1]}"
        )
    return image


def _pixel(image: Image.Image, x: int, y: int) -> tuple[int, int, int]:
    return image.getpixel((x, y))


def _delta(a: tuple[int, int, int], b: tuple[int, int, int]) -> tuple[list[int], int]:
    channels = [abs(a[index] - b[index]) for index in range(3)]
    return channels, max(channels)


def _row(
    key: str,
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    expected: tuple[int, int, int],
) -> dict:
    ab_channels, ab_max = _delta(a, b)
    a_channels, a_max = _delta(a, expected)
    b_channels, b_max = _delta(b, expected)
    worst = max(ab_max, a_max, b_max)
    return {
        "key": key,
        "expected": list(expected),
        "a": list(a),
        "b": list(b),
        "a_b": ab_channels,
        "a_expected": a_channels,
        "b_expected": b_channels,
        "max": worst,
    }


def compare_frames(
    frame_a: Path,
    frame_b: Path,
    layout: dict,
    tokens: dict[str, tuple[int, int, int]],
    *,
    tolerance: int = DEFAULT_TOLERANCE,
    layout_path: Path | None = None,
    tokens_path: Path | None = None,
) -> dict:
    missing = [key for key in layout["keys"] if key not in tokens]
    if missing:
        raise TokenFrameError("layout keys missing from tokens: " + ", ".join(missing))
    if "paper" not in tokens:
        raise TokenFrameError("tokens are missing the paper background colour")
    image_a = _open(frame_a, layout)
    image_b = _open(frame_b, layout)
    rows = [
        _row(
            "background",
            _pixel(image_a, *BACKGROUND_POINT),
            _pixel(image_b, *BACKGROUND_POINT),
            tokens["paper"],
        )
    ]
    for cell in cells(layout):
        center_x = cell["x"] + cell["w"] // 2
        center_y = cell["y"] + cell["h"] // 2
        row = _row(
            cell["key"],
            _pixel(image_a, center_x, center_y),
            _pixel(image_b, center_x, center_y),
            tokens[cell["key"]],
        )
        row["at"] = [center_x, center_y]
        rows.append(row)
    worst = max(rows, key=lambda row: row["max"])
    failed = [row["key"] for row in rows if row["max"] > tolerance]
    return {
        "schema_version": 2,
        "status": "PASS" if not failed else "FAIL",
        "tolerance": tolerance,
        "frame_a": str(frame_a),
        "frame_b": str(frame_b),
        "frame_a_sha256": file_sha256(frame_a),
        "frame_b_sha256": file_sha256(frame_b),
        "layout_sha256": file_sha256(layout_path) if layout_path else None,
        "tokens_sha256": file_sha256(tokens_path) if tokens_path else None,
        "rows": rows,
        "failed": failed,
        "worst": {"key": worst["key"], "max": worst["max"]},
    }


def verify_report(
    report,
    *,
    layout: dict,
    tokens: dict[str, tuple[int, int, int]],
    layout_path: Path,
    tokens_path: Path,
    report_path: Path,
    tolerance: int = DEFAULT_TOLERANCE,
) -> dict:
    """Recompute the proof from the actual frames and compare it with the report.

    A report is only evidence if its rows can be reproduced from the frame
    files and the current tokens.  Structure errors are INCOMPLETE; any
    mismatch between the saved report and the recomputed one is FAIL.
    """
    structural: list[str] = []
    mismatches: list[str] = []
    if not isinstance(report, dict):
        return {"status": "INCOMPLETE", "problems": ["report is not an object"]}
    if report.get("schema_version") != 2:
        structural.append("schema_version is not 2")
    if report.get("tolerance") != tolerance:
        mismatches.append(
            f"tolerance is {report.get('tolerance')!r}, expected {tolerance}"
        )

    rows = report.get("rows")
    expected_keys = ["background"] + list(layout["keys"])
    if not isinstance(rows, list):
        structural.append("rows is not a list")
        rows = []
    if len(rows) != len(expected_keys):
        structural.append(f"rows has {len(rows)} entries, expected {len(expected_keys)}")
    saved_rows: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            structural.append("row is not an object")
            continue
        key = row.get("key")
        if key not in expected_keys:
            structural.append(f"unknown row key {key!r}")
            continue
        if key in saved_rows:
            structural.append(f"duplicate row key {key!r}")
            continue
        saved_rows[key] = row
    if sorted(saved_rows) != sorted(expected_keys):
        structural.append("row keys do not match the layout")

    frames: dict[str, Path] = {}
    for key, hash_key in (("frame_a", "frame_a_sha256"), ("frame_b", "frame_b_sha256")):
        raw = report.get(key)
        recorded = report.get(hash_key)
        if not raw:
            structural.append(f"{key} path is missing")
            continue
        frame = Path(str(raw))
        if not frame.is_absolute():
            frame = Path(report_path).parent / frame
        if not frame.is_file():
            structural.append(f"{key} file is missing: {frame}")
            continue
        frames[key] = frame
        if not recorded:
            structural.append(f"{hash_key} is missing")
        elif recorded != file_sha256(frame):
            mismatches.append(f"{hash_key} does not match {frame.name}")

    for key, path in (("layout_sha256", layout_path), ("tokens_sha256", tokens_path)):
        recorded = report.get(key)
        if not recorded:
            structural.append(f"{key} is missing")
        elif recorded != file_sha256(path):
            mismatches.append(f"{key} does not match the current {Path(path).name}")

    if structural:
        return {"status": "INCOMPLETE", "problems": structural + mismatches}

    try:
        fresh = compare_frames(
            frames["frame_a"],
            frames["frame_b"],
            layout,
            tokens,
            tolerance=tolerance,
            layout_path=layout_path,
            tokens_path=tokens_path,
        )
    except TokenFrameError as exc:
        return {
            "status": "INCOMPLETE",
            "problems": [f"cannot recompute from the frames: {exc}"],
        }
    if report.get("status") != fresh["status"]:
        mismatches.append(
            f"status is {report.get('status')!r}, recomputed {fresh['status']!r}"
        )
    if report.get("failed") != fresh["failed"]:
        mismatches.append("failed list does not match the recomputed rows")
    if report.get("worst") != fresh["worst"]:
        mismatches.append("worst does not match the recomputed rows")
    fresh_rows = {row["key"]: row for row in fresh["rows"]}
    for key, fresh_row in fresh_rows.items():
        saved = saved_rows.get(key)
        if saved is None:
            structural.append(f"row {key!r} is missing")
            continue
        for field in ("expected", "a", "b", "max"):
            if saved.get(field) != fresh_row[field]:
                mismatches.append(f"{key}: saved {field} does not match the frame")

    if structural:
        status = "INCOMPLETE"
    elif mismatches:
        status = "FAIL"
    else:
        status = "PASS"
    return {"status": status, "problems": structural + mismatches}
