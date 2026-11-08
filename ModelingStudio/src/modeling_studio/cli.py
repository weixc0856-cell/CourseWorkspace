from __future__ import annotations

import json
from pathlib import Path

import typer

from .blender_runner import BuildError, build_model
from .config import ConfigError, PROJECT_ROOT, WorkflowConfig, load_config
from .contracts import ModelPlan, Revision, ValidationReport, VisualAnalysis
from .image_analyzer import analyze_image
from .job import Job, create_job, load_job, read_json, stage_done
from .model_planner import plan_model
from .reviser import revise as revise_job
from .script_guard import ScriptRejected, guard_script
from .script_generator import generate_script
from .server import ServerBusy, ServerStartError, probe
from .validator import validate_job

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _config() -> WorkflowConfig:
    try:
        return load_config()
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)


def _job(config: WorkflowConfig, job_id: str) -> Job:
    try:
        return load_job(config, job_id)
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)


def _print_validation(report: ValidationReport) -> None:
    for check in report.checks:
        typer.echo(f"[{check.id}] {check.status}: {check.detail}")
    typer.echo(f"status: {report.status}")


def _run_stage(action):
    try:
        return action()
    except (ServerBusy, ServerStartError, BuildError, ScriptRejected, RuntimeError, FileNotFoundError) as exc:
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)


@app.command()
def audit() -> None:
    """Show config, model paths, and local server status."""
    config = _config()
    status = probe(config)
    typer.echo(f"base_url: {config.llm.base_url}")
    remote = config.remote
    key_present = bool(remote.runtime().resolved_key())
    typer.echo(
        f"remote: {remote.provider} enabled={remote.enabled} "
        f"model={remote.model} key={'set' if key_present else 'missing'} "
        f"vision={remote.supports_vision} ({remote.vision_model or 'none'})"
    )
    typer.echo(f"healthy: {status['healthy']}  port_in_use: {status['port_in_use']}")
    typer.echo(f"models_on_server: {status['models']}")
    typer.echo(f"lock: {status.get('lock')}")
    for key, model in config.models.items():
        try:
            args = config.server_args(key)
            detail = f"ok (ctx {model.context})"
        except ConfigError as exc:
            args = []
            detail = f"missing: {exc}"
        typer.echo(f"{key}: {model.alias} -> {detail}")
    typer.echo(f"jobs: {config.jobs_dir}")
    typer.echo(f"task records: {config.runtime.task_root_resolved}")
    typer.echo(f"blender: {config.blender.executable}")


@app.command("schemas")
def schemas(
    output: Path = typer.Option(PROJECT_ROOT / "schemas", "--output"),
) -> None:
    """Export JSON Schemas for the three stage contracts."""
    output.mkdir(parents=True, exist_ok=True)
    models = {
        "visual_analysis": VisualAnalysis,
        "model_plan": ModelPlan,
        "validation": ValidationReport,
        "revision": Revision,
    }
    for name, model in models.items():
        target = output / f"{name}.schema.json"
        payload = json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2)
        target.write_text(payload + "\n", encoding="utf-8")
        typer.echo(f"wrote {target}")


