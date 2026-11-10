from __future__ import annotations

import json
import time
from pathlib import Path

from ..contracts import Status
from ..paths import LessonPaths
from ..utils import run_command, which_command
from .base import StageOutcome, selected, verify_media


def run(paths: LessonPaths) -> StageOutcome:
    shots = [shot for shot in paths.storyboard.shots if selected(paths, shot.id) and shot.engine == "blender"]
    if not shots:
        return StageOutcome("render:blender", Status.NOT_APPLICABLE)

    started = time.monotonic()
    log_dir = paths.build_root / "logs"
    outputs: list[Path] = []
    warnings: list[str] = []
    errors: list[str] = []

    def check_output(shot, output: Path, *, record_errors: bool = True) -> bool:
        if not output.is_file():
            if record_errors:
                errors.append(f"{shot.id}: blender output missing: {output}")
            return False
        if output.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"}:
            try:
                _, shot_warnings = verify_media(
                    output,
                    width=paths.lesson.outputs.resolution[0],
                    height=paths.lesson.outputs.resolution[1],
                    fps=float(paths.lesson.outputs.fps),
                    expected_duration_s=shot.expected_duration_s,
                )
            except Exception as exc:  # noqa: BLE001
                if record_errors:
                    errors.append(f"{shot.id}: {exc}")
                return False
            warnings.extend(f"{shot.id}: {item}" for item in shot_warnings)
        return True

    for shot in shots:
        task_path = paths.blend_task_path(shot)
        if task_path is None or not task_path.is_file():
            errors.append(f"{shot.id}: blend task not found: {shot.blend_task}")
            continue
        try:
            task_data = json.loads(task_path.read_text(encoding="utf-8"))
            output = Path(task_data["output"])
            if not output.is_absolute():
                output = paths.workspace / output
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{shot.id}: cannot read blender task output: {exc}")
            continue
        # Reuse a valid output that is newer than the task file.  Rendering is
        # expensive and the output is already covered by the same media check.
        if output.is_file() and output.stat().st_mtime >= task_path.stat().st_mtime:
            if check_output(shot, output, record_errors=False):
                outputs.append(output)
                continue
        command = [
            *which_command("powershell"),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(paths.workspace / "scripts" / "blender-render.ps1"),
            "-Lesson",
            paths.slug,
            "-Task",
            str(task_path),
        ]
        result = run_command(
            command,
            paths.workspace,
            timeout=1900,
            log_path=log_dir / f"blender-{shot.id}.log",
        )
        if result.exit_code != 0:
            detail = result.stderr[-1000:]
            ps_log = log_dir / f"blender-{task_path.stem}.log"
            if ps_log.is_file():
                detail += chr(10) + ps_log.read_text(encoding="utf-8-sig", errors="replace")[-1500:]
            errors.append(
                f"{shot.id}: blender exited {result.exit_code}: {detail}"
            )
            continue
        if check_output(shot, output):
            outputs.append(output)

    duration_ms = int((time.monotonic() - started) * 1000)
    if errors:
        return StageOutcome(
            "render:blender",
            Status.FAIL,
            outputs=outputs,
            warnings=warnings,
            errors=errors,
            duration_ms=duration_ms,
        )
    return StageOutcome(
        "render:blender", Status.PASS, outputs=outputs, warnings=warnings, duration_ms=duration_ms
    )
