from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from course_control.rendering import adapters
from course_control.rendering.adapters.base import StageOutcome
from course_control.platform.atomic import write_json_atomic
from course_control.platform.build_lock import BuildLock
from course_control.platform.checkpoint import (
    STAGE_ORDER,
    CheckpointStore,
    run_stage,
    stage_inputs,
)
from course_control.content.collect import collect
from course_control.platform.config_resolve import blocking_conflicts, resolve_config, write_snapshot
from course_control.content.contracts import ShotsFile, Status
from course_control.content.paths import ContractError, LessonPaths
from course_control.delivery.report import ReportBuilder
from course_control.content.validators import validate
from course_control.quality.verify import verify
from course_control.platform.workspace_layout import build_root_for


@dataclass
class BuildOptions:
    skip_render: bool = False
    skip_compose: bool = False
    storyboard: Path | None = None
    storyboard_source: str | None = None
    shots: list[str] | None = None
    build_root: Path | None = None
    # Top-level resume: reuse stages whose inputs, configuration and outputs
    # still match their checkpoint. ``resume_from`` re-runs that stage and
    # everything after it while keeping earlier stages.
    resume: bool = False
    resume_from: str | None = None


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
        root = options.build_root or build_root_for(workspace, lesson_dir.name)
        return root / "director" / "storyboard.director.yaml"
    return None


