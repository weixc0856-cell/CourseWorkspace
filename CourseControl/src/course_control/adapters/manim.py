from __future__ import annotations

import shutil
import time
from pathlib import Path

from ..contracts import Status
from ..paths import LessonPaths
from ..utils import probe_media, run_command, which_command
from .base import StageOutcome, selected


def run(paths: LessonPaths) -> StageOutcome:
    shots = [shot for shot in paths.storyboard.shots if selected(paths, shot.id) and shot.engine == "manim"]
    if not shots:
        return StageOutcome("render:manim", Status.NOT_APPLICABLE)

    started = time.monotonic()
    log_dir = paths.build_root / "logs"
    media_dir = paths.build_root / "tmp" / "manim-media"
    outputs: list[Path] = []
    errors: list[str] = []

    for shot in shots:
        scene_path, class_name = paths.scene_path(shot)
        if not class_name:
            errors.append(f"{shot.id}: manim scene must use <file>.py::<ClassName>")
            continue
        relative_scene = scene_path.relative_to(paths.engine_root("manim"))
        command = [
            *which_command("uv"),
            "run",
            "manim",
            "render",
            "-r",
            f"{paths.lesson.outputs.resolution[0]},{paths.lesson.outputs.resolution[1]}",
            "--fps",
            str(paths.lesson.outputs.fps),
            "--media_dir",
            str(media_dir),
            str(relative_scene),
            class_name,
        ]
        result = run_command(
            command,
            paths.engine_root("manim"),
            timeout=1800,
            log_path=log_dir / f"manim-{shot.id}.log",
        )
        if result.exit_code != 0:
            errors.append(f"{shot.id}: manim exited {result.exit_code}: {result.stderr[-1500:]}")
            continue
        candidates = sorted(media_dir.glob(f"videos/**/{class_name}.mp4"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            errors.append(f"{shot.id}: rendered file for {class_name} not found under {media_dir}")
            continue
        target = paths.build_root / "animation" / f"{scene_path.stem}.mp4"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidates[-1], target)
        probe_media(target)
        outputs.append(target)

    duration_ms = int((time.monotonic() - started) * 1000)
    if errors:
        return StageOutcome("render:manim", Status.FAIL, outputs=outputs, errors=errors, duration_ms=duration_ms)
    return StageOutcome("render:manim", Status.PASS, outputs=outputs, duration_ms=duration_ms)
