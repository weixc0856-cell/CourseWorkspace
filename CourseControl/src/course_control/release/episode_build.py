"""Record the episode render as the build of record.

Episode-based lessons render the Remotion ``Episode`` composition rather than
the deck pipeline, so they had no ``final/build-report.json``; the quality gate
then compared an old deck report against the new film and called it stale.
This module records the episode build from the artifacts that actually exist:
every file is hashed, every media file is probed, and the checks compare the
film with the declared episode timeline.  It records, it does not invent.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from course_control.content.contracts import (
    Artifact,
    BuildReport,
    CheckRecord,
    StageRecord,
    Status,
)
from course_control.content.paths import LessonPaths
from course_control.delivery.report import toolchain_versions
from course_control.platform.utils import probe_media

DURATION_TOLERANCE_S = 0.1


class EpisodeBuildError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _audio_seconds(path: Path) -> float | None:
    """Duration of an audio file; probe_media expects a video stream."""
    if path.suffix.lower() == ".wav":
        try:
            import wave

            with wave.open(str(path), "rb") as handle:
                return handle.getnframes() / float(handle.getframerate())
        except (OSError, wave.Error, EOFError):
            return None
    try:
        return probe_media(path).duration
    except Exception:  # noqa: BLE001
        return None


def _artifact(paths: LessonPaths, path: Path) -> Artifact:
    relative = path.resolve().relative_to(paths.build_root.resolve()).as_posix()
    probe = None
    if path.suffix.lower() in {".mp4", ".png", ".jpg", ".jpeg", ".webm", ".wav", ".mp3"}:
        try:
            probe = probe_media(path).as_dict()
        except Exception:  # noqa: BLE001
            probe = None
    return Artifact(
        path=relative,
        kind=path.suffix.lower().lstrip(".") or "file",
        size_bytes=path.stat().st_size,
        sha256=_sha256(path),
        probe=probe,
    )


def record_episode_build(
    paths: LessonPaths,
    *,
    video: Path,
    narration: Path | None = None,
    captioned: Path | None = None,
    timing: Path | None = None,
    run_id: str | None = None,
) -> tuple[BuildReport, Path]:
    """Write final/build-report.json for the episode film."""
    video = Path(video).resolve()
    if not video.is_file():
        raise EpisodeBuildError(f"episode film not found: {video}")
    timing_path = timing or (paths.workspace / "RemotionStudio" / "src" / "episode" / "timing.json")
    if not timing_path.is_file():
        raise EpisodeBuildError(f"episode timing not found: {timing_path}")
    episode = json.loads(timing_path.read_text(encoding="utf-8"))
    expected_seconds = float(episode.get("total_seconds") or 0.0)
    expected_fps = int(episode.get("fps") or paths.lesson.outputs.fps)
    expected_size = tuple(paths.lesson.outputs.resolution)

    info = probe_media(video)
    checks: list[CheckRecord] = []

    def check(check_id: str, ok: bool, expected: str, actual: str, detail: str | None = None) -> None:
        checks.append(
            CheckRecord(
                id=check_id,
                status=Status.PASS if ok else Status.FAIL,
                expected=expected,
                actual=actual,
                detail=detail,
            )
        )

    duration = float(info.duration or 0.0)
    check(
        "episode.duration",
        abs(duration - expected_seconds) <= DURATION_TOLERANCE_S,
        f"{expected_seconds:.3f}s ±{DURATION_TOLERANCE_S}s",
        f"{duration:.3f}s",
    )
    check("episode.fps", int(round(info.fps or 0)) == expected_fps, str(expected_fps), str(info.fps))
    check(
        "episode.resolution",
        (info.width, info.height) == expected_size,
        f"{expected_size[0]}x{expected_size[1]}",
        f"{info.width}x{info.height}",
    )
    if narration is not None:
        narration = Path(narration).resolve()
        if not narration.is_file():
            check("episode.audio", False, "narration track present", str(narration))
        else:
            audio_seconds = _audio_seconds(narration)
            check("episode.audio", info.has_audio, "film carries audio", f"audio={info.has_audio}")
            check(
                "episode.audio_duration",
                audio_seconds is not None
                and abs(audio_seconds - duration) <= DURATION_TOLERANCE_S,
                f"{duration:.3f}s ±{DURATION_TOLERANCE_S}s",
                f"{audio_seconds:.3f}s" if audio_seconds is not None else "unreadable",
                detail=str(narration),
            )

    started = _now()
    stages: list[StageRecord] = [
        StageRecord(
            name="render:episode",
            status=Status.PASS,
            started_at=started,
            finished_at=started,
            outputs=[str(video)],
            warnings=["recorded from the rendered film; the renderer command is in the episode log"],
        )
    ]
    if narration is not None and Path(narration).is_file():
        stages.append(
            StageRecord(
                name="mux:narration",
                status=Status.PASS,
                started_at=started,
                finished_at=started,
                outputs=[str(Path(narration).resolve())],
                reason="narration track muxed into the film",
            )
        )
    subtitles_ass = paths.build_root / "subtitles.ass"
    if captioned is not None:
        captioned = Path(captioned).resolve()
        if captioned.is_file():
            stages.append(
                StageRecord(
                    name="burn_subtitles",
                    status=Status.PASS,
                    started_at=started,
                    finished_at=started,
                    outputs=[str(captioned), str(subtitles_ass)],
                    warnings=["ASS rendered from build/subtitles/bilingual.draft.json"],
                )
            )
        else:
            stages.append(
                StageRecord(
                    name="burn_subtitles",
                    status=Status.SKIPPED,
                    started_at=started,
                    finished_at=started,
                    reason=f"captioned film not found: {captioned}",
                )
            )

    candidates: list[Path] = [video]
    if captioned is not None and captioned.is_file():
        candidates.append(captioned)
    candidates.extend(
        path
        for path in (
            Path(narration).resolve() if narration is not None and Path(narration).is_file() else None,
            subtitles_ass if subtitles_ass.is_file() else None,
            paths.build_root / "subtitles" / "bilingual.draft.json",
        )
        if path is not None and Path(path).is_file()
    )
    final_dir = paths.build_root / "final"
    if final_dir.is_dir():
        candidates.extend(
            path
            for path in final_dir.glob("*")
            if path.is_file() and path.name != "build-report.json"
        )
    seen: set[Path] = set()
    artifacts = []
    for path in candidates:
        path = path.resolve()
        if path in seen:
            continue
        try:
            path.relative_to(paths.build_root.resolve())
        except ValueError:
            continue
        seen.add(path)
        artifacts.append(_artifact(paths, path))

    statuses = [stage.status for stage in stages] + [item.status for item in checks]
    if any(status == Status.FAIL for status in statuses):
        verdict = "fail"
    elif any(status in (Status.SKIPPED, Status.NOT_RUN) for status in statuses):
        verdict = "incomplete"
    else:
        verdict = "pass"
    failures: list[str] = []
    for stage in stages:
        if stage.status == Status.FAIL:
            failures.append(f"{stage.name}: {stage.reason or 'failed'}")
    for item in checks:
        if item.status == Status.FAIL:
            failures.append(f"{item.id}: expected {item.expected}, got {item.actual}")
    if verdict != "pass" and not failures:
        failures.append(f"verdict is {verdict} but no failure detail was recorded")

    report = BuildReport(
        run_id=run_id or f"episode-{datetime.now().strftime('%Y%m%dT%H%M%S')}",
        lesson=paths.slug,
        started_at=started,
        finished_at=_now(),
        toolchain=toolchain_versions(paths.workspace),
        stages=stages,
        artifacts=artifacts,
        checks=checks,
        verdict=verdict,
        failures=failures,
    )
    target = paths.build_root / "final" / "build-report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report, target


__all__ = ["EpisodeBuildError", "record_episode_build"]