def _options_fingerprint(config_fingerprint: str, options: BuildOptions) -> str:
    payload = {
        "config": config_fingerprint,
        "skip_render": options.skip_render,
        "skip_compose": options.skip_compose,
        "storyboard": str(options.storyboard) if options.storyboard else None,
        "storyboard_source": options.storyboard_source,
        "shots": sorted(options.shots or []),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _validate_resume_from(value: str | None) -> None:
    if value is not None and value not in STAGE_ORDER:
        raise ContractError(
            "--resume-from must be one of: " + ", ".join(STAGE_ORDER)
        )


def run_build(workspace: Path, lesson_dir: Path, options: BuildOptions) -> tuple:
    _validate_resume_from(options.resume_from)
    lock = BuildLock(workspace, lesson_dir.name)
    lock.acquire()
    try:
        return _run_build_locked(workspace, lesson_dir, options)
    finally:
        lock.release()


class _Run:
    """One build run: report builder, resume bookkeeping and checkpoints."""

    def __init__(self, builder: ReportBuilder, paths: LessonPaths, options: BuildOptions):
        self.builder = builder
        self.paths = paths
        self.options = options
        self.store: CheckpointStore | None = None
        self.record = {
            "schema_version": 1,
            "run_id": builder.run_id,
            "lesson": paths.slug,
            "started_at": builder.started_at,
            "config_fingerprint": builder.config_fingerprint,
            "config_snapshot": builder.config_snapshot,
            "resume": {
                "enabled": options.resume,
                "from": options.resume_from,
                "reused": [],
                "replayed": [],
                "invalid": {},
            },
        }

    def force(self, stage: str) -> bool:
        if self.options.resume_from is None or stage not in STAGE_ORDER:
            return False
        return STAGE_ORDER.index(stage) >= STAGE_ORDER.index(self.options.resume_from)

    def run(self, stage: str, action) -> StageOutcome:
        if self.store is None:
            return action()
        inputs = stage_inputs(self.paths, stage)
        outcome, reused, reasons = run_stage(
            stage,
            inputs,
            action,
            self.store,
            resume=self.options.resume,
            run_id=self.builder.run_id,
            force=self.force(stage),
        )
        resume = self.record["resume"]
        if reused:
            resume["reused"].append(stage)
            self.builder.reused_stages.append(stage)
        else:
            resume["replayed"].append(stage)
            if reasons:
                resume["invalid"][stage] = reasons
        return outcome

    def finish(self) -> tuple:
        report = self.builder.finalize()
        path = self.builder.write(report)
        self.record["finished_at"] = report.finished_at
        self.record["verdict"] = report.verdict
        write_json_atomic(
            self.paths.build_root / "runtime" / "last-run.json", self.record
        )
        return report, path


def _run_build_locked(workspace: Path, lesson_dir: Path, options: BuildOptions) -> tuple:
    storyboard = storyboard_override(workspace, lesson_dir, options)
    paths = LessonPaths.load(
        workspace, lesson_dir, storyboard_override=storyboard, build_root_override=options.build_root
    )
    if options.storyboard_source is None:
        options.storyboard_source = paths.lesson.build.storyboard_source
        if options.storyboard_source == "director" and options.storyboard is None:
            storyboard = storyboard_override(workspace, lesson_dir, options)
            paths = LessonPaths.load(
                workspace,
                lesson_dir,
                storyboard_override=storyboard,
                build_root_override=options.build_root,
            )
    if options.shots:
        known = {shot.id for shot in paths.storyboard.shots}
        unknown = sorted(set(options.shots) - known)
        if unknown:
            raise ContractError(f"unknown shot ids for this storyboard: {', '.join(unknown)}")
        paths.selected_shot_ids = set(options.shots)

    adapters.slides.clean_staging(paths)
    builder = ReportBuilder(paths)

    config_report = resolve_config(workspace, paths)
    snapshot = write_snapshot(paths, config_report)
    try:
        snapshot_rel = snapshot.resolve().relative_to(paths.build_root.resolve()).as_posix()
    except ValueError:
        snapshot_rel = str(snapshot)
    builder.config_fingerprint = _options_fingerprint(
        config_report["fingerprint"], options
    )
    builder.config_snapshot = snapshot_rel
    builder.resumed = options.resume
    run = _Run(builder, paths, options)
    run.store = CheckpointStore(paths.build_root, builder.config_fingerprint)

    blocking = blocking_conflicts(config_report)
    config_warnings = list(config_report["warnings"]) + [
        item["message"]
        for item in config_report["conflicts"]
        if item.get("severity") != "blocking"
    ]
    builder.add_stage(
        StageOutcome(
            "config",
            Status.FAIL if blocking else Status.PASS,
            outputs=[snapshot],
            warnings=config_warnings,
            errors=[item["message"] for item in blocking],
            reason="configuration_conflict" if blocking else None,
        )
    )
    builder.add_check(
        "V-42",
        Status.FAIL if blocking else Status.PASS,
        expected="configuration resolves without blocking conflicts",
        actual=(
            "ok"
            if not blocking
            else "; ".join(item["message"] for item in blocking)
        ),
        detail=(
            f"fingerprint={builder.config_fingerprint}; "
            f"warnings={len(config_warnings)}"
        ),
    )
    if blocking:
        _mark_not_run(
            builder,
            [
                "validate",
                "capture_slides",
                "render:motion_canvas",
                "render:manim",
                "render:blender",
                "render:code_video",
                "collect",
                "compose",
                "brand",
                "verify",
            ],
            "upstream_failed",
        )
        return run.finish()

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
        return run.finish()

    if paths.lesson.compose.mode == "recording":
        builder.add_stage(_stage("capture_slides", Status.NOT_APPLICABLE, reason="recording_mode"))
    elif paths.lesson.compose.mode == "scene":
        builder.add_stage(_stage("capture_slides", Status.NOT_APPLICABLE, reason="scene_mode"))
    elif paths.lesson.compose.mode == "shots":
        builder.add_stage(_stage("capture_slides", Status.NOT_APPLICABLE, reason="shots_mode"))
    elif options.skip_compose:
        builder.add_stage(_stage("capture_slides", Status.SKIPPED, reason="skip_compose"))
    else:
        outcome = run.run(
            "capture_slides", lambda: adapters.slides.capture_slides(paths)
        )
        builder.add_stage(outcome)
        if outcome.status == Status.FAIL:
            _mark_not_run(
                builder,
                ["render:motion_canvas", "render:manim", "render:blender", "render:code_video", "collect", "compose", "brand", "verify"],
                "upstream_failed",
            )
            return run.finish()

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
        outcome = run.run(name, lambda adapter=adapter: adapter(paths))
        builder.add_stage(outcome)
        if outcome.status == Status.FAIL:
            _mark_not_run(builder, ["collect", "compose", "brand", "verify"], "upstream_failed")
            return run.finish()
        if outcome.status == Status.SKIPPED:
            skip_downstream = True

    if skip_downstream:
        builder.add_stage(_stage("collect", Status.NOT_RUN, reason="upstream_skipped"))
        builder.add_stage(_stage("compose", Status.NOT_RUN, reason="upstream_skipped"))
        builder.add_stage(_stage("verify", Status.NOT_RUN, reason="upstream_skipped"))
        return run.finish()

    shots_file = paths.build_root / "shots.json"
    collect_inputs = stage_inputs(paths, "collect")
    reused_collect = False
    if options.resume and not run.force("collect") and run.store is not None:
        valid, reasons = run.store.check("collect", collect_inputs)
        if valid:
            checkpoint = run.store.load("collect")
            assert checkpoint is not None
            collect_outcome = StageOutcome(
                "collect",
                Status.PASS,
                outputs=[
                    Path(item) if Path(item).is_absolute() else paths.build_root / item
                    for item in checkpoint.outputs
                ],
                warnings=[f"resumed from checkpoint {checkpoint.run_id}: collect"],
                reason="resumed_from_checkpoint",
            )
            run.record["resume"]["reused"].append("collect")
            builder.reused_stages.append("collect")
            reused_collect = True
            # The non-resumed path gets the model back from collect(); the
            # resumed path must read the artifact it was told to trust.
            shots_file = ShotsFile.model_validate(
                json.loads(
                    (paths.build_root / "shots.json").read_text(encoding="utf-8")
                )
            )
        else:
            run.record["resume"]["replayed"].append("collect")
            run.record["resume"]["invalid"]["collect"] = reasons
    if not reused_collect:
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
            return run.finish()
        collect_outcome = StageOutcome(
            "collect",
            Status.PASS,
            outputs=outputs,
            warnings=warnings,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        run.record["resume"]["replayed"].append("collect")
        if run.store is not None:
            run.store.save(collect_outcome, collect_inputs, builder.run_id)
    builder.add_stage(collect_outcome)

    if options.skip_compose:
        builder.add_stage(_stage("compose", Status.SKIPPED, reason="skip_compose"))
        builder.add_stage(_stage("brand", Status.SKIPPED, reason="skip_compose"))
        builder.add_check("V-14", Status.NOT_RUN, detail="compose skipped")
        builder.add_stage(_stage("verify", Status.SKIPPED, reason="skip_compose"))
        return run.finish()

    compose_outcome = run.run("compose", lambda: adapters.remotion.compose(paths))
    builder.add_stage(compose_outcome)
    if compose_outcome.status == Status.FAIL:
        _mark_not_run(builder, ["verify"], "upstream_failed")
        return run.finish()

    if paths.lesson.subtitles.enabled and paths.lesson.subtitles.render == "burn_in":
        burn_outcome = run.run(
            "burn_subtitles", lambda: adapters.burn.burn_subtitles(paths)
        )
        builder.add_stage(burn_outcome)
        if burn_outcome.status == Status.FAIL:
            builder.add_stage(_stage("verify", Status.NOT_RUN, reason="upstream_failed"))
            return run.finish()

    if paths.lesson.branding.enabled:
        brand_outcome = run.run("brand", lambda: adapters.brand.run(paths))
        builder.add_stage(brand_outcome)
        if brand_outcome.status == Status.FAIL:
            builder.add_stage(_stage("verify", Status.NOT_RUN, reason="upstream_failed"))
            return run.finish()
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

    return run.finish()
