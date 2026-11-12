from __future__ import annotations

import json

import typer

from pathlib import Path

from course_control.content.paths import ContractError, LessonPaths
from course_control.content.validators import validate

from . import app
from course_control.cli._common import _paths, _lesson_path


@app.command("direction-validate")
def direction_validate_command(spec: Path = typer.Option(..., "--spec")) -> None:
    """Validate an AnimationDirection shot list before writing renderer code."""
    from course_control.direction.animation_direction import AnimationDirection
    from course_control.voice.audio_plan import AudioPlan
    from course_control.direction.narrative import NarrativePlan

    try:
        direction = AnimationDirection.model_validate_json(spec.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"invalid animation direction: {exc}", err=True)
        raise typer.Exit(2)
    problems = direction.problems()
    for problem in problems:
        typer.echo(problem)
    if not problems:
        typer.echo(f"direction ok: {len(direction.shots)} shots / {direction.total_seconds:g}s")
    raise typer.Exit(0 if not problems else 1)


@app.command("director-plan")
def director_plan_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    out: Path | None = typer.Option(None, "--out"),
    strict: bool = typer.Option(False, "--strict"),
) -> None:
    """Build and validate the director plan for one lesson."""
    from course_control.direction import build

    try:
        plan, paths = build(
            workspace.resolve(),
            _lesson_path(workspace, lesson_dir, lesson),
            out.resolve() if out is not None else None,
        )
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    typer.echo(f"status: {plan.status}")
    typer.echo(
        f"shots: {plan.summary.shots} ({plan.summary.ready_shots} ready, "
        f"{plan.summary.planned_shots} planned) / chapters: {plan.summary.chapters}"
    )
    typer.echo(
        f"narration: {plan.summary.narration_segments} segments / "
        f"duration: {plan.duration.planned_seconds:g}s of {plan.duration.target_seconds:g}s"
    )
    typer.echo(f"errors: {plan.summary.errors}, warnings: {plan.summary.warnings}")
    for check in plan.checks:
        if check.level == "info":
            continue
        target = check.shot_id or check.chapter_id or ""
        typer.echo(f"  [{check.level}] {check.rule} {target}: {check.message}".rstrip())
    for name, path in paths.items():
        typer.echo(f"{name}: {path}")
    failed = plan.status == "blocked" or (strict and plan.summary.warnings > 0)
    raise typer.Exit(1 if failed else 0)


@app.command("director-validate")
def director_validate_command(
    plan: Path = typer.Option(..., "--plan"),
) -> None:
    """Re-run the structural gates on an existing director_plan.json."""
    from course_control.direction import validate_file

    if not plan.is_file():
        typer.echo(f"plan not found: {plan}", err=True)
        raise typer.Exit(2)
    try:
        parsed = validate_file(plan)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"invalid director plan: {exc}", err=True)
        raise typer.Exit(2)
    for check in parsed.checks:
        target = check.shot_id or check.chapter_id or ""
        typer.echo(f"[{check.level}] {check.rule} {target}: {check.message}".rstrip())
    if not parsed.checks:
        typer.echo("no issues")
    typer.echo(f"status: {parsed.status}")
    raise typer.Exit(1 if parsed.summary.errors else 0)


