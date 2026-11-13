"""Repair planning: map a defect to the smallest rerun that can fix it.

The mapping is a table, not a model.  It can be wrong, but it is inspectable and
the same defect always gets the same plan.  A defect that cannot be attributed
stops the line instead of guessing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from course_control.content.contracts import StrictModel
from course_control.platform.atomic import write_json_atomic
from course_control.quality.defect import Defect, DefectReport

Strategy = Literal[
    "rerun_stage",
    "reauthor_segment",
    "substitute_source",
    "re_render_shot",
    "stop",
]

MAX_ATTEMPTS = 3

# root cause -> (strategy, stages that must run again)
PLAN_BY_CAUSE: dict[str, tuple[Strategy, list[str]]] = {
    "source_data": (
        "substitute_source",
        ["understand", "plan", "author", "direct", "produce", "verify", "deliver"],
    ),
    "evidence_collection": (
        "substitute_source",
        ["understand", "plan", "author", "direct", "produce", "verify", "deliver"],
    ),
    "script_length": (
        "reauthor_segment",
        ["author", "direct", "produce", "verify", "deliver"],
    ),
    "visual_grammar": (
        "re_render_shot",
        ["direct", "produce", "verify", "deliver"],
    ),
    "render_engine": (
        "re_render_shot",
        ["produce", "verify", "deliver"],
    ),
    "audio_timing": (
        "rerun_stage",
        ["produce", "verify", "deliver"],
    ),
    "contract_violation": ("stop", []),
    "unknown": ("stop", []),
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class RepairPlan(StrictModel):
    schema_version: Literal[1] = 1
    project_id: str
    generated_at: str
    attempt: int = 1
    defect_ids: list[str] = []
    strategy: Strategy = "stop"
    rebuild_scope: list[str] = []
    expected_cost: dict = {}
    blocked: bool = False
    reason: str | None = None


class RepairPlanFile(StrictModel):
    schema_version: Literal[1] = 1
    project_id: str
    generated_at: str
    plans: list[RepairPlan] = []


def plan_for(defect: Defect, *, attempt: int = 1, project_id: str = "") -> RepairPlan:
    if attempt > MAX_ATTEMPTS:
        return RepairPlan(
            project_id=project_id,
            generated_at=_now(),
            attempt=attempt,
            defect_ids=[defect.id],
            strategy="stop",
            blocked=True,
            reason=f"attempt {attempt} exceeds limit {MAX_ATTEMPTS}",
        )
    strategy, scope = PLAN_BY_CAUSE.get(
        defect.root_cause_hint, ("stop", [])
    )
    blocked = strategy == "stop"
    return RepairPlan(
        project_id=project_id,
        generated_at=_now(),
        attempt=attempt,
        defect_ids=[defect.id],
        strategy=strategy,
        rebuild_scope=scope,
        blocked=blocked,
        reason=(
            f"cannot attribute {defect.symptom}"
            if blocked
            else None
        ),
    )


def plan(report: DefectReport, *, attempt: int = 1) -> RepairPlanFile:
    plans = [
        plan_for(defect, attempt=attempt, project_id=report.project_id)
        for defect in report.defects
    ]
    return RepairPlanFile(
        project_id=report.project_id,
        generated_at=_now(),
        plans=plans,
    )


def save(plans: RepairPlanFile, path: Path) -> Path:
    write_json_atomic(path, plans.model_dump(mode="json"))
    return path


def load(path: Path) -> RepairPlanFile | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return RepairPlanFile.model_validate(data)


__all__ = [
    "MAX_ATTEMPTS",
    "PLAN_BY_CAUSE",
    "RepairPlan",
    "RepairPlanFile",
    "plan_for",
    "plan",
    "save",
    "load",
]
