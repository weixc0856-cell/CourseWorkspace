"""Host-side session execution and evidence collection (E1)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import ctypes
from pathlib import Path

from .session import (
    AssertionResult,
    CheckResult,
    CommandResult,
    EnvironmentResult,
    EvidenceManifest,
    ExecutionResult,
    FailureCode,
    FailureDetail,
    RecordingResult,
    SessionContractError,
    SessionSpec,
    ValidationReport,
    cache_key,
    load_session_spec,
    normalize_stream,
    now,
    sha256_text,
)

CREATE_NEW_CONSOLE = 0x00000010

if os.name == "nt":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        pass


class SessionRunError(RuntimeError):
    pass


def _run(command: list[str], *, timeout: int = 120, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _docker_ready() -> str:
    executable = shutil.which("docker")
    if not executable:
        raise SessionRunError("docker executable not found")
    result = _run([executable, "info", "--format", "{{.ServerVersion}}"], timeout=30)
    if result.returncode != 0:
        raise SessionRunError(f"docker daemon unavailable: {result.stderr.strip()}")
    return executable


def _image_digest(docker: str, image: str) -> str | None:
    result = _run([docker, "image", "inspect", image, "--format", "{{.Id}}"], timeout=30)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _remove_tree(path: Path) -> None:
    def on_error(_func, target, _exc):
        try:
            os.unlink(target)
        except OSError:
            try:
                os.rmdir(target)
            except OSError:
                pass

    shutil.rmtree(path, onexc=on_error)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prepare(workspace: Path, lesson_dir: Path, spec: SessionSpec) -> tuple[Path, dict[str, str]]:
    build_root = workspace / "build" / spec.lesson / "code" / spec.shot_id
    workdir = build_root / "work"
    if workdir.exists():
        _remove_tree(workdir)
    workdir.mkdir(parents=True)
    hashes: dict[str, str] = {}
    for entry in spec.files:
        source = (lesson_dir / entry.source).resolve()
        try:
            source.relative_to(lesson_dir.resolve())
        except ValueError as exc:
            raise SessionRunError(f"source escapes lesson directory: {entry.source}") from exc
        if not source.is_file():
            raise SessionRunError(f"session file not found: {source}")
        target = workdir / entry.path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        hashes[entry.path] = _hash_file(source)
    return workdir, hashes


def _write_run_spec(workdir: Path, spec: SessionSpec) -> Path:
    payload = {
        "workdir": spec.environment.workdir,
        "timeout_s": spec.environment.timeout_s,
        "transcript": spec.environment.workdir.rstrip("/") + "/transcript.log",
        "commands": [
            {
                "id": command.id,
                "run": command.run,
                "timeout_s": spec.environment.timeout_s,
            }
            for command in spec.commands
        ],
    }
    path = workdir / "run.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _docker_argv(
    docker: str,
    spec: SessionSpec,
    workdir: Path,
    runner: Path,
    *,
    tty: bool,
    network: str | None = None,
    suffix: str = "",
) -> list[str]:
    env = spec.environment
    command = [
        docker,
        "run",
        "--rm",
        "--name",
        f"course-session-{spec.session_id}{suffix}",
        "--user",
        env.user,
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        str(env.pids),
        "--memory",
        env.memory,
        "--cpus",
        str(env.cpus),
        "--network",
        network or env.network,
        "--add-host",
        "host.docker.internal:host-gateway",
        "-v",
        f"{workdir}:/work:rw",
        "-v",
        f"{runner}:/runner.py:ro",
    ]
    if tty:
        command.append("-t")
    command.extend([env.image, "python3", "/runner.py", "/work/run.json", "/work/raw-result.json"])
    return command


def _first_difference(expected: str, actual: str) -> str:
    expected_lines = expected.split("\n")
    actual_lines = actual.split("\n")
    for index in range(max(len(expected_lines), len(actual_lines))):
        left = expected_lines[index] if index < len(expected_lines) else "<missing>"
        right = actual_lines[index] if index < len(actual_lines) else "<missing>"
        if left != right:
            return f"line {index + 1}: expected {left!r}, actual {right!r}"
    return "streams differ"


def _assert_commands(
    workdir: Path,
    spec: SessionSpec,
    raw: dict,
    commands: list | None = None,
) -> tuple[list[CommandResult], FailureCode | None]:
    raw_by_id = {item.get("id"): item for item in raw.get("commands", [])}
    results: list[CommandResult] = []
    failure: FailureCode | None = None
    for command in (commands if commands is not None else spec.commands):
        item = raw_by_id.get(command.id, {})
        stdout = item.get("stdout", "")
        stderr = item.get("stderr", "")
        exit_code = item.get("exit_code")
        timed_out = bool(item.get("timed_out"))
        assertions: list[AssertionResult] = []

        def add(name: str, ok: bool, detail: str = "") -> None:
            assertions.append(AssertionResult(name=name, ok=ok, detail=detail))

        exit_ok = exit_code == command.expect.exit_code
        add(
            "exit_code",
            exit_ok,
            "" if exit_ok else f"{exit_code} != {command.expect.exit_code}",
        )
        if timed_out:
            failure = failure or FailureCode.TIMEOUT
        elif exit_code != command.expect.exit_code:
            failure = failure or FailureCode.EXECUTION_FAILED

        if command.expect.stdout:
            expected_path = workdir / command.expect.stdout
            if not expected_path.is_file():
                add("stdout", False, f"expected file missing: {command.expect.stdout}")
                failure = failure or FailureCode.EVIDENCE_INCOMPLETE
            else:
                expected = normalize_stream(expected_path.read_text(encoding="utf-8"))
                actual = normalize_stream(stdout)
                ok = expected == actual
                add("stdout", ok, "" if ok else _first_difference(expected, actual))
                if not ok:
                    failure = failure or FailureCode.ASSERTION_FAILED
        if command.expect.stderr:
            expected_path = workdir / command.expect.stderr
            if not expected_path.is_file():
                add("stderr", False, f"expected file missing: {command.expect.stderr}")
                failure = failure or FailureCode.EVIDENCE_INCOMPLETE
            else:
                expected = normalize_stream(expected_path.read_text(encoding="utf-8"))
                actual = normalize_stream(stderr)
                ok = expected == actual
                add("stderr", ok, "" if ok else _first_difference(expected, actual))
                if not ok:
                    failure = failure or FailureCode.ASSERTION_FAILED
        for relative in command.expect.files:
            target = workdir / relative
            try:
                ok = target.exists()
            except OSError:
                ok = False
            add(f"file:{relative}", ok, "" if ok else "missing")
            if not ok:
                failure = failure or FailureCode.ASSERTION_FAILED

        results.append(
            CommandResult(
                id=command.id,
                argv=command.run,
                exit_code=exit_code,
                timed_out=timed_out,
                duration_ms=int(item.get("duration_ms", 0)),
                stdout=stdout,
                stderr=stderr,
                stdout_sha256=sha256_text(stdout),
                stderr_sha256=sha256_text(stderr),
                assertions=assertions,
            )
        )
    return results, failure


def _mintty() -> str:
    executable = shutil.which("mintty")
    if executable:
        return executable
    program_files = os.environ.get("ProgramFiles")
    if program_files:
        candidate = Path(program_files) / "Git/usr/bin/mintty.exe"
        if candidate.is_file():
            return str(candidate)
    raise SessionRunError("mintty not found; install Git for Windows or add mintty to PATH")


def _window_text(hwnd: int) -> str:
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _find_window(title: str, timeout: float = 8.0) -> int:
    if os.name != "nt":
        return 0
    user32 = ctypes.windll.user32
    handles: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            text = _window_text(hwnd)
            if text == title or title in text:
                handles.append(int(hwnd))
        return True

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        handles.clear()
        user32.EnumWindows(callback, 0)
        if handles:
            return handles[0]
        time.sleep(0.2)
    return 0


def _focus_window(hwnd: int, size: tuple[int, int] | None = None) -> None:
    if os.name != "nt" or not hwnd:
        return
    user32 = ctypes.windll.user32
    if user32.IsZoomed(hwnd):
        user32.ShowWindow(hwnd, 9)
    user32.ShowWindow(hwnd, 1)
    if size is not None:
        width, height = size
        user32.SetWindowPos(hwnd, -1, 0, 0, width, height, 0x0040)
    else:
        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    time.sleep(0.8)


def _unfocus_window(hwnd: int) -> None:
    if os.name != "nt" or not hwnd:
        return
    ctypes.windll.user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002)


def _window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    if os.name != "nt" or not hwnd:
        return None
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        pass

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    rect = RECT()
    if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return None
    return int(rect.left), int(rect.top), int(width), int(height)


def _start_recording(
    spec: SessionSpec,
    output: Path,
    hwnd: int | None = None,
    log_path: Path | None = None,
    rect: tuple[int, int, int, int] | None = None,
) -> subprocess.Popen:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SessionRunError("ffmpeg executable not found")
    if rect is not None and spec.record.target == "vscode":
        left, top, width, height = rect
        source_args = [
            "-f",
            "lavfi",
            "-i",
            f"ddagrab=framerate={spec.record.fps}:offset_x={left}:offset_y={top}:video_size={width}x{height}",
        ]
        filters = "hwdownload,format=bgra,scale=trunc(iw/2)*2:trunc(ih/2)*2"
    elif spec.record.capture == "window":
        if not hwnd:
            raise SessionRunError("window handle not found for recording")
        source_args = [
            "-f",
            "gdigrab",
            "-framerate",
            str(spec.record.fps),
            "-i",
            f"hwnd={hwnd}",
        ]
        filters = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    else:
        source_args = [
            "-f",
            "gdigrab",
            "-framerate",
            str(spec.record.fps),
            "-i",
            "desktop",
        ]
        filters = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        *source_args,
        "-vf",
        filters,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        str(output),
    ]
    log_handle = log_path.open("wb") if log_path else subprocess.DEVNULL
    return subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=log_handle,
    )


def _probe_recording(path: Path, spec: SessionSpec) -> RecordingResult | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not path.is_file():
        return None
    result = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,avg_frame_rate,nb_frames",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        timeout=60,
    )
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout or "{}")
    stream = (data.get("streams") or [{}])[0]
    try:
        numerator, denominator = str(stream.get("avg_frame_rate", "0/1")).split("/")
        fps = float(numerator) / float(denominator or 1)
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    duration = float((data.get("format") or {}).get("duration", 0.0))
    frames = int(stream.get("nb_frames") or 0)
    return RecordingResult(
        path=str(path),
        sha256=_hash_file(path),
        width=int(stream.get("width", 0)),
        height=int(stream.get("height", 0)),
        fps=fps,
        frames=frames,
        duration_s=duration,
        probe_ok=bool(stream.get("width") and stream.get("height")),
        capture=spec.record.capture,
    )


def _apply_trims(
    video: Path,
    raw: dict,
    record_started: float,
    spec: SessionSpec,
    recording: RecordingResult,
) -> RecordingResult:
    items = {item.get("id"): item for item in raw.get("commands", [])}
    total = recording.duration_s
    cuts = []
    for command in spec.commands:
        trim = command.trim
        if trim is None:
            continue
        target = trim.command or command.id
        item = items.get(target)
        if not item or "started_at" not in item or "finished_at" not in item:
            raise SessionRunError(f"trim target has no timing: {target}")
        start = max(0.0, float(item["started_at"]) - record_started + trim.keep_head_s)
        end = min(total, float(item["finished_at"]) - record_started - trim.keep_tail_s)
        if end > start:
            cuts.append((start, end))
    if not cuts:
        return recording
    cuts.sort()
    keep = []
    cursor = 0.0
    for start, end in cuts:
        if start > cursor:
            keep.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < total:
        keep.append((cursor, total))
    if not keep:
        raise SessionRunError("trim removed the entire recording")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SessionRunError("ffmpeg executable not found")
    parts = []
    for index, (start, end) in enumerate(keep):
        parts.append(
            f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[v{index}]"
        )
    parts.append(
        "".join(f"[v{index}]" for index in range(len(keep)))
        + f"concat=n={len(keep)}:v=1:a=0[out]"
    )
    temp = video.with_name(video.stem + ".trim" + video.suffix)
    result = _run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-filter_complex",
            ";".join(parts),
            "-map",
            "[out]",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            str(temp),
        ],
        timeout=300,
    )
    if result.returncode != 0 or not temp.is_file():
        raise SessionRunError(f"trim failed: {result.stderr.strip()[-500:]}")
    temp.replace(video)
    return _probe_recording(video, spec) or recording


def run_session(
    workspace: Path,
    spec_path: Path,
    lesson_dir: Path,
    *,
    record: bool = False,
) -> tuple[ExecutionResult, EvidenceManifest, RecordingResult | None]:
    workspace = workspace.resolve()
    lesson_dir = lesson_dir.resolve()
    spec = load_session_spec(spec_path)
    if spec.environment.kind == "host":
        from .vscode_runner import run_vscode_session

        return run_vscode_session(workspace, spec_path, lesson_dir, record=record)
    docker = _docker_ready()
    digest = _image_digest(docker, spec.environment.image)
    if digest is None:
        raise SessionRunError(
            f"image not found: {spec.environment.image}; build it with scripts/build-session-image.ps1"
        )
    workdir, file_hashes = _prepare(workspace, lesson_dir, spec)
    run_spec = _write_run_spec(workdir, spec)
    runner = Path(__file__).with_name("container_runner.py")
    build_root = workdir.parent
    raw_path = workdir / "raw-result.json"
    if raw_path.exists():
        raw_path.unlink()

    started_at = now()
    recording = None
    recording_error = None
    record_started: float | None = None
    try:
        if record:
            if spec.record.target != "terminal":
                raise SessionRunError("E1 only implements record.target=terminal")
            video = build_root / "session.mp4"
            video.parent.mkdir(parents=True, exist_ok=True)
            args = _docker_argv(docker, spec, workdir, runner, tty=True)
            batch = build_root / "run-session.bat"
            batch.write_text(
                "@echo off\r\n"
                "ping -n 2 127.0.0.1 >nul\r\n"
                + subprocess.list2cmdline(args)
                + "\r\nping -n 3 127.0.0.1 >nul\r\n",
                encoding="utf-8",
            )
            mintty = _mintty()
            window_title = f"{spec.record.window_title}-{spec.session_id}"
            mintty_env = os.environ.copy()
            mintty_env["MSYS_NO_PATHCONV"] = "1"
            mintty_env["MSYS2_ARG_CONV_EXCL"] = "*"
            console = subprocess.Popen(
                [
                    mintty,
                    "-t",
                    window_title,
                    "-s",
                    "120x35",
                    "-e",
                    "cmd",
                    "/c",
                    str(batch),
                ],
                env=mintty_env,
            )
            hwnd = _find_window(window_title)
            if not hwnd:
                console.terminate()
                raise SessionRunError(
                    f"mintty window not found: {spec.record.window_title}"
                )
            _focus_window(hwnd)
            process = _start_recording(spec, video, hwnd, build_root / "ffmpeg.log")
            record_started = time.time()
            deadline = time.monotonic() + spec.environment.timeout_s + 120
            while time.monotonic() < deadline and not raw_path.is_file():
                time.sleep(0.5)
            time.sleep(1.0)
            try:
                if process.stdin is not None:
                    process.stdin.write(b"q")
                    process.stdin.flush()
                process.wait(timeout=15)
            except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
            if hwnd:
                _unfocus_window(hwnd)
                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
            recording = _probe_recording(video, spec)
            if recording is None:
                recording_error = "recording probe failed"
        else:
            args = _docker_argv(docker, spec, workdir, runner, tty=False)
            result = _run(args, timeout=spec.environment.timeout_s + 120)
            if result.returncode != 0 and not raw_path.is_file():
                raise SessionRunError(
                    f"container failed ({result.returncode}): {result.stderr.strip()[-800:]}"
                )
    except subprocess.TimeoutExpired as exc:
        raise SessionRunError(f"session timed out: {exc}") from exc

    if not raw_path.is_file():
        result = ExecutionResult(
            shot_id=spec.shot_id,
            session_id=spec.session_id,
            status="failed",
            failure=FailureCode.EVIDENCE_INCOMPLETE,
            environment=EnvironmentResult(
                image=spec.environment.image,
                image_digest=digest,
                network=spec.environment.network,
            ),
            started_at=started_at,
            finished_at=now(),
        )
        manifest = EvidenceManifest(
            shot_id=spec.shot_id,
            session_id=spec.session_id,
            spec_sha256=_hash_file(spec_path),
            execution_result=None,
            cache_key=cache_key(spec, file_hashes, digest),
        )
        manifest_path = build_root / "evidence.json"
        manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
        (build_root / "result.json").write_text(
            result.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        return result, manifest, recording

    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if recording is not None and record_started is not None:
        try:
            recording = _apply_trims(
                build_root / "session.mp4", raw, record_started, spec, recording
            )
        except SessionRunError as exc:
            recording_error = str(exc)
    commands, failure = _assert_commands(workdir, spec, raw)
    if failure is None and recording_error:
        failure = FailureCode.RECORDING_FAILED
    offline_failure = None
    if spec.offline_commands:
        offline_raw_path = workdir / "offline-raw-result.json"
        if offline_raw_path.exists():
            offline_raw_path.unlink()
        offline_spec_path = workdir / "offline-run.json"
        offline_spec_path.write_text(
            json.dumps(
                {
                    "workdir": spec.environment.workdir,
                    "timeout_s": spec.environment.timeout_s,
                    "transcript": spec.environment.workdir.rstrip("/") + "/offline-transcript.log",
                    "commands": [
                        {
                            "id": command.id,
                            "run": command.run,
                            "timeout_s": spec.environment.timeout_s,
                        }
                        for command in spec.offline_commands
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        offline_args = _docker_argv(
            docker,
            spec,
            workdir,
            runner,
            tty=False,
            network="none",
            suffix="-offline",
        )
        offline_args = [
            arg.replace("/work/run.json", "/work/offline-run.json").replace(
                "/work/raw-result.json", "/work/offline-raw-result.json"
            )
            for arg in offline_args
        ]
        offline_run = _run(offline_args, timeout=spec.environment.timeout_s + 120)
        if not offline_raw_path.is_file():
            offline_failure = FailureCode.OFFLINE_VERIFY_FAILED
        else:
            offline_raw = json.loads(offline_raw_path.read_text(encoding="utf-8"))
            offline_commands, offline_failure = _assert_commands(
                workdir, spec, offline_raw, commands=spec.offline_commands
            )
            commands.extend(offline_commands)
            (build_root / "offline-result.json").write_text(
                json.dumps(offline_raw, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    if offline_failure is not None:
        failure = failure or offline_failure
    status = "passed" if failure is None else "failed"
    result = ExecutionResult(
        shot_id=spec.shot_id,
        session_id=spec.session_id,
        status=status,
        failure=failure,
        commands=commands,
        environment=EnvironmentResult(
            image=spec.environment.image,
            image_digest=digest,
            network=spec.environment.network,
            platform=os.name,
        ),
        started_at=started_at,
        finished_at=now(),
    )
    (build_root / "result.json").write_text(
        result.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    execution_failure = result.failure in {
        FailureCode.TIMEOUT,
        FailureCode.EXECUTION_FAILED,
        FailureCode.ASSERTION_FAILED,
        FailureCode.EVIDENCE_INCOMPLETE,
        FailureCode.ENVIRONMENT_FAILED,
    }
    checks = [
        CheckResult(
            id="V-23",
            status="pass" if not execution_failure else "fail",
            detail=(
                "execution evidence complete"
                if not execution_failure
                else (result.failure.value if result.failure else "failed")
            ),
        )
    ]
    if record:
        recording_ok = recording is not None and recording.probe_ok
        checks.append(
            CheckResult(
                id="V-24",
                status="pass" if recording_ok else "fail",
                detail=(
                    f"{recording.width}x{recording.height} {recording.duration_s:.3f}s"
                    if recording_ok and recording is not None
                    else (recording_error or "recording missing")
                ),
            )
        )
    else:
        checks.append(CheckResult(id="V-24", status="not_applicable", detail="record disabled"))
    if spec.offline_commands:
        checks.append(
            CheckResult(
                id="V-25",
                status="pass" if offline_failure is None else "fail",
                detail=(
                    f"{len(spec.offline_commands)} offline commands passed"
                    if offline_failure is None
                    else offline_failure.value
                ),
            )
        )
    else:
        checks.append(CheckResult(id="V-25", status="not_applicable", detail="no offline commands"))
    validation = ValidationReport(
        shot_id=spec.shot_id,
        session_id=spec.session_id,
        status="pass" if all(check.status != "fail" for check in checks) else "fail",
        failures=(
            [FailureDetail(code=result.failure, message=result.failure.value)]
            if result.failure is not None
            else []
        ),
        checks=checks,
    )
    (build_root / "validation.json").write_text(
        validation.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    recording_path = build_root / "recording.json"
    if recording is not None:
        recording_path.write_text(recording.model_dump_json(indent=2) + "\n", encoding="utf-8")
    manifest = EvidenceManifest(
        shot_id=spec.shot_id,
        session_id=spec.session_id,
        spec_sha256=_hash_file(spec_path),
        execution_result="result.json",
        recording_result="recording.json" if recording is not None else None,
        validation_report="validation.json",
        transcript="work/transcript.log" if (workdir / "transcript.log").is_file() else None,
        artifacts=["session.mp4"] if (build_root / "session.mp4").is_file() else [],
        cache_key=cache_key(spec, file_hashes, digest),
    )
    (build_root / "evidence.json").write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return result, manifest, recording
