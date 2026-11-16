"""Defect diagnosis, repair planning and regression comparison."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from . import app
from course_control.cli._common import _paths
from course_control.content.paths import ContractError


def _defects(paths):
    from course_control.quality.defect import collect

    return collect(paths.build_root, paths.slug)


@app.command("quality-diagnose")
def quality_diagnose_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Collect blocking defects from the reports a build already wrote."""
    paths = _paths(workspace, lesson, lesson_dir)
    report = _defects(paths)
    target = paths.build_root / "quality" / "defects.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if as_json:
        typer.echo(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        typer.echo(f"defects: {len(report.defects)}")
        for defect in report.defects:
            typer.echo(
                f"  {defect.id} [{defect.dimension}/{defect.severity}] {defect.symptom}"
            )
        typer.echo(f"report: {target}")
    raise typer.Exit(1 if report.defects else 0)


@app.command("quality-repair-plan")
def quality_repair_plan_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    attempt: int = typer.Option(1, "--attempt", min=1),
) -> None:
    """Turn defects into the smallest rerun that can fix them."""
    from course_control.quality.defect import load as load_defects
    from course_control.quality.repair import plan, save

    paths = _paths(workspace, lesson, lesson_dir)
    report = load_defects(paths.build_root / "quality" / "defects.json")
    if report is None:
        report = _defects(paths)
    plans = plan(report, attempt=attempt)
    target = save(plans, paths.build_root / "quality" / "repair-plan.json")
    typer.echo(f"plans: {len(plans.plans)}")
    for item in plans.plans:
        scope = ", ".join(item.rebuild_scope) or "-"
        typer.echo(
            f"  {item.strategy:<16} attempt {item.attempt} "
            f"defects={','.join(item.defect_ids)} scope={scope}"
            + (f"  blocked: {item.reason}" if item.blocked else "")
        )
    typer.echo(f"plan: {target}")
    raise typer.Exit(1 if any(item.blocked for item in plans.plans) else 0)


@app.command("quality-regression")
def quality_regression_command(
    before: Path = typer.Option(..., "--before", help="earlier defects.json"),
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Compare the current defects with an earlier report."""
    from course_control.quality.defect import load as load_defects
    from course_control.quality.regression import compare

    paths = _paths(workspace, lesson, lesson_dir)
    earlier = load_defects(before)
    if earlier is None:
        typer.echo(f"cannot read {before}", err=True)
        raise typer.Exit(1)
    current = _defects(paths)
    result = compare(earlier, current)
    target = paths.build_root / "quality" / "regression.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if as_json:
        typer.echo(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        typer.echo(f"fixed: {len(result.fixed)}")
        typer.echo(f"still open: {len(result.still_open)}")
        typer.echo(f"introduced: {len(result.introduced)}")
        for defect_id in result.introduced:
            typer.echo(f"  [regression] {defect_id}")
        typer.echo(f"report: {target}")
    raise typer.Exit(1 if result.regressed else 0)


@app.command("quality-certificate")
def quality_certificate_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
    refresh: bool = typer.Option(
        False, "--refresh", help="Scan defects and run the quality gate before issuing."
    ),
) -> None:
    """Issue the quality certificate for a lesson's current reports.

    The certificate reads three artifacts.  ``--refresh`` writes the two that a
    build does not write by itself, so issuing a verdict is one command instead
    of the diagnose → gate → certificate sequence.
    """
    from course_control.quality.certificate import issue, save

    paths = _paths(workspace, lesson, lesson_dir)
    from course_control.authoring.pipeline import assert_storyboard_signed

    try:
        assert_storyboard_signed(paths.lesson_dir, paths.storyboard_source)
        from course_control.release.check import content_exception_for

        exception = content_exception_for(paths.build_root, paths.slug)
        if exception is not None:
            raise RuntimeError(
                "open content exception: "
                + str(exception.get("reason") or exception.get("detail") or "see queue")
            )
    except Exception as exc:  # noqa: BLE001 - the gate is user-facing
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(3)
    if refresh:
        from course_control.quality.defect import collect
        from course_control.quality.quality_gates import evaluate

        report = collect(paths.build_root, paths.slug)
        defects_path = paths.build_root / "quality" / "defects.json"
        defects_path.parent.mkdir(parents=True, exist_ok=True)
        defects_path.write_text(
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        evaluate(paths)
        typer.echo(f"refreshed: {defects_path}")

    certificate = issue(paths.build_root, paths.slug)
    target = save(certificate, paths.build_root / "quality" / "certificate.json")
    if as_json:
        typer.echo(json.dumps(certificate.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        typer.echo(f"verdict: {certificate.verdict}")
        for dimension, status in certificate.dimensions.items():
            typer.echo(f"  {dimension}: {status}")
        for defect_id in certificate.open_defects:
            typer.echo(f"  [open] {defect_id}")
        if certificate.reason:
            typer.echo(f"reason: {certificate.reason}")
        typer.echo(f"certificate: {target}")
    raise typer.Exit(0 if certificate.verdict == "pass" else 1)

@app.command("exception-observe")
def exception_observe_command(
    lesson: str = typer.Option(..., "--lesson"),
    check: str = typer.Option(..., "--check"),
    state: str = typer.Option("open", "--state", help="open or resolved"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    build_root: Path | None = typer.Option(
        None, "--build-root", help="record against this build root (dev fixtures)"
    ),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    run_id: str = typer.Option("", "--run-id"),
    detail: str = typer.Option("", "--detail"),
    owner: str = typer.Option("unassigned", "--owner"),
    scope: str = typer.Option("", "--scope"),
    reason: str = typer.Option("", "--reason"),
    clear_when: str = typer.Option("", "--clear-when"),
    release_policy: str = typer.Option("", "--release-policy"),
    observed_at: str | None = typer.Option(None, "--observed-at"),
) -> None:
    """Record one automatic check observation in the per-lesson queue.

    A passing check writes ``resolved`` and keeps the entry; it never writes
    ``cleared``.  A corrupt queue, index or legacy file leaves every file
    unchanged and exits 1.
    """
    from course_control.quality.exceptions import ExceptionQueueError, record_observation

    if state not in {"open", "resolved"}:
        typer.echo("state must be open or resolved", err=True)
        raise typer.Exit(2)
    if build_root is not None:
        from course_control.platform.workspace_layout import content_root

        allowed = content_root(workspace.resolve()).resolve()
        candidate = build_root.resolve()
        try:
            candidate.relative_to(allowed)
        except ValueError:
            typer.echo(
                f"build root must stay inside the content root: {candidate}", err=True
            )
            raise typer.Exit(2)
        target_root = candidate
        target_lesson = lesson
    else:
        try:
            paths = _paths(workspace, lesson, lesson_dir)
        except ContractError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
        target_root = paths.build_root
        target_lesson = paths.slug
    try:
        result = record_observation(
            target_root,
            target_lesson,
            check,
            resolved=state == "resolved",
            observed_at=observed_at,
            run_id=run_id,
            detail=detail,
            owner=owner,
            scope=scope,
            reason=reason,
            clear_when=clear_when,
            release_policy=release_policy,
        )
    except ExceptionQueueError as exc:
        typer.echo(f"exception queue unchanged: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"{result['check']}: {result['status']} ({result['lesson']})")