@app.command("guard")
def guard(
    script: Path = typer.Option(..., "--script"),
) -> None:
    """Run the static guard against a generated script."""
    if not script.is_file():
        typer.echo(f"script not found: {script}", err=True)
        raise typer.Exit(1)
    try:
        guard_script(script.read_text(encoding="utf-8"))
    except ScriptRejected as exc:
        typer.echo(f"rejected: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo("accepted")


@app.command("run")
def run_pipeline(
    image: Path = typer.Option(..., "--image"),
    job_id: str | None = typer.Option(None, "--job-id"),
    notes: str | None = typer.Option(None, "--notes"),
    revise_result: bool = typer.Option(False, "--revise"),
    resume: bool = typer.Option(False, "--resume"),
) -> None:
    """Run image analysis, planning, script generation, Blender build, and validation."""
    config = _config()
    try:
        job = create_job(config, image, job_id=job_id, notes=notes)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    typer.echo(f"job: {job.root}")

    def done(stage: str, artifact: Path) -> bool:
        return stage_done(job, stage, artifact, resume)

    try:
        if done("analyze", job.visual_analysis):
            typer.echo("analyze: skipped (resume)")
        else:
            analysis = analyze_image(config, job)
            typer.echo(f"analyze: {analysis.object} ({len(analysis.parts)} parts)")

        if done("plan", job.model_plan):
            typer.echo("plan: skipped (resume)")
        else:
            plan = plan_model(config, job)
            typer.echo(f"plan: {plan.object_name} ({len(plan.parts)} parts)")

        if done("generate", job.script):
            typer.echo("generate: skipped (resume)")
        else:
            code = generate_script(config, job)
            typer.echo(f"generate: {code.count(chr(10)) + 1} lines -> {job.script}")

        if done("build", job.scene_dir / "preview.png"):
            typer.echo("build: skipped (resume)")
        else:
            outputs = build_model(config, job)
            typer.echo(f"build: {outputs['blend']}")

        if done("validate", job.validation):
            typer.echo("validate: rerun (cheap, refreshes validation.json)")
        report = validate_job(config, job)
        _print_validation(report)
        if revise_result and report.status == "pass":
            try:
                revision = revise_job(config, job)
                typer.echo(f"revision: {len(revision.differences)} differences")
            except RuntimeError as exc:
                typer.echo(f"revision failed (model build is still valid): {exc}", err=True)
    except (ServerBusy, ServerStartError, BuildError, ScriptRejected, RuntimeError, FileNotFoundError) as exc:
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
    raise typer.Exit(0 if report.status == "pass" else 1)


@app.command("analyze")
def analyze_command(job_id: str = typer.Option(..., "--job")) -> None:
    """Stage 1: image analysis."""
    config = _config()
    analysis = _run_stage(lambda: analyze_image(config, _job(config, job_id)))
    typer.echo(json.dumps(analysis.model_dump(), ensure_ascii=False, indent=2))


@app.command("plan")
def plan_command(job_id: str = typer.Option(..., "--job")) -> None:
    """Stage 2: modeling plan."""
    config = _config()
    plan = _run_stage(lambda: plan_model(config, _job(config, job_id)))
    typer.echo(json.dumps(plan.model_dump(), ensure_ascii=False, indent=2))


@app.command("generate")
def generate_command(job_id: str = typer.Option(..., "--job")) -> None:
    """Stage 3: generate build_model.py."""
    config = _config()
    job = _job(config, job_id)
    code = _run_stage(lambda: generate_script(config, job))
    typer.echo(f"wrote {job.script} ({code.count(chr(10)) + 1} lines)")


@app.command("build")
def build_command(
    job_id: str = typer.Option(..., "--job"),
    revise_result: bool = typer.Option(False, "--revise"),
) -> None:
    """Stage 4+5: execute in Blender and validate."""
    config = _config()
    job = _job(config, job_id)
    try:
        outputs = build_model(config, job)
        typer.echo(f"build: {outputs['blend']}")
        report = validate_job(config, job)
        _print_validation(report)
        if revise_result and report.status == "pass":
            try:
                revision = revise_job(config, job)
                typer.echo(f"revision: {len(revision.differences)} differences")
            except RuntimeError as exc:
                typer.echo(f"revision failed (model build is still valid): {exc}", err=True)
    except (BuildError, ScriptRejected, RuntimeError) as exc:
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
    raise typer.Exit(0 if report.status == "pass" else 1)


@app.command("revise")
def revise_command(job_id: str = typer.Option(..., "--job")) -> None:
    """Stage 6: compare the original image with the rendered preview."""
    config = _config()
    revision = _run_stage(lambda: revise_job(config, _job(config, job_id)))
    typer.echo(json.dumps(revision.model_dump(), ensure_ascii=False, indent=2))


@app.command("status")
def status_command(job_id: str = typer.Option(..., "--job")) -> None:
    """Show job metadata, task records, and produced files."""
    config = _config()
    job = _job(config, job_id)
    if job.metadata.is_file():
        typer.echo(json.dumps(read_json(job.metadata), ensure_ascii=False, indent=2))
    if job.tasks_dir.is_dir():
        typer.echo("tasks:")
        for path in sorted(job.tasks_dir.glob("*.json")):
            typer.echo(f"  {path.name}: {json.loads(path.read_text(encoding='utf-8')).get('status')}")
    for path in (
        job.image,
        job.visual_analysis,
        job.model_plan,
        job.script,
        job.scene_dir / "model.blend",
        job.scene_dir / "model.glb",
        job.scene_dir / "preview.png",
        job.validation,
        job.revision,
    ):
        typer.echo(f"{'ok ' if path.is_file() else '-- '} {path}")


if __name__ == "__main__":
    app()
