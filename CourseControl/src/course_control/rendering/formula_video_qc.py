"""Final-video formula check: crop the declared region and compare its edge map
with the rendered formula PNG. This is a presence/visibility check, not OCR and
not a substitute for human mathematical review.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat

from course_control.rendering.formulas import FormulaSpec, render_formula
from course_control.platform.utils import which_command


def _edge_signature(path: Path, size: int = 96) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    background.alpha_composite(image)
    gray = ImageOps.grayscale(background)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    if edges.width > 6 and edges.height > 6:
        edges = edges.crop((3, 3, edges.width - 3, edges.height - 3))
    return edges.resize((size, size), Image.Resampling.BILINEAR)


def image_similarity(expected: Path, actual: Path) -> float:
    """Return normalized edge-map similarity in [0, 1]."""
    left = _edge_signature(expected)
    right = _edge_signature(actual)
    if ImageStat.Stat(left).mean[0] < 1.0 or ImageStat.Stat(right).mean[0] < 1.0:
        return 0.0
    left_values = list(left.getdata())  # type: ignore[arg-type]
    right_values = list(right.getdata())  # type: ignore[arg-type]
    mean_left = sum(left_values) / len(left_values)
    mean_right = sum(right_values) / len(right_values)
    numerator = sum(
        (a - mean_left) * (b - mean_right)
        for a, b in zip(left_values, right_values)
    )
    denom_left = sum((a - mean_left) ** 2 for a in left_values) ** 0.5
    denom_right = sum((b - mean_right) ** 2 for b in right_values) ** 0.5
    if denom_left == 0 or denom_right == 0:
        return 0.0
    return max(0.0, min(1.0, numerator / (denom_left * denom_right)))


def _crop_frame(
    video: Path,
    timestamp_s: float,
    bbox: tuple[int, int, int, int],
    out: Path,
) -> Path:
    x, y, width, height = bbox
    if width <= 0 or height <= 0:
        raise ValueError("bbox width/height must be positive")
    out.parent.mkdir(parents=True, exist_ok=True)
    command = [
        *which_command("ffmpeg"),
        "-v", "error", "-y",
        "-ss", f"{timestamp_s:.3f}",
        "-i", str(video),
        "-frames:v", "1",
        "-vf", f"crop={width}:{height}:{x}:{y}",
        str(out),
    ]
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0 or not out.is_file():
        raise RuntimeError(f"frame crop failed: {result.stderr[-800:]}")
    return out


def check_formula_video(
    spec: FormulaSpec,
    video: Path,
    timestamp_s: float,
    bbox: tuple[int, int, int, int],
    out_dir: Path,
    workspace: Path,
    *,
    threshold: float = 0.45,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    render = render_formula(spec, out_dir / "formula", workspace)
    expected = Path(render["png"])
    actual = _crop_frame(video, timestamp_s, bbox, out_dir / "video-crop.png")
    score = image_similarity(expected, actual)
    result = {
        "formula_id": spec.formula_id,
        "video": str(video),
        "timestamp_s": timestamp_s,
        "bbox": bbox,
        "expected_png": str(expected),
        "actual_crop": str(actual),
        "edge_similarity": round(score, 4),
        "threshold": threshold,
        "pass": score >= threshold,
        "note": "edge-presence check only; mathematical review remains separate",
    }
    (out_dir / "formula.video.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def load_bbox(value: str) -> tuple[int, int, int, int]:
    parts = [int(item.strip()) for item in value.replace("x", ",").split(",") if item.strip()]
    if len(parts) != 4:
        raise ValueError("bbox must be x,y,w,h")
    return parts[0], parts[1], parts[2], parts[3]
