from __future__ import annotations

from pathlib import Path

import typer

from . import app
from course_control.cli._common import _paths
from course_control.content.paths import ContractError
from course_control.production.preflight import run_preflight


@app.command("preflight")
def preflight_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    strict: bool = typer.Option(False, "--strict", help="treat warnings as errors"),
) -> None:
    """Check episode.spec.yaml and quality.rubric.yaml before any render."""
    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report = run_preflight(paths.lesson_dir, strict=strict)
    typer.echo(f"lesson: {report.lesson}")
    if report.spec is not None:
        typer.echo(f"episode: {report.spec.episode}")
        typer.echo(f"beats: {len(report.spec.beats)} ({report.spec.total_seconds}s)")
        typer.echo(f"claims: {len(report.spec.claims)}")
    for warning in report.warnings:
        typer.echo(f"  [warn] {warning}")
    for error in report.errors:
        typer.echo(f"  [error] {error}")
    typer.echo("status: " + ("PASS" if report.ok else "FAIL"))
    raise typer.Exit(0 if report.ok else 1)


@app.command("checks")
def checks_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    stage: str = typer.Option("spec", "--stage"),
    book_index: Path | None = typer.Option(None, "--book-index", help="book index.json used by claim_source_coverage"),
    strict: bool = typer.Option(False, "--strict", help="review items also fail the run"),
) -> None:
    """Run typed auto/review checks and write an exception queue."""
    import json

    from course_control.production.checks import run_checks
    from course_control.production.episode_spec import load_episode_spec
    from course_control.production.quality_rubric import load_quality_rubric

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    try:
        spec = load_episode_spec(paths.lesson_dir / "authoring" / "episode.spec.yaml")
        rubric = load_quality_rubric(paths.lesson_dir / "authoring" / "quality.rubric.yaml")
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"checks failed to load: {exc}", err=True)
        raise typer.Exit(1)
    report = run_checks(spec, rubric, paths.lesson_dir, paths.build_root, book_index=book_index)
    typer.echo(f"book index: {book_index if book_index else 'not provided'}")
    for result in report.results:
        typer.echo(f"  [{result.status}] {result.id} ({result.kind}): {result.actual!r}")
    payload = report.as_dict(stage)
    target = paths.build_root / "quality" / "exceptions.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    typer.echo(f"exceptions: {target}")
    failed = bool(report.auto_failed) or (strict and bool(report.review_open))
    typer.echo("status: " + ("FAIL" if failed else "PASS"))
    raise typer.Exit(1 if failed else 0)
