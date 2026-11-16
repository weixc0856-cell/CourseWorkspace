from __future__ import annotations

import json

import typer

from pathlib import Path

from course_control.content.paths import ContractError
from course_control.content.validators import validate
from course_control.quality.verify import verify

from . import app
from course_control.cli._common import _paths


@app.command("scene-validate")
def scene_validate_command(
    task: Path = typer.Option(..., "--task"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Validate a Blender task IR v2 file before execution."""
    from course_control.rendering.blender_scene import SceneContractError, task_summary, validate_scene_task

    if not task.is_file():
        typer.echo(f"task not found: {task}", err=True)
        raise typer.Exit(1)
    try:
        data = json.loads(task.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        typer.echo(f"invalid JSON in {task}: {exc}", err=True)
        raise typer.Exit(1)
    from course_control.rendering.scene_presets import expand_task

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
    from course_control.rendering.blender_scene import BlenderSceneTask

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
    from course_control.rendering.blender_runner import SceneRunError, run_scene_task
    from course_control.rendering.blender_scene import SceneContractError

    try:
        task_data = json.loads(task.read_text(encoding="utf-8"))
        task_lesson = str(task_data.get("lesson") or "").strip()
    except (OSError, json.JSONDecodeError):
        task_lesson = ""
    if task_lesson:
        from course_control.authoring.pipeline import assert_storyboard_signed
        from course_control.content.paths import ContractError, LessonPaths
        from course_control.platform.workspace_layout import lessons_root

        lesson_path = lessons_root(workspace.resolve()) / task_lesson
        if not (lesson_path / "lesson.yaml").is_file():
            typer.echo(
                f"blocked: task declares lesson {task_lesson} but {lesson_path / 'lesson.yaml'} is missing",
                err=True,
            )
            raise typer.Exit(3)
        try:
            sign_paths = LessonPaths.load(workspace.resolve(), lesson_path)
            assert_storyboard_signed(sign_paths.lesson_dir, sign_paths.storyboard_source)
        except Exception as exc:  # noqa: BLE001 - the gate is user-facing
            typer.echo(f"blocked: {exc}", err=True)
            raise typer.Exit(3)

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
    from course_control.rendering.blender_task import BlenderTaskError, load_blender_task

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
    from course_control.rendering.simulation import load_spec

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
    from course_control.rendering.simulation import load_spec, run_simulation, write_data

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
    from course_control.rendering.layout import TEMPLATES

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
    from course_control.rendering.layout import get_template, ok, validate_content, validate_template

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
    from course_control.direction.animation_direction import AnimationDirection
    from course_control.voice.audio_plan import AudioPlan
    from course_control.direction.narrative import NarrativePlan
    from course_control.rendering.formulas import FormulaSpec, load_spec, source_problems

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
    from course_control.rendering.formulas import load_spec, render_formula

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
    from course_control.rendering.formula_video_qc import check_formula_video, load_bbox
    from course_control.rendering.formulas import load_spec

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
    from course_control.rendering.formulas import audit_formula, load_spec

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
    from course_control.rendering.branding import build_plan, write_plan

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
    from course_control.rendering.branding import (
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


@app.command("asset-scene-validate")
def asset_scene_validate_command(
    spec: Path = typer.Option(..., "--spec", help="environment or shot JSON spec"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    library: Path | None = typer.Option(None, "--library"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Validate an asset-based environment/shot spec against the asset library."""
    from course_control.scene_spec import load_spec, validate_spec

    if not spec.is_file():
        typer.echo(f"spec not found: {spec}", err=True)
        raise typer.Exit(2)
    issues = validate_spec(spec, workspace, library)
    try:
        parsed = load_spec(spec)
        summary = {"kind": parsed.kind, "id": parsed.id, "path": str(spec)}
    except Exception:  # noqa: BLE001 - issues already explain the failure
        summary = {"path": str(spec)}
    if as_json:
        typer.echo(json.dumps(
            {"ok": not any(item.level == "error" for item in issues),
             **summary,
             "issues": [item.as_dict() for item in issues]},
            ensure_ascii=False, indent=2,
        ))
    else:
        for item in issues:
            typer.echo(f"[{item.level}] {item.message}")
        if not issues:
            typer.echo(f"ok: {summary.get('kind')} / {summary.get('id')} / {spec}")
    raise typer.Exit(1 if any(item.level == "error" for item in issues) else 0)


@app.command("asset-scene-schema")
def asset_scene_schema_command(
    output: Path = typer.Option(Path("shared/scene-specs"), "--output"),
) -> None:
    """Export JSON Schemas for environments, shots, cameras, terrain and render."""
    from course_control.scene_spec.models import CameraSpec, EnvironmentSpec, RenderSpec, ShotSpec, TerrainSpec

    output.mkdir(parents=True, exist_ok=True)
    models = {
        "environment": EnvironmentSpec,
        "shot": ShotSpec,
        "camera": CameraSpec,
        "terrain": TerrainSpec,
        "render": RenderSpec,
    }
    for name, model in models.items():
        payload = json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2)
        (output / f"{name}.schema.json").write_text(payload + chr(10), encoding="utf-8")
        typer.echo(f"wrote {output / (name + '.schema.json')}")
    combined = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Asset scene spec",
        "oneOf": [
            {"$ref": "environment.schema.json"},
            {"$ref": "shot.schema.json"},
        ],
    }
    (output / "scene-spec.schema.json").write_text(
        json.dumps(combined, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8"
    )
    typer.echo(f"wrote {output / 'scene-spec.schema.json'}")
