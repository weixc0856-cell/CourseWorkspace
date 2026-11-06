"""Deterministic scalar fields for scientific visualization.

This module must stay dependency-free apart from the standard library: it runs
inside Blender's bundled Python and is imported by both the executor and the
scene verifier.
"""

from __future__ import annotations

import math
import os
import sys
from functools import lru_cache

AXES = {"x": 0, "y": 1, "z": 2}

_SOURCE = os.path.join(os.getcwd(), "shared", "scene_expr", "src")
if _SOURCE not in sys.path:
    sys.path.insert(0, _SOURCE)

from scene_expr import ExpressionError, compile_expression  # noqa: E402


@lru_cache(maxsize=64)
def compile_cached(expression):
    return compile_expression(expression)


def evaluate_field(field, coordinate):
    kind = field["kind"]
    if kind == "axis":
        value = coordinate[AXES[field["axis"]]]
        return float(value) * field["scale"] + field["offset"]
    if kind == "distance":
        point = field["point"]
        dx = float(coordinate[0]) - point[0]
        dy = float(coordinate[1]) - point[1]
        dz = float(coordinate[2]) - point[2]
        return math.sqrt(dx * dx + dy * dy + dz * dz) * field["scale"]
    if kind == "noise":
        x = float(coordinate[0]) * field["scale"]
        y = float(coordinate[1]) * field["scale"]
        z = float(coordinate[2]) * field["scale"]
        value = math.sin(
            x * 12.9898 + y * 78.233 + z * 37.719 + field["seed"] * 0.137
        ) * 43758.5453
        return value - math.floor(value)
    if kind == "expression":
        compiled = compile_cached(field["expression"])
        try:
            return compiled(coordinate[0], coordinate[1], coordinate[2])
        except ExpressionError as exc:
            raise ValueError(f"expression failed: {exc}") from exc
    raise ValueError(f"unsupported field kind: {kind}")
