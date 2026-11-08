"""Runtime typography checks for Manim scenes.

Static layout validation cannot see the final positions of animated text. These
checks run at the end of ``construct`` and report text that leaves the safe area
or overlaps another text object. Set ``STRICT_LAYOUT=1`` to turn findings into a
render failure.
"""
from __future__ import annotations

import os
from itertools import combinations

from manim import Text, config


def _texts(mobject):
    if isinstance(mobject, Text):
        yield mobject
    for child in getattr(mobject, "submobjects", ()):
        yield from _texts(child)


def _bounds(mobject) -> tuple[float, float, float, float]:
    return (
        float(mobject.get_left()[0]),
        float(mobject.get_bottom()[1]),
        float(mobject.get_right()[0]),
        float(mobject.get_top()[1]),
    )


def _overlap(first, second, pad: float = 0.01) -> bool:
    ax0, ay0, ax1, ay1 = first
    bx0, by0, bx1, by1 = second
    return (
        min(ax1, bx1) - max(ax0, bx0) > pad
        and min(ay1, by1) - max(ay0, by0) > pad
    )


def scene_issues(scene, safe_margin: float = 0.5) -> list[str]:
    frame_left = -config.frame_width / 2 + safe_margin
    frame_right = config.frame_width / 2 - safe_margin
    frame_bottom = -config.frame_height / 2 + safe_margin
    frame_top = config.frame_height / 2 - safe_margin

    texts = list(dict.fromkeys(text for mob in scene.mobjects for text in _texts(mob)))
    issues: list[str] = []
    for text in texts:
        x0, y0, x1, y1 = _bounds(text)
        if x0 < frame_left or x1 > frame_right or y0 < frame_bottom or y1 > frame_top:
            issues.append(
                f"text outside safe area: {text.text!r} "
                f"({x0:.2f}, {y0:.2f})..({x1:.2f}, {y1:.2f})"
            )
    for first, second in combinations(texts, 2):
        if _overlap(_bounds(first), _bounds(second)):
            issues.append(f"text overlap: {first.text!r} / {second.text!r}")
    return issues


def enforce(scene, safe_margin: float = 0.5) -> None:
    issues = scene_issues(scene, safe_margin=safe_margin)
    for issue in issues:
        print(f"[layout] {issue}", flush=True)
    if issues and os.environ.get("STRICT_LAYOUT") == "1":
        raise RuntimeError("layout check failed: " + "; ".join(issues))
