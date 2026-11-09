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
    storyboard: Path | None = typer.Option(None, "--storyboard"),
    shots: list[str] | None = typer.Option(None, "--shots"),
    build_root: Path | None = typer.Option(None, "--build-root"),
) -> None:
    """Run the applicable stages for a lesson."""
    try:
        report, report_path = run_build(
            workspace.resolve(),
            (lesson_dir / lesson).resolve(),
            BuildOptions(
                skip_render=skip_render,
                skip_compose=skip_compose,
                storyboard=storyboard,
                shots=shots,
                build_root=build_root,
            ),
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
    from .animation_direction import AnimationDirection
    from .audio_plan import AudioPlan
    from .narrative import NarrativePlan
    from .director.schema import DirectorPlan
    from .layout.schema import LayoutTemplate
    from .simulation import SimulationSpec
    from .producer.schema import DeliveryManifest, ProductionOrder, ProductionState
    from .formulas import FormulaSpec
    from .session import EvidenceManifest, SessionSpec

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
        "audio-plan": AudioPlan,
        "narrative-plan": NarrativePlan,
        "director-plan": DirectorPlan,
        "production-order": ProductionOrder,
        "production-state": ProductionState,
        "delivery-manifest": DeliveryManifest,
        "layout-template": LayoutTemplate,
        "simulation-spec": SimulationSpec,
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
    from .contracts_v1 import V1_MODELS

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

    from .contracts_v1 import V1_MODELS
    from .paths import format_validation_error

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


@app.command("e6-adapt")
def e6_adapt_command(
    manifest: Path = typer.Option(
        Path("build/manim-transformer/e6/manifest.json"), "--manifest"
    ),
    output: Path = typer.Option(
        Path("build/manim-transformer/e6/render.manifest.v1.json"), "--output"
    ),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    run_id: str | None = typer.Option(None, "--run-id"),
) -> None:
    """Read E6 V0 manifest and media, then write a V1 RenderManifest.

    V0 and its media are never modified.  Failed automatic checks are written
    into the manifest and make the command exit 1.
    """
    from .legacy_e6 import LegacyE6Error, adapt_e6_manifest

    if not manifest.is_file():
        typer.echo(f"manifest not found: {manifest}", err=True)
        raise typer.Exit(2)
    try:
        render, checks = adapt_e6_manifest(
            manifest, workspace=workspace, run_id=run_id
        )
    except LegacyE6Error as exc:
        typer.echo(f"E6 adapt failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render.model_dump_json(indent=2) + chr(10),
        encoding="utf-8",
    )
    typer.echo(f"wrote {output}")
    for check in checks:
        typer.echo(f"[{check.id}] {check.status}: {check.detail}")
    failed = [check for check in checks if check.status == "fail"]
    raise typer.Exit(1 if failed else 0)


@app.command("e65-adapt")
def e65_adapt_command(
    manifest: Path = typer.Option(
        Path("build/manim-multi-head/e6.5/manifest.json"), "--manifest"
    ),
    output_dir: Path | None = typer.Option(None, "--output-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    voice_ref: Path | None = typer.Option(None, "--voice-ref"),
    run_id: str | None = typer.Option(None, "--run-id"),
) -> None:
    """Generate V1 NarrationSpec/TimelineSpec/ShotSpec/RenderManifest for E6.5."""
    from .e65 import E65Error, adapt_e65

    if not manifest.is_file():
        typer.echo(f"manifest not found: {manifest}", err=True)
        raise typer.Exit(2)
    try:
        result = adapt_e65(
            manifest,
            workspace=workspace,
            voice_ref=voice_ref,
            run_id=run_id,
            output_dir=output_dir,
        )
    except E65Error as exc:
        typer.echo(f"E6.5 adapt failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    render = result["manifest"]
    for key, path in result["paths"].items():
        if isinstance(path, list):
            for item in path:
                typer.echo(f"wrote {item}")
        else:
            typer.echo(f"wrote {path}")
    for check in render.checks:
        typer.echo(f"[{check.id}] {check.status}: {check.detail}")
    failed = [check for check in render.checks if check.status == "fail"]
    raise typer.Exit(1 if failed else 0)


@app.command("timeline-v1")
def timeline_v1_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    """Write a V1 TimelineSpec from an existing build/<slug>/shots.json."""
    from .contracts import ShotsFile
    from .v1_timeline import V1TimelineError, write_timeline_contract

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    shots_path = paths.build_root / "shots.json"
    if not shots_path.is_file():
        typer.echo(f"shots.json missing: {shots_path}", err=True)
        raise typer.Exit(2)
    shots = ShotsFile.model_validate_json(shots_path.read_text(encoding="utf-8"))
    try:
        target, timeline = write_timeline_contract(shots, paths, output=output)
    except V1TimelineError as exc:
        typer.echo(f"timeline-v1 failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(
        f"wrote {target} ({timeline.total_frames} frames, "
        f"{len(timeline.video)} video entries)"
    )


@app.command("session-evidence-v1")
def session_evidence_v1_command(
    spec: Path = typer.Option(..., "--spec"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    output: Path | None = typer.Option(None, "--output"),
    run_id: str | None = typer.Option(None, "--run-id"),
) -> None:
    """Upgrade an existing session evidence.json to V1 EvidenceManifest."""
    from .session import SessionContractError, load_session_spec
    from .session_evidence_v1 import V1EvidenceError, adapt_session_evidence

    workspace = workspace.resolve()
    try:
        manifest = adapt_session_evidence(
            spec, workspace, run_id=run_id
        )
    except (V1EvidenceError, SessionContractError) as exc:
        typer.echo(f"session-evidence-v1 failed: {exc}", err=True)
        raise typer.Exit(1)
    session = load_session_spec(spec)
    target = output or (
        workspace
        / "build"
        / session.lesson
        / "code"
        / session.shot_id
        / "evidence.v1.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(manifest.model_dump_json(indent=2) + chr(10), encoding="utf-8")
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
    from .scene_presets import expand_task

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


@app.command("tts-status")
def tts_status_command(
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    port: int = typer.Option(50000, "--port"),
) -> None:
    """Show VoxCPM health, port owner and lock holder."""
    from ai_runtime.locks import FileLock

    from .narrate import health, load_local_paths, port_owner

    workspace = workspace.resolve()
    config = load_local_paths(workspace)
    base = f"http://127.0.0.1:{port}"
    payload = health(base)
    owner = port_owner(port)
    info = FileLock(workspace / "runtime" / "locks" / f"tts-{port}.lock").read()
    typer.echo(f"TTS {port}: {(payload or {}).get('status', 'down')}")
    if payload:
        typer.echo(
            f"model: {payload.get('model', 'unknown')}, "
            f"sample_rate: {payload.get('sample_rate', 'unknown')}"
        )
    if owner:
        typer.echo(f"port owner: {owner['process']} pid={owner['pid']}")
    else:
        typer.echo("port owner: none")
    if info:
        typer.echo(
            f"lock: task={info.task_id} pid={info.pid} since={info.created_at}"
        )
    else:
        typer.echo("lock: free")


@app.command("narrate")
def narrate_command(
    lesson: str = typer.Option(..., "--lesson"),
    segment_id: str = typer.Option(..., "--segment-id"),
    text: str | None = typer.Option(None, "--text"),
    text_file: Path | None = typer.Option(None, "--text-file"),
    voice_ref: Path | None = typer.Option(None, "--voice-ref"),
    prompt_text: str | None = typer.Option(None, "--prompt-text"),
    prompt_text_file: Path | None = typer.Option(None, "--prompt-text-file"),
    mode: str = typer.Option("prompt_reference", "--mode"),
    style: str | None = typer.Option(None, "--style"),
    reference_wav: Path | None = typer.Option(None, "--reference-wav"),
    text_frontend: bool = typer.Option(True, "--text-frontend/--no-text-frontend"),
    output: Path | None = typer.Option(None, "--out"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    runtime_dir: Path | None = typer.Option(None, "--runtime-dir"),
    start_service: bool = typer.Option(True, "--start-service/--no-start-service"),
    force: bool = typer.Option(False, "--force"),
    speed: float = typer.Option(1.0, "--speed"),
    wait_timeout_s: int = typer.Option(1800, "--wait-timeout-s"),
) -> None:
    """Synthesize one narration segment with VoxCPM2 (V1)."""
    from .narrate import (
        TtsError,
        TtsService,
        load_local_paths,
        segment_cache_key,
        synthesize,
    )

    workspace = workspace.resolve()
    config = load_local_paths(workspace)
    tts = config.get("tts") or {}
    ai_root = Path(config.get("ai_root") or "").resolve()
    runtime = runtime_dir or Path(tts.get("runtime_dir") or (ai_root / "VoxCPM-Runtime"))
    if text is None:
        if text_file is None:
            typer.echo("provide --text or --text-file", err=True)
            raise typer.Exit(2)
        text = text_file.read_text(encoding="utf-8")
    if voice_ref is None:
        value = tts.get("voice_ref_en") or tts.get("voice_ref")
        if not value:
            typer.echo("provide --voice-ref or config tts.voice_ref", err=True)
            raise typer.Exit(2)
        voice_ref = Path(value)
    reference_wav = reference_wav or voice_ref
    if prompt_text is None:
        if prompt_text_file is not None:
            prompt_text = prompt_text_file.read_text(encoding="utf-8").strip()
        else:
            default_prompt = (
                tts.get("prompt_text_en")
                if tts.get("voice_ref_en")
                else tts.get("prompt_text")
            )
            prompt_text = str(default_prompt or "").strip() or None
    output = output or (
        workspace / "build" / lesson / "narration" / "segments" / f"{segment_id}.wav"
    )
    meta_path = output.with_suffix(".meta.json")
    key = segment_cache_key(
        text,
        voice_ref,
        prompt_text or "",
        mode=mode,
        style=style,
        speed=speed,
        text_frontend=text_frontend,
    )
    if not force and output.is_file() and meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("cache_key") == key:
            typer.echo(f"cache hit: {output}")
            raise typer.Exit(0)

    log_path = workspace / "build" / lesson / "narration" / "tts-server.log"
    try:
        with TtsService(
            workspace,
            ai_root=ai_root,
            runtime_dir=runtime,
            log_path=log_path,
            start_service=start_service,
            wait_timeout_s=wait_timeout_s,
        ) as service:
            typer.echo(f"TTS 50000: ready ({service.mode})")
            details = synthesize(
                service.base_url,
                text,
                voice_ref,
                prompt_text,
                output,
                speed=speed,
                mode=mode,
                reference_wav=reference_wav,
                style=style,
                text_frontend=text_frontend,
            )
    except TtsError as exc:
        typer.echo(f"TTS error: {exc}", err=True)
        raise typer.Exit(1)
    meta = {
        "schema_version": 1,
        "lesson": lesson,
        "segment_id": segment_id,
        "text_sha256": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest(),
        "voice_ref": str(voice_ref),
        "voice_ref_sha256": __import__("hashlib").sha256(voice_ref.read_bytes()).hexdigest(),
        "prompt_text_sha256": __import__("hashlib").sha256(
            (prompt_text or "").encode("utf-8")
        ).hexdigest(),
        "cache_key": key,
        "cache_hit": False,
        "model": "VoxCPM2",
        "timesteps": 10,
        "speed": speed,
        "mode": mode,
        "style": style,
        "reference_wav": str(reference_wav),
        "text_frontend": text_frontend,
        "output": str(output),
        **details,
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    typer.echo(
        f"wrote {output} ({details['audio_seconds']:.3f}s audio, "
        f"{details['synth_seconds']:.1f}s synth)"
    )


@app.command("session-validate")
def session_validate_command(
    spec: Path = typer.Option(..., "--spec"),
    lesson_dir: Path = typer.Option(..., "--lesson-dir"),
) -> None:
    """Validate a session spec without executing it."""
    from .session import SessionContractError, load_session_spec

    try:
        session = load_session_spec(spec)
    except SessionContractError as exc:
        for message in exc.messages:
            typer.echo(f"  - {message}", err=True)
        raise typer.Exit(1)
    missing = [
        entry.source
        for entry in session.files
        if not (lesson_dir.resolve() / entry.source).is_file()
    ]
    if missing:
        for item in missing:
            typer.echo(f"  - session file not found: {item}", err=True)
        raise typer.Exit(1)
    typer.echo(
        json.dumps(
            {
                "lesson": session.lesson,
                "shot_id": session.shot_id,
                "session_id": session.session_id,
                "commands": len(session.commands),
                "files": len(session.files),
                "image": session.environment.image,
                "network": session.environment.network,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command("session-run")
def session_run_command(
    spec: Path = typer.Option(..., "--spec"),
    lesson_dir: Path = typer.Option(..., "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    record: bool = typer.Option(False, "--record/--no-record"),
) -> None:
    """Execute and verify a code/terminal session (E1)."""
    from .session import SessionContractError
    from .session_runner import SessionRunError, run_session

    if not spec.is_file():
        typer.echo(f"session spec not found: {spec}", err=True)
        raise typer.Exit(1)
    try:
        result, manifest, recording = run_session(
            workspace.resolve(), spec, lesson_dir, record=record
        )
    except (SessionContractError, SessionRunError) as exc:
        messages = getattr(exc, "messages", [str(exc)])
        for message in messages:
            typer.echo(f"  - {message}", err=True)
        raise typer.Exit(1)
    for command in result.commands:
        for assertion in command.assertions:
            status = "pass" if assertion.ok else "fail"
            typer.echo(f"[{command.id}/{assertion.name}] {status}: {assertion.detail}")
    lesson = json.loads(spec.read_text(encoding="utf-8")).get("lesson", "")
    validation_path = (
        workspace.resolve() / "build" / lesson / "code" / manifest.shot_id / "validation.json"
    )
    if validation_path.is_file():
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        for check in validation.get("checks", []):
            typer.echo(f"[{check['id']}] {check['status']}: {check.get('detail', '')}")
    if recording is not None:
        typer.echo(
            f"recording: {recording.path} ({recording.width}x{recording.height}, "
            f"{recording.duration_s:.3f}s)"
        )
    typer.echo(f"status: {result.status}")
    typer.echo(f"failure: {result.failure.value if result.failure else 'none'}")
    typer.echo(f"evidence: build/{lesson}/code/{manifest.shot_id}/evidence.json")
    raise typer.Exit(0 if result.status == "passed" else 1)


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


@app.command("ingest")
def ingest_command(
    lesson: str = typer.Option(..., "--lesson"),
    source: str = typer.Option(..., "--source"),
    kind: str = typer.Option("auto", "--kind"),
    source_id: str | None = typer.Option(None, "--id"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Fetch/copy one source into lessons/<slug>/authoring/sources/."""
    from .authoring.ingest import IngestError, ingest

    try:
        entry = ingest(
            workspace.resolve(),
            (lesson_dir / lesson).resolve(),
            source,
            kind=kind,
            source_id=source_id,
        )
    except IngestError as exc:
        typer.echo(f"ingest failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"source: {entry.id} ({entry.kind})")
    typer.echo(f"local: {entry.local_path}")
    typer.echo(f"sha256: {entry.sha256}")


@app.command("digest")
def digest_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
) -> None:
    """Build a deterministic source digest with stable citation refs."""
    from .authoring.digest import build_digest

    try:
        digest = build_digest((lesson_dir / lesson).resolve())
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"digest failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"sources: {len(digest.sources)}")
    typer.echo(f"sections: {len(digest.sections)}")
    typer.echo(f"digest: {digest.lesson}")


def _authoring_client(workspace: Path, start_service: bool, remote_only: bool = False):
    from .authoring.llm import AuthoringClient, AuthoringConfig

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
    from .authoring.llm import AuthoringBlocked, AuthoringError

    try:
        action()
    except AuthoringBlocked as exc:
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(3)
    except (AuthoringError, FileNotFoundError, ValueError) as exc:
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)


@app.command("brief")
def brief_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    start_service: bool = typer.Option(True, "--start-service/--no-start-service"),
    remote: bool = typer.Option(False, "--remote"),
) -> None:
    """Generate a course brief candidate from the approved source digest."""
    from .authoring.digest import load_digest
    from .authoring.pipeline import generate_brief

    def action() -> None:
        root = (lesson_dir / lesson).resolve()
        digest = load_digest(root / "authoring" / "source-digest.json")
        with _authoring_client(workspace, start_service, remote_only=remote) as client:
            brief = generate_brief(client, workspace.resolve(), root, digest)
        typer.echo(f"brief: {brief.lesson} ({len(brief.objectives)} objectives)")

    _run_authoring(action)


@app.command("outline")
def outline_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    start_service: bool = typer.Option(True, "--start-service/--no-start-service"),
    remote: bool = typer.Option(False, "--remote"),
) -> None:
    """Generate an outline candidate from the approved brief."""
    from .authoring.digest import load_digest
    from .authoring.models import Brief
    from .authoring.pipeline import generate_outline

    def action() -> None:
        root = (lesson_dir / lesson).resolve()
        digest = load_digest(root / "authoring" / "source-digest.json")
        brief = _load_authoring(root, "brief.json", Brief)
        with _authoring_client(workspace, start_service, remote_only=remote) as client:
            outline = generate_outline(client, workspace.resolve(), root, digest, brief)
        typer.echo(f"outline: {len(outline.pages)} pages")

    _run_authoring(action)


@app.command("script")
def script_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    start_service: bool = typer.Option(True, "--start-service/--no-start-service"),
    remote: bool = typer.Option(False, "--remote"),
) -> None:
    """Generate the English emotional narration script candidate."""
    from .authoring.digest import load_digest
    from .authoring.models import Outline
    from .authoring.pipeline import generate_script

    def action() -> None:
        root = (lesson_dir / lesson).resolve()
        digest = load_digest(root / "authoring" / "source-digest.json")
        outline = _load_authoring(root, "outline.json", Outline)
        with _authoring_client(workspace, start_service, remote_only=remote) as client:
            script = generate_script(client, workspace.resolve(), root, digest, outline)
        typer.echo(f"script: {len(script.pages)} pages")

    _run_authoring(action)


@app.command("content-draft")
def content_draft_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    start_service: bool = typer.Option(True, "--start-service/--no-start-service"),
    remote: bool = typer.Option(False, "--remote"),
) -> None:
    """Generate candidate slides, notes and storyboard from approved outline/script."""
    from .authoring.digest import load_digest
    from .authoring.models import NarrationScript, Outline
    from .authoring.pipeline import generate_content

    def action() -> None:
        root = (lesson_dir / lesson).resolve()
        digest = load_digest(root / "authoring" / "source-digest.json")
        outline = _load_authoring(root, "outline.json", Outline)
        script = _load_authoring(root, "narration.script.json", NarrationScript)
        with _authoring_client(workspace, start_service, remote_only=remote) as client:
            paths = generate_content(
                client, workspace.resolve(), root, digest, outline, script
            )
        for name, path in paths.items():
            typer.echo(f"{name}: {path}")

    _run_authoring(action)


@app.command("author-accept")
def author_accept_command(
    lesson: str = typer.Option(..., "--lesson"),
    kind: str = typer.Option(..., "--kind"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Human gate: promote a candidate artifact and record its sha256."""
    from .authoring.pipeline import accept_artifact, accept_content

    root = (lesson_dir / lesson).resolve()
    try:
        if kind == "content":
            written = accept_content(workspace.resolve(), root)
        else:
            written = accept_artifact(workspace.resolve(), root, kind)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"accept failed: {exc}", err=True)
        raise typer.Exit(1)
    for path in written:
        typer.echo(f"accepted: {path}")


@app.command("narration-build")
def narration_build_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    mode: str | None = typer.Option(None, "--mode"),
    start_service: bool = typer.Option(True, "--start-service/--no-start-service"),
    force: bool = typer.Option(False, "--force"),
    only_segment: str | None = typer.Option(None, "--segment-id"),
    sample_pages: int = typer.Option(0, "--sample-pages", min=0),
    dry_run: bool = typer.Option(False, "--dry-run"),
    wait_timeout_s: int = typer.Option(1800, "--wait-timeout-s"),
) -> None:
    """Synthesize the whole course narration and write measured page spans."""
    from .authoring.models import NarrationScript
    from .narration_course import (
        NarrationCourseBlocked,
        NarrationCourseError,
        dry_run as estimate,
        synthesize_course,
    )
    from .authoring.pipeline import assert_approved

    workspace = workspace.resolve()
    root = (lesson_dir / lesson).resolve()
    try:
        paths = LessonPaths.load(workspace, root)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    script_relative = (
        paths.lesson.authoring.script
        if paths.lesson.authoring and paths.lesson.authoring.script
        else "authoring/narration.script.json"
    )
    script_path = root / script_relative
    if not script_path.is_file():
        typer.echo(f"script not found: {script_path}", err=True)
        raise typer.Exit(1)
    script = NarrationScript.model_validate(
        json.loads(script_path.read_text(encoding="utf-8"))
    )
    if dry_run:
        info = estimate(script)
        for key, value in info.items():
            typer.echo(f"{key}: {value}")
        raise typer.Exit(0)
    try:
        assert_approved(root, script_relative)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"script is not approved: {exc}", err=True)
        raise typer.Exit(1)
    if mode:
        paths.lesson.narration.mode = mode
    try:
        meta = synthesize_course(
            workspace,
            paths,
            script,
            start_service=start_service,
            wait_timeout_s=wait_timeout_s,
            force=force,
            only_segment=only_segment,
            sample=sample_pages > 0,
            page_limit=sample_pages or None,
        )
    except NarrationCourseBlocked as exc:
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(3)
    except (NarrationCourseError, ContractError) as exc:
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"segments: {meta['totals']['segments']} (cache hits: {meta['totals']['cache_hits']})")
    typer.echo(f"audio: {meta['assembly']['duration_s']} s")
    if sample_pages:
        typer.echo(f"sample: {paths.build_root / 'narration' / 'sample' / 'sample.wav'}")
    else:
        typer.echo(f"meta: {paths.build_root / 'narration' / 'narration.meta.json'}")


@app.command("subtitles-build")
def subtitles_build_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    glossary: Path | None = typer.Option(None, "--glossary"),
    planned: bool = typer.Option(False, "--planned"),
    strict: bool = typer.Option(True, "--strict/--no-strict"),
    start_service: bool = typer.Option(True, "--start-service/--no-start-service"),
    remote: bool = typer.Option(False, "--remote"),
) -> None:
    """Build a bilingual subtitle draft from measured narration."""
    from .authoring.models import NarrationScript
    from .authoring.pipeline import assert_approved
    from .subtitles import SubtitleBlocked, SubtitleError, build_subtitles

    workspace = workspace.resolve()
    root = (lesson_dir / lesson).resolve()
    try:
        paths = LessonPaths.load(workspace, root)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    script_relative = (
        paths.lesson.authoring.script
        if paths.lesson.authoring and paths.lesson.authoring.script
        else "authoring/narration.script.json"
    )
    script_path = root / script_relative
    meta_path = paths.build_root / "narration" / "narration.meta.json"
    if not script_path.is_file() or (not planned and not meta_path.is_file()):
        typer.echo("approved script and narration.meta.json are required (or use --planned)", err=True)
        raise typer.Exit(1)
    script = NarrationScript.model_validate(
        json.loads(script_path.read_text(encoding="utf-8"))
    )
    meta = None if planned else json.loads(meta_path.read_text(encoding="utf-8"))
    try:
        if not planned:
            assert_approved(root, script_relative)
        with _authoring_client(workspace, start_service, remote_only=remote) as client:
            draft, srt_path = build_subtitles(
                workspace, paths, script, meta, client,
                glossary_path=glossary, strict=(strict and not planned),
            )
    except SubtitleBlocked as exc:
        typer.echo(f"blocked: {exc}", err=True)
        raise typer.Exit(3)
    except (SubtitleError, Exception) as exc:  # noqa: BLE001
        typer.echo(f"failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"cues: {len(draft.cues)}")
    if draft.counts.get("problems"):
        typer.echo(f"warnings: {draft.counts['problems']} cue policy issues (planned draft)")
    typer.echo(f"draft: {srt_path}")


@app.command("subtitles-accept")
def subtitles_accept_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Human gate: promote the bilingual draft into lessons/<slug>/subtitles.srt."""
    from .subtitles import SubtitleError, accept_subtitles

    workspace = workspace.resolve()
    root = (lesson_dir / lesson).resolve()
    try:
        paths = LessonPaths.load(workspace, root)
        target = accept_subtitles(workspace, paths)
    except (ContractError, SubtitleError, Exception) as exc:  # noqa: BLE001
        typer.echo(f"accept failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"accepted: {target}")


@app.command("burn-subs")
def burn_subs_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    encoder: str = typer.Option("auto", "--encoder"),
) -> None:
    """Burn the generated ASS subtitles onto the clean master."""
    from .adapters.burn import burn_subtitles

    workspace = workspace.resolve()
    root = (lesson_dir / lesson).resolve()
    try:
        paths = LessonPaths.load(workspace, root)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    if encoder not in ("auto", "qsv", "libx264"):
        typer.echo("--encoder must be auto, qsv or libx264", err=True)
        raise typer.Exit(2)
    outcome = burn_subtitles(paths, encoder=encoder)
    for output in outcome.outputs:
        typer.echo(f"output: {output}")
    for warning in outcome.warnings:
        typer.echo(f"warning: {warning}")
    for error in outcome.errors:
        typer.echo(f"error: {error}", err=True)
    typer.echo(f"status: {outcome.status.value}")
    raise typer.Exit(0 if outcome.status.value == "pass" else 1)


if __name__ == "__main__":
    app()


@app.command("formula-validate")
def formula_validate_command(
    spec: Path = typer.Option(..., "--spec"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Validate one FormulaSpec without rendering."""
    from .animation_direction import AnimationDirection
    from .audio_plan import AudioPlan
    from .narrative import NarrativePlan
    from .formulas import FormulaSpec, load_spec, source_problems

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
    from .formulas import load_spec, render_formula

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
    from .formula_video_qc import check_formula_video, load_bbox
    from .formulas import load_spec

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


@app.command("direction-validate")
def direction_validate_command(spec: Path = typer.Option(..., "--spec")) -> None:
    """Validate an AnimationDirection shot list before writing renderer code."""
    from .animation_direction import AnimationDirection
    from .audio_plan import AudioPlan
    from .narrative import NarrativePlan

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


@app.command("formula-audit")
def formula_audit_command(
    spec: Path = typer.Option(..., "--spec"),
    out: Path = typer.Option(..., "--out"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Run source, KaTeX compile, optional symbolic and visual checks."""
    from .formulas import audit_formula, load_spec

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


@app.command("director-plan")
def director_plan_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    out: Path | None = typer.Option(None, "--out"),
    strict: bool = typer.Option(False, "--strict"),
) -> None:
    """Build and validate the director plan for one lesson."""
    from .director import build

    try:
        plan, paths = build(
            workspace.resolve(),
            (lesson_dir / lesson).resolve(),
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
    from .director import validate_file

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


@app.command("producer-order")
def producer_order_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    force: bool = typer.Option(False, "--force"),
    approve_by: str | None = typer.Option(None, "--approve"),
    audience: str | None = typer.Option(None, "--audience"),
    language: str | None = typer.Option(None, "--language"),
    target_seconds: float | None = typer.Option(None, "--target-seconds"),
    must_cover: list[str] | None = typer.Option(None, "--must-cover"),
    must_not: list[str] | None = typer.Option(None, "--must-not"),
    allow_network: bool = typer.Option(False, "--allow-network"),
    allow_new_dependencies: bool = typer.Option(False, "--allow-new-dependencies"),
    allow_publish: bool = typer.Option(False, "--allow-publish"),
    max_wall_seconds: float | None = typer.Option(None, "--max-wall-seconds"),
    max_api_cost_usd: float | None = typer.Option(None, "--max-api-cost-usd"),
    max_local_model_calls: int | None = typer.Option(None, "--max-local-model-calls"),
) -> None:
    """Create or load the production order for one lesson."""
    from .director.inputs import load_inputs
    from .producer.order import OrderOverrides, approve, ensure_order, load_order, order_path, save_order

    try:
        inputs = load_inputs(workspace.resolve(), (lesson_dir / lesson).resolve())
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    overrides = OrderOverrides(
        audience=audience,
        language=language,
        target_seconds=target_seconds,
        must_cover=must_cover,
        must_not=must_not,
        allow_network=allow_network,
        allow_new_dependencies=allow_new_dependencies,
        allow_publish=allow_publish,
        max_wall_seconds=max_wall_seconds,
        max_api_cost_usd=max_api_cost_usd,
        max_local_model_calls=max_local_model_calls,
    )
    try:
        order, path = ensure_order(inputs, inputs.paths.build_root, overrides, force)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"cannot create order: {exc}", err=True)
        raise typer.Exit(1)
    if approve_by:
        approve(order, approve_by)
        save_order(order, path)
    typer.echo(f"order: {path}")
    typer.echo(f"id: {order.order_id} / {order.target_seconds:g}s / {order.language}")
    typer.echo(f"must cover: {len(order.must_cover)} items")
    typer.echo(f"approved by: {order.approved_by or 'pending'}")


@app.command("producer-run")
def producer_run_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    force_order: bool = typer.Option(False, "--force-order"),
    approve: str | None = typer.Option(None, "--approve"),
) -> None:
    """Run the automated portion: validate, director plan, delivery package, state."""
    from .producer.orchestrator import run

    try:
        result = run(
            workspace.resolve(),
            (lesson_dir / lesson).resolve(),
            force_order=force_order,
            approve_by=approve,
        )
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    typer.echo(f"state: {result.state.status} / delivery: {result.manifest.status}")
    typer.echo(f"director: {result.plan.status} ({result.plan.summary.shots} shots)")
    for item in result.manifest.items:
        present = sum(1 for record in item.files if record.status == "present")
        typer.echo(f"  {item.id}: {item.status} ({present}/{len(item.files)} files)")
    for entry in result.manifest.missing:
        typer.echo(f"  missing: {entry}")
    for problem in result.limits:
        typer.echo(f"  limit: {problem}")
    for name, path in result.paths.items():
        typer.echo(f"{name}: {path}")
    raise typer.Exit(1 if result.state.status == "blocked" else 0)


@app.command("producer-status")
def producer_status_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Show the production order, state and delivery status."""
    from .producer.orchestrator import status

    try:
        data = status(workspace.resolve(), (lesson_dir / lesson).resolve())
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    order, state, manifest = data["order"], data["state"], data["manifest"]
    typer.echo(f"order: {order.order_id} / approved by: {order.approved_by or 'pending'}")
    typer.echo(f"state: {state.status}")
    typer.echo(f"usage: {state.usage.wall_seconds:g}s wall / ${state.usage.api_cost_usd:g} / {state.usage.local_model_calls} calls")
    for name, value in state.stages.items():
        typer.echo(f"  {name}: {value}")
    if manifest is not None:
        typer.echo(f"delivery: {manifest.status} / missing: {len(manifest.missing)}")
        for entry in manifest.missing:
            typer.echo(f"  missing: {entry}")
    raise typer.Exit(0 if state.status != "blocked" else 1)


@app.command("producer-affected")
def producer_affected_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """List shots whose inputs changed since the last producer run."""
    from .producer.orchestrator import affected

    try:
        deltas = affected(workspace.resolve(), (lesson_dir / lesson).resolve())
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    if not deltas:
        typer.echo("no affected shots")
        raise typer.Exit(0)
    for delta in deltas:
        typer.echo(f"{delta.shot_id}: {delta.change} ({'; '.join(delta.reasons)})")
    raise typer.Exit(0)


@app.command("producer-rebuild")
def producer_rebuild_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    execute: bool = typer.Option(False, "--execute"),
    compose: bool = typer.Option(False, "--compose"),
    build_root: Path | None = typer.Option(None, "--build-root"),
) -> None:
    """Plan (and optionally run) a local rebuild of affected shots."""
    from .producer.orchestrator import execute_rebuild, plan_rebuild

    try:
        rebuild = plan_rebuild(
            workspace.resolve(),
            (lesson_dir / lesson).resolve(),
            build_root.resolve() if build_root is not None else None,
            compose=compose,
        )
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    if not rebuild.deltas:
        typer.echo("no affected shots")
        raise typer.Exit(0)
    for delta in rebuild.deltas:
        typer.echo(f"{delta.shot_id}: {delta.change} ({'; '.join(delta.reasons)})")
    typer.echo(f"authorized: {'yes' if rebuild.authorized else 'no'}")
    typer.echo("command: " + " ".join(rebuild.command))
    if not execute:
        raise typer.Exit(0)
    if not rebuild.authorized:
        typer.echo("refused: order.authorizations.allow_render is false", err=True)
        raise typer.Exit(2)
    try:
        result = execute_rebuild(
            rebuild,
            workspace.resolve(),
            (lesson_dir / lesson).resolve(),
            build_root.resolve() if build_root is not None else None,
            compose=compose,
        )
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report = result["report"]
    typer.echo(f"verdict: {report.verdict}")
    for stage in report.stages:
        if stage.name.startswith("render:"):
            typer.echo(f"  {stage.name}: {stage.status.value}")
    typer.echo(f"state refreshed: {'yes' if result['state'] is not None else 'no'}")
    raise typer.Exit(1 if result["failed"] else 0)


@app.command("layout-templates")
def layout_templates_command() -> None:
    """List the validated layout templates."""
    from .layout import TEMPLATES

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
    from .layout import get_template, ok, validate_content, validate_template

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


@app.command("simulation-validate")
def simulation_validate_command(
    spec: Path = typer.Option(..., "--spec"),
) -> None:
    """Validate a SimulationSpec JSON file."""
    from .simulation import load_spec

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
    from .simulation import load_spec, run_simulation, write_data

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


@app.command("audio-plan")
def audio_plan_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Validate the content-kind/BGM policy and write audio_plan.json."""
    from .audio_plan import write_audio_plan

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    plan, target = write_audio_plan(paths.build_root, paths.lesson)
    typer.echo(f"content_kind: {plan.content_kind}")
    typer.echo(f"bgm_allowed: {plan.bgm_allowed}")
    typer.echo(f"cues: {len(plan.cues)}")
    for warning in plan.warnings:
        typer.echo(f"warning: {warning}")
    for error in plan.errors:
        typer.echo(f"error: {error}", err=True)
    typer.echo(f"audio_plan: {target}")
    raise typer.Exit(0 if plan.status == "ready" else 2)


@app.command("audio-mix")
def audio_mix_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Mix the planned BGM bed into the finished video with ducking."""
    from .audio_mix import mix_lesson

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    result = mix_lesson(workspace.resolve(), paths)
    typer.echo(f"status: {result.status.value}")
    if result.output is not None:
        typer.echo(f"output: {result.output}")
    for warning in result.warnings:
        typer.echo(f"warning: {warning}")
    for error in result.errors:
        typer.echo(f"error: {error}", err=True)
    typer.echo(f"report: {result.report_path}")
    raise typer.Exit(0 if result.status.value in {"pass", "skipped"} else 1)


@app.command("media-qc")
def media_qc_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Run full-file audio/video/subtitle checks on the finished video."""
    from .media_qc import BLOCKED, INCOMPLETE, run_media_qc

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report, target = run_media_qc(workspace.resolve(), paths)
    typer.echo(f"status: {report['status']}")
    for check in report["checks"]:
        typer.echo(f"  [{check['id']}] {check['status']}: {check['detail']}")
    typer.echo(f"report: {target}")
    if report["status"] == BLOCKED:
        raise typer.Exit(1)
    if report["status"] == INCOMPLETE:
        raise typer.Exit(3)
    raise typer.Exit(0)


@app.command("quality-report")
def quality_report_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Aggregate the five quality dimensions from existing artifacts."""
    from .quality import BLOCKED, INCOMPLETE, build_quality_report

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report, target = build_quality_report(workspace.resolve(), paths)
    for item in report["dimensions"]:
        typer.echo(f"  [{item['id']}] {item['status']}: {item['reason']}")
    states = report["states"]
    typer.echo(f"BUILD_PASS: {states['BUILD_PASS']}")
    typer.echo(f"QUALITY_PASS: {states['QUALITY_PASS']}")
    typer.echo(f"RELEASE_APPROVED: {states['RELEASE_APPROVED']}")
    typer.echo(f"report: {target}")
    if any(item["status"] == BLOCKED for item in report["dimensions"]):
        raise typer.Exit(1)
    if any(item["status"] == INCOMPLETE for item in report["dimensions"]):
        raise typer.Exit(3)
    raise typer.Exit(0)


@app.command("narrative-validate")
def narrative_validate_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Validate the Director narrative plan against the content methodology."""
    from .narrative import validate_lesson

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


@app.command("asr-align")
def asr_align_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
    model: str = typer.Option("small.en", "--model"),
    language: str = typer.Option("en", "--language"),
    device: str = typer.Option("cpu", "--device"),
    compute_type: str = typer.Option("int8", "--compute-type"),
) -> None:
    """Transcribe narration with ASR and check subtitle/speech agreement."""
    from .alignment import BLOCKED, INCOMPLETE, run_alignment

    try:
        paths = _paths(workspace, lesson, lesson_dir)
    except ContractError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    report, target = run_alignment(
        workspace.resolve(),
        paths,
        model_size=model,
        language=language,
        device=device,
        compute_type=compute_type,
    )
    typer.echo(f"status: {report['status']}")
    typer.echo(f"cues: {report.get('cue_count', 0)}  words: {report.get('word_count', 0)}")
    typer.echo(f"mean coverage: {report.get('mean_coverage', 0)}")
    for mismatch in report.get("mismatches", [])[:8]:
        typer.echo(
            f"  cue {mismatch['index']}: coverage {mismatch['coverage']} "
            f"({mismatch['start_ms']}–{mismatch['end_ms']} ms)"
        )
    for interval in report.get("uncovered_speech", [])[:8]:
        typer.echo(
            f"  uncovered {interval['start_s']}–{interval['end_s']}s: {interval['text'][:80]}"
        )
    for error in report.get("errors", []):
        typer.echo(f"error: {error}", err=True)
    typer.echo(f"report: {target}")
    if report["status"] == BLOCKED:
        raise typer.Exit(1)
    if report["status"] == INCOMPLETE:
        raise typer.Exit(3)
    raise typer.Exit(0)


@app.command("teaching-qa")
def teaching_qa_command(
    lesson: str = typer.Option(..., "--lesson"),
    lesson_dir: Path = typer.Option(Path("lessons"), "--lesson-dir"),
    workspace: Path = typer.Option(Path.cwd(), "--workspace"),
) -> None:
    """Run structural teaching checks; never claims learner understanding."""
    from .teaching_qa import run_teaching_qa

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
