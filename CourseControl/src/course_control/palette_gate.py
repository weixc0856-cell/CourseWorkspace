"""Palette accessibility gate for the build pipeline.

The palette table lives with the animation project
(``ManimSandbox/common/palettes.py``); it is pure standard library, so the
build tool can load it by path without importing Manim.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

GATES = {"ink_contrast": 7.0, "focus_contrast": 3.0, "support_contrast": 3.0, "muted_contrast": 4.5}


def load_module(workspace: Path):
    path = Path(workspace) / "ManimSandbox" / "common" / "palettes.py"
    if not path.is_file():
        raise FileNotFoundError(f"palette table not found: {path}")
    spec = importlib.util.spec_from_file_location("course_palettes", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load palette table: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def report(workspace: Path, key: str) -> dict:
    return load_module(workspace).report(key)


def ok(data: dict) -> bool:
    return all(float(data[field]) >= threshold for field, threshold in GATES.items())


def describe(data: dict) -> str:
    parts = [f"{field}={data[field]}:1 (min {GATES[field]:.0f})" for field in GATES]
    return ", ".join(parts)
