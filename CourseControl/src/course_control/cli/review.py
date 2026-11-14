"""Shot review commands: build a review package or compare takes."""
from __future__ import annotations

import json
from pathlib import Path

import typer

from . import app


@app.command("shot-review")
def shot_review_command(
    shot: str = typer.Option(..., "--shot"),
    video: Path = typer.Option(..., "--video"),
    out: Path | None = typer.Option(None, "--out"),
    manifest: Path | None = typer.Option(None, "--manifest"),
    manifest_dir: Path | None = typer.Option(None, "--manifest-dir"),
    contact_frames: int = typer.Option(9, "--contact-frames", min=3),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Extract frames, contact sheet, preview, metadata, QC and review.md for one shot."""
    from course_control.review.shot_review import build_shot_review

    try:
        result = build_shot_review(
            workspace,
            shot=shot,
            video=video,
            out_dir=out,
            manifest=manifest,
            manifest_dir=manifest_dir,
            contact_frames=contact_frames,
        )
    except Exception as exc:  # noqa: BLE001 - CLI reports the failure
        typer.echo(f"shot review failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    raise typer.Exit(1 if result.status == "FAIL" else 0)


@app.command("shot-review-compare")
def shot_review_compare_command(
    shot: str = typer.Option(..., "--shot"),
    take: list[str] = typer.Option([], "--take", help="label=video; repeat for each take"),
    out: Path = typer.Option(..., "--out"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Build a side-by-side first/middle/last comparison; no aesthetic score."""
    from course_control.review.compare import build_comparison

    if len(take) < 2:
        typer.echo("shot-review-compare needs at least two --take label=video", err=True)
        raise typer.Exit(2)
    items: list[tuple[str, Path]] = []
    for value in take:
        if "=" not in value:
            typer.echo(f"invalid --take (expected label=video): {value}", err=True)
            raise typer.Exit(2)
        label, path = value.split("=", 1)
        items.append((label, Path(path)))
    try:
        target = build_comparison(workspace, shot=shot, takes=items, out=out)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"shot comparison failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(str(target))
