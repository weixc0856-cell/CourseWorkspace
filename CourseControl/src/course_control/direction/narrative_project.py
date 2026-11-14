"""Narrative validation for a topic project.

A topic video has no ``lesson.yaml``, so ``validate_lesson`` cannot read its
plan.  The contract is the same ``NarrativePlan``; only the location and the
report target differ.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from course_control.content.paths import LessonPaths
from course_control.delivery.project import load_project
from course_control.direction.narrative import NarrativePlan, validate_lesson, validate_plan
from course_control.platform.workspace_layout import build_root_for, lessons_root


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _plan_path(project_dir: Path, plan_path: Path | None) -> Path:
    if plan_path is not None:
        candidate = Path(plan_path)
        if not candidate.is_absolute():
            candidate = (project_dir / candidate).resolve()
        return candidate
    for candidate in (
        project_dir / "authoring" / "narrative-plan.json",
        project_dir / "narrative-plan.json",
    ):
        if candidate.is_file():
            return candidate
    return project_dir / "authoring" / "narrative-plan.json"


def validate_project(
    workspace: Path,
    project_file: Path,
    *,
    plan_path: Path | None = None,
) -> tuple[dict, Path]:
    workspace = workspace.resolve()
    project_file = Path(project_file).resolve()
    spec = load_project(project_file)
    if spec.project.mode == "course":
        lesson = (
            spec.production.course.lesson
            if spec.production.course is not None
            else None
        ) or spec.project.id
        paths = LessonPaths.load(workspace, lessons_root(workspace) / lesson)
        return validate_lesson(workspace, paths)
    project_dir = project_file.parent
    target = build_root_for(workspace, spec.project.id) / "quality" / "narrative.json"
    report: dict = {
        "schema_version": 1,
        "project": spec.project.id,
        "generated_at": _now(),
        "status": "fail",
        "form": "long",
        "issues": [],
    }

    def finish() -> tuple[dict, Path]:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return report, target

    path = _plan_path(project_dir, plan_path)
    if not path.is_file():
        report["issues"] = [
            {
                "level": "error",
                "rule": "N-00",
                "message": f"narrative plan not found: {path}",
            }
        ]
        return finish()

    try:
        plan = NarrativePlan.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        report["issues"] = [
            {"level": "error", "rule": "N-00", "message": str(exc)}
        ]
        return finish()

    report["form"] = plan.form
    issues = validate_plan(plan)
    topic = spec.production.topic_video
    if topic is not None:
        total = plan.beats[-1].end_s if plan.beats else 0.0
        tolerance = max(15.0, float(topic.target_seconds) * 0.10)
        if abs(total - float(topic.target_seconds)) > tolerance:
            issues.append(
                {
                    "level": "warning",
                    "rule": "N-15",
                    "message": (
                        f"narrative ends at {total:.1f}s but topic target is "
                        f"{float(topic.target_seconds):.1f}s"
                    ),
                }
            )
    report["issues"] = issues
    report["status"] = "fail" if any(item["level"] == "error" for item in issues) else "pass"
    return finish()


__all__ = ["validate_project"]