@app.command("beats-validate")
def beats_validate_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    sheet: Path | None = typer.Option(None, "--sheet"),
) -> None:
    """Validate the director beat sheet against the measured narration."""
    from course_control.rendering import palette_gate
    from course_control.direction.beats import load_segments, load_sheet, validate_sheet_report

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    sheet_path = sheet or (paths.lesson_dir / "authoring" / "beats.yaml")
    if not sheet_path.is_file():
        typer.echo(f"missing beat sheet: {sheet_path}", err=True)
        raise typer.Exit(1)
    meta = paths.build_root / "narration" / "narration.meta.json"
    if not meta.is_file():
        typer.echo(f"missing narration meta: {meta}", err=True)
        raise typer.Exit(1)

    beat_sheet = load_sheet(sheet_path)
    segments = load_segments(meta)
    try:
        palette = palette_gate.report(workspace.resolve(), beat_sheet.palette)
        palette_ok = palette_gate.ok(palette)
        state = "ok" if palette_ok else "FAILS contrast gates"
        typer.echo(f"palette: {beat_sheet.palette} ({palette['label']}) {state}")
        if not palette_ok:
            typer.echo(f"  {palette_gate.describe(palette)}", err=True)
    except Exception as exc:  # noqa: BLE001
        palette_ok = False
        typer.echo(f"palette: {beat_sheet.palette} unreadable: {exc}", err=True)

    report = validate_sheet_report(beat_sheet, segments, palette_ok=palette_ok)
    for issue in report["errors"]:
        typer.echo(f"  [error] {issue}")
    for issue in report["warnings"]:
        typer.echo(f"  [warning] {issue}")
    typer.echo(
        f"shots: {len(beat_sheet.shots)}; errors: {len(report['errors'])}; "
        f"warnings: {len(report['warnings'])}; sheet: {sheet_path}"
    )
    raise typer.Exit(0 if not report["errors"] else 1)


@app.command("animation-score")
def animation_score_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    sheet: Path | None = typer.Option(None, "--sheet"),
    profile: str | None = typer.Option(None, "--profile"),
) -> None:
    """Report motion metrics. This is a metric tool, not a release gate."""
    from course_control.rendering import palette_gate
    from course_control.direction.animation_score import score
    from course_control.direction.beats import load_segments, load_sheet
    from course_control.rendering.grammar import try_load_registry

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    sheet_path = sheet or (paths.lesson_dir / "authoring" / "beats.yaml")
    meta = paths.build_root / "narration" / "narration.meta.json"
    if not sheet_path.is_file() or not meta.is_file():
        typer.echo(f"missing beat sheet or narration meta: {sheet_path} / {meta}", err=True)
        raise typer.Exit(1)

    beat_sheet = load_sheet(sheet_path)
    segments = load_segments(meta)
    try:
        palette_ok = palette_gate.ok(palette_gate.report(workspace.resolve(), beat_sheet.palette))
    except Exception:  # noqa: BLE001
        palette_ok = False

    media_qc = None
    media_path = paths.build_root / "quality" / "media-qc.json"
    if media_path.is_file():
        media_qc = json.loads(media_path.read_text(encoding="utf-8"))
    build_verdict = None
    build_path = paths.build_root / "final" / "build-report.json"
    if build_path.is_file():
        build_verdict = json.loads(build_path.read_text(encoding="utf-8")).get("verdict")

    result = score(
        beat_sheet,
        segments,
        media_qc=media_qc,
        build_verdict=build_verdict,
        palette_ok=palette_ok,
        registry=try_load_registry(workspace.resolve()),
        profile=profile,
    )
    typer.echo(f"score: {result['score']}/100  verdict: {result['verdict']}")
    typer.echo(f"release_gate: {result.get('release_gate', 'legacy')} (metric only)")
    for name, value in result["components"].items():
        typer.echo(f"  {name}: {value}")
    typer.echo("metrics: " + json.dumps(result["metrics"], ensure_ascii=False))
    for issue in result["issues"]:
        typer.echo(f"  [issue] {issue}")
    typer.echo("use `course-control quality-gate` for the release decision")
    raise typer.Exit(0)


@app.command("narrative-validate")
def narrative_validate_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Validate the Director narrative plan against the content methodology."""
    from course_control.direction.narrative import validate_lesson

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report, target = validate_lesson(workspace.resolve(), paths)
    typer.echo(f"status: {report['status']} (form={report['form']})")
    for issue in report["issues"]:
        typer.echo(f"  [{issue['rule']}] {issue['level']}: {issue['message']}")
    typer.echo(f"report: {target}")
    raise typer.Exit(1 if report["status"] == "fail" else 0)


@app.command("teaching-qa")
def teaching_qa_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Run structural teaching checks; never claims learner understanding."""
    from course_control.direction.teaching_qa import run_teaching_qa

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report, target = run_teaching_qa(workspace.resolve(), paths)
    typer.echo(f"status: {report['status']} (structural: {report['structural_status']})")
    for check in report["checks"]:
        typer.echo(f"  [{check['id']}] {check['status']}: {check['detail']}")
    typer.echo("learner_evidence: missing")
    typer.echo(f"report: {target}")
    raise typer.Exit(1 if report["structural_status"] == "BLOCKED" else 0)


