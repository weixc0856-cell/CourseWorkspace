from __future__ import annotations

import json

import typer

from pathlib import Path

from ..paths import LessonPaths
from ..workspace_layout import lessons_root


def _lesson_root(workspace: Path, lesson_dir: Path | None) -> Path:
    """Resolve the lessons directory; None means <content_root>/lessons."""
    root = lessons_root(workspace) if lesson_dir is None else Path(lesson_dir)
    if not root.is_absolute():
        root = Path(workspace) / root
    return root.resolve()


def _lesson_path(workspace: Path, lesson_dir: Path | None, lesson: str) -> Path:
    return (_lesson_root(workspace, lesson_dir) / lesson).resolve()


def _paths(workspace: Path, lesson: str, lesson_dir: Path | None) -> LessonPaths:
    return LessonPaths.load(workspace.resolve(), _lesson_path(workspace, lesson_dir, lesson))


def _print_issues(result) -> None:
    for issue in result.issues:
        typer.echo(f"[{issue.rule}] {issue.level}: {issue.message}")
    if not result.issues:
        typer.echo("no issues")


def _authoring_client(workspace: Path, start_service: bool, remote_only: bool = False):
    from ..authoring.llm import AuthoringClient, AuthoringConfig

    return AuthoringClient(
        AuthoringConfig.load(workspace.resolve()),
        start_service=start_service,
        remote_only=remote_only,
    )


def _load_authoring(lesson_dir: Path, name: str, model_type):
    path = lesson_dir.resolve() / "authoring" / name
    if not path.is_file():
        typer.echo(f"missing approved artifact: {path}", err=True)
        raise typer.Exit(1)
    return model_type.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _run_authoring(action) -> None:
    from ..authoring.llm import AuthoringBlocked, AuthoringError

    try:
        action()
    except AuthoringBlocked as exc:
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(3)
    except (AuthoringError, FileNotFoundError, ValueError) as exc:
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
