"""Animatic artefacts: manifest, timeline, contact sheet and the report.

The report answers one question: can this animatic be trusted as a preview?
That means the picture must be as long as the timeline, every unit must have a
picture, and the narration must not drift against the frame grid.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from course_control.quality.code_video_qc import contact_sheet
from course_control.content.paths import LessonPaths
from course_control.platform.media import probe_media
from course_control.animatic.timeline import Timeline

# Picture and audio may disagree by less than a frame and still be in sync.
# Long lessons are allowed the same slack as a fraction of their runtime: a
# 21-minute cut that is 0.6s short at the tail is still in sync throughout.
AUDIO_TOLERANCE_S = 0.10
AUDIO_TOLERANCE_RATIO = 0.001
PICTURE_TOLERANCE_S = 0.10
# Acceptance rejects a drift above roughly 2.5 frames at 30 fps.  The preview
# keeps its wider tolerance so a long cut is not failed over rounding, but a
# drift that acceptance would reject must never disappear silently (P5 lesson 3).
ACCEPTANCE_AUDIO_DRIFT_S = 0.083


def write_artifacts(
    paths: LessonPaths,
    timeline: Timeline,
    result: dict,
    *,
    sheet: bool = True,
) -> dict:
    out: Path = result["out"]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    segments = result["segments"]
    video: Path = result["video"]

    (out / "timeline.json").write_text(
        json.dumps(timeline.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    picture = _probe(video)
    audio = result.get("audio")
    checks = _checks(timeline, segments, picture, audio)

    sheet_path = None
    if sheet and video.is_file():
        step = max(2.0, timeline.duration_s / 12) if timeline.duration_s else 2.0
        try:
            sheet_path = contact_sheet(
                video, out / "contact-sheet.png", step=step, cols=4, thumb=320, workspace=paths.build_root
            )
        except Exception as exc:  # noqa: BLE001 - a contact sheet is nice to have
            checks.append(
                {"id": "contact_sheet", "status": "warn", "detail": f"{type(exc).__name__}: {exc}"}
            )

    manifest = {
        "schema_version": 1,
        "lesson": paths.slug,
        "generated_at": now,
        "mode": timeline.mode,
        "fps": timeline.fps,
        "size": [timeline.width, timeline.height],
        "duration_s": round(timeline.duration_s, 3),
        "video": {"file": video.name, **picture},
        "audio": audio,
        "units": len(timeline.units),
        "cache": {
            "reused": sum(1 for segment in segments if segment.reused),
            "encoded": sum(1 for segment in segments if not segment.reused),
        },
        "segments": [
            {
                "id": segment.unit.id,
                "file": segment.path.name,
                "frames": segment.frames,
                "reused": segment.reused,
                "key": segment.key,
                "status": segment.status,
            }
            for segment in segments
        ],
    }
    (out / "animatic.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = {
        "schema_version": 1,
        "lesson": paths.slug,
        "generated_at": now,
        # A warn (silent preview, short source clip) is a caveat, not a failure.
        "ok": all(check["status"] != "fail" for check in checks),
        "checks": checks,
        "video": {"file": video.name, **picture},
        "audio": audio,
        "contact_sheet": sheet_path.name if sheet_path else None,
        "warnings": list(timeline.warnings),
        "units": [
            {
                **segment.unit.as_dict(),
                "frames": segment.frames,
                "status": segment.status,
                "detail": segment.detail,
                "reused": segment.reused,
            }
            for segment in segments
        ],
    }
    (out / "animatic-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _probe(path: Path) -> dict:
    try:
        info = probe_media(path)
    except Exception as exc:  # noqa: BLE001 - report the failure rather than raise
        return {"duration": None, "width": None, "height": None, "error": str(exc)}
    video = info.first("video")
    return {
        "duration": info.duration_s,
        "width": video.width if video else None,
        "height": video.height if video else None,
    }


def _checks(timeline: Timeline, segments: list, picture: dict, audio: dict | None) -> list[dict]:
    checks: list[dict] = []

    placeholders = [segment.unit.id for segment in segments if segment.status == "placeholder"]
    checks.append(
        {
            "id": "pictures",
            "status": "pass" if not placeholders else "fail",
            "expected": "every unit has a picture",
            "actual": "ok" if not placeholders else f"{len(placeholders)} placeholder(s)",
            "detail": ", ".join(placeholders[:8]) or None,
        }
    )

    expected = timeline.duration_s
    actual = picture.get("duration")
    delta = None if actual is None else actual - expected
    checks.append(
        {
            "id": "picture_duration",
            "status": "pass" if delta is not None and abs(delta) <= PICTURE_TOLERANCE_S else "fail",
            "expected": f"{expected:.2f}s ± {PICTURE_TOLERANCE_S:.2f}s",
            "actual": "unknown" if actual is None else f"{actual:.2f}s",
            "detail": None if delta is None else f"delta {delta:+.2f}s",
        }
    )

    if audio is None:
        checks.append(
            {"id": "audio_sync", "status": "warn", "expected": "narration present", "actual": "silent animatic"}
        )
    else:
        audio_duration = audio.get("duration_s")
        drift = None if audio_duration is None else audio_duration - expected
        tolerance = max(AUDIO_TOLERANCE_S, expected * AUDIO_TOLERANCE_RATIO)
        checks.append(
            {
                "id": "audio_sync",
                "status": "pass" if drift is not None and abs(drift) <= tolerance else "fail",
                "expected": f"narration within {tolerance:.2f}s of the picture",
                "actual": "unknown" if audio_duration is None else f"{audio_duration:.2f}s",
                "detail": None if drift is None else f"delta {drift:+.2f}s",
            }
        )
        acceptance_ok = drift is not None and abs(drift) <= ACCEPTANCE_AUDIO_DRIFT_S
        checks.append(
            {
                "id": "audio_sync_acceptance",
                "status": "pass" if acceptance_ok else "warn",
                "expected": f"|delta| <= {ACCEPTANCE_AUDIO_DRIFT_S:.3f}s (verify threshold)",
                "actual": "unknown" if drift is None else f"delta {drift:+.3f}s",
                "detail": (
                    None
                    if acceptance_ok
                    else "preview tolerance is wider; verify rejects this drift"
                ),
            }
        )

    short = [segment.unit.id for segment in segments if segment.status == "short_source"]
    checks.append(
        {
            "id": "source_length",
            "status": "pass" if not short else "warn",
            "expected": "clips at least as long as their slot",
            "actual": "ok" if not short else f"{len(short)} short clip(s)",
            "detail": ", ".join(short[:8]) or None,
        }
    )
    return checks
