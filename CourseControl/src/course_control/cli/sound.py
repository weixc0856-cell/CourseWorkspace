from __future__ import annotations

from pathlib import Path

import typer

from . import app
from course_control.cli._common import _lesson_path


@app.command("sound-design")
def sound_design_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    out: Path | None = typer.Option(None, "--out"),
    plan: Path | None = typer.Option(None, "--plan", help="Reuse this director plan instead of build/director."),
    strict: bool = typer.Option(False, "--strict", help="Exit 1 on warnings as well as errors."),
) -> None:
    """Write the voice/music/effects/ambience plan and its cue sheet."""
    from course_control.content.paths import ContractError
    from course_control.sound.service import run

    try:
        design, paths = run(
            workspace.resolve(),
            _lesson_path(workspace, lesson_dir, lesson),
            out.resolve() if out is not None else None,
            plan.resolve() if plan is not None else None,
        )
    except (ContractError, ValueError, FileNotFoundError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    typer.echo(
        f"content kind: {design.content_kind} → {design.style} / "
        f"voice {len(design.voice)} · music {len(design.music)} · "
        f"sfx {len(design.sfx)} · ambience {len(design.ambience)}"
    )
    typer.echo(f"mix: {design.mix.loudness_lufs:g} LUFS / {design.mix.true_peak_db:g} dBTP")
    typer.echo(f"errors: {design.errors}, warnings: {design.warnings}")
    for check in design.checks:
        typer.echo(f"  [{check.level}] {check.id}: {check.message}")
    for name, path in paths.items():
        typer.echo(f"{name}: {path}")
    failed = design.errors > 0 or (strict and design.warnings > 0)
    raise typer.Exit(1 if failed else 0)
