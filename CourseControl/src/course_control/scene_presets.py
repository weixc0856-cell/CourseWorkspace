from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from .paths import ContractError

PRESET_ROOT = Path("BlenderStudio") / "assets" / "materials" / "presets"
PRESET_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SHADERS = {"principled", "emission"}


def preset_root(workspace: Path) -> Path:
    return workspace / PRESET_ROOT


def load_presets(workspace: Path) -> dict[str, dict]:
    directory = preset_root(workspace)
    if not directory.is_dir():
        raise ContractError(f"material preset directory not found: {directory}")
    presets: dict[str, dict] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ContractError(f"{path.name}: invalid JSON: {exc}") from exc
        name = data.get("preset")
        if not isinstance(name, str) or not PRESET_NAME_RE.match(name):
            raise ContractError(f"{path.name}: invalid preset name: {name!r}")
        if name in presets:
            raise ContractError(f"duplicate material preset: {name}")
        shader = data.get("shader")
        if shader not in SHADERS:
            raise ContractError(f"{path.name}: shader must be one of {sorted(SHADERS)}")
        params = data.get("params") or {}
        if not isinstance(params, dict):
            raise ContractError(f"{path.name}: params must be an object")
        presets[name] = {
            "preset": name,
            "shader": shader,
            "params": params,
            "path": path.relative_to(workspace).as_posix(),
        }
    if not presets:
        raise ContractError(f"no material presets found in {directory}")
    return presets


def expand_task(task: dict, workspace: Path) -> tuple[dict, list[dict]]:
    """Return a deep-copied task with preset materials expanded.

    The expanded task is the effective contract: both validators and Blender
    only ever see ``shader`` + ``params``. The returned references are recorded
    in the run manifest so the expansion stays traceable.
    """
    if not isinstance(task, dict):
        raise ContractError("task must be a JSON object")
    raw_materials = task.get("materials")
    if not isinstance(raw_materials, list):
        return copy.deepcopy(task), []

    presets: dict[str, dict] | None = None
    expanded_materials = []
    references: list[dict] = []
    for index, item in enumerate(raw_materials):
        if not isinstance(item, dict) or "preset" not in item:
            expanded_materials.append(copy.deepcopy(item))
            continue
        if "shader" in item or "params" in item:
            raise ContractError(
                f"materials[{index}]: preset cannot be combined with shader or params"
            )
        if presets is None:
            presets = load_presets(workspace)
        name = item.get("preset")
        definition = presets.get(name)
        if definition is None:
            raise ContractError(
                f"materials[{index}]: unknown preset {name!r}; "
                f"available: {sorted(presets)}"
            )
        expanded_materials.append(
            {
                "id": item.get("id"),
                "shader": definition["shader"],
                "params": copy.deepcopy(definition["params"]),
            }
        )
        references.append(
            {
                "material": item.get("id"),
                "preset": name,
                "path": definition["path"],
            }
        )

    result = copy.deepcopy(task)
    result["materials"] = expanded_materials
    return result, references
