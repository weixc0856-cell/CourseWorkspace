"""Side-by-side shot comparison for human review, without aesthetic scoring."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageOps

from .shot_review import _extract_frame, _video_info

HEADER = 34


def build_comparison(
    workspace: Path,
    *,
    shot: str,
    takes: Iterable[tuple[str, Path]],
    out: Path,
) -> Path:
    workspace = Path(workspace).resolve()
    items = [(label, Path(path).resolve()) for label, path in takes]
    if len(items) < 2:
        raise ValueError("comparison needs at least two takes")
    for label, path in items:
        if not path.is_file():
            raise FileNotFoundError(f"{label}: video not found: {path}")
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    columns = len(items)
    infos = [_video_info(path) for _label, path in items]
    portrait = all((info.get("height") or 0) > (info.get("width") or 1) for info in infos)
    cell_w, cell_h = (180, 320) if portrait else (320, 180)
    sheet = Image.new("RGB", (cell_w * columns, (cell_h + HEADER) * 3), (8, 12, 14))
    draw = ImageDraw.Draw(sheet)
    for column, ((label, path), info) in enumerate(zip(items, infos)):
        duration = float(info.get("duration_s") or 0.0)
        times = [0.05, duration / 2 if duration else 0.0, max(0.0, duration - 0.1)]
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            for row, seconds in enumerate(times):
                frame_path = _extract_frame(workspace, path, seconds, temp / f"{column}-{row}.png")
                with Image.open(frame_path) as image:
                    fitted = ImageOps.contain(image.convert("RGB"), (cell_w, cell_h))
                x = column * cell_w + (cell_w - fitted.width) // 2
                y = (cell_h + HEADER) * row + HEADER + (cell_h - fitted.height) // 2
                sheet.paste(fitted, (x, y))
        draw.rectangle(
            [(column * cell_w, 0), ((column + 1) * cell_w, HEADER)],
            fill=(20, 26, 30),
        )
        draw.text((column * cell_w + 10, 10), f"{label} · {shot}", fill=(242, 235, 221))
    sheet.save(out, quality=90)
    return out
