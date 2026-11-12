"""Create, load and approve the production order."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from course_control.direction.inputs import DirectorInputs
from course_control.direction.planners import default_style
from course_control.delivery.schema import Authorizations, ProductionOrder, ResourceLimits


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def order_path(build_root: Path) -> Path:
    return build_root / "production" / "order.json"


def load_order(path: Path) -> ProductionOrder:
    return ProductionOrder.model_validate_json(path.read_text(encoding="utf-8"))


def save_order(order: ProductionOrder, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(order.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


@dataclass
class OrderOverrides:
    audience: str | None = None
    language: str | None = None
    target_seconds: float | None = None
    must_cover: list[str] | None = None
    must_not: list[str] | None = None
    note: str = ""
    allow_network: bool | None = None
    allow_new_dependencies: bool | None = None
    allow_publish: bool | None = None
    allow_render: bool | None = None
    max_wall_seconds: float | None = None
    max_api_cost_usd: float | None = None
    max_local_model_calls: int | None = None


def default_order(inputs: DirectorInputs, overrides: OrderOverrides | None = None) -> ProductionOrder:
    overrides = overrides or OrderOverrides()
    lesson = inputs.paths.lesson
    policy = lesson.duration
    target = overrides.target_seconds or (policy.target_seconds if policy else None)
    if target is None:
        target = float(inputs.brief.duration.get("target_seconds", 600))
    style = default_style()
    authorizations = Authorizations(
        allow_network=bool(overrides.allow_network) if overrides.allow_network is not None else False,
        allow_new_dependencies=(
            bool(overrides.allow_new_dependencies) if overrides.allow_new_dependencies is not None else False
        ),
        allow_publish=bool(overrides.allow_publish) if overrides.allow_publish is not None else False,
        allow_render=bool(overrides.allow_render) if overrides.allow_render is not None else True,
    )
    limits = ResourceLimits(
        max_wall_seconds=overrides.max_wall_seconds or 14400.0,
        max_api_cost_usd=overrides.max_api_cost_usd or 0.0,
        max_local_model_calls=overrides.max_local_model_calls or 0,
    )
    return ProductionOrder(
        order_id=f"{lesson.lesson_id}-v1",
        lesson_id=lesson.lesson_id,
        title=lesson.title_en,
        audience=overrides.audience or inputs.brief.audience,
        language=overrides.language or inputs.script.language,
        target_seconds=target,
        style={
            "background": style.background,
            "ink": style.ink,
            "accent": style.accent,
            "warm": style.warm,
            "typography": style.typography.heading_font,
        },
        must_cover=overrides.must_cover or list(inputs.brief.objectives),
        must_not=overrides.must_not or [],
        authorizations=authorizations,
        limits=limits,
        created_at=now(),
        note=overrides.note,
    )


def approve(order: ProductionOrder, approved_by: str) -> ProductionOrder:
    order.approved_by = approved_by
    order.approved_at = now()
    return order


def ensure_order(
    inputs: DirectorInputs,
    build_root: Path,
    overrides: OrderOverrides | None = None,
    force: bool = False,
) -> tuple[ProductionOrder, Path]:
    path = order_path(build_root)
    if path.is_file() and not force:
        return load_order(path), path
    order = default_order(inputs, overrides)
    return order, save_order(order, path)
