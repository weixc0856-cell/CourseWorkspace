from __future__ import annotations

import json

import typer

from pathlib import Path

from course_control.content.paths import ContractError
from course_control.content.validators import validate
from course_control.quality.verify import verify

from . import app
from course_control.cli._common import _paths, _lesson_path


@app.command("producer-order")
def producer_order_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    force: bool = typer.Option(False, "--force"),
    approve_by: str | None = typer.Option(None, "--approve"),
    audience: str | None = typer.Option(None, "--audience"),
    language: str | None = typer.Option(None, "--language"),
    target_seconds: float | None = typer.Option(None, "--target-seconds"),
    must_cover: list[str] | None = typer.Option(None, "--must-cover"),
    must_not: list[str] | None = typer.Option(None, "--must-not"),
    allow_network: bool = typer.Option(False, "--allow-network"),
    allow_new_dependencies: bool = typer.Option(False, "--allow-new-dependencies"),
    allow_publish: bool = typer.Option(False, "--allow-publish"),
    max_wall_seconds: float | None = typer.Option(None, "--max-wall-seconds"),
    max_api_cost_usd: float | None = typer.Option(None, "--max-api-cost-usd"),
    max_local_model_calls: int | None = typer.Option(None, "--max-local-model-calls"),
) -> None:
    """Create or load the production order for one lesson."""
    from course_control.direction.inputs import load_inputs
    from course_control.delivery.order import OrderOverrides, approve, ensure_order, load_order, order_path, save_order

    try:
        inputs = load_inputs(workspace.resolve(), _lesson_path(workspace, lesson_dir, lesson))
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    overrides = OrderOverrides(
        audience=audience,
        language=language,
        target_seconds=target_seconds,
        must_cover=must_cover,
        must_not=must_not,
        allow_network=allow_network,
        allow_new_dependencies=allow_new_dependencies,
        allow_publish=allow_publish,
        max_wall_seconds=max_wall_seconds,
        max_api_cost_usd=max_api_cost_usd,
        max_local_model_calls=max_local_model_calls,
    )
    try:
        order, path = ensure_order(inputs, inputs.paths.build_root, overrides, force)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"cannot create order: {exc}", err=True)
        raise typer.Exit(1)
    if approve_by:
        approve(order, approve_by)
        save_order(order, path)
    typer.echo(f"order: {path}")
    typer.echo(f"id: {order.order_id} / {order.target_seconds:g}s / {order.language}")
    typer.echo(f"must cover: {len(order.must_cover)} items")
    typer.echo(f"approved by: {order.approved_by or 'pending'}")


@app.command("producer-run")
def producer_run_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    force_order: bool = typer.Option(False, "--force-order"),
    approve: str | None = typer.Option(None, "--approve"),
) -> None:
    """Run the automated portion: validate, director plan, delivery package, state."""
    from course_control.delivery.orchestrator import run

    try:
        result = run(
            workspace.resolve(),
            _lesson_path(workspace, lesson_dir, lesson),
            force_order=force_order,
            approve_by=approve,
        )
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    typer.echo(f"state: {result.state.status} / delivery: {result.manifest.status}")
    typer.echo(f"director: {result.plan.status} ({result.plan.summary.shots} shots)")
    for item in result.manifest.items:
        present = sum(1 for record in item.files if record.status == "present")
        typer.echo(f"  {item.id}: {item.status} ({present}/{len(item.files)} files)")
    for entry in result.manifest.missing:
        typer.echo(f"  missing: {entry}")
    for problem in result.limits:
        typer.echo(f"  limit: {problem}")
    for name, path in result.paths.items():
        typer.echo(f"{name}: {path}")
    raise typer.Exit(1 if result.state.status == "blocked" else 0)


