from __future__ import annotations

from pathlib import Path

import typer

from . import app
from course_control.cli._common import _lesson_path


@app.command("visual-design")
def visual_design_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    out: Path | None = typer.Option(None, "--out"),
    plan: Path | None = typer.Option(None, "--plan", help="Reuse this director plan instead of build/director."),
    shot: list[str] = typer.Option(None, "--shot", help="Only design these shots (repeatable)."),
    strict: bool = typer.Option(False, "--strict", help="Exit 1 on warnings as well as errors."),
) -> None:
    """Write per-shot visual designs and keyframe boards before any engine renders."""
    from course_control.content.paths import ContractError
    from course_control.design.service import run

    try:
        document, paths = run(
            workspace.resolve(),
            _lesson_path(workspace, lesson_dir, lesson),
            out.resolve() if out is not None else None,
            list(shot or []),
            plan.resolve() if plan is not None else None,
        )
    except (ContractError, ValueError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    typer.echo(f"shots: {len(document.shots)} / theme: {document.theme_default}")
    typer.echo(
        f"authored: {sum(1 for item in document.shots if item.authorship == 'authored')}, "
        f"derived: {sum(1 for item in document.shots if item.authorship == 'derived')}"
    )
    typer.echo(f"errors: {document.errors}, warnings: {document.warnings}")
    for check in document.checks:
        if check.level == "info":
            continue
        target = f" {check.shot_id}" if check.shot_id else ""
        typer.echo(f"  [{check.level}] {check.id}{target}: {check.message}".rstrip())
    for name, path in paths.items():
        typer.echo(f"{name}: {path}")
    failed = document.errors > 0 or (strict and document.warnings > 0)
    raise typer.Exit(1 if failed else 0)
