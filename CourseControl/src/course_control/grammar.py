"""Visual grammar registry: the machine-readable forms of motion language.

A grammar is *not* a quality standard.  It declares the production envelope a
shot opts into (length, action rhythm, continuity expectations) and the
capabilities its renderer must provide.  Quality is evaluated per grammar by
``quality_gates``; a grammar never lowers the universal hard constraints.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError, model_validator

from .contracts import StrictModel

REGISTRY_REL = Path("shared/grammars/visual-grammars.yaml")


class ShotWindow(StrictModel):
    min: float = Field(gt=0)
    max: float = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self):
        if self.max < self.min:
            raise ValueError("shot_seconds.max must be >= min")
        return self


class GrammarConstraints(StrictModel):
    first_action_by: float = Field(0.35, ge=0.0, le=1.0)
    max_action_gap_s: float = Field(4.0, gt=0)
    long_lived_ratio_min: float = Field(0.0, ge=0.0, le=1.0)
    camera_motive_required: bool = False
    min_actions: int = Field(2, ge=0)
    freeze_counts_against: bool = False
    max_cut_rate_per_10s: float | None = Field(default=None, gt=0)
    min_actions_per_10s: float = Field(2.5, gt=0)


class GrammarSpec(StrictModel):
    label: str = Field(min_length=1)
    purpose: list[str] = Field(default_factory=list)
    shot_seconds: ShotWindow
    constraints: GrammarConstraints = GrammarConstraints()
    capabilities: list[str] = Field(default_factory=list)


class GrammarRegistry(StrictModel):
    schema_version: Literal[1] = 1
    grammars: dict[str, GrammarSpec] = Field(min_length=1)

    def get(self, name: str) -> GrammarSpec:
        try:
            return self.grammars[name]
        except KeyError as exc:
            raise KeyError(f"unknown visual grammar: {name}") from exc

    def has(self, name: str) -> bool:
        return name in self.grammars


DEFAULT_LONG_TAKE = GrammarSpec(
    label="长镜头连续演化",
    shot_seconds=ShotWindow(min=5.0, max=16.0),
    constraints=GrammarConstraints(
        first_action_by=0.35,
        max_action_gap_s=4.0,
        long_lived_ratio_min=0.5,
        camera_motive_required=True,
        min_actions=2,
        freeze_counts_against=False,
        min_actions_per_10s=2.5,
    ),
    capabilities=["2d_vector", "transform", "camera_move", "deterministic"],
)


def default_registry() -> GrammarRegistry:
    """Fallback used by tests and by callers that have no workspace."""
    return GrammarRegistry(grammars={"long_take": DEFAULT_LONG_TAKE})


def load_registry(workspace: Path) -> GrammarRegistry:
    path = (workspace / REGISTRY_REL).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"visual grammar registry not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"grammar registry root must be a mapping: {path}")
    try:
        return GrammarRegistry.model_validate(data)
    except ValidationError as exc:  # pragma: no cover - surfaced as a build error
        raise ValueError(f"invalid grammar registry {path}: {exc}") from exc


def try_load_registry(workspace: Path) -> GrammarRegistry:
    try:
        return load_registry(workspace)
    except (OSError, ValueError):
        return default_registry()


__all__ = [
    "DEFAULT_LONG_TAKE",
    "GrammarConstraints",
    "GrammarRegistry",
    "GrammarSpec",
    "REGISTRY_REL",
    "ShotWindow",
    "default_registry",
    "load_registry",
    "try_load_registry",
]
