from __future__ import annotations

import typer

from pathlib import Path

from course_control.content.paths import ContractError

from . import app
from course_control.cli._common import _paths


@app.command("e6-adapt")
def e6_adapt_command(
    manifest: Path = typer.Option(
        Path("build/manim-transformer/e6/manifest.json"), "--manifest"
    ),
    output: Path = typer.Option(
        Path("build/manim-transformer/e6/render.manifest.v1.json"), "--output"
    ),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    run_id: str | None = typer.Option(None, "--run-id"),
) -> None:
    """Read E6 V0 manifest and media, then write a V1 RenderManifest.

    V0 and its media are never modified.  Failed automatic checks are written
    into the manifest and make the command exit 1.
    """
    from course_control.content.legacy_e6 import LegacyE6Error, adapt_e6_manifest

    if not manifest.is_file():
        typer.echo(f"manifest not found: {manifest}", err=True)
        raise typer.Exit(2)
    try:
        render, checks = adapt_e6_manifest(
            manifest, workspace=workspace, run_id=run_id
        )
    except LegacyE6Error as exc:
        typer.echo(f"E6 adapt failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render.model_dump_json(indent=2) + chr(10),
        encoding="utf-8",
    )
    typer.echo(f"wrote {output}")
    for check in checks:
        typer.echo(f"[{check.id}] {check.status}: {check.detail}")
    failed = [check for check in checks if check.status == "fail"]
    raise typer.Exit(1 if failed else 0)


@app.command("e65-adapt")
def e65_adapt_command(
    manifest: Path = typer.Option(
        Path("build/manim-multi-head/e6.5/manifest.json"), "--manifest"
    ),
    output_dir: Path | None = typer.Option(None, "--output-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    voice_ref: Path | None = typer.Option(None, "--voice-ref"),
    run_id: str | None = typer.Option(None, "--run-id"),
) -> None:
    """Generate V1 NarrationSpec/TimelineSpec/ShotSpec/RenderManifest for E6.5."""
    from course_control.content.e65 import E65Error, adapt_e65

    if not manifest.is_file():
        typer.echo(f"manifest not found: {manifest}", err=True)
        raise typer.Exit(2)
    try:
        result = adapt_e65(
            manifest,
            workspace=workspace,
            voice_ref=voice_ref,
            run_id=run_id,
            output_dir=output_dir,
        )
    except E65Error as exc:
        typer.echo(f"E6.5 adapt failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    render = result["manifest"]
    for key, path in result["paths"].items():
        if isinstance(path, list):
            for item in path:
                typer.echo(f"wrote {item}")
        else:
            typer.echo(f"wrote {path}")
    for check in render.checks:
        typer.echo(f"[{check.id}] {check.status}: {check.detail}")
    failed = [check for check in render.checks if check.status == "fail"]
    raise typer.Exit(1 if failed else 0)


@app.command("timeline-v1")
def timeline_v1_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    """Write a V1 TimelineSpec from an existing build/<slug>/shots.json."""
    from course_control.content.contracts import ShotsFile
    from course_control.content.v1_timeline import V1TimelineError, write_timeline_contract

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    shots_path = paths.build_root / "shots.json"
    if not shots_path.is_file():
        typer.echo(f"shots.json missing: {shots_path}", err=True)
        raise typer.Exit(2)
    shots = ShotsFile.model_validate_json(shots_path.read_text(encoding="utf-8"))
    try:
        target, timeline = write_timeline_contract(shots, paths, output=output)
    except V1TimelineError as exc:
        typer.echo(f"timeline-v1 failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(
        f"wrote {target} ({timeline.total_frames} frames, "
        f"{len(timeline.video)} video entries)"
    )
