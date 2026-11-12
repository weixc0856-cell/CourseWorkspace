from __future__ import annotations

import json

import typer

from pathlib import Path

from ..paths import ContractError
from ..validators import validate
from ..verify import verify

from . import app
from ._common import _paths


@app.command("scene-validate")
def scene_validate_command(
    task: Path = typer.Option(..., "--task"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Validate a Blender task IR v2 file before execution."""
    from ..blender_scene import SceneContractError, task_summary, validate_scene_task

    if not task.is_file():
        typer.echo(f"task not found: {task}", err=True)
        raise typer.Exit(1)
    try:
        data = json.loads(task.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.echo(f"invalid JSON in {task}: {exc}", err=True)
        raise typer.Exit(1)
    from ..scene_presets import expand_task

    try:
        data, _presets = expand_task(data, workspace.resolve())
    except ContractError as exc:
        typer.echo(f"{task}: {exc}", err=True)
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
    from ..blender_scene import BlenderSceneTask

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
    from ..blender_runner import SceneRunError, run_scene_task
    from ..blender_scene import SceneContractError

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


@app.command("blender-task-validate")
def blender_task_validate_command(
    task: Path = typer.Option(..., "--task"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Validate a Blender task against the v1 course or v2 scene contract."""
    from ..blender_task import BlenderTaskError, load_blender_task

    try:
        ref = load_blender_task(task, workspace.resolve())
    except BlenderTaskError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(
        f"schema_version={ref.version} lesson={ref.lesson} output={ref.output}"
    )


@app.command("simulation-validate")
def simulation_validate_command(
    spec: Path = typer.Option(..., "--spec"),
) -> None:
    """Validate a SimulationSpec JSON file."""
    from ..simulation import load_spec

    try:
        parsed = load_spec(spec)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"invalid simulation spec: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(
        f"ok: {parsed.simulation_id} / {parsed.frames} frames / "
        f"radius {parsed.grid.radius} / seed {parsed.seed}"
    )


@app.command("simulation-run")
def simulation_run_command(
    spec: Path = typer.Option(..., "--spec"),
    out: Path = typer.Option(..., "--out"),
) -> None:
    """Run a SimulationSpec and write SimulationData JSON."""
    from ..simulation import load_spec, run_simulation, write_data

    try:
        parsed = load_spec(spec)
        data = run_simulation(parsed)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"simulation failed: {exc}", err=True)
        raise typer.Exit(1)
    write_data(data, out)
    ranges = [
        (round(min(frame[k] for frame in data.fractions), 3), round(max(frame[k] for frame in data.fractions), 3))
        for k in range(3)
    ]
    typer.echo(f"cells={len(data.cells)} frames={len(data.frames_species)}")
    typer.echo(f"fractions={ranges}")
    typer.echo(f"data: {out}")


@app.command("layout-templates")
def layout_templates_command() -> None:
    """List the validated layout templates."""
    from ..layout import TEMPLATES

    for template in TEMPLATES.values():
        visual = template.region("main_visual")
        area = visual.area if visual else 0.0
        typer.echo(f"{template.id}: {template.content_type} / visual {area:.0%} / {template.name}")


@app.command("layout-validate")
def layout_validate_command(
    template: str = typer.Option(..., "--template"),
    title_chars: int = typer.Option(0, "--title-chars", min=0),
    body_chars: int = typer.Option(0, "--body-chars", min=0),
    bullets: int = typer.Option(0, "--bullets", min=0),
) -> None:
    """Validate one layout template, optionally against content sizes."""
    from ..layout import get_template, ok, validate_content, validate_template

    try:
        layout = get_template(template)
    except KeyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2)
    checks = validate_template(layout) + validate_content(
        layout, title_chars=title_chars, body_chars=body_chars, bullet_count=bullets
    )
    for check in checks:
        typer.echo(f"[{check.level}] {check.id}: {check.message}")
    if not checks:
        typer.echo("no issues")
    raise typer.Exit(0 if ok(checks) else 1)


