from __future__ import annotations

import json

import typer

from pathlib import Path

from ..contracts import Status
from ..paths import ContractError
from ..pipeline import BuildOptions, run_build
from ..report import check_report_payload, toolchain_versions
from ..validators import validate
from ..verify import verify
from ..workspace_layout import content_root as resolve_content_root

from . import app
from ._common import _paths, _print_issues, _lesson_path


@app.command()
def audit(workspace: Path = typer.Option(Path.cwd(), "--workspace")) -> None:
    """Print toolchain versions and workspace paths."""
    versions = toolchain_versions(workspace.resolve())
    for name, version in versions.items():
        typer.echo(f"{name}: {version}")
    typer.echo(f"workspace: {workspace.resolve()}")


def validate_lesson(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
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


@app.command("separation")
def separation_command(
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Report course files that leaked into the program workspace."""
    from ..separation import audit as separation_audit

    report = separation_audit(workspace)
    if as_json:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    elif not report["configured"]:
        typer.echo(report["note"])
    else:
        typer.echo(f"content root: {report['content_root']}  lessons: {report['lessons']}")
        for entry in report["entries"]:
            mark = "allowed" if entry["allowed"] else "PROBLEM"
            reason = f"  ({entry['reason']})" if entry["allowed"] else ""
            typer.echo(f"  [{mark}] {entry['path']}{reason}")
        if not report["entries"]:
            typer.echo("  no lesson-shaped files in the workspace")
        for item in report.get("docs_data") or []:
            typer.echo(f"  [warn] docs carries non-prose data: {item}")
    raise typer.Exit(1 if report["problems"] else 0)


@app.command("content-root")
def content_root_command(
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Print the directory that holds lessons, build, deliver and runtime."""
    typer.echo(resolve_content_root(workspace.resolve()))


# Typer exposes a command named validate-lesson by default; keep a friendly alias.
app.command("validate")(validate_lesson)


@app.command("build")
def build_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    skip_render: bool = typer.Option(False, "--skip-render"),
    skip_compose: bool = typer.Option(False, "--skip-compose"),
    storyboard: Path | None = typer.Option(None, "--storyboard"),
    storyboard_source: str | None = typer.Option(
        None, "--storyboard-source", help="storyboard or director"
    ),
    shots: list[str] | None = typer.Option(None, "--shots"),
    build_root: Path | None = typer.Option(None, "--build-root"),
    resume: bool = typer.Option(
        False,
        "--resume",
        help="reuse stages whose inputs, configuration and outputs still match",
    ),
    resume_from: str | None = typer.Option(
        None,
        "--resume-from",
        help="re-run this stage and everything after it (implies --resume)",
    ),
) -> None:
    """Run the applicable stages for a lesson."""
    if storyboard_source not in (None, "storyboard", "director"):
        typer.echo("--storyboard-source must be storyboard or director", err=True)
        raise typer.Exit(2)
    try:
        report, report_path = run_build(
            workspace.resolve(),
            _lesson_path(workspace, lesson_dir, lesson),
            BuildOptions(
                skip_render=skip_render,
                skip_compose=skip_compose,
                storyboard=storyboard,
                storyboard_source=storyboard_source,
                shots=shots,
                build_root=build_root,
                resume=resume or resume_from is not None,
                resume_from=resume_from,
            ),
        )
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    typer.echo(f"verdict: {report.verdict}")
    typer.echo(f"report: {report_path}")
    for stage in report.stages:
        typer.echo(f"  {stage.name}: {stage.status.value}")
    if report.reused_stages:
        typer.echo("  resumed: " + ", ".join(report.reused_stages))
    for failure in report.failures:
        typer.echo(f"  ! {failure}")
    raise typer.Exit(1 if report.verdict == "fail" else 0)


@app.command("verify")
def verify_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
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
    from ..contracts import ShotsFile

    shots_file = ShotsFile.model_validate(json.loads(shots_path.read_text(encoding="utf-8")))
    checks = verify(paths, shots_file)
    report_path = paths.build_root / "final" / "build-report.json"
    if report_path.is_file():
        checks.append(check_report_payload(paths, json.loads(report_path.read_text(encoding="utf-8"))))
    for check in checks:
        typer.echo(f"[{check.id}] {check.status.value}: {check.detail or check.actual or ''}")
    failed = [check for check in checks if check.status == Status.FAIL]
    raise typer.Exit(1 if failed else 0)


@app.command("schemas")
def schemas_command(
    output: Path = typer.Option(Path("shared/schemas"), "--output"),
) -> None:
    """Export JSON Schema files for all contracts."""
    from ..blender_scene import BlenderSceneTask
    from ..contracts import BuildReport, LessonConfig, ShotsFile, Storyboard
    from ..animation_direction import AnimationDirection
    from ..audio_plan import AudioPlan
    from ..beats import BeatSheet
    from ..narrative import NarrativePlan
    from ..director.schema import DirectorPlan
    from ..layout.schema import LayoutTemplate
    from ..simulation import SimulationSpec
    from ..audio.voice_bible import VoiceBible
    from ..audio.lexicon import Lexicon
    from ..producer.schema import DeliveryManifest, ProductionOrder, ProductionState
    from ..formulas import FormulaSpec
    from ..session import EvidenceManifest, SessionSpec

    output.mkdir(parents=True, exist_ok=True)
    models = {
        "lesson": LessonConfig,
        "storyboard": Storyboard,
        "shots": ShotsFile,
        "build-report": BuildReport,
        "blender-scene-task": BlenderSceneTask,
        "session": SessionSpec,
        "evidence": EvidenceManifest,
        "formula": FormulaSpec,
        "animation-direction": AnimationDirection,
        "beats": BeatSheet,
        "audio-plan": AudioPlan,
        "narrative-plan": NarrativePlan,
        "director-plan": DirectorPlan,
        "production-order": ProductionOrder,
        "production-state": ProductionState,
        "delivery-manifest": DeliveryManifest,
        "layout-template": LayoutTemplate,
        "simulation-spec": SimulationSpec,
        "voice-bible": VoiceBible,
        "lexicon": Lexicon,
    }
    for name, model in models.items():
        target = output / f"{name}.schema.json"
        payload = json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + chr(10)
        target.write_text(payload, encoding="utf-8")
        typer.echo(f"wrote {target}")


@app.command("schemas-v1")
def schemas_v1_command(
    output: Path = typer.Option(Path("shared/schemas"), "--output"),
) -> None:
    """Export JSON Schema files for normalized contracts V1."""
    from ..contracts_v1 import V1_MODELS

    output.mkdir(parents=True, exist_ok=True)
    for name, model in V1_MODELS.items():
        target = output / f"{name}.schema.json"
        payload = json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + chr(10)
        target.write_text(payload, encoding="utf-8")
        typer.echo(f"wrote {target}")


@app.command("contract-v1-validate")
def contract_v1_validate_command(
    kind: str = typer.Option(
        ...,
        "--kind",
        help=(
            "asset-ref-v1 / lesson-v1 / shot-v1 / narration-v1 / "
            "timeline-v1 / evidence-v1 / render-v1"
        ),
    ),
    file: Path = typer.Option(..., "--file"),
) -> None:
    """Validate one normalized contract V1 file and print field-level errors."""
    from pydantic import ValidationError

    from ..contracts_v1 import V1_MODELS
    from ..paths import format_validation_error

    model = V1_MODELS.get(kind)
    if model is None:
        typer.echo(f"unknown contract kind: {kind}", err=True)
        raise typer.Exit(2)
    if not file.is_file():
        typer.echo(f"file not found: {file}", err=True)
        raise typer.Exit(2)
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.echo(f"invalid JSON in {file}: {exc}", err=True)
        raise typer.Exit(2) from exc
    try:
        model.model_validate(payload)
    except ValidationError as exc:
        typer.echo(format_validation_error(exc, str(file)), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"{kind}: ok")
