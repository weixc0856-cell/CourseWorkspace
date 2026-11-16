"""News-side checks for the shared production contracts.

`checks.py` owns the executor and the course rules; this module only adds rules
and hands back a registry that the executor can merge in. Nothing here imports
or edits the executor.

Why `timeline_components_resolve` exists: the sprint contract validates that a
timeline entry's `renderer` is a *string*. It does not know whether that
component exists, so a typo renders nothing and still passes every gate. This
rule closes that hole by resolving every renderer against
`RemotionStudio/src/components/registry.json`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import yaml

Status = str  # "pass" | "fail" | "review" | "not_run"
RuleResult = tuple[Status, Any, Any, str]


def _find_workspace(ctx: Any) -> Path | None:
    """Locate the repo root. The executor's context carries no workspace."""
    explicit = getattr(ctx, "workspace", None)
    if explicit is not None and (Path(explicit) / "RemotionStudio" / "src" / "components" / "registry.json").is_file():
        return Path(explicit).resolve()
    candidates: list[Path] = []
    lesson_dir = getattr(ctx, "lesson_dir", None)
    build_root = getattr(ctx, "build_root", None)
    for seed in (lesson_dir, build_root):
        if seed is None:
            continue
        for parent in Path(seed).resolve().parents:
            candidates.append(parent)
    candidates.append(Path.cwd().resolve())
    for candidate in candidates:
        if (candidate / "RemotionStudio" / "src" / "components" / "registry.json").is_file():
            return candidate
    return None


def _load_timeline(ctx: Any) -> dict | None:
    path = Path(getattr(ctx, "lesson_dir")) / "authoring" / "timeline.yaml"
    if not path.is_file():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def timeline_components_resolve(ctx: Any) -> RuleResult:
    """Every renderer named in the timeline must exist in the component registry."""
    timeline = _load_timeline(ctx)
    if timeline is None:
        return "not_run", None, "authoring/timeline.yaml", str(getattr(ctx, "lesson_dir", ""))

    workspace = _find_workspace(ctx)
    if workspace is None:
        return "not_run", None, "RemotionStudio/src/components/registry.json", "workspace not found"

    registry_path = workspace / "RemotionStudio" / "src" / "components" / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    known = set((registry.get("components") or {}).keys())

    used: list[str] = []
    missing: list[str] = []
    for entry in timeline.get("entries") or []:
        renderer = entry.get("renderer")
        if not renderer:
            continue
        used.append(renderer)
        if renderer not in known:
            missing.append(f"{entry.get('id')}→{renderer}")

    if missing:
        return "fail", missing, sorted(known), str(registry_path)
    return "pass", sorted(set(used)), sorted(known), str(registry_path)


NEWS_RULES: dict[str, Callable[[Any], RuleResult]] = {
    "timeline_components_resolve": timeline_components_resolve,
}
