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


# --- cross-engine consistency ------------------------------------------------
#
# Remotion imports tokens.json directly.  Manim and the layout system keep
# Python copies, and those copies are what actually render.  This check turns a
# silent hex drift into a single failing command; it does not add a new palette.

_MANIM_NAMES = {
    "BG": "paper",
    "SURFACE": "surface",
    "INK": "ink",
    "BODY": "text",
    "MUTED": "muted",
    "DIVIDER": "border",
    "ORANGE": "orange",
    "NAVY": "navy",
    "BLUE": "blue",
    "TEAL": "teal",
    "PURPLE": "purple",
    "RED": "red",
    "FLOW": "flow",
}

_LAYOUT_NAMES = {
    "background": "paper",
    "surface": "surface",
    "ink": "ink",
    "body": "text",
    "muted": "muted",
    "accent": "orange",
    "navy": "navy",
    "blue": "blue",
    "teal": "teal",
    "purple": "purple",
    "red": "red",
    "flow": "flow",
    "divider": "border",
}

_THEME_NAMES = {
    "paper": "paper",
    "surface": "surface",
    "ink": "ink",
    "body": "text",
    "muted": "muted",
    "border": "border",
    "accent": "orange",
    "blue": "blue",
    "teal": "teal",
    "purple": "purple",
    "red": "red",
}


def _python_hexes(path: Path, names: dict[str, str]) -> dict[str, str]:
    import re

    text = Path(path).read_text(encoding="utf-8")
    found: dict[str, str] = {}
    for source in names:
        match = re.search(rf'^{source}\s*(?::\s*str\s*)?=\s*"(#[0-9A-Fa-f]{{6}})"', text, flags=re.M)
        if match:
            found[source] = match.group(1)
    return found


def consistency_problems(workspace: Path) -> list[str]:
    """Compare the three brand-token carriers; return one line per drift.

    Blender is deliberately absent: its scene colours are lighting decisions,
    not brand tokens.  The engines that draw the channel's visual identity are
    Remotion (tokens.json), Manim (design_system.py) and the layout system.
    """
    workspace = Path(workspace)
    tokens = json.loads(
        (workspace / "shared" / "design-tokens" / "tokens.json").read_text(encoding="utf-8")
    )["colors"]
    themes = _read(workspace)["themes"]["editorial_science"]["colors"]
    problems: list[str] = []

    def compare(label: str, values: dict[str, str], mapping: dict[str, str]) -> None:
        for source, token in mapping.items():
            expected = tokens.get(token)
            actual = values.get(source)
            if expected is None:
                problems.append(f"{label}: token {token!r} is missing")
            elif actual is None:
                problems.append(f"{label}: {source!r} is missing")
            elif actual.upper() != expected.upper():
                problems.append(
                    f"{label}: {source} is {actual}, tokens.{token} is {expected}"
                )

    compare("themes.editorial_science", themes, _THEME_NAMES)
    compare(
        "ManimSandbox/common/design_system.py",
        _python_hexes(workspace / "ManimSandbox" / "common" / "design_system.py", _MANIM_NAMES),
        _MANIM_NAMES,
    )
    from course_control.rendering.layout import DESIGN

    layout = {
        "background": DESIGN.background,
        "surface": DESIGN.surface,
        "ink": DESIGN.ink,
        "body": DESIGN.body,
        "muted": DESIGN.muted,
        "accent": DESIGN.accent,
        "navy": DESIGN.navy,
        "blue": DESIGN.blue,
        "teal": DESIGN.teal,
        "purple": DESIGN.purple,
        "red": DESIGN.red,
        "flow": DESIGN.flow,
        "divider": DESIGN.divider,
    }
    compare("rendering.layout.DESIGN", layout, _LAYOUT_NAMES)
    return problems
