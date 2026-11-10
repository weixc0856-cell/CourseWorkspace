"""Scripted production counts.

Manual counts drift: ACCEPTANCE said 412 tests when the suite had 438, and
"27 shots" meant 27 beat-sheet entries for one renderable scene.  These counts
come from files and reports, not from prose, and are written to
``build/<slug>/quality/stats.json`` for reuse in documents.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .paths import LessonPaths
from .utils import count_srt_cues


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _page_count(path: Path) -> int | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    return len(re.findall(r"^##\s+\S", text, flags=re.M))


def lesson_stats(paths: LessonPaths) -> dict:
    lesson = paths.lesson
    build_root = paths.build_root
    pages = _page_count(paths.content_path(lesson.content.slides))

    production_shots = None
    if paths.production is not None:
        production_shots = sum(len(sequence.shots) for sequence in paths.production.sequences)

    meta = _load(build_root / "narration" / "narration.meta.json")
    segments = meta.get("segments") or []
    audio_assets = len(segments)
    if meta.get("pages"):
        duration = float(meta["pages"][-1].get("end_s") or 0.0)
    elif segments:
        duration = max(float(item.get("end_s") or 0.0) for item in segments)
    else:
        duration = None

    cues = None
    subtitle_path = paths.subtitles_path()
    if subtitle_path is not None and subtitle_path.is_file():
        cues = count_srt_cues(subtitle_path)
    elif (build_root / "subtitles.srt").is_file():
        cues = count_srt_cues(build_root / "subtitles.srt")

    media_qc = _load(build_root / "quality" / "media-qc.json")
    quality = _load(build_root / "quality" / "quality-report.json")
    package = _load(build_root / "package" / "manifest.json")
    build_report = _load(build_root / "final" / "build-report.json")

    storyboard_shots = len(paths.storyboard.shots)
    authority = "production.yaml" if lesson.compose.mode == "shots" else "storyboard.yaml"
    unit = "shot" if lesson.compose.mode == "shots" else "page"
    return {
        "schema_version": 1,
        "lesson": paths.slug,
        "mode": lesson.compose.mode,
        "authority": authority,
        "production_unit": unit,
        "counts": {
            "pages": pages,
            "storyboard_shots": storyboard_shots,
            "production_shots": production_shots,
            "audio_assets": audio_assets,
            "subtitle_cues": cues,
            "delivery_files": len(package.get("files") or []),
            "build_artifacts": len(build_report.get("artifacts") or []),
        },
        "duration_seconds": round(duration, 3) if duration else None,
        "status": {
            "build": build_report.get("verdict"),
            "media_qc": media_qc.get("status"),
            "quality": (quality.get("states") or {}),
            "release_approved": (quality.get("states") or {}).get("RELEASE_APPROVED"),
        },
        "sources": {
            "slides": lesson.content.slides,
            "storyboard": str(paths.storyboard_source) if paths.storyboard_source else None,
            "narration_meta": (build_root / "narration" / "narration.meta.json").is_file(),
            "package": (build_root / "package" / "manifest.json").is_file(),
        },
    }


def write_stats(paths: LessonPaths, payload: dict) -> Path:
    target = paths.build_root / "quality" / "stats.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target


__all__ = ["lesson_stats", "write_stats"]
