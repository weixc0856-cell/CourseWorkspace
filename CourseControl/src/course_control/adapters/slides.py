from __future__ import annotations

import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..contracts import Status
from ..paths import LessonPaths
from ..utils import run_command, which_command
from .base import StageOutcome

BASE_URL = "http://localhost:8081"
CAPTURE_URL = f"{BASE_URL}/CourseSlides/template/"


def _server_ready() -> bool:
    try:
        with urllib.request.urlopen(CAPTURE_URL, timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _start_server(paths: LessonPaths, log_dir: Path) -> subprocess.Popen:
    script = paths.workspace / "CourseSlides" / "node_modules" / "live-server" / "live-server.js"
    if not script.is_file():
        raise RuntimeError(f"live-server not found: {script}")
    log_path = log_dir / "slides-server.log"
    log_dir.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("w", encoding="utf-8")
    command = [
        *which_command("node"),
        str(script),
        str(paths.workspace),
        "--port=8081",
        "--entry-file=index.html",
        "--watch=lessons,CourseSlides/template,CourseSlides/css",
        "--no-browser",
    ]
    process = subprocess.Popen(
        command,
        cwd=str(paths.workspace),
        stdout=handle,
        stderr=subprocess.STDOUT,
    )
    for _ in range(40):
        if _server_ready():
            return process
        if process.poll() is not None:
            break
        time.sleep(0.5)
    process.terminate()
    raise RuntimeError(f"live-server did not become ready; see {log_path}")


def capture_slides(paths: LessonPaths) -> StageOutcome:
    log_dir = paths.build_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    manifest = paths.build_root / "slides" / "capture-manifest.json"
    started = time.monotonic()
    server = None
    try:
        if not _server_ready():
            server = _start_server(paths, log_dir)
        width, height = paths.lesson.outputs.resolution
        command = [
            *which_command("node"),
            "scripts/capture-slides.mjs",
            "--lesson",
            paths.slug,
            "--width",
            str(width),
            "--height",
            str(height),
        ]
        result = run_command(
            command,
            paths.workspace / "RemotionStudio",
            timeout=600,
            log_path=log_dir / "capture-slides.log",
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        if result.exit_code != 0:
            return StageOutcome(
                "capture_slides",
                Status.FAIL,
                errors=[f"capture exited {result.exit_code}", result.stderr[-2000:]],
                duration_ms=duration_ms,
            )
        if not manifest.is_file():
            return StageOutcome(
                "capture_slides",
                Status.FAIL,
                errors=[f"capture manifest missing: {manifest}"],
                duration_ms=duration_ms,
            )
        return StageOutcome(
            "capture_slides",
            Status.PASS,
            outputs=[manifest, paths.build_root / "slides"],
            duration_ms=duration_ms,
        )
    except Exception as exc:  # noqa: BLE001 - surface the message to the report
        return StageOutcome(
            "capture_slides",
            Status.FAIL,
            errors=[str(exc)],
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


def clean_staging(paths: LessonPaths) -> None:
    staging = paths.workspace / "RemotionStudio" / "public" / "staging" / paths.slug
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
