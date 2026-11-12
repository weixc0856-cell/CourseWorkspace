from __future__ import annotations

import json
from pathlib import Path

from course_control.content.paths import ContractError

COLORMAP_PATH = Path("shared") / "colormaps.json"


def load_colormaps(workspace: Path) -> dict:
    path = workspace / COLORMAP_PATH
    if not path.is_file():
        raise ContractError(f"colormap library not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(f"colormap library is not valid JSON: {exc}") from exc
    colormaps = data.get("colormaps")
    if not isinstance(colormaps, dict) or not colormaps:
        raise ContractError("colormap library has no colormaps")
    return colormaps
