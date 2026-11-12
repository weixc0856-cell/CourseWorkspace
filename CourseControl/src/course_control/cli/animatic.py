from __future__ import annotations

from pathlib import Path

import typer

from course_control.content.paths import ContractError, LessonPaths
from . import app
from course_control.cli._common import _lesson_path


@app.command("animatic")
def animatic_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    audio: Path | None = typer.Option(
        None,
        "--audio",
        help="Scratch or reference narration; defaults to build/<slug>/narration/narration.wav",
    ),
    silent: bool = typer.Option(False, "--silent", help="No audio at all"),
    shot: list[str] = typer.Option(None, "--shot", help="Re-encode only these units; the rest is reused"),
    size: str = typer.Option("854x480", "--size", help="WIDTHxHEIGHT; the preview default is 480p"),
    force: bool = typer.Option(False, "--force", help="Ignore the segment cache"),
) -> None:
    """Build a watchable 480p animatic of one lesson on its real timeline."""
    from course_control.animatic import AnimaticError, build, resolve, write_artifacts

    parsed = _size(size)
    try:
        paths = LessonPaths.load(workspace.resolve(), _lesson_path(workspace, lesson_dir, lesson))
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    try:
        timeline = resolve(paths, size=parsed)
        result = build(
            paths,
            timeline,
            audio=audio,
            silent=silent,
            only=set(shot) if shot else None,
            force=force,
        )
        report = write_artifacts(paths, timeline, result)
    except (AnimaticError, OSError) as exc:
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)

    kinds = {"clip": 0, "still": 0, "placeholder": 0}
    for unit in timeline.units:
        kinds[unit.kind] = kinds.get(unit.kind, 0) + 1
    typer.echo(f"animatic: {report['video']['file']}  ({result['out']})")
    typer.echo(
        f"mode: {timeline.mode}  units: {len(timeline.units)} "
        f"({kinds['clip']} clip, {kinds['still']} still, {kinds['placeholder']} placeholder)  "
        f"duration: {report['video'].get('duration') or 0:.2f}s"
    )
    audio_row = report.get("audio")
    typer.echo(
        "audio: silent"
        if not audio_row
        else f"audio: {Path(audio_row['source']).name}  {audio_row.get('duration_s') or 0:.2f}s"
    )
    cache = {"reused": 0, "encoded": 0}
    for segment in result["segments"]:
        cache["reused" if segment.reused else "encoded"] += 1
    typer.echo(f"segments: {cache['encoded']} encoded, {cache['reused']} reused")
    for check in report["checks"]:
        typer.echo(f"  [{check['status']}] {check['id']}: {check['actual']}")
    for warning in report["warnings"][:8]:
        typer.echo(f"  warning: {warning}")
    for unit in report["units"]:
        if unit["status"] != "ok":
            typer.echo(f"  {unit['status']}: {unit['id']} — {unit['detail'] or ''}".rstrip())
    typer.echo(f"ok: {report['ok']}")
    raise typer.Exit(0 if report["ok"] else 1)


def _size(value: str) -> tuple[int, int]:
    try:
        width, height = value.lower().split("x", 1)
        parsed = (int(width), int(height))
    except ValueError:
        typer.echo(f"invalid --size '{value}'; expected WIDTHxHEIGHT", err=True)
        raise typer.Exit(2)
    if parsed[0] < 16 or parsed[1] < 16 or parsed[0] % 2 or parsed[1] % 2:
        typer.echo("--size must be even and at least 16x16", err=True)
        raise typer.Exit(2)
    return parsed