@app.command("producer-status")
def producer_status_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Show the production order, state and delivery status."""
    from course_control.delivery.orchestrator import status

    try:
        data = status(workspace.resolve(), _lesson_path(workspace, lesson_dir, lesson))
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    order, state, manifest = data["order"], data["state"], data["manifest"]
    typer.echo(f"order: {order.order_id} / approved by: {order.approved_by or 'pending'}")
    typer.echo(f"state: {state.status}")
    typer.echo(f"usage: {state.usage.wall_seconds:g}s wall / ${state.usage.api_cost_usd:g} / {state.usage.local_model_calls} calls")
    for name, value in state.stages.items():
        typer.echo(f"  {name}: {value}")
    if manifest is not None:
        typer.echo(f"delivery: {manifest.status} / missing: {len(manifest.missing)}")
        for entry in manifest.missing:
            typer.echo(f"  missing: {entry}")
    raise typer.Exit(0 if state.status != "blocked" else 1)


@app.command("producer-affected")
def producer_affected_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """List shots whose inputs changed since the last producer run."""
    from course_control.delivery.orchestrator import affected

    try:
        deltas = affected(workspace.resolve(), _lesson_path(workspace, lesson_dir, lesson))
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    if not deltas:
        typer.echo("no affected shots")
        raise typer.Exit(0)
    for delta in deltas:
        typer.echo(f"{delta.shot_id}: {delta.change} ({'; '.join(delta.reasons)})")
    raise typer.Exit(0)


@app.command("producer-rebuild")
def producer_rebuild_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    execute: bool = typer.Option(False, "--execute"),
    compose: bool = typer.Option(False, "--compose"),
    build_root: Path | None = typer.Option(None, "--build-root"),
) -> None:
    """Plan (and optionally run) a local rebuild of affected shots."""
    from course_control.delivery.orchestrator import execute_rebuild, plan_rebuild

    try:
        rebuild = plan_rebuild(
            workspace.resolve(),
            _lesson_path(workspace, lesson_dir, lesson),
            build_root.resolve() if build_root is not None else None,
            compose=compose,
        )
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    if not rebuild.deltas:
        typer.echo("no affected shots")
        raise typer.Exit(0)
    for delta in rebuild.deltas:
        typer.echo(f"{delta.shot_id}: {delta.change} ({'; '.join(delta.reasons)})")
    typer.echo(f"authorized: {'yes' if rebuild.authorized else 'no'}")
    typer.echo("command: " + " ".join(rebuild.command))
    if not execute:
        raise typer.Exit(0)
    if not rebuild.authorized:
        typer.echo("refused: order.authorizations.allow_render is false", err=True)
        raise typer.Exit(2)
    try:
        result = execute_rebuild(
            rebuild,
            workspace.resolve(),
            _lesson_path(workspace, lesson_dir, lesson),
            build_root.resolve() if build_root is not None else None,
            compose=compose,
        )
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report = result["report"]
    typer.echo(f"verdict: {report.verdict}")
    for stage in report.stages:
        if stage.name.startswith("render:"):
            typer.echo(f"  {stage.name}: {stage.status.value}")
    typer.echo(f"state refreshed: {'yes' if result['state'] is not None else 'no'}")
    raise typer.Exit(1 if result["failed"] else 0)


@app.command("package")
def package_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    out: Path | None = typer.Option(None, "--out"),
) -> None:
    """Collect a standard delivery package with SHA-256 for every file."""
    from course_control.delivery.package import PackageError, build_package

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    try:
        manifest, root = build_package(paths, out)
    except PackageError as exc:
        typer.echo(f"package failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"package: {root}")
    typer.echo(f"run_id: {manifest.get('run_id') or 'unknown'}")
    for item in manifest["files"]:
        typer.echo(f"  {item['status']:>13}  {item['path']}")
    raise typer.Exit(0)


@app.command("package-verify")
def package_verify_command(
    package: Path = typer.Option(..., "--package"),
) -> None:
    """Re-hash a delivery package and report missing or changed files."""
    from course_control.delivery.package import verify_package

    problems = verify_package(package)
    if problems:
        for problem in problems:
            typer.echo(problem, err=True)
        raise typer.Exit(2)
    typer.echo("package ok")
    raise typer.Exit(0)


@app.command("release-approve")
def release_approve_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    stage: str = typer.Option("release", "--stage", help="review or release"),
    approved_by: str = typer.Option(..., "--by"),
    decision: str = typer.Option("approved", "--decision", help="approved or rejected"),
    note: str = typer.Option("", "--note"),
) -> None:
    """Record a traceable human review or release decision.

    A release sign-off is refused unless the automatic verification is complete
    and the human review has already been approved.
    """
    import hashlib
    from datetime import datetime, timezone

    from course_control.quality.quality import build_quality_report

    if stage not in {"review", "release"}:
        typer.echo("stage must be review or release", err=True)
        raise typer.Exit(1)
    if decision not in {"approved", "rejected"}:
        typer.echo("decision must be approved or rejected", err=True)
        raise typer.Exit(1)
    if not approved_by.strip():
        typer.echo("--by must name the approver", err=True)
        raise typer.Exit(1)
    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    report, quality_path = build_quality_report(workspace.resolve(), paths)
    states = report["states"]
    if decision == "approved" and not states["VERIFY_PASS"]:
        typer.echo("automatic verification is not pass; refusing approval", err=True)
        typer.echo(f"VERIFY_INCOMPLETE={states['VERIFY_INCOMPLETE']} VERIFY_FAIL={states['VERIFY_FAIL']}", err=True)
        raise typer.Exit(2)
    if stage == "release" and decision == "approved" and not states["REVIEW_APPROVED"]:
        typer.echo("human review is not approved; refusing release sign-off", err=True)
        raise typer.Exit(2)

    build_report = paths.build_root / "final" / "build-report.json"
    final = paths.build_root / "final" / "course-video-mixed.mp4"
    if not final.is_file():
        final = paths.build_root / "final" / "course-video.mp4"
    if not build_report.is_file() or not final.is_file():
        typer.echo("build-report.json and final video are required", err=True)
        raise typer.Exit(2)

    def sha(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    payload = {
        "schema_version": 1,
        "lesson": paths.slug,
        "stage": stage,
        "decision": decision,
        "approved_by": approved_by.strip(),
        "approved_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "note": note,
        "build_report_sha256": sha(build_report),
        "final_video_sha256": sha(final),
        "quality_report_sha256": sha(quality_path),
    }
    target = paths.build_root / "quality" / f"{stage}-approval.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")
    typer.echo(f"{stage} decision: {decision} by {payload['approved_by']}")
    typer.echo(f"record: {target}")
    raise typer.Exit(0)


@app.command("review-status")
def review_status_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Show the adjudication queue for content findings."""
    from course_control.quality.review_decisions import summarize

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report = summarize(paths.build_root)
    if as_json:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        typer.echo(f"findings: {len(report['findings'])}")
        typer.echo(f"undecided: {len(report['undecided'])}")
        typer.echo(f"counts: {report['counts']}")
        for item in report["undecided"][:20]:
            typer.echo(f"  [open] {item}")
        if report["unknown_decisions"]:
            typer.echo("unknown decision values: " + ", ".join(report["unknown_decisions"]))
        if report["stale_decisions"]:
            typer.echo(
                "decisions for findings that no longer exist: "
                + ", ".join(report["stale_decisions"][:10])
            )
        typer.echo("needs human review: " + ("yes" if report["needs_human_review"] else "no"))
    raise typer.Exit(1 if report["needs_human_review"] else 0)