@app.command("formula-validate")
def formula_validate_command(
    spec: Path = typer.Option(..., "--spec"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Validate one FormulaSpec without rendering."""
    from ..animation_direction import AnimationDirection
    from ..audio_plan import AudioPlan
    from ..narrative import NarrativePlan
    from ..formulas import FormulaSpec, load_spec, source_problems

    try:
        formula = load_spec(spec)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"invalid formula spec: {exc}", err=True)
        raise typer.Exit(2)
    issues = source_problems(formula)
    for issue in issues:
        typer.echo(f"[{issue.stage}/{issue.level}] {issue.message}")
    if not issues:
        typer.echo("no issues")
    raise typer.Exit(0 if not any(issue.level == "error" for issue in issues) else 1)


@app.command("formula-render")
def formula_render_command(
    spec: Path = typer.Option(..., "--spec"),
    out: Path = typer.Option(..., "--out"),
    engine: str | None = typer.Option(None, "--engine", help="katex|mathjax"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Render one FormulaSpec with KaTeX (HTML/PNG) or MathJax (SVG/PNG)."""
    from ..formulas import load_spec, render_formula

    try:
        formula = load_spec(spec)
        payload = render_formula(formula, out.resolve(), workspace.resolve(), engine=engine)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"formula render failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"png: {payload['png']}")
    typer.echo(f"size: {payload['width']}x{payload['height']}")


@app.command("formula-video-qc")
def formula_video_qc_command(
    spec: Path = typer.Option(..., "--spec"),
    video: Path = typer.Option(..., "--video"),
    timestamp: float = typer.Option(..., "--timestamp"),
    bbox: str = typer.Option(..., "--bbox", help="x,y,w,h"),
    out: Path = typer.Option(..., "--out"),
    threshold: float = typer.Option(0.45, "--threshold"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Check a formula region in the final encoded video by edge similarity."""
    from ..formula_video_qc import check_formula_video, load_bbox
    from ..formulas import load_spec

    try:
        formula = load_spec(spec)
        result = check_formula_video(
            formula,
            video.resolve(),
            timestamp,
            load_bbox(bbox),
            out.resolve(),
            workspace.resolve(),
            threshold=threshold,
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"formula video QC failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"edge similarity: {result['edge_similarity']} (threshold {threshold})")
    typer.echo(f"result: {out / 'formula.video.json'}")
    raise typer.Exit(0 if result["pass"] else 1)


@app.command("formula-audit")
def formula_audit_command(
    spec: Path = typer.Option(..., "--spec"),
    out: Path = typer.Option(..., "--out"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Run source, KaTeX compile, optional symbolic and visual checks."""
    from ..formulas import audit_formula, load_spec

    try:
        formula = load_spec(spec)
        audit = audit_formula(formula, out.resolve(), workspace.resolve())
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"formula audit failed: {exc}", err=True)
        raise typer.Exit(1)
    for issue in audit.issues:
        typer.echo(f"[{issue.stage}/{issue.level}] {issue.message}")
    if not audit.issues:
        typer.echo("no issues")
    typer.echo(f"audit: {out / 'formula.audit.json'}")
    raise typer.Exit(0 if audit.ok else 1)


@app.command("brand-plan")
def brand_plan_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Resolve the brand segments for a lesson without rendering anything."""
    from ..branding import build_plan, write_plan

    try:
        paths = _paths(workspace, lesson, lesson_dir)
        plan = build_plan(paths)
        target = write_plan(paths, plan)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    if as_json:
        typer.echo(json.dumps(plan.as_dict(), ensure_ascii=False, indent=2))
        return
    typer.echo(f"lesson: {plan.lesson_id}  content_kind: {plan.content_kind}")
    typer.echo(f"master: {plan.master or '(none yet)'}")
    for segment in plan.segments:
        typer.echo(
            f"  {segment['kind']}: {segment['preset']} / {segment['composition']} "
            f"{segment['duration_s']}s ({segment['duration_frames']} frames)"
        )
    typer.echo(f"brand total: {plan.brand_duration_s}s")
    typer.echo(f"plan: {target}")


@app.command("brand-render")
def brand_render_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    force: bool = typer.Option(False, "--force", help="Ignore the segment cache."),
    stitch: bool = typer.Option(
        False, "--stitch", help="Also concatenate around the existing viewing master."
    ),
) -> None:
    """Render the brand segments (and optionally stitch the delivery master)."""
    from ..branding import (
        build_plan,
        delivery_path,
        render_segments,
        run_branding,
        write_plan,
    )

    try:
        paths = _paths(workspace, lesson, lesson_dir)
        if stitch:
            plan, record = run_branding(paths, force=force)
            typer.echo(
                f"delivery: {delivery_path(paths)}  mode: {record['mode']}  "
                f"{record['duration_s']}s"
            )
            return
        plan = build_plan(paths)
        write_plan(paths, plan)
        for record in render_segments(paths, plan, force=force):
            typer.echo(
                f"  {record['composition']}: {record['status']} "
                f"{record['duration_s']}s"
            )
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
