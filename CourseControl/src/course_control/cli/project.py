"""ProjectSpec, artifact index and run records.

These commands are additive: they read and write new files under
``<content root>/projects`` and ``<content root>/runtime`` and never change how
an existing lesson builds.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from . import app


def _spec(workspace: Path, project: Path | None, project_id: str | None):
    from course_control.delivery.project import find_project, load_project

    if project is not None:
        return load_project(project)
    if project_id:
        path = find_project(workspace, project_id)
        if path is None:
            typer.echo(f"project not found: {project_id}", err=True)
            raise typer.Exit(1)
        return load_project(path)
    typer.echo("pass --project <path> or --id <project-id>", err=True)
    raise typer.Exit(1)


@app.command("project-validate")
def project_validate_command(
    project: Path | None = typer.Option(None, "--project", help="path to project.yaml"),
    project_id: str | None = typer.Option(None, "--id", help="project id under <content root>/projects"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Validate a ProjectSpec."""
    from pydantic import ValidationError

    workspace = workspace.resolve()
    try:
        spec = _spec(workspace, project, project_id)
    except (ValidationError, ValueError) as exc:
        typer.echo(f"invalid: {exc}", err=True)
        raise typer.Exit(1)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
    if as_json:
        typer.echo(json.dumps(spec.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2))
    else:
        typer.echo(f"project: {spec.project.id} ({spec.project.mode})")
        typer.echo(f"title: {spec.project.title}")
        typer.echo(f"sources: {len(spec.input.sources)}")
        typer.echo(f"quality: {spec.production.quality_profile}")
        typer.echo(f"autonomy: {spec.execution.autonomy}")
        typer.echo("status: valid")
    raise typer.Exit(0)


@app.command("project-show")
def project_show_command(
    project: Path | None = typer.Option(None, "--project"),
    project_id: str | None = typer.Option(None, "--id"),
    lesson: str | None = typer.Option(None, "--lesson", help="synthesise a spec for an existing lesson"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Print a ProjectSpec, including the synthesised form of a legacy lesson."""
    from course_control.delivery.project import synthesize_for_lesson

    workspace = workspace.resolve()
    try:
        if lesson:
            spec = synthesize_for_lesson(workspace, lesson)
        else:
            spec = _spec(workspace, project, project_id)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(spec.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2))


@app.command("artifact-index")
def artifact_index_command(
    lesson: str = typer.Option(..., "--lesson"),
    project_id: str | None = typer.Option(None, "--project-id"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Rebuild the artifact registry from an existing build tree."""
    from course_control.platform.artifacts import (
        rebuild_from_build,
        registry_path,
        save_registry,
    )
    from course_control.platform.workspace_layout import build_root_for

    workspace = workspace.resolve()
    build = build_root_for(workspace, lesson)
    if not build.is_dir():
        typer.echo(f"no build directory: {build}", err=True)
        raise typer.Exit(1)
    registry = rebuild_from_build(build, project_id or lesson)
    target = save_registry(registry, registry_path(workspace, project_id or lesson))
    typer.echo(f"artifacts: {len(registry.artifacts)}")
    typer.echo(f"registry: {target}")


@app.command("run-start")
def run_start_command(
    project_id: str | None = typer.Option(None, "--project"),
    lesson: str | None = typer.Option(None, "--lesson"),
    autonomy: str | None = typer.Option(None, "--autonomy", help="A0 / A1 / A2 / A3"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Start a run record for a project or a legacy lesson."""
    from course_control.delivery.project import find_project, load_project, synthesize_for_lesson
    from course_control.platform.run_record import new_run

    workspace = workspace.resolve()
    if project_id:
        path = find_project(workspace, project_id)
        if path is None:
            typer.echo(f"project not found: {project_id}", err=True)
            raise typer.Exit(1)
        spec = load_project(path)
    elif lesson:
        spec = synthesize_for_lesson(workspace, lesson)
    else:
        typer.echo("pass --project <id> or --lesson <slug>", err=True)
        raise typer.Exit(1)
    level = autonomy or spec.execution.autonomy
    if level not in {"A0", "A1", "A2", "A3"}:
        typer.echo(f"unknown autonomy level: {level}", err=True)
        raise typer.Exit(1)
    record, path = new_run(workspace, spec.project.id, spec.project.mode, autonomy=level)
    typer.echo(f"run: {record.run_id}")
    typer.echo(f"project: {record.project_id} ({record.mode}, {record.autonomy})")
    typer.echo(f"record: {path}")


@app.command("run-status")
def run_status_command(
    run_id: str = typer.Option(..., "--run"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Show the stage history of one run."""
    from course_control.platform.run_record import load_run

    workspace = workspace.resolve()
    record = load_run(workspace, run_id)
    if record is None:
        typer.echo(f"run not found: {run_id}", err=True)
        raise typer.Exit(1)
    if as_json:
        typer.echo(json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return
    typer.echo(f"run: {record.run_id}  status: {record.status}")
    typer.echo(f"project: {record.project_id} ({record.mode}, {record.autonomy})")
    for stage in record.stages:
        suffix = f"  {stage.reason}" if stage.reason else ""
        typer.echo(f"  {stage.name:<12} {stage.status}{suffix}")
