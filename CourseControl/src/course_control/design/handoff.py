"""Carry the visual design's per-shot theme into the build handoff.

The design layer decides which theme a shot renders in.  Until now that decision
stopped at ``design/visual_design.json``: every ShotSpec reached the engines with
``theme=None``.  This module is the one-way wire — design wins for shots that do
not declare a theme themselves, and a shot's own storyboard value always wins.
"""
from __future__ import annotations

import json
from pathlib import Path

from course_control.content.contracts import Storyboard

DESIGN_FILE = ("design", "visual_design.json")


def load_theme_map(build_root: Path) -> dict[str, str]:
    path = Path(build_root).joinpath(*DESIGN_FILE)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    themes: dict[str, str] = {}
    for shot in data.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        theme = (shot.get("art_direction") or {}).get("theme")
        shot_id = shot.get("shot_id")
        if isinstance(theme, str) and isinstance(shot_id, str):
            themes[shot_id] = theme
    return themes


def apply_themes(storyboard: Storyboard, themes: dict[str, str]) -> tuple[Storyboard, list[str]]:
    """Return the storyboard with design themes applied, plus the shot ids changed."""
    if not themes:
        return storyboard, []
    changed: list[str] = []
    shots = []
    for shot in storyboard.shots:
        theme = themes.get(shot.id)
        if theme and shot.theme is None:
            shot = shot.model_copy(update={"theme": theme})
            changed.append(shot.id)
        shots.append(shot)
    if not changed:
        return storyboard, []
    return storyboard.model_copy(update={"shots": shots}), changed
