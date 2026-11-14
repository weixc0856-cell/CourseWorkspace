from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from course_control.content.contracts import Status
from course_control.content.paths import LessonPaths
from course_control.platform.timeouts import resolve_timeout
from course_control.platform.utils import load_json, probe_media, run_command, which_command
from course_control.rendering.adapters.base import StageOutcome
from course_control.rendering.adapters.slides import clean_staging


def _build_relative(paths: LessonPaths, value: str) -> str:
    """Turn a workspace-relative timeline asset into a build-root-relative one."""
    candidate = Path(str(value))
    if not candidate.is_absolute():
        candidate = paths.workspace / candidate
    try:
        return candidate.resolve().relative_to(paths.build_root.resolve()).as_posix()
    except (OSError, ValueError):
        return str(value)


def _render_props(
    paths: LessonPaths,
    timeline_path: Path,
    use_timeline: bool,
    shots_path: Path,
) -> Path:
    """Return the props file passed to Remotion.

    Timeline assets are stored workspace-relative (``build/<slug>/...``). The
    renderer reads them from ``public/staging/<slug>/``; rewriting them to
    build-root-relative here keeps default and isolated ``--build-root`` runs
    identical. For burn-in we also render a clean master (``captions=false``);
    the ASS burn happens in a later pipeline stage.
    """
    burn_in = (
        paths.lesson.subtitles.enabled
        and paths.lesson.subtitles.render == "burn_in"
    )
    if not use_timeline:
        if not burn_in:
            return shots_path
        data = load_json(shots_path)
    else:
        data = load_json(timeline_path)
        for key in ("video", "audio"):
            for item in data.get(key) or []:
                asset = item.get("asset") if isinstance(item, dict) else None
                if isinstance(asset, dict) and asset.get("path"):
                    asset["path"] = _build_relative(paths, asset["path"])
        if not burn_in:
            target = paths.build_root / "final" / "render-props.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return target
    data["captions"] = False
    target = paths.build_root / "final" / "render-props.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target


def compose(paths: LessonPaths) -> StageOutcome:
    started = time.monotonic()
    log_dir = paths.build_root / "logs"
    shots_path = paths.build_root / "shots.json"
    timeline_path = paths.build_root / "contracts" / "timeline.spec.json"
    use_timeline = (
        paths.lesson.compose.renderer == "timeline" and timeline_path.is_file()
    )
    output = paths.build_root / "final" / "course-video.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    remotion_root = paths.workspace / "RemotionStudio"

    if not use_timeline and not shots_path.is_file():
        return StageOutcome(
            "compose",
            Status.FAIL,
            errors=["neither timeline.spec.json nor shots.json is available"],
            reason="missing_timeline",
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    stage_args = [
        *which_command("node"),
        "scripts/stage-assets.mjs",
        "--lesson",
        paths.slug,
        "--timeline" if use_timeline else "--shots",
        str(timeline_path if use_timeline else shots_path),
        "--build-root",
        str(paths.build_root),
    ]
    stage = run_command(
        stage_args,
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

    props_path = _render_props(paths, timeline_path, use_timeline, shots_path)
    composition = "CourseTimeline" if use_timeline else "CourseVideo"
    render_timeout = resolve_timeout(paths, "compose")
    render = run_command(
        [
            *which_command("npx"),
            "remotion",
            "render",
            "src/index.ts",
            composition,
            str(output),
            f"--props={props_path}",
            "--timeout=120000",
            *(
                [f"--concurrency={os.environ['COURSEWORKSPACE_RENDER_CONCURRENCY']}"]
                if os.environ.get("COURSEWORKSPACE_RENDER_CONCURRENCY")
                else []
            ),
        ],
        remotion_root,
        timeout=render_timeout,
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
