from __future__ import annotations

import json
from pathlib import Path

import typer

from .config import ConfigError, PROJECT_ROOT
from .contracts import Finding, ModelReply, ReviewReport, ReviewTask
from .review import load_report, run_review

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command("review")
def review_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    """Review one lesson with the online model. Never changes lesson content."""
    config_path = config or (workspace / "config" / "content-qa.yaml")
    try:
        report, path = run_review(
            workspace, lesson_dir / lesson, config_path=config_path
        )
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    typer.echo(f"status: {report.status}")
    typer.echo(f"findings: {len(report.findings)}")
    typer.echo(f"report: {path}")
    for error in report.errors:
        typer.echo(f"  ! {error}", err=True)
    if report.status == "blocked":
        raise typer.Exit(3)
    raise typer.Exit(0 if report.status == "completed" else 1)


@app.command("status")
def status_command(
    lesson: str = typer.Option(..., "--lesson"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Show the last review report for a lesson."""
    report = load_report(workspace.resolve(), lesson)
    if report is None:
        typer.echo("no review report")
        raise typer.Exit(1)
    typer.echo(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


@app.command("schema")
def schema_command(
    output: Path = typer.Option(PROJECT_ROOT / "schemas", "--output"),
) -> None:
    """Export JSON Schemas for review contracts."""
    output.mkdir(parents=True, exist_ok=True)
    models = {
        "content-review": ReviewReport,
        "content-finding": Finding,
        "content-reply": ModelReply,
        "content-task": ReviewTask,
    }
    for name, model in models.items():
        target = output / f"{name}.schema.json"
        target.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        typer.echo(f"wrote {target}")


if __name__ == "__main__":
    app()
