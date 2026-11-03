from __future__ import annotations

import shutil
import time
from pathlib import Path

from ..contracts import Status
from ..paths import LessonPaths
from ..utils import probe_media, run_command, which_command
from .base import StageOutcome
from .slides import clean_staging


def compose(paths: LessonPaths) -> StageOutcome:
    started = time.monotonic()
    log_dir = paths.build_root / "logs"
    shots_path = paths.build_root / "shots.json"
    output = paths.build_root / "final" / "course-video.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    remotion_root = paths.workspace / "RemotionStudio"

    stage = run_command(
        [
            *which_command("node"),
            "scripts/stage-assets.mjs",
            "--lesson",
            paths.slug,
            "--shots",
            str(shots_path),
        ],
        remotion_root,
        timeout=300,
        log_path=log_dir / "staging.log",
    )
    if stage.exit_code != 0:
        return StageOutcome(
            "compose",
            Status.FAIL,
            errors=[f"staging exited {stage.exit_code}", stage.stderr[-2000:]],
            reason="staging_failed",
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    render = run_command(
        [
            *which_command("npx"),
            "remotion",
            "render",
            "src/index.ts",
            "CourseVideo",
            str(output),
            f"--props={shots_path}",
        ],
        remotion_root,
        timeout=1800,
        log_path=log_dir / "remotion.log",
    )
    duration_ms = int((time.monotonic() - started) * 1000)

    if render.exit_code != 0:
        return StageOutcome(
            "compose",
            Status.FAIL,
            errors=[f"remotion exited {render.exit_code}", render.stderr[-2000:]],
            reason="render_failed",
            duration_ms=duration_ms,
        )
    if not output.is_file():
        return StageOutcome(
            "compose",
            Status.FAIL,
            errors=[f"final video missing: {output}"],
            reason="render_failed",
            duration_ms=duration_ms,
        )

    probe_media(output)
    clean_staging(paths)
    return StageOutcome("compose", Status.PASS, outputs=[output], duration_ms=duration_ms)
