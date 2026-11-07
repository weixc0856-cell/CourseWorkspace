"""E2: drive a real VS Code window and verify its terminal session."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from .printwindow import PrintWindowRecorder
from .session import (
    EnvironmentResult,
    EvidenceManifest,
    ExecutionResult,
    FailureCode,
    RecordingResult,
    SessionContractError,
    SessionSpec,
    ValidationReport,
    cache_key,
    load_session_spec,
    now,
)
from .session_runner import (
    SessionRunError,
    _assert_commands,
    _find_window,
    _focus_window,
    _hash_file,
    _probe_recording,
    _start_recording,
    _window_rect,
    _window_text,
    _unfocus_window,
)

CREATE_NEW_CONSOLE = 0x00000010


def _program_files(*parts: str) -> Path | None:
    root = os.environ.get("ProgramFiles")
    return Path(root).joinpath(*parts) if root else None


def _code_command() -> str:
    executable = shutil.which("code")
    if executable:
        return executable
    candidate = _program_files("Microsoft VS Code", "bin", "code.cmd")
    if candidate is not None and candidate.is_file():
        return str(candidate)
    raise SessionRunError("VS Code code.cmd not found; add VS Code to PATH")


def _bash_path() -> str:
    executable = shutil.which("bash")
    if executable:
        return executable
    candidate = _program_files("Git", "bin", "bash.exe")
    if candidate is not None and candidate.is_file():
        return str(candidate)
    raise SessionRunError("Git Bash not found; add Git Bash to PATH")


def _prepare(workspace: Path, lesson_dir: Path, spec: SessionSpec, session_id: str) -> tuple[Path, dict[str, str]]:
    build_root = workspace / "build" / spec.lesson / "code" / spec.shot_id
    workdir = build_root / "vscode-workspace"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    hashes: dict[str, str] = {}
    for entry in spec.files:
        source = (lesson_dir / entry.source).resolve()
        if not source.is_file():
            raise SessionRunError(f"session file not found: {source}")
        target = workdir / entry.path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        hashes[entry.path] = _hash_file(source)
    profile = build_root / "vscode-profile"
    (profile / "User").mkdir(parents=True, exist_ok=True)
    settings = {
        "window.title": f"CourseDemo-{session_id}",
        "workbench.startupEditor": "none",
        "window.restoreWindows": "none",
        "editor.cursorBlinking": "solid",
        "workbench.list.smoothScrolling": False,
        "editor.smoothScrolling": False,
        "security.workspace.trust.enabled": False,
        "telemetry.telemetryLevel": "off",
        "extensions.autoUpdate": False,
        "terminal.integrated.shellIntegration.enabled": True,
        "git.openRepositoryInParentFolders": "never",
        "workbench.secondarySideBar.defaultVisibility": "hidden",
        "chat.commandCenter.enabled": False,
    }
    (profile / "User" / "settings.json").write_text(
        json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return workdir, hashes


def _write_session(workdir: Path, spec: SessionSpec, session_id: str) -> Path:
    payload = {
        "cwd": str(workdir),
        "shellPath": _bash_path(),
        "startDelayMs": 2500,
        "commands": [
            {"id": command.id, "command": shlex.join(command.run)}
            for command in spec.commands
        ],
    }
    path = workdir / f"vscode-session-{session_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def run_vscode_session(
    workspace: Path,
    spec_path: Path,
    lesson_dir: Path,
    *,
    record: bool = False,
) -> tuple[ExecutionResult, EvidenceManifest, RecordingResult | None]:
    workspace = workspace.resolve()
    lesson_dir = lesson_dir.resolve()
    spec = load_session_spec(spec_path)
    if spec.environment.kind == "docker":
        raise SessionRunError("use session-run for docker environments")
    build_root = workspace / "build" / spec.lesson / "code" / spec.shot_id
    build_root.mkdir(parents=True, exist_ok=True)
    workdir, file_hashes = _prepare(workspace, lesson_dir, spec, spec.session_id)
    session_file = _write_session(workdir, spec, spec.session_id)
    result_file = build_root / "vscode-result.json"
    if result_file.exists():
        result_file.unlink()

    code = _code_command()
    demo = workspace / "CourseDemo"
    profile = build_root / "vscode-profile"
    extensions = build_root / "vscode-extensions"
    extensions.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["COURSE_DEMO_SESSION"] = str(session_file)
    env["COURSE_DEMO_RESULT"] = str(result_file)
    args = [
        code,
        "--new-window",
        f"--extensionDevelopmentPath={demo}",
        f"--user-data-dir={profile}",
        f"--extensions-dir={extensions}",
        "--disable-telemetry",
        "--disable-workspace-trust",
        "--skip-welcome",
        str(workdir),
    ]
    started_at = now()
    recording = None
    recording_error = None
    try:
        subprocess.Popen(args, env=env)
    except OSError as exc:
        raise SessionRunError(f"cannot launch VS Code: {exc}") from exc

    window_title = f"CourseDemo-{spec.session_id}"
    if record:
        hwnd = _find_window(window_title, timeout=20.0)
        if not hwnd:
            raise SessionRunError(f"VS Code window not found: {window_title}")
        _focus_window(hwnd, spec.record.resolution)
        video = build_root / "session.mp4"
        rect = _window_rect(hwnd)
        if rect is None:
            raise SessionRunError("cannot read VS Code window rectangle")
        print(
            f"VSCODE_WINDOW title={_window_text(hwnd)!r} rect={rect}",
            flush=True,
        )
        process = PrintWindowRecorder(
            hwnd, video, spec.record.fps, build_root / "ffmpeg.log"
        ).start()
    else:
        hwnd = 0
        process = None

    deadline = time.monotonic() + spec.environment.timeout_s + 120
    while time.monotonic() < deadline and not result_file.is_file():
        time.sleep(0.5)
    if process is not None:
        time.sleep(2.0)
        process.stop()
    if hwnd:
        _unfocus_window(hwnd)
        try:
            import ctypes

            ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
        except Exception:  # noqa: BLE001
            pass
    if record:
        recording = _probe_recording(build_root / "session.mp4", spec)
        if recording is None:
            recording_error = "recording probe failed"

    if not result_file.is_file():
        result = ExecutionResult(
            shot_id=spec.shot_id,
            session_id=spec.session_id,
            status="failed",
            failure=FailureCode.EVIDENCE_INCOMPLETE,
            environment=EnvironmentResult(image=None, network="host"),
            started_at=started_at,
            finished_at=now(),
        )
        manifest = EvidenceManifest(
            shot_id=spec.shot_id,
            session_id=spec.session_id,
            spec_sha256=_hash_file(spec_path),
            cache_key=cache_key(spec, file_hashes, None),
        )
        (build_root / "result.json").write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
        (build_root / "evidence.json").write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return result, manifest, recording

    payload = json.loads(result_file.read_text(encoding="utf-8"))
    raw = {
        "commands": [
            {
                "id": item.get("id"),
                "exit_code": item.get("exit_code"),
                "timed_out": False,
                "duration_ms": 0,
                "stdout": item.get("output", ""),
                "stderr": "",
            }
            for item in payload.get("commands", [])
        ]
    }
    commands, failure = _assert_commands(workdir, spec, raw)
    if payload.get("shell_integration") is not True and failure is None:
        failure = FailureCode.EVIDENCE_INCOMPLETE
    if failure is None and recording_error:
        failure = FailureCode.RECORDING_FAILED
    status = "passed" if failure is None else "failed"
    result = ExecutionResult(
        shot_id=spec.shot_id,
        session_id=spec.session_id,
        status=status,
        failure=failure,
        commands=commands,
        environment=EnvironmentResult(image=None, network="host", platform=os.name),
        started_at=started_at,
        finished_at=now(),
    )
    (build_root / "result.json").write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    checks = [
        {
            "id": "V-23",
            "status": "pass" if failure in (None, FailureCode.RECORDING_FAILED) else "fail",
            "detail": "execution evidence complete" if failure is None else (failure.value if failure else ""),
        }
    ]
    if record:
        checks.append(
            {
                "id": "V-24",
                "status": "pass" if recording is not None and recording.probe_ok else "fail",
                "detail": (
                    f"{recording.width}x{recording.height} {recording.duration_s:.3f}s"
                    if recording is not None and recording.probe_ok
                    else (recording_error or "recording missing")
                ),
            }
        )
    else:
        checks.append({"id": "V-24", "status": "not_applicable", "detail": "record disabled"})
    validation = ValidationReport(
        shot_id=spec.shot_id,
        session_id=spec.session_id,
        status="pass" if all(item["status"] != "fail" for item in checks) else "fail",
        checks=checks,
    )
    (build_root / "validation.json").write_text(validation.model_dump_json(indent=2) + "\n", encoding="utf-8")
    recording_json = build_root / "recording.json"
    if recording is not None:
        recording_json.write_text(recording.model_dump_json(indent=2) + "\n", encoding="utf-8")
    manifest = EvidenceManifest(
        shot_id=spec.shot_id,
        session_id=spec.session_id,
        spec_sha256=_hash_file(spec_path),
        execution_result="result.json",
        recording_result="recording.json" if recording is not None else None,
        validation_report="validation.json",
        transcript="vscode-result.json",
        artifacts=["session.mp4"] if (build_root / "session.mp4").is_file() else [],
        cache_key=cache_key(spec, file_hashes, None),
    )
    (build_root / "evidence.json").write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return result, manifest, recording
