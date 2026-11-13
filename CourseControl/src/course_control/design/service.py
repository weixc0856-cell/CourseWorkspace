"""Run the visual design layer for one lesson."""
from __future__ import annotations

from pathlib import Path

from course_control.content.paths import LessonPaths
from course_control.design.checks import check_design
from course_control.design.planner import build_design, load_authored
from course_control.design.report import write_artifacts
from course_control.design.schema import VisualDesign
from course_control.direction import build as build_director
from course_control.direction.inputs import load_inputs
from course_control.direction.schema import DirectorPlan
from course_control.rendering.theme import load_theme


def load_plan(workspace: Path, lesson_dir: Path, plan_file: Path | None = None) -> DirectorPlan:
    """Reuse the director plan when it exists; rebuild it when it does not."""
    if plan_file is not None and plan_file.is_file():
        return DirectorPlan.model_validate_json(plan_file.read_text(encoding="utf-8"))
    paths = LessonPaths.load(workspace, lesson_dir)
    candidate = paths.build_root / "director" / "director_plan.json"
    if candidate.is_file():
        return DirectorPlan.model_validate_json(candidate.read_text(encoding="utf-8"))
    plan, _ = build_director(workspace, lesson_dir)
    return plan


def run(
    workspace: Path,
    lesson_dir: Path,
    out_dir: Path | None = None,
    shots: list[str] | None = None,
    plan_file: Path | None = None,
) -> tuple[VisualDesign, dict[str, Path]]:
    workspace = workspace.resolve()
    lesson_dir = lesson_dir.resolve()
    paths = LessonPaths.load(workspace, lesson_dir)
    plan = load_plan(workspace, lesson_dir, plan_file)
    inputs = load_inputs(workspace, lesson_dir)

    selected = set(shots or [])
    if selected:
        missing = selected - {shot.id for shot in plan.shots}
        if missing:
            raise ValueError(f"unknown shots: {', '.join(sorted(missing))}")
        plan = plan.model_copy(update={"shots": [shot for shot in plan.shots if shot.id in selected]})

    document = build_design(workspace, plan, inputs.outline, load_authored(lesson_dir))
    document.checks = check_design(document)

    target = (out_dir or (paths.build_root / "design")).resolve()
    written = write_artifacts(document, target, lambda name: load_theme(workspace, name))
    return document, written
