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
        value = tts.get("voice_ref")
        if not value:
            typer.echo("provide --voice-ref or config tts.voice_ref", err=True)
            raise typer.Exit(2)
        voice_ref = Path(value)
    if prompt_text is None:
        if prompt_text_file is not None:
            prompt_text = prompt_text_file.read_text(encoding="utf-8").strip()
        else:
            prompt_text = str(tts.get("prompt_text") or "").strip() or None
    output = output or (
        workspace / "build" / lesson / "narration" / "segments" / f"{segment_id}.wav"
    )
    meta_path = output.with_suffix(".meta.json")
    key = segment_cache_key(text, voice_ref, prompt_text or "")
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


if __name__ == "__main__":
    app()