@app.command("review-decide")
def review_decide_command(
    lesson: str = typer.Option(..., "--lesson"),
    finding: str = typer.Option(..., "--id"),
    decision: str = typer.Option(
        ..., "--decision", help="accepted / rejected / fixed / deferred"
    ),
    by: str = typer.Option(..., "--by", help="the person making the decision"),
    note: str = typer.Option("", "--note"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Record one adjudication decision for a content finding."""
    from course_control.quality.review_decisions import DecisionError, record_decision

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    try:
        record_decision(paths.build_root, paths.slug, finding, decision, by=by, note=note)
    except DecisionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    typer.echo(f"{finding}: {decision} by {by}")


@app.command("vendor-check")
def vendor_check_command(
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Check every shot's copied three.js against the canonical vendor file."""
    from course_control.platform.vendor import audit

    problems = audit(workspace.resolve())
    for item in problems:
        typer.echo(item)
    if not problems:
        typer.echo("vendor ok")
    raise typer.Exit(1 if problems else 0)


@app.command("vendor-sync")
def vendor_sync_command(
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    shot: str | None = typer.Option(None, "--shot", help="sync only this shot"),
) -> None:
    """Copy the canonical three.js into shot directories."""
    from course_control.platform.vendor import sync, uses_three
    from course_control.platform.workspace_layout import engine_root

    shots_root = engine_root(workspace, "code_video") / "shots"

    if shot:
        target = shots_root / shot
        if not target.is_dir():
            typer.echo(f"shot not found: {target}", err=True)
            raise typer.Exit(1)
        projects = [target]
    elif shots_root.is_dir():
        # Shot sources are content and absent from a clean clone; nothing to sync
        # is a valid answer, not a crash.
        projects = sorted(
            path for path in shots_root.iterdir() if path.is_dir() and uses_three(path)
        )
    else:
        projects = []
    result = sync(workspace.resolve(), projects)
    typer.echo(f"copied: {', '.join(result['copied']) or 'none'}")
    typer.echo(f"current: {', '.join(result['current']) or 'none'}")
    for error in result["errors"]:
        typer.echo(error, err=True)
    raise typer.Exit(1 if result["errors"] else 0)


@app.command("stats")
def stats_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
    write: bool = typer.Option(False, "--write", help="write build/<slug>/quality/stats.json"),
) -> None:
    """Count pages, shots, audio assets, cues and delivery files from artifacts."""
    from course_control.quality.stats import lesson_stats, write_stats

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report = lesson_stats(paths)
    if write:
        write_stats(paths, report)
    if as_json:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        typer.echo(f"lesson: {report['lesson']} ({report['mode']}, authority={report['authority']})")
        for key, value in report["counts"].items():
            typer.echo(f"  {key}: {value}")
        typer.echo(f"  duration_seconds: {report['duration_seconds']}")
        typer.echo(f"  build: {report['status']['build']}  media_qc: {report['status']['media_qc']}")


@app.command("config-resolve")
def config_resolve_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
    write: bool = typer.Option(False, "--write", help="write build/<slug>/logs/config-resolution.json"),
) -> None:
    """Resolve every configuration value and report its source and conflicts."""
    from course_control.platform.config_resolve import blocking_conflicts, resolve_config, write_snapshot

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report = resolve_config(workspace.resolve(), paths)
    if write:
        write_snapshot(paths, report)
    if as_json:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        typer.echo(f"lesson: {report['lesson']}")
        typer.echo(f"fingerprint: {report['fingerprint']}")
        for item in report["values"]:
            typer.echo(f"  {item['key']}: {item['value']}  <- {item['source']}")
        for item in report["warnings"]:
            typer.echo(f"  [warn] {item}")
        for item in report["conflicts"]:
            typer.echo(f"  [{item['severity']}] {item['code']}: {item['message']}")
    raise typer.Exit(1 if blocking_conflicts(report) else 0)
