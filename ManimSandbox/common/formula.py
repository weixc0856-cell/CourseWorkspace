"""Load a FormulaSpec and turn its single LaTeX source into MathTex.

The FormulaSpec is the authority; Manim is only the animation renderer.
"""
from __future__ import annotations

import json
from pathlib import Path

from manim import MathTex


def load_formula_spec(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not str(data.get("latex", "")).strip():
        raise ValueError(f"{path}: FormulaSpec.latex is required")
    return data


def formula_tex(path: str | Path, **kwargs) -> MathTex:
    spec = load_formula_spec(path)
    return MathTex(spec["latex"], **kwargs)
