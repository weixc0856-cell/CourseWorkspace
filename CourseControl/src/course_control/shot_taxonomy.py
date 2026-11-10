"""Load and validate the shot capability taxonomy."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REQUIRED = (
    "purpose",
    "input_contract",
    "visual_goal",
    "use_when",
    "avoid_when",
    "animation_rules",
    "quality_checks",
)
EXPECTED = (
    "concept",
    "mechanism",
    "comparison",
    "data",
    "structure",
    "transformation",
    "narrative",
    "summary",
)
STATUSES = {"verified", "unverified"}


def load_taxonomy(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"shot taxonomy not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("shot taxonomy must be a mapping")
    return data


def validate(data: dict) -> list[str]:
    problems: list[str] = []
    types = data.get("types")
    if not isinstance(types, dict) or not types:
        return ["types must be a non-empty mapping"]
    for name in EXPECTED:
        if name not in types:
            problems.append(f"missing shot type: {name}")
    for name, spec in types.items():
        if not isinstance(spec, dict):
            problems.append(f"{name}: must be a mapping")
            continue
        status = spec.get("status")
        if status not in STATUSES:
            problems.append(f"{name}: status must be one of {sorted(STATUSES)}")
        for key in REQUIRED:
            value = spec.get(key)
            if value in (None, "", [], {}):
                problems.append(f"{name}: {key} is missing")
        if status == "verified" and not spec.get("sample"):
            problems.append(f"{name}: verified without a sample")
        if status == "unverified" and spec.get("sample"):
            problems.append(f"{name}: unverified but declares a sample")
    return problems


def _sample_ok(workspace: Path, sample: str | None) -> bool:
    """A sample counts only when SPEC, VERIFY and no failing must-have exist."""
    if not sample:
        return False
    project = workspace / str(sample)
    verify = project / "VERIFY.md"
    if not (project / "SPEC.md").is_file() or not verify.is_file():
        return False
    text = verify.read_text(encoding="utf-8", errors="replace")
    return not re.search(r"\|\s*fail\s*\|", text, re.I)


def coverage(data: dict, workspace: Path) -> dict:
    verified = []
    unverified = []
    for name, spec in (data.get("types") or {}).items():
        if (spec or {}).get("status") == "verified" and _sample_ok(
            workspace, (spec or {}).get("sample")
        ):
            verified.append(name)
        else:
            unverified.append(name)
    return {"verified": sorted(verified), "unverified": sorted(unverified)}


__all__ = ["EXPECTED", "coverage", "load_taxonomy", "validate"]
