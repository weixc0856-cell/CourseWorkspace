"""Shared visual themes.

The colour values live in ``shared/design-tokens/themes.json`` so that Blender,
Manim, Motion Canvas, code-video scenes and Remotion read one source.  This
module only loads them and hands a scene a plain dict; it never grades pixels.

Themes are a default, not a gate: a scene that declares no theme gets
``editorial_science`` and nothing fails for using a dark one.
"""
from __future__ import annotations

import json
from pathlib import Path

# Kept in sync with shared/design-tokens/themes.json; tests assert the file has
# exactly these keys.
SCENE_THEMES = ("editorial_science", "deep_space", "engineering_studio")
DEFAULT_THEME = "editorial_science"


def themes_path(workspace: Path) -> Path:
    return Path(workspace) / "shared" / "design-tokens" / "themes.json"


def _read(workspace: Path) -> dict:
    path = themes_path(workspace)
    if not path.is_file():
        raise FileNotFoundError(f"theme tokens not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def theme_names(workspace: Path) -> tuple[str, ...]:
    return tuple(_read(workspace)["themes"].keys())


def load_theme(workspace: Path, name: str | None = None) -> dict:
    """Return one theme as a flat dict: colours, fonts, role and semantics."""
    data = _read(workspace)
    key = name or data.get("default", DEFAULT_THEME)
    themes = data["themes"]
    if key not in themes:
        raise KeyError(f"unknown theme: {key}")
    theme = dict(themes[key])
    theme["name"] = key
    theme["default"] = data.get("default", DEFAULT_THEME)
    theme["semantics"] = data.get("semantics", {})
    theme["rules"] = data.get("rules", [])
    return theme


def write_theme_json(workspace: Path, target: Path, name: str | None = None) -> Path:
    """Materialise ``theme.json`` next to a scene, for capture.mjs to serve."""
    payload = load_theme(workspace, name)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
