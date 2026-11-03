from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from .contracts import Status
from .paths import ContractError, LessonPaths
from .pipeline import BuildOptions, run_build
from .report import check_report_payload, toolchain_versions
from .validators import validate
from .verify import verify

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _paths(workspace: Path, lesson: str, lesson_dir: Path) -> LessonPaths:
    return LessonPaths.load(workspace.resolve(), (lesson_dir / lesson).resolve())


def _print_issues(result) -> None:
    for issue in result.issues:
        typer.echo(f"[{issue.rule}] {issue.level}: {issue.message}")
    if not result.issues:
        typer.echo("no issues")


@app.command()
def audit(workspace: Path = typer.Option(Path.cwd(), "--workspace")) -> None:
    """Print toolchain versions and workspace paths."""
    versions = toolchain_versions(workspace.resolve())
    for name, version in versions.items():
        typer.echo(f"{name}: {version}")
    typer.echo(f"workspace: {workspace.resolve()}")


def validate_lesson(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Validate lesson contracts without rendering."""
    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    result = validate(paths)
    _print_issues(result)
    raise typer.Exit(0 if result.ok else 1)


@app.command("build")
def build_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    skip_render: bool = typer.Option(False, "--skip-render"),
    skip_compose: bool = typer.Option(False, "--skip-compose"),
) -> None:
    """Run the applicable stages for a lesson."""
    try:
        report, report_path = run_build(
            workspace.resolve(),
            (lesson_dir / lesson).resolve(),
            BuildOptions(skip_render=skip_render, skip_compose=skip_compose),
        )
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    typer.echo(f"verdict: {report.verdict}")
    typer.echo(f"report: {report_path}")
    for stage in report.stages:
        typer.echo(f"  {stage.name}: {stage.status.value}")
    for failure in report.failures:
        typer.echo(f"  ! {failure}")
    raise typer.Exit(1 if report.verdict == "fail" else 0)


@app.command("verify")
def verify_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Verify an existing shots.json and final video."""
    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    shots_path = paths.build_root / "shots.json"
    if not shots_path.is_file():
        typer.echo(f"shots.json missing: {shots_path}", err=True)
        raise typer.Exit(1)
    from .contracts import ShotsFile

    shots_file = ShotsFile.model_validate(json.loads(shots_path.read_text(encoding="utf-8")))
    checks = verify(paths, shots_file)
    report_path = paths.build_root / "final" / "build-report.json"
    if report_path.is_file():
        checks.append(check_report_payload(paths, json.loads(report_path.read_text(encoding="utf-8"))))
    for check in checks:
        typer.echo(f"[{check.id}] {check.status.value}: {check.detail or check.actual or ''}")
    failed = [check for check in checks if check.status == Status.FAIL]
    raise typer.Exit(1 if failed else 0)


# Typer exposes a command named validate-lesson by default; keep a friendly alias.
app.command("validate")(validate_lesson)


@app.command("schemas")
def schemas_command(
    output: Path = typer.Option(Path("shared/schemas"), "--output"),
) -> None:
    """Export JSON Schema files for all contracts."""
    from .blender_scene import BlenderSceneTask
    from .contracts import BuildReport, LessonConfig, ShotsFile, Storyboard

    output.mkdir(parents=True, exist_ok=True)
    models = {
        "lesson": LessonConfig,
        "storyboard": Storyboard,
        "shots": ShotsFile,
        "build-report": BuildReport,
        "blender-scene-task": BlenderSceneTask,
    }
    for name, model in models.items():
        target = output / f"{name}.schema.json"
        payload = json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + chr(10)
        target.write_text(payload, encoding="utf-8")
        typer.echo(f"wrote {target}")


@app.command("scene-validate")
def scene_validate_command(
    task: Path = typer.Option(..., "--task"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Validate a Blender task IR v2 file before execution."""
    from .blender_scene import SceneContractError, task_summary, validate_scene_task

    if not task.is_file():
        typer.echo(f"task not found: {task}", err=True)
        raise typer.Exit(1)
    try:
        data = json.loads(task.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.echo(f"invalid JSON in {task}: {exc}", err=True)
        raise typer.Exit(1)
    try:
        validated = validate_scene_task(data, workspace.resolve())
    except SceneContractError as exc:
        typer.echo(f"{task} does not match the Blender scene contract:", err=True)
        for message in exc.messages:
            typer.echo(f"  - {message}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(task_summary(validated), ensure_ascii=False, indent=2))


@app.command("scene-schema")
def scene_schema_command(
    output: Path = typer.Option(
        Path("shared/schemas/blender-scene-task.schema.json"), "--output"
    ),
) -> None:
    """Export the Blender task IR v2 JSON Schema."""
    from .blender_scene import BlenderSceneTask

    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(BlenderSceneTask.model_json_schema(), ensure_ascii=False, indent=2)
    output.write_text(payload + chr(10), encoding="utf-8")
    typer.echo(f"wrote {output}")


@app.command("scene-run")
def scene_run_command(
    task: Path = typer.Option(..., "--task"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    verify: bool = typer.Option(True, "--verify/--no-verify"),
) -> None:
    """Validate, execute, and verify a Blender task IR v2 file."""
    from .blender_runner import SceneRunError, run_scene_task
    from .blender_scene import SceneContractError

    try:
        result = run_scene_task(workspace.resolve(), task, verify=verify)
    except (SceneContractError, SceneRunError) as exc:
        messages = getattr(exc, "messages", [str(exc)])
        for message in messages:
            typer.echo(f"  - {message}", err=True)
        raise typer.Exit(1)
    for check in result.checks:
        typer.echo(f"[{check.id}] {check.status}: {check.detail}")
    typer.echo(f"status: {result.status}")
    typer.echo(f"manifest: {result.manifest_path}")
    raise typer.Exit(0 if result.status == "pass" else 1)


if __name__ == "__main__":
    app()
