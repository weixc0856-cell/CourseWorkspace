from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from . import adapters
from .build_lock import BuildLock
from .adapters.base import StageOutcome
from .collect import collect
from .contracts import Status
from .paths import ContractError, LessonPaths
from .report import ReportBuilder
from .validators import validate
from .verify import verify


@dataclass
class BuildOptions:
    skip_render: bool = False
    skip_compose: bool = False
    storyboard: Path | None = None
    storyboard_source: str | None = None
    shots: list[str] | None = None
    build_root: Path | None = None


def _stage(name: str, status: Status, reason: str | None = None, errors: list[str] | None = None) -> StageOutcome:
    return StageOutcome(name, status, reason=reason, errors=errors or [])


def _mark_not_run(builder: ReportBuilder, names: list[str], reason: str) -> None:
    existing = {stage.name for stage in builder.stages}
    for name in names:
        if name not in existing:
            builder.add_stage(_stage(name, Status.NOT_RUN, reason=reason))


def storyboard_override(
    workspace: Path, lesson_dir: Path, options: BuildOptions
) -> Path | None:
    """Resolve the explicit storyboard input for a build.

    ``--storyboard`` wins; ``--storyboard-source director`` reads the
    director handoff; the default returns None (lesson's storyboard or the
    synthetic shots-mode storyboard).
    """
    if options.storyboard is not None:
        return options.storyboard
    if options.storyboard_source == "director":
        root = options.build_root or (workspace / "build" / lesson_dir.name)
        return root / "director" / "storyboard.director.yaml"
    return None


def run_build(workspace: Path, lesson_dir: Path, options: BuildOptions) -> tuple:
    lock = BuildLock(workspace, lesson_dir.name)
    lock.acquire()
    try:
        return _run_build_locked(workspace, lesson_dir, options)
    finally:
        lock.release()


