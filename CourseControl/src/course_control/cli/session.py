from __future__ import annotations

import json

import typer

from pathlib import Path

from ..validators import validate
from ..verify import verify

from . import app
from ._common import _lesson_root


@app.command("session-validate")
def session_validate_command(
    spec: Path = typer.Option(..., "--spec"),
    lesson_dir: Path = typer.Option(..., "--lesson-dir"),
) -> None:
    """Validate a session spec without executing it."""
    from ..session import SessionContractError, load_session_spec

    try:
        session = load_session_spec(spec)
    except SessionContractError as exc:
        for message in exc.messages:
            typer.echo(f"  - {message}", err=True)
        raise typer.Exit(1)
    missing = [
        entry.source
        for entry in session.files
        if not (lesson_dir.resolve() / entry.source).is_file()
    ]
    if missing:
        for item in missing:
            typer.echo(f"  - session file not found: {item}", err=True)
        raise typer.Exit(1)
    typer.echo(
        json.dumps(
            {
                "lesson": session.lesson,
                "shot_id": session.shot_id,
                "session_id": session.session_id,
                "commands": len(session.commands),
                "files": len(session.files),
                "image": session.environment.image,
                "network": session.environment.network,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command("session-run")
def session_run_command(
    spec: Path = typer.Option(..., "--spec"),
    lesson_dir: Path = typer.Option(..., "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    record: bool = typer.Option(False, "--record/--no-record"),
) -> None:
    """Execute and verify a code/terminal session (E1)."""
    from ..session import SessionContractError
    from ..session_runner import SessionRunError, run_session

    if not spec.is_file():
        typer.echo(f"session spec not found: {spec}", err=True)
        raise typer.Exit(1)
    try:
        result, manifest, recording = run_session(
            workspace.resolve(), spec, lesson_dir, record=record
        )
    except (SessionContractError, SessionRunError) as exc:
        messages = getattr(exc, "messages", [str(exc)])
        for message in messages:
            typer.echo(f"  - {message}", err=True)
        raise typer.Exit(1)
    for command in result.commands:
        for assertion in command.assertions:
            status = "pass" if assertion.ok else "fail"
            typer.echo(f"[{command.id}/{assertion.name}] {status}: {assertion.detail}")
    lesson = json.loads(spec.read_text(encoding="utf-8")).get("lesson", "")
    validation_path = (
        workspace.resolve() / "build" / lesson / "code" / manifest.shot_id / "validation.json"
    )
    if validation_path.is_file():
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        for check in validation.get("checks", []):
            typer.echo(f"[{check['id']}] {check['status']}: {check.get('detail', '')}")
    if recording is not None:
        typer.echo(
            f"recording: {recording.path} ({recording.width}x{recording.height}, "
            f"{recording.duration_s:.3f}s)"
        )
    typer.echo(f"status: {result.status}")
    typer.echo(f"failure: {result.failure.value if result.failure else 'none'}")
    typer.echo(f"evidence: build/{lesson}/code/{manifest.shot_id}/evidence.json")
    raise typer.Exit(0 if result.status == "passed" else 1)


@app.command("session-evidence-v1")
def session_evidence_v1_command(
    spec: Path = typer.Option(..., "--spec"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    output: Path | None = typer.Option(None, "--output"),
    run_id: str | None = typer.Option(None, "--run-id"),
) -> None:
    """Upgrade an existing session evidence.json to V1 EvidenceManifest."""
    from ..session import SessionContractError, load_session_spec
    from ..session_evidence_v1 import V1EvidenceError, adapt_session_evidence

    workspace = workspace.resolve()
    try:
        manifest = adapt_session_evidence(
            spec, workspace, run_id=run_id
        )
    except (V1EvidenceError, SessionContractError) as exc:
        typer.echo(f"session-evidence-v1 failed: {exc}", err=True)
        raise typer.Exit(1)
    session = load_session_spec(spec)
    target = output or (
        workspace
        / "build"
        / session.lesson
        / "code"
        / session.shot_id
        / "evidence.v1.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(manifest.model_dump_json(indent=2) + chr(10), encoding="utf-8")
    typer.echo(f"wrote {target}")
