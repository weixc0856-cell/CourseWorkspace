"""Production contract: Lesson / Sequence / Shot.

Shots are the only timing authority.  A sequence groups shots for authoring and
review; it never carries its own clock.  The contract says how a shot is
produced, not how it should look.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError, model_validator

from .renderers import RENDERERS, missing_capabilities
from .contracts import ShotSpec, Storyboard, StrictModel, Transition, TransitionKind

Purpose = Literal[
    "explain", "demonstrate", "simulate", "compare",
    "narrate", "emote", "orient", "summarize",
]
Renderer = Literal["code_video", "manim", "motion_canvas", "blender", "remotion"]
CameraMovement = Literal["static", "pan", "push_in", "pull_out", "orbit", "handheld"]


class CameraPlan(StrictModel):
    movement: CameraMovement = "static"
    motive: str | None = None

    @model_validator(mode="after")
    def _motive_when_moving(self):
        if self.movement != "static" and not (self.motive or "").strip():
            raise ValueError("a moving camera needs a motive")
        return self


class ActionPlan(StrictModel):
    type: str = Field(min_length=1)
    target: str | None = None
    at: float = Field(0.0, ge=0.0, le=1.0)
    note: str | None = None


class ShotPlan(StrictModel):
    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    duration_s: float = Field(gt=0)
    purpose: Purpose
    visual_type: str = Field(min_length=1)
    grammar: str = Field(min_length=1)
    techniques: list[str] = Field(default_factory=list)
    renderer: Renderer
    source: str | None = None
    transition: Transition = Transition()
    camera: CameraPlan = CameraPlan()
    objects: list[str] = Field(default_factory=list)
    actions: list[ActionPlan] = Field(default_factory=list)
    audio: dict = Field(default_factory=dict)
    captions: dict = Field(default_factory=dict)
    notes: str | None = None

    @model_validator(mode="after")
    def _source_required(self):
        if self.renderer != "remotion" and not (self.source or "").strip():
            raise ValueError(f"{self.id}: source is required for renderer '{self.renderer}'")
        return self


class Sequence(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    shots: list[ShotPlan] = Field(min_length=1)


class ProductionPlan(StrictModel):
    schema_version: Literal[1] = 1
    lesson: str = Field(min_length=1)
    style: str | None = None
    quality: str | None = None
    sequences: list[Sequence] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self):
        shot_ids = [shot.id for sequence in self.sequences for shot in sequence.shots]
        duplicates = sorted({item for item in shot_ids if shot_ids.count(item) > 1})
        if duplicates:
            raise ValueError(f"shot ids must be unique: {duplicates}")
        sequence_ids = [sequence.id for sequence in self.sequences]
        dup_seq = sorted({item for item in sequence_ids if sequence_ids.count(item) > 1})
        if dup_seq:
            raise ValueError(f"sequence ids must be unique: {dup_seq}")
        return self

    @property
    def shots(self) -> list[ShotPlan]:
        return [shot for sequence in self.sequences for shot in sequence.shots]

    @property
    def total_seconds(self) -> float:
        return sum(shot.duration_s for shot in self.shots)


def load_production(path: Path) -> ProductionPlan:
    if not path.is_file():
        raise FileNotFoundError(f"production contract not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"production contract root must be a mapping: {path}")
    try:
        return ProductionPlan.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"invalid production contract {path}: {exc}") from exc


def timed_shots(plan: ProductionPlan) -> list[tuple[ShotPlan, float, float]]:
    """Return (shot, start_s, end_s) with shot order as the only clock."""
    cursor = 0.0
    rows: list[tuple[ShotPlan, float, float]] = []
    for shot in plan.shots:
        rows.append((shot, round(cursor, 3), round(cursor + shot.duration_s, 3)))
        cursor += shot.duration_s
    return rows


def normalize_source(renderer: str, source: str) -> str:
    """Accept ``CodeVideoStudio/shots/x`` and ``shots/x`` alike.

    The result is engine-relative, which is what ``ShotSpec.scene`` expects.
    """
    prefixes = {
        "code_video": "CodeVideoStudio/",
        "manim": "ManimSandbox/",
        "motion_canvas": "MotionStudio/",
        "blender": "BlenderStudio/",
    }
    prefix = prefixes.get(renderer)
    if prefix and source.startswith(prefix):
        return source[len(prefix) :]
    return source


def shot_specs(plan: ProductionPlan) -> list[ShotSpec]:
    specs: list[ShotSpec] = []
    for index, shot in enumerate(plan.shots, start=1):
        if shot.renderer == "remotion":
            raise ValueError(f"{shot.id}: remotion is a compositor, not a shot renderer")
        scene = normalize_source(shot.renderer, shot.source or "")
        specs.append(
            ShotSpec(
                id=shot.id,
                slide=index,
                engine=shot.renderer,  # type: ignore[arg-type]
                scene=scene,
                cue_seconds=0.0,
                expected_duration_s=shot.duration_s,
            )
        )
    return specs


def synthetic_storyboard(plan: ProductionPlan) -> Storyboard:
    return Storyboard(schema_version=1, lesson=plan.lesson, shots=shot_specs(plan))


def validate_plan(
    plan: ProductionPlan,
    *,
    workspace: Path | None = None,
    registry=None,
) -> list[str]:
    issues: list[str] = []
    if registry is not None:
        for shot in plan.shots:
            if not registry.has(shot.grammar):
                issues.append(f"{shot.id}: unknown grammar '{shot.grammar}'")
                continue
            spec = registry.get(shot.grammar)
            window = spec.shot_seconds
            if not (window.min <= shot.duration_s <= window.max):
                issues.append(
                    f"{shot.id}: {shot.duration_s:.1f}s outside grammar "
                    f"'{shot.grammar}' window [{window.min}, {window.max}]"
                )
            missing = missing_capabilities(shot.renderer, spec.capabilities)
            if missing:
                issues.append(
                    f"{shot.id}: renderer '{shot.renderer}' missing capabilities: "
                    + ", ".join(missing)
                )
    for shot in plan.shots:
        if shot.renderer == "remotion":
            continue
        if shot.renderer not in RENDERERS:
            issues.append(f"{shot.id}: unknown renderer '{shot.renderer}'")
            continue
        if workspace is None:
            continue
        roots = {
            "code_video": "CodeVideoStudio",
            "manim": "ManimSandbox",
            "motion_canvas": "MotionStudio",
            "blender": "BlenderStudio",
        }
        source = normalize_source(shot.renderer, shot.source or "")
        target = (workspace / roots[shot.renderer] / source.split("::", 1)[0]).resolve()
        if target.is_dir():
            target = target / "SPEC.md"
        if not target.is_file():
            issues.append(f"{shot.id}: source not found: {target}")
    return issues
