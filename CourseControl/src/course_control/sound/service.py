"""Run the sound design layer for one lesson."""
from __future__ import annotations

from pathlib import Path

from course_control.content.paths import LessonPaths
from course_control.design.service import load_plan
from course_control.sound.checks import check_sound
from course_control.sound.planner import build_sound, load_visual_design
from course_control.sound.report import write_artifacts
from course_control.sound.schema import SoundDesign


def run(
    workspace: Path,
    lesson_dir: Path,
    out_dir: Path | None = None,
    plan_file: Path | None = None,
) -> tuple[SoundDesign, dict[str, Path]]:
    workspace = workspace.resolve()
    lesson_dir = lesson_dir.resolve()
    paths = LessonPaths.load(workspace, lesson_dir)
    plan = load_plan(workspace, lesson_dir, plan_file)
    visual = load_visual_design(paths.build_root / "design" / "visual_design.json")

    design = build_sound(paths.lesson, plan, visual)
    design.checks = check_sound(
        design,
        has_visual_design=visual is not None,
        has_narration=bool(plan.narration),
    )

    target = (out_dir or (paths.build_root / "sound")).resolve()
    written = write_artifacts(design, target)
    return design, written
