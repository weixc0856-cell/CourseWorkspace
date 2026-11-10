"""Read-only audit of the production-plan representations for one lesson.

There is one authority per mode: `shots` uses `authoring/production.yaml`;
`deck` and `scene` use `storyboard.yaml`.  The director plan, beat sheet and
normalized timeline are views, not a second authority.  This tool reports
where the counts disagree so a migration can be planned instead of guessed.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .paths import LessonPaths


def _count_yaml(path: Path, key: str) -> int | None:
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    if key == "shots":
        return len(data.get("shots") or [])
    if key == "sequences":
        return sum(len(sequence.get("shots") or []) for sequence in data.get("sequences") or [])
    return None


def _director_shots(paths: LessonPaths) -> int | None:
    path = paths.build_root / "director" / "director_plan.json"
    if not path.is_file():
        return None
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return len(data.get("shots") or []) if isinstance(data, dict) else None


def audit_plan(paths: LessonPaths) -> dict:
    mode = paths.lesson.compose.mode
    production = _count_yaml(paths.lesson_dir / "authoring" / "production.yaml", "sequences")
    storyboard = None if mode == "shots" else len(paths.storyboard.shots)
    beats = _count_yaml(paths.lesson_dir / "authoring" / "beats.yaml", "shots")
    director = _director_shots(paths)
    shots_file = paths.build_root / "shots.json"
    build_shots = None
    if shots_file.is_file():
        try:
            import json

            build_shots = len(json.loads(shots_file.read_text(encoding="utf-8")).get("shots") or [])
        except (OSError, ValueError):
            build_shots = None
    authority = "production.yaml" if mode == "shots" else "storyboard.yaml"
    counts = {
        "storyboard": storyboard,
        "production": production,
        "beats": beats,
        "director": director,
        "build_shots": build_shots,
    }
    expected = counts["production"] if mode == "shots" else counts["storyboard"]
    mismatches = {
        key: value
        for key, value in counts.items()
        if key not in {"storyboard", "production"} and value is not None and expected is not None and value != expected
    }
    return {
        "schema_version": 1,
        "lesson": paths.slug,
        "mode": mode,
        "authority": authority,
        "counts": counts,
        "expected": expected,
        "mismatches": mismatches,
        "note": (
            "deck/scene: Page is the production unit; beats are internal actions, "
            "not independently re-rendered shots. shots: Shot is the unit."
        ),
    }
