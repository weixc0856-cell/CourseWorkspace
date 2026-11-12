"""Compose the director plan and write the production handoff."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from course_control.direction.inputs import load_inputs
from course_control.direction.outputs import write_outputs
from course_control.direction.planners import default_style, duration_plan, plan_all
from course_control.direction.probe import probe_asset_seconds
from course_control.direction.schema import DirectorPlan, DirectorSummary
from course_control.direction.validator import validate


def _summary(plan: DirectorPlan) -> DirectorSummary:
    errors = sum(1 for check in plan.checks if check.level == "error")
    warnings = sum(1 for check in plan.checks if check.level == "warning")
    infos = sum(1 for check in plan.checks if check.level == "info")
    ready = sum(1 for shot in plan.shots if shot.readiness == "ready")
    return DirectorSummary(
        status=plan.status,
        errors=errors,
        warnings=warnings,
        infos=infos,
        shots=len(plan.shots),
        ready_shots=ready,
        planned_shots=len(plan.shots) - ready,
        chapters=len(plan.chapters),
        narration_segments=len(plan.narration),
    )


def build(
    workspace: Path,
    lesson_dir: Path,
    out_dir: Path | None = None,
) -> tuple[DirectorPlan, dict[str, Path]]:
    inputs = load_inputs(workspace, lesson_dir)
    chapters, shots, narration, decisions = plan_all(inputs)
    planned = round(sum(shot.target_seconds for shot in shots), 3)
    plan = DirectorPlan(
        lesson_id=inputs.paths.slug,
        title=f"{inputs.paths.lesson.title_en} — {inputs.paths.lesson.title_zh}",
        status="draft",
        approval=inputs.approval,
        duration=duration_plan(inputs, planned),
        style=default_style(),
        chapters=chapters,
        shots=shots,
        narration=narration,
        checks=[],
        summary=DirectorSummary(
            status="draft",
            shots=len(shots),
            ready_shots=0,
            planned_shots=len(shots),
            chapters=len(chapters),
            narration_segments=len(narration),
        ),
        generator={
            "name": "course-control.director",
            "version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "policy": {"speech_words_per_second": 2.5},
        },
    )
    for shot_id, seconds in probe_asset_seconds(inputs.paths, plan.shots).items():
        next(shot for shot in plan.shots if shot.id == shot_id).asset_seconds = seconds
    plan.checks = validate(plan, inputs, decisions)
    errors = sum(1 for check in plan.checks if check.level == "error")
    planned_shots = sum(1 for shot in shots if shot.readiness == "planned")
    if errors:
        plan.status = "blocked"
    elif not inputs.approval.approved or planned_shots:
        plan.status = "draft"
    else:
        plan.status = "ready"
    plan.summary = _summary(plan)

    target = (out_dir or (inputs.paths.build_root / "director")).resolve()
    paths = write_outputs(plan, target)
    return plan, paths


def validate_file(plan_file: Path) -> DirectorPlan:
    plan = DirectorPlan.model_validate_json(plan_file.read_text(encoding="utf-8"))
    plan.checks = validate(plan)
    if any(check.level == "error" for check in plan.checks):
        plan.status = "blocked"
    plan.summary = _summary(plan)
    return plan
