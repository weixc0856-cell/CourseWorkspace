from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

from ..contracts import Status
from ..paths import LessonPaths
from ..utils import probe_media, run_command, which_command
from .base import StageOutcome


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ass_filter(ass_path: Path) -> str:
    # Windows: escape the drive colon or ffmpeg parses it as an option.
    return "ass='" + ass_path.as_posix().replace(":", "\\:") + "'"


def _command(clean: Path, output: Path, ass: Path, encoder: str) -> list[str]:
    base = [
        *which_command("ffmpeg"),
        "-y",
        "-i",
        str(clean),
        "-vf",
        _ass_filter(ass),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
    ]
    if encoder == "qsv":
        video = ["-c:v", "h264_qsv", "-global_quality", "20", "-preset", "medium"]
    else:
        video = ["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p"]
    return [*base, *video, "-c:a", "copy", "-movflags", "+faststart", str(output)]


def burn_subtitles(paths: LessonPaths, *, encoder: str = "auto") -> StageOutcome:
    started = time.monotonic()
    clean = paths.build_root / "final" / "course-video.mp4"
    ass = paths.build_root / "subtitles.ass"
    output = paths.build_root / "final" / "course-video-captioned.mp4"
    logs = paths.build_root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    if not clean.is_file():
        return StageOutcome(
            "burn_subtitles",
            Status.FAIL,
            errors=[f"clean master not found: {clean}"],
            reason="missing_clean_master",
        )
    if not ass.is_file():
        return StageOutcome(
            "burn_subtitles",
            Status.FAIL,
            errors=[f"ASS subtitles not found: {ass}"],
            reason="missing_ass",
        )

    clean_info = probe_media(clean)
    attempts: list[str] = []
    encoders = [encoder] if encoder in ("qsv", "libx264") else ["qsv", "libx264"]
    for name in encoders:
        result = run_command(
            _command(clean, output, ass, name),
            paths.workspace,
            timeout=3600,
            log_path=logs / f"burn-{name}.log",
        )
        attempts.append(f"{name}: exit {result.exit_code}")
        if result.exit_code != 0 or not output.is_file():
            output.unlink(missing_ok=True)
            continue
        info = probe_media(output)
        frame = 1.0 / (clean_info.fps or 30.0)
        problems: list[str] = []
        if clean_info.duration is not None and info.duration is not None:
            if abs(info.duration - clean_info.duration) > frame + 0.05:
                problems.append(
                    f"duration {info.duration:.3f}s differs from clean {clean_info.duration:.3f}s"
                )
        if (info.width, info.height) != (clean_info.width, clean_info.height):
            problems.append(
                f"resolution {info.width}x{info.height} != {clean_info.width}x{clean_info.height}"
            )
        if info.fps != clean_info.fps:
            problems.append(f"fps {info.fps} != {clean_info.fps}")
        if info.has_audio != clean_info.has_audio:
            problems.append("audio stream presence differs from clean master")
        record = {
            "schema_version": 1,
            "lesson": paths.slug,
            "generated_at": _now(),
            "input": clean.relative_to(paths.build_root).as_posix(),
            "output": output.relative_to(paths.build_root).as_posix(),
            "subtitles_ass": ass.relative_to(paths.build_root).as_posix(),
            "encoder": name,
            "encoder_fallback": name != encoders[0],
            "attempts": attempts,
            "command": _command(clean, output, ass, name),
            "duration_s": info.duration,
            "video_duration_s": clean_info.duration,
            "fps": info.fps,
            "resolution": [info.width, info.height],
            "has_audio": info.has_audio,
            "sha256": _sha(output),
            "problems": problems,
        }
        (paths.build_root / "final" / "burn.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if problems:
            return StageOutcome(
                "burn_subtitles",
                Status.FAIL,
                outputs=[output],
                errors=problems,
                reason="burn_validation_failed",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        return StageOutcome(
            "burn_subtitles",
            Status.PASS,
            outputs=[output],
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    return StageOutcome(
        "burn_subtitles",
        Status.FAIL,
        errors=[f"all encoders failed: {attempts}"],
        reason="burn_failed",
        duration_ms=int((time.monotonic() - started) * 1000),
    )
