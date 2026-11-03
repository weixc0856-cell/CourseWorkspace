from __future__ import annotations

import time
from pathlib import Path

from ..contracts import Status
from ..paths import LessonPaths
from ..utils import probe_media
from .base import StageOutcome


def expected_output(paths: LessonPaths, scene_path: Path) -> Path:
    return paths.build_root / "animation" / f"{scene_path.stem}.mp4"


def run(paths: LessonPaths) -> StageOutcome:
    shots = [shot for shot in paths.storyboard.shots if shot.engine == "motion_canvas"]
    if not shots:
        return StageOutcome("render:motion_canvas", Status.NOT_APPLICABLE)

    started = time.monotonic()
    warnings: list[str] = []
    missing: list[str] = []
    outputs: list[Path] = []
    for shot in shots:
        scene_path, _ = paths.scene_path(shot)
        output = expected_output(paths, scene_path)
        if output.is_file():
            try:
                probe_media(output)
            except Exception as exc:  # noqa: BLE001
                return StageOutcome(
                    "render:motion_canvas",
                    Status.FAIL,
                    errors=[f"invalid motion output {output}: {exc}"],
                    duration_ms=int((time.monotonic() - started) * 1000),
                )
            outputs.append(output)
        else:
            missing.append(f"{shot.id}: {output}")

    if not missing:
        return StageOutcome(
            "render:motion_canvas",
            Status.PASS,
            outputs=outputs,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    if paths.lesson.build.allow_manual_animation_export:
        warnings.extend(f"manual export required: {item}" for item in missing)
        return StageOutcome(
            "render:motion_canvas",
            Status.SKIPPED,
            outputs=outputs,
            warnings=warnings,
            reason="manual_export_required",
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    return StageOutcome(
        "render:motion_canvas",
        Status.FAIL,
        outputs=outputs,
        errors=[f"missing motion output: {item}" for item in missing],
        duration_ms=int((time.monotonic() - started) * 1000),
    )
