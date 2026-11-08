"""Render director artifacts: plan JSON, storyboard handoff, shot directions, review."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from ..animation_direction import AnimationDirection, ShotDirection
from ..contracts import ShotSpec, Storyboard
from .schema import DirectorPlan, ShotPlan


def _direction(plan: DirectorPlan, shot: ShotPlan) -> AnimationDirection:
    return AnimationDirection(
        lesson_id=plan.lesson_id,
        title=shot.title,
        total_seconds=shot.duration_s,
        style=plan.style.model_dump(),
        shots=[
            ShotDirection(
                shot_id=shot.id,
                start_s=0.0,
                end_s=shot.duration_s,
                learning_intent=shot.learning_intent,
                visual_metaphor=shot.visual_metaphor,
                composition=shot.composition,
                focus=shot.title,
                camera=shot.camera,
                shot_size=shot.shot_size,
                motion=shot.motion,
                transition=shot.transition,
                end_state="holds the single claim for the last 1.5 s",
                continuity="same palette roles and type scale as adjacent shots; every camera move must serve the claim",
                on_screen_text=shot.on_screen_text,
                reference="docs/课程视觉风格指南.md sections 1-4",
                acceptance=[
                    "no text clipping or overlap",
                    "one claim per frame",
                    "palette roles match the style guide",
                    "motion supports the claim rather than decorating it",
                ],
            )
        ],
    )


def _storyboard(plan: DirectorPlan) -> Storyboard:
    shots: list[ShotSpec] = []
    for shot in plan.shots:
        if shot.engine == "remotion":
            continue
        shots.append(
            ShotSpec(
                id=shot.id,
                slide=shot.slide,
                engine=shot.engine,  # type: ignore[arg-type]
                scene=shot.scene or "",
                cue_seconds=shot.cue_seconds,
                expected_duration_s=shot.asset_seconds,
                blend_task=shot.blend_task,
                engine_profile=shot.engine_profile,
                note=(
                    f"director: {shot.readiness}; {shot.notes}"
                    if shot.notes
                    else f"director: {shot.readiness}"
                ),
            )
        )
    return Storyboard(schema_version=1, lesson=plan.lesson_id, shots=shots)


def _review(plan: DirectorPlan) -> str:
    lines = [
        f"# Director review — {plan.lesson_id}",
        "",
        f"- status: **{plan.status}**",
        f"- planned: {plan.duration.planned_seconds:g}s / target {plan.duration.target_seconds:g}s",
        f"- shots: {plan.summary.shots} ({plan.summary.ready_shots} ready, {plan.summary.planned_shots} planned)",
        f"- narration: {plan.summary.narration_segments} segments",
        f"- approved inputs: {'yes' if plan.approval.approved else 'no'}",
        "",
        "## Chapters",
        "",
        "| chapter | title | objective | seconds | shots |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for chapter in plan.chapters:
        lines.append(
            f"| {chapter.id} | {chapter.title} | {chapter.learning_objective} | "
            f"{chapter.target_seconds:g} | {', '.join(chapter.shot_ids)} |"
        )
    lines += [
        "",
        "## Shots",
        "",
        "| shot | slide | chapter | engine | readiness | window | purpose | title |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for shot in plan.shots:
        lines.append(
            f"| {shot.id} | {shot.slide} | {shot.chapter_id} | {shot.engine} | {shot.readiness} | "
            f"{shot.start_s:g}-{shot.end_s:g}s | {shot.purpose} | {shot.title} |"
        )
    for level, title in (("error", "Errors"), ("warning", "Warnings"), ("info", "Info")):
        items = [check for check in plan.checks if check.level == level]
        lines += ["", f"## {title} ({len(items)})", ""]
        if not items:
            lines.append("- none")
        for check in items:
            target = check.shot_id or check.chapter_id or ""
            lines.append(f"- `{check.rule}` {target}: {check.message}".rstrip())
    lines += [
        "",
        "## Handoff",
        "",
        "- `storyboard.director.yaml` contains every non-remotion shot; planned shots carry a note.",
        "- `directions/<shot>.json` validates with `course-control direction-validate --spec <file>`.",
        "- `shot_specs/<shot>.json` is the ShotSpec handoff for the engine adapters.",
        "- Remotion shots are composed from slides, so they are not written into the storyboard.",
        "",
    ]
    return "\n".join(lines)


def write_outputs(plan: DirectorPlan, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    directions = out_dir / "directions"
    directions.mkdir(exist_ok=True)
    shot_specs = out_dir / "shot_specs"
    shot_specs.mkdir(exist_ok=True)

    plan_path = out_dir / "director_plan.json"
    plan_path.write_text(
        json.dumps(plan.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    storyboard_path = out_dir / "storyboard.director.yaml"
    storyboard = _storyboard(plan)
    storyboard_path.write_text(
        yaml.safe_dump(storyboard.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    for shot in plan.shots:
        direction = _direction(plan, shot)
        (directions / f"{shot.id}.json").write_text(
            json.dumps(direction.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    storyboard_by_id = {item.id: item for item in storyboard.shots}
    for shot in plan.shots:
        spec = storyboard_by_id.get(shot.id)
        if spec is None:
            continue
        (shot_specs / f"{shot.id}.json").write_text(
            json.dumps(spec.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    review_path = out_dir / "director_review.md"
    review_path.write_text(_review(plan), encoding="utf-8")
    return {
        "plan": plan_path,
        "storyboard": storyboard_path,
        "directions": directions,
        "shot_specs": shot_specs,
        "review": review_path,
    }
