from __future__ import annotations

import json
from pathlib import Path

import typer

from ..paths import ContractError, LessonPaths
from . import app
from ._common import _lesson_path


@app.command("lock")
def lock_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    picture: bool = typer.Option(False, "--picture", help="Picture lock only"),
    dialogue: bool = typer.Option(False, "--dialogue", help="Dialogue lock only"),
    approved_by: str | None = typer.Option(None, "--approved-by"),
    note: str | None = typer.Option(None, "--note"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Snapshot the picture and/or the narration, and record who approved it."""
    from ..locks import LockError, dialogue as dialogue_lock, picture as picture_lock

    targets = []
    if picture:
        targets.append(("picture", picture_lock))
    if dialogue:
        targets.append(("dialogue", dialogue_lock))
    if not targets:
        targets = [("picture", picture_lock), ("dialogue", dialogue_lock)]

    paths = _load(workspace, lesson_dir, lesson)
    results = {}
    for name, module in targets:
        try:
            results[name] = module.write(paths, approved_by=approved_by, note=note)
        except LockError as exc:
            typer.echo(f"{name}: failed: {exc}", err=True)
            results[name] = {"error": str(exc)}

    if as_json:
        typer.echo(
            json.dumps(
                {
                    name: {
                        "path": str(item.get("path")) if item.get("path") else None,
                        "error": item.get("error"),
                        "checks": (item.get("lock") or {}).get("checks"),
                    }
                    for name, item in results.items()
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for name, item in results.items():
            if item.get("error"):
                continue
            lock = item["lock"]
            typer.echo(f"{name} lock: {item['path']}")
            for check in lock["checks"]:
                detail = f" — {check['detail']}" if check.get("detail") else ""
                typer.echo(f"  [{check['status']}] {check['id']}{detail}")
    failed = any(item.get("error") for item in results.values()) or any(
        check["status"] == "fail"
        for item in results.values()
        for check in (item.get("lock") or {}).get("checks") or []
    )
    raise typer.Exit(1 if failed else 0)


@app.command("lock-status")
def lock_status_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Compare current picture and narration against their locks."""
    from ..locks import LockError, affected, dialogue as dialogue_lock, diff, picture as picture_lock

    paths = _load(workspace, lesson_dir, lesson)
    report: dict[str, dict] = {}
    for name, module in (("picture", picture_lock), ("dialogue", dialogue_lock)):
        lock = module.load(paths)
        if lock is None:
            report[name] = {"locked": False}
            continue
        try:
            current = module.snapshot(paths)
        except LockError as exc:
            report[name] = {"locked": True, "locked_at": lock.get("locked_at"), "error": str(exc)}
            continue
        changes = diff(lock.get("hashes") or {}, current.get("hashes") or {})
        report[name] = {
            "locked": True,
            "locked_at": lock.get("locked_at"),
            "changes": changes,
            "affected": affected(changes),
        }

    if as_json:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for name, item in report.items():
            if not item.get("locked"):
                typer.echo(f"{name}: not locked")
                continue
            typer.echo(f"{name}: locked at {item.get('locked_at')}")
            if item.get("error"):
                typer.echo(f"  cannot verify: {item['error']}", err=True)
                continue
            if not item["changes"]:
                typer.echo("  no drift")
                continue
            for change in item["changes"]:
                downstream = ", ".join(change["downstream"]) or "-"
                typer.echo(f"  {change['change']}: {change['key']}  → re-check {downstream}")
            typer.echo(f"  affected: {', '.join(item['affected']) or '-'}")

    drifted = any(item.get("changes") or item.get("error") for item in report.values())
    raise typer.Exit(1 if drifted else 0)


def _load(workspace: Path, lesson_dir: Path | None, lesson: str) -> LessonPaths:
    try:
        return LessonPaths.load(workspace.resolve(), _lesson_path(workspace, lesson_dir, lesson))
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
