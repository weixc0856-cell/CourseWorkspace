"""Deterministic slow camera moves for captured still slides."""
from __future__ import annotations

from .contracts import MotionPolicy


def slide_motion(index: int, policy: MotionPolicy) -> dict | None:
    """Return a Ken Burns spec for slide ``index`` or None for static slides."""
    if policy.slides == "static":
        return None
    hi = max(1.04, policy.scale)
    lo = 1.04
    pan = policy.pan_percent
    patterns = [
        (lo, hi, 0.0, 0.0, pan, -pan),
        (hi, lo, -pan, pan, 0.0, 0.0),
        (1.04, min(1.10, hi + 0.02), pan, -pan, 0.0, 0.0),
        (min(1.10, hi + 0.02), 1.04, 0.0, 0.0, -pan, pan),
    ]
    scale_from, scale_to, x_from, x_to, y_from, y_to = patterns[(index - 1) % 4]
    return {
        "kind": "ken_burns",
        "scale_from": round(scale_from, 4),
        "scale_to": round(scale_to, 4),
        "pan_x_from": round(x_from, 3),
        "pan_x_to": round(x_to, 3),
        "pan_y_from": round(y_from, 3),
        "pan_y_to": round(y_to, 3),
    }
