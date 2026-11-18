"""Content product tiers: one machine-readable layer for A-E.

The task book separates five products (micro explainer, short explainer,
research brief, deep lecture, course series).  This module is the single source
for their duration windows, aspect rules, narrative modules and visual density.
It does not render anything and does not replace ``duration`` in lesson.yaml:
the lesson still owns its own target; the tier says whether that target is a
legal instance of the declared product.

A lesson without ``product_tier`` keeps the legacy behaviour and reports
``NOT_DECLARED``.  That is not a pass: release-check counts it as INCOMPLETE.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from course_control.content.contracts import LessonConfig

ProductTier = Literal[
    "micro_explainer",
    "short_explainer",
    "research_brief",
    "deep_lecture",
    "course_series",
]

# Narrative modules are composable; the tier only says which ones must be
# present before the product is complete.  Ids match the module names used by
# the short-storyboard contract and the narrative-plan bridge below.
Module = Literal[
    "hook", "context", "mechanism", "evidence", "implication", "conclusion"
]

# narrative-plan.json beat ids predate the module vocabulary; this bridge keeps
# one plan usable by both without rewriting existing lessons.
BEAT_MODULES: dict[str, Module] = {
    "cold_open": "hook",
    "question": "context",
    "intuition": "context",
    "mechanism": "mechanism",
    "test": "evidence",
    "connect": "conclusion",
}


@dataclass(frozen=True)
class TierPolicy:
    id: ProductTier
    label: str
    min_s: float
    max_s: float
    aspects: tuple[str, ...]
    modules: tuple[Module, ...]
    visual_density: str
    description: str

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "min_s": self.min_s,
            "max_s": self.max_s,
            "aspects": list(self.aspects),
            "modules": list(self.modules),
            "visual_density": self.visual_density,
            "description": self.description,
        }


TIERS: dict[ProductTier, TierPolicy] = {
    "micro_explainer": TierPolicy(
        id="micro_explainer",
        label="Micro Explainer",
        min_s=30,
        max_s=90,
        aspects=("9:16", "16:9", "1:1"),
        modules=("hook", "conclusion"),
        visual_density="one hero frame; a still frame is allowed when it carries the point",
        description="One concept, one counter-intuitive fact, one point.",
    ),
    "short_explainer": TierPolicy(
        id="short_explainer",
        label="Short Explainer",
        min_s=90,
        max_s=180,
        aspects=("9:16", "16:9", "1:1"),
        modules=("hook", "mechanism", "evidence", "conclusion"),
        visual_density="a real mechanism move, not a labelled still",
        description="A complete explanation chain the viewer can repeat afterwards.",
    ),
    "research_brief": TierPolicy(
        id="research_brief",
        label="Research Brief",
        min_s=180,
        max_s=360,
        aspects=("16:9",),
        modules=("context", "evidence", "mechanism", "implication"),
        visual_density="evidence plates and data charts; every number has a source",
        description="One paper, news event or product analysis with limits and impact.",
    ),
    "deep_lecture": TierPolicy(
        id="deep_lecture",
        label="Deep Lecture",
        min_s=600,
        max_s=1800,
        aspects=("16:9",),
        modules=("mechanism", "evidence", "conclusion"),
        visual_density="structured board dominates; mechanism animation only where it explains",
        description="A full problem decomposition; never a stretched short script.",
    ),
    "course_series": TierPolicy(
        id="course_series",
        label="Course Series",
        min_s=480,
        max_s=1800,
        aspects=("16:9",),
        modules=("context", "mechanism", "evidence", "conclusion"),
        visual_density="one page system across episodes; reusable assets",
        description="One episode inside a course; the series total lives on the project layer.",
    ),
}


def policy_for(tier: ProductTier | str) -> TierPolicy:
    try:
        return TIERS[tier]  # type: ignore[index]
    except KeyError as exc:
        raise ValueError(f"unknown product tier: {tier!r}") from exc


def aspect_of(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        raise ValueError("resolution must be positive")
    if width == height:
        return "1:1"
    return "16:9" if width > height else "9:16"


@dataclass
class ProductCheck:
    lesson: str
    tier: str | None = None
    aspect: str | None = None
    target_s: float | None = None
    window: tuple[float, float] | None = None
    modules_found: list[str] = field(default_factory=list)
    modules_required: list[str] = field(default_factory=list)
    status: str = "NOT_DECLARED"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        policy = TIERS.get(self.tier) if self.tier else None  # type: ignore[arg-type]
        return {
            "schema_version": 1,
            "lesson": self.lesson,
            "status": self.status,
            "tier": self.tier,
            "policy": policy.as_dict() if policy else None,
            "aspect": self.aspect,
            "target_s": self.target_s,
            "window_s": list(self.window) if self.window else None,
            "modules_found": self.modules_found,
            "modules_required": self.modules_required,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _narrative_modules(lesson: LessonConfig, lesson_dir: Path | None) -> tuple[list[str], str | None]:
    """Read the approved narrative plan if it exists; never invent a module."""
    source = lesson.authoring.narrative if lesson.authoring else None
    if not source or lesson_dir is None:
        return [], "narrative plan not declared; module coverage unchecked"
    path = Path(source)
    if not path.is_absolute():
        path = Path(lesson_dir) / path
    if not path.is_file():
        return [], f"narrative plan not found: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [], f"cannot read narrative plan {path}: {exc}"
    found: list[str] = []
    for beat in data.get("beats") or []:
        if not isinstance(beat, dict):
            continue
        mapping = BEAT_MODULES.get(str(beat.get("id") or ""))
        if mapping and mapping not in found:
            found.append(mapping)
    short_form = data.get("short_form")
    if isinstance(short_form, dict):
        for key, module in (("hook", "hook"), ("payoff", "conclusion")):
            if short_form.get(key) and module not in found:
                found.append(module)
    return found, None


def check_product(lesson: LessonConfig, lesson_dir: Path | None = None) -> ProductCheck:
    """Check a lesson against its declared product tier.

    States:
      NOT_DECLARED  no tier declared; legacy lesson, not a pass
      INCOMPLETE    tier declared but a required artifact was not read
      FAIL          a hard rule is violated
      PASS          window, aspect and modules all verified
    """
    result = ProductCheck(lesson=lesson.lesson_id)
    tier = lesson.product_tier
    if not tier:
        result.warnings.append(
            "product_tier is not declared; add one of: " + ", ".join(TIERS)
        )
        return result

    policy = policy_for(tier)
    result.tier = tier
    result.window = (policy.min_s, policy.max_s)
    result.modules_required = list(policy.modules)
    width, height = lesson.outputs.resolution
    result.aspect = aspect_of(width, height)

    duration = lesson.duration
    if duration is None or duration.target_seconds is None:
        result.errors.append("a declared product_tier needs duration.target_seconds")
    else:
        result.target_s = float(duration.target_seconds)
        if not (policy.min_s <= result.target_s <= policy.max_s):
            result.errors.append(
                f"target {result.target_s:g}s is outside the {policy.label} window "
                f"[{policy.min_s:g}, {policy.max_s:g}]"
            )
        if duration.min_seconds is not None and duration.min_seconds < policy.min_s:
            result.errors.append(
                f"duration.min_seconds {duration.min_seconds:g}s is below the "
                f"{policy.label} floor {policy.min_s:g}s"
            )
        if duration.max_seconds is not None and duration.max_seconds > policy.max_s:
            result.errors.append(
                f"duration.max_seconds {duration.max_seconds:g}s exceeds the "
                f"{policy.label} ceiling {policy.max_s:g}s"
            )

    if result.aspect not in policy.aspects:
        result.errors.append(
            f"aspect {result.aspect} is not allowed for {policy.label} "
            f"(allowed: {', '.join(policy.aspects)})"
        )

    found, note = _narrative_modules(lesson, lesson_dir)
    result.modules_found = found
    if note:
        result.warnings.append(note)
    missing = [module for module in policy.modules if module not in found]
    if missing and not note:
        result.errors.append(
            f"{policy.label} narrative is missing module(s): {', '.join(missing)}"
        )

    if result.errors:
        result.status = "FAIL"
    elif note:
        result.status = "INCOMPLETE"
    else:
        result.status = "PASS"
    return result


def write_product_record(result: ProductCheck, target: Path) -> Path:
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(result.as_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target