@app.command("grammar-list")
def grammar_list_command(
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """List the visual grammars available to production contracts."""
    from course_control.rendering.grammar import try_load_registry

    registry = try_load_registry(workspace.resolve())
    if as_json:
        typer.echo(json.dumps(registry.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return
    for name, spec in registry.grammars.items():
        window = spec.shot_seconds
        typer.echo(
            f"{name:14s} {spec.label}  shots {window.min:g}-{window.max:g}s  "
            f"long_lived>={spec.constraints.long_lived_ratio_min:g}"
        )


@app.command("plan-audit")
def plan_audit_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Report the count of every production representation and the authority."""
    from course_control.direction.plan_audit import audit_plan

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report = audit_plan(paths)
    if as_json:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        typer.echo(f"mode: {report['mode']}  authority: {report['authority']}")
        for key, value in report["counts"].items():
            typer.echo(f"  {key}: {value}")
        if report["mismatches"]:
            typer.echo("mismatches:")
            for key, value in report["mismatches"].items():
                typer.echo(f"  {key}={value} (expected {report['expected']})")
        else:
            typer.echo("mismatches: none")
    raise typer.Exit(0)


@app.command("production-validate")
def production_validate_command(
    plan: Path | None = typer.Option(None, "--plan"),
    lesson: str | None = typer.Option(None, "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Validate a shot-driven production contract before any render."""
    from course_control.rendering.grammar import try_load_registry
    from course_control.content.paths import ContractError, LessonPaths
    from course_control.content.production import load_production, validate_plan
    from course_control.platform.workspace_layout import engine_roots

    workspace = workspace.resolve()
    registry = try_load_registry(workspace)
    if plan is None:
        if not lesson:
            typer.echo("give --plan or --lesson", err=True)
            raise typer.Exit(2)
        try:
            paths = LessonPaths.load(workspace, _lesson_path(workspace, lesson_dir, lesson))
        except ContractError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
        if paths.production is None or paths.production_source is None:
            typer.echo("lesson has no production contract", err=True)
            raise typer.Exit(1)
        production = paths.production
        source = paths.production_source
    else:
        source = plan if plan.is_absolute() else (workspace / plan).resolve()
        try:
            production = load_production(source)
        except (OSError, ValueError) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
    issues = validate_plan(
        production,
        workspace=workspace,
        engine_roots=lambda engine: engine_roots(workspace, engine),
        registry=registry,
    )
    payload = {
        "lesson": production.lesson,
        "sequences": len(production.sequences),
        "shots": len(production.shots),
        "total_seconds": round(production.total_seconds, 3),
        "issues": issues,
    }
    if as_json:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        typer.echo(
            f"lesson: {payload['lesson']}  sequences: {payload['sequences']}  "
            f"shots: {payload['shots']}  total: {payload['total_seconds']}s"
        )
        for issue in issues:
            typer.echo(f"  [fail] {issue}")
        typer.echo("verdict: " + ("pass" if not issues else "fail"))
    raise typer.Exit(0 if not issues else 1)


@app.command("quality-gate")
def quality_gate_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    profile: str | None = typer.Option(None, "--profile"),
    waive: list[str] = typer.Option([], "--waive", help="shot:check prefix to waive"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Evaluate hard constraints, grammar constraints and metrics separately."""
    from course_control.content.paths import ContractError, LessonPaths
    from course_control.quality.quality_gates import evaluate

    workspace = workspace.resolve()
    try:
        paths = LessonPaths.load(workspace, _lesson_path(workspace, lesson_dir, lesson))
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report = evaluate(paths, profile=profile, waivers=waive)
    if as_json:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        typer.echo(f"verification: {report.get('verification_status', 'pass')}")
        typer.echo(f"hard: {'fail' if report['hard_failures'] else 'pass'}")
        for item in report["hard_failures"]:
            typer.echo(f"  [hard] {item.get('source')}:{item.get('id')} {item.get('detail') or ''}")
        typer.echo(f"incomplete: {len(report.get('incomplete_failures') or [])}")
        for item in report.get("incomplete_failures") or []:
            typer.echo(f"  [incomplete] {item.get('source')}:{item.get('id')} {item.get('detail') or ''}")
        typer.echo(f"grammar: {'fail' if report['grammar_failures'] else 'pass'}")
        for issue in report["grammar_failures"]:
            typer.echo(f"  [grammar] {issue}")
        for issue in report.get("grammar_warnings") or []:
            typer.echo(f"  [warning] {issue}")
        metrics = report.get("metrics") or {}
        if metrics:
            typer.echo(f"metrics: score {metrics.get('score')} ({metrics.get('release_gate')})")
            typer.echo("  " + json.dumps(metrics.get("metrics") or {}, ensure_ascii=False))
        typer.echo("human review: required")
        typer.echo("releasable: " + ("yes, after human sign-off" if report["releasable"] else "no"))
    raise typer.Exit(0 if report["releasable"] else 1)


@app.command("reference-compare")
def reference_compare_command(
    lesson: str = typer.Option(..., "--lesson"),
    reference: str = typer.Option(..., "--reference"),
    lesson_dir: Path | None = typer.Option(None, "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Compare measured motion metrics with a named reference record."""
    from course_control.direction.animation_score import score
    from course_control.direction.beats import load_segments, load_sheet
    from course_control.rendering.grammar import try_load_registry
    from course_control.content.paths import ContractError, LessonPaths
    from course_control.quality.reference import compare, load_reference, resolve_reference

    workspace = workspace.resolve()
    try:
        paths = LessonPaths.load(workspace, _lesson_path(workspace, lesson_dir, lesson))
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    sheet = paths.lesson_dir / "authoring" / "beats.yaml"
    meta = paths.build_root / "narration" / "narration.meta.json"
    if not sheet.is_file() or not meta.is_file():
        typer.echo("reference-compare needs authoring/beats.yaml and narration meta", err=True)
        raise typer.Exit(1)
    media = paths.build_root / "quality" / "media-qc.json"
    result = score(
        load_sheet(sheet),
        load_segments(meta),
        media_qc=json.loads(media.read_text(encoding="utf-8")) if media.is_file() else None,
        registry=try_load_registry(workspace),
    )
    try:
        record = load_reference(resolve_reference(workspace, reference))
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report = compare(result["metrics"], record)
    target = paths.build_root / "quality" / "reference-compare.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if as_json:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
        return
    typer.echo(f"reference: {report['reference']}  overall: {report['overall']}")
    for name, item in report["dimensions"].items():
        typer.echo(f"  {name:18s} {item['status']:14s} {item['detail']}")
    for item in report["required_improvements"]:
        typer.echo(f"  [required] {item}")
    typer.echo("human review: required")
    typer.echo(f"report: {target}")


@app.command("shot-taxonomy")
def shot_taxonomy_command(
    path: Path = typer.Option(
        Path("shared/grammars/shot-taxonomy.yaml"), "--taxonomy"
    ),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Validate the shot capability taxonomy and its sample coverage."""
    from course_control.direction.shot_taxonomy import coverage, load_taxonomy, validate

    try:
        data = load_taxonomy(path.resolve())
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    problems = validate(data)
    cover = coverage(data, workspace.resolve())
    report = {"problems": problems, "coverage": cover}
    if as_json:
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for name, spec in (data.get("types") or {}).items():
            typer.echo(f"  {name:16s} {spec.get('status')}  {spec.get('sample') or '-'}")
        typer.echo("verified samples: " + (", ".join(cover["verified"]) or "none"))
        typer.echo("unverified: " + (", ".join(cover["unverified"]) or "none"))
        for problem in problems:
            typer.echo(f"  [problem] {problem}", err=True)
    raise typer.Exit(1 if problems else 0)
