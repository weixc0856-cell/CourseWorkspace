from __future__ import annotations

import http.server
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

from course_control.content.contracts import Status
from course_control.content.paths import LessonPaths
from course_control.platform.timeouts import resolve_timeout
from course_control.platform.utils import run_command, which_command
from course_control.rendering.adapters.base import StageOutcome

BASE_URL = "http://localhost:8081"
CAPTURE_URL = f"{BASE_URL}/CourseSlides/template/"


def _server_ready() -> bool:
    try:
        with urllib.request.urlopen(CAPTURE_URL, timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _expected_pages(paths: LessonPaths) -> int:
    """Page count declared by this lesson's slides.md."""
    slides = paths.content_path(paths.lesson.content.slides)
    text = slides.read_text(encoding="utf-8")
    return sum(1 for line in text.splitlines() if line.strip() == "---") + 1


def _make_handler(workspace: Path, lessons: Path, log_handle):
    """Serve /CourseSlides from the repo and /lessons from the content root.

    The template reads ``../../lessons/<slug>/slides.md``, which resolves to
    ``/lessons/<slug>/slides.md`` at the server root.  Serving only the
    workspace made that miss and fall back to a one-page placeholder deck, so
    the capture reported success for a lesson that was never loaded.
    """

    class Handler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path: str) -> str:
            clean = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
            rel = clean.lstrip("/")
            if rel == "lessons" or rel.startswith("lessons/"):
                base = lessons
                tail = rel[len("lessons"):].lstrip("/")
            else:
                base = workspace
                tail = rel
            candidate = (base / tail).resolve()
            if candidate != base and not str(candidate).startswith(str(base) + os.sep):
                return str(base / "__denied__")
            return str(candidate)

        def log_message(self, fmt, *args):  # noqa: A003 - stdlib signature
            print(fmt % args, file=log_handle)

    return Handler


class _CaptureServer:
    """Threaded static server used only by the capture stage."""

    def __init__(self, workspace: Path, lessons: Path, log_handle) -> None:
        handler = _make_handler(workspace, lessons, log_handle)
        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 8081), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def terminate(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def wait(self, timeout: float | None = None) -> None:
        self._thread.join(timeout)

    def kill(self) -> None:
        self.terminate()


def _start_server(paths: LessonPaths, log_dir: Path) -> _CaptureServer:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "slides-server.log"
    handle = log_path.open("w", encoding="utf-8")
    server = _CaptureServer(paths.workspace, paths.lesson_dir.parent, handle)
    for _ in range(40):
        if _server_ready():
            return server
        time.sleep(0.5)
    server.terminate()
    handle.close()
    raise RuntimeError(f"capture server did not become ready; see {log_path}")


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
            "--out",
            str(paths.build_root / "slides"),
        ]
        result = run_command(
            command,
            paths.workspace / "RemotionStudio",
            timeout=resolve_timeout(paths, "capture_slides"),
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
        expected = _expected_pages(paths)
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            total = int(data.get("total_slides") or 0)
            captured = int(data.get("captured") or 0)
        except (OSError, ValueError, TypeError) as exc:
            return StageOutcome(
                "capture_slides",
                Status.FAIL,
                errors=[f"cannot read capture manifest: {exc}"],
                duration_ms=duration_ms,
            )
        if total != expected or captured != expected:
            return StageOutcome(
                "capture_slides",
                Status.FAIL,
                errors=[
                    f"captured {captured}/{total} pages but slides.md declares {expected}; "
                    "the server probably served a fallback deck instead of this lesson"
                ],
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