def _run_build_locked(workspace: Path, lesson_dir: Path, options: BuildOptions) -> tuple:
    storyboard = storyboard_override(workspace, lesson_dir, options)
    paths = LessonPaths.load(
        workspace, lesson_dir, storyboard_override=storyboard, build_root_override=options.build_root
    )
    if options.shots:
        known = {shot.id for shot in paths.storyboard.shots}
        unknown = sorted(set(options.shots) - known)
        if unknown:
            raise ContractError(f"unknown shot ids for this storyboard: {', '.join(unknown)}")
        paths.selected_shot_ids = set(options.shots)
    adapters.slides.clean_staging(paths)
    builder = ReportBuilder(paths)

    started = time.monotonic()
    validation = validate(paths)
    for issue in validation.issues:
        builder.add_check(
            issue.rule,
            Status.FAIL if issue.level == "error" else Status.PASS,
            detail=("error: " if issue.level == "error" else "warning: ") + issue.message,
        )
    validate_outcome = StageOutcome(
        "validate",
        Status.PASS if validation.ok else Status.FAIL,
        warnings=[issue.message for issue in validation.warnings],
        errors=[issue.message for issue in validation.errors],
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    builder.add_stage(validate_outcome)
    if not validation.ok:
        _mark_not_run(
            builder,
            ["capture_slides", "render:motion_canvas", "render:manim", "render:blender", "render:code_video", "collect", "compose", "brand", "verify"],
            "upstream_failed",
        )
        report = builder.finalize()
        return report, builder.write(report)

    if paths.lesson.compose.mode == "recording":
        builder.add_stage(_stage("capture_slides", Status.NOT_APPLICABLE, reason="recording_mode"))
    elif paths.lesson.compose.mode == "scene":
        builder.add_stage(_stage("capture_slides", Status.NOT_APPLICABLE, reason="scene_mode"))
    elif paths.lesson.compose.mode == "shots":
        builder.add_stage(_stage("capture_slides", Status.NOT_APPLICABLE, reason="shots_mode"))
    elif options.skip_compose:
        builder.add_stage(_stage("capture_slides", Status.SKIPPED, reason="skip_compose"))
    else:
        outcome = adapters.slides.capture_slides(paths)
        builder.add_stage(outcome)
        if outcome.status == Status.FAIL:
            _mark_not_run(
                builder,
                ["render:motion_canvas", "render:manim", "render:blender", "render:code_video", "collect", "compose", "brand", "verify"],
                "upstream_failed",
            )
            report = builder.finalize()
            return report, builder.write(report)

    skip_downstream = False
    for engine, adapter in (
        ("motion_canvas", adapters.motion_canvas.run),
        ("manim", adapters.manim.run),
        ("blender", adapters.blender.run),
        ("code_video", adapters.code_video.run),
    ):
        name = f"render:{engine}"
        if engine not in paths.lesson.engines:
            builder.add_stage(_stage(name, Status.NOT_APPLICABLE, reason="engine_not_used"))
            continue
        if options.skip_render:
            builder.add_stage(_stage(name, Status.SKIPPED, reason="skip_render"))
            skip_downstream = True
            continue
        outcome = adapter(paths)
        builder.add_stage(outcome)
        if outcome.status == Status.FAIL:
            _mark_not_run(builder, ["collect", "compose", "brand", "verify"], "upstream_failed")
            report = builder.finalize()
            return report, builder.write(report)
        if outcome.status == Status.SKIPPED:
            skip_downstream = True

    if skip_downstream:
        builder.add_stage(_stage("collect", Status.NOT_RUN, reason="upstream_skipped"))
        builder.add_stage(_stage("compose", Status.NOT_RUN, reason="upstream_skipped"))
        builder.add_stage(_stage("verify", Status.NOT_RUN, reason="upstream_skipped"))
        report = builder.finalize()
        return report, builder.write(report)

    started = time.monotonic()
    try:
        shots_file, warnings, outputs = collect(paths)
    except ContractError as exc:
        builder.add_stage(
            StageOutcome(
                "collect",
                Status.FAIL,
                errors=[str(exc)],
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        )
        _mark_not_run(builder, ["compose", "verify"], "upstream_failed")
        report = builder.finalize()
        return report, builder.write(report)

    builder.add_stage(
        StageOutcome(
            "collect",
            Status.PASS,
            outputs=outputs,
            warnings=warnings,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    )

    if options.skip_compose:
        builder.add_stage(_stage("compose", Status.SKIPPED, reason="skip_compose"))
        builder.add_stage(_stage("brand", Status.SKIPPED, reason="skip_compose"))
        builder.add_check("V-14", Status.NOT_RUN, detail="compose skipped")
        builder.add_stage(_stage("verify", Status.SKIPPED, reason="skip_compose"))
        report = builder.finalize()
        return report, builder.write(report)

    compose_outcome = adapters.remotion.compose(paths)
    builder.add_stage(compose_outcome)
    if compose_outcome.status == Status.FAIL:
        _mark_not_run(builder, ["verify"], "upstream_failed")
        report = builder.finalize()
        return report, builder.write(report)

    if paths.lesson.subtitles.enabled and paths.lesson.subtitles.render == "burn_in":
        burn_outcome = adapters.burn.burn_subtitles(paths)
        builder.add_stage(burn_outcome)
        if burn_outcome.status == Status.FAIL:
            builder.add_stage(_stage("verify", Status.NOT_RUN, reason="upstream_failed"))
            report = builder.finalize()
            return report, builder.write(report)

    if paths.lesson.branding.enabled:
        brand_outcome = adapters.brand.run(paths)
        builder.add_stage(brand_outcome)
        if brand_outcome.status == Status.FAIL:
            builder.add_stage(_stage("verify", Status.NOT_RUN, reason="upstream_failed"))
            report = builder.finalize()
            return report, builder.write(report)
    else:
        builder.add_stage(_stage("brand", Status.NOT_APPLICABLE, reason="branding_disabled"))

    started = time.monotonic()
    checks = verify(paths, shots_file)
    for check in checks:
        builder.checks.append(check)
    builder.add_stage(
        StageOutcome(
            "verify",
            Status.PASS if all(check.status != Status.FAIL for check in checks) else Status.FAIL,
            errors=[check.detail or check.id for check in checks if check.status == Status.FAIL],
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    )

    report = builder.finalize()
    return report, builder.write(report)
