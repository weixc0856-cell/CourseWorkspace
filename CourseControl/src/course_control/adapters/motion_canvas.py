from __future__ import annotations

import os
import time
from pathlib import Path

from ..contracts import Status
from ..paths import LessonPaths
from ..utils import MediaInfo, probe_media, run_command, which_command
from .base import StageOutcome, selected

MAX_ATTEMPTS = 2
DEFAULT_VITE_PORT = 4173
DEFAULT_SINK_PORT = 4174


def expected_output(paths: LessonPaths, scene_path: Path) -> Path:
    return paths.build_root / "animation" / f"{scene_path.stem}.mp4"


def scene_id(scene_path: Path) -> str:
    return scene_path.stem.replace("_", "-")


def _render_once(
    paths: LessonPaths,
    shot_id: str,
    scene_path: Path,
    target: Path,
    attempt: int,
) -> tuple[bool, str]:
    log_dir = paths.build_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    width, height = paths.lesson.outputs.animation_canvas
    command = [
        *which_command("node"),
        "scripts/render-headless.mjs",
        "--scene",
        scene_id(scene_path),
        "--fps",
        str(paths.lesson.outputs.fps),
        "--width",
        str(width),
        "--height",
        str(height),
        "--out",
        str(target),
        "--vite-port",
        os.environ.get("MOTION_CANVAS_VITE_PORT", str(DEFAULT_VITE_PORT)),
        "--sink-port",
        os.environ.get("MOTION_CANVAS_SINK_PORT", str(DEFAULT_SINK_PORT)),
    ]
    fail_at = os.environ.get("MOTION_CANVAS_FAIL_AT")
    if fail_at:
        command += ["--fail-at", fail_at]
    result = run_command(
        command,
        paths.engine_root("motion_canvas"),
        timeout=1800,
        log_path=log_dir / f"motion-canvas-{shot_id}-attempt{attempt}.log",
    )
    if result.exit_code != 0:
        return False, f"headless render exited {result.exit_code}: {result.stderr[-1500:]}"
    if not target.is_file() or target.stat().st_size == 0:
        return False, f"headless render produced no media: {target}"
    return True, ""


def _verify(target: Path, paths: LessonPaths) -> tuple[MediaInfo, list[str]]:
    info = probe_media(target)
    warnings: list[str] = []
    width, height = paths.lesson.outputs.animation_canvas
    if info.width != width or info.height != height:
        raise ValueError(
            f"resolution {info.width}x{info.height} does not match {width}x{height}"
        )
    if info.fps is None or abs(info.fps - paths.lesson.outputs.fps) > 0.01:
        raise ValueError(f"fps {info.fps} does not match {paths.lesson.outputs.fps}")
    if info.duration is None or info.duration <= 0:
        raise ValueError("duration is missing or zero")
    return info, warnings


def run(paths: LessonPaths) -> StageOutcome:
    shots = [
        shot
        for shot in paths.storyboard.shots
        if selected(paths, shot.id) and shot.engine == "motion_canvas"
    ]
    if not shots:
        return StageOutcome("render:motion_canvas", Status.NOT_APPLICABLE)

    started = time.monotonic()
    warnings: list[str] = []
    errors: list[str] = []
    outputs: list[Path] = []

    for shot in shots:
        scene_path, _ = paths.scene_path(shot)
        target = expected_output(paths, scene_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        # Reuse a valid, newer-than-source render. Otherwise render headlessly.
        if target.is_file() and target.stat().st_mtime >= scene_path.stat().st_mtime:
            try:
                info, shot_warnings = _verify(target, paths)
                warnings.extend(f"{shot.id}: {item}" for item in shot_warnings)
                if shot.expected_duration_s and info.duration:
                    delta = abs(info.duration - shot.expected_duration_s)
                    if delta > max(1.0, shot.expected_duration_s * 0.10):
                        warnings.append(
                            f"{shot.id}: duration {info.duration:.2f}s differs from "
                            f"expected {shot.expected_duration_s:.2f}s"
                        )
                outputs.append(target)
                continue
            except Exception:  # noqa: BLE001 - stale/invalid media is re-rendered
                target.unlink(missing_ok=True)

        last_error = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            target.unlink(missing_ok=True)
            ok, error = _render_once(paths, shot.id, scene_path, target, attempt)
            if not ok:
                last_error = error
                warnings.append(f"{shot.id}: attempt {attempt} failed")
                continue
            try:
                info, shot_warnings = _verify(target, paths)
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                target.unlink(missing_ok=True)
                continue
            warnings.extend(f"{shot.id}: {item}" for item in shot_warnings)
            if shot.expected_duration_s and info.duration:
                delta = abs(info.duration - shot.expected_duration_s)
                if delta > max(1.0, shot.expected_duration_s * 0.10):
                    warnings.append(
                        f"{shot.id}: duration {info.duration:.2f}s differs from "
                        f"expected {shot.expected_duration_s:.2f}s"
                    )
            outputs.append(target)
            last_error = ""
            break
        if last_error:
            errors.append(f"{shot.id}: {last_error}")

    duration_ms = int((time.monotonic() - started) * 1000)
    if errors:
        return StageOutcome(
            "render:motion_canvas",
            Status.FAIL,
            outputs=outputs,
            warnings=warnings,
            errors=errors,
            duration_ms=duration_ms,
        )
    return StageOutcome(
        "render:motion_canvas",
        Status.PASS,
        outputs=outputs,
        warnings=warnings,
        duration_ms=duration_ms,
    )
