"""Dialogue Lock: the narration the subtitles and the mix were cut against.

The lock records what was actually spoken: the script that produced it, the
audio, the voice assets that shaped it, and how the measured segments line up
with the subtitle cues.  It never blocks a re-record; it makes an unrecorded
change visible.

Its most useful check is ``script_matches_narration``: a script edited after
synthesis means the subtitles and the mix are about to consume a stale voice.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..media import sha256_file
from ..paths import LessonPaths
from ..srt import parse_srt_strict
from .dependencies import LockError

LOCK_NAME = "dialogue.lock.json"


def snapshot(paths: LessonPaths) -> dict:
    meta_path = paths.build_root / "narration" / "narration.meta.json"
    if not meta_path.is_file():
        raise LockError(
            f"no narration yet: {meta_path} (run `course-control narration-build` first)"
        )
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LockError(f"narration meta is unreadable: {meta_path}: {exc}") from exc

    audio = paths.build_root / "narration" / "narration.wav"
    script_rel = paths.lesson.authoring.script if paths.lesson.authoring else None
    script = paths.content_path(script_rel) if script_rel else None
    subtitles = paths.subtitles_path()

    assets_meta = meta.get("assets") or {}
    hashes = {
        "script": _sha(script),
        "narration": _sha(audio),
        "voice_bible": (assets_meta.get("voice_bible") or {}).get("sha256") or "",
        "lexicon": (assets_meta.get("lexicon") or {}).get("sha256") or "",
        "subtitles": _sha(subtitles),
    }

    segments = [
        {
            "id": item.get("segment_id") or item.get("id"),
            "slide": item.get("slide"),
            "start_s": item.get("start_s"),
            "end_s": item.get("end_s"),
            "duration_s": item.get("duration_s"),
            "text_sha256": item.get("text_sha256"),
            "spoken_text_sha256": item.get("spoken_text_sha256"),
            "lexicon_applied": item.get("lexicon_applied") or [],
        }
        for item in meta.get("segments") or []
    ]

    checks: list[dict] = []
    recorded = (meta.get("source") or {}).get("script_sha256")
    current = hashes["script"]
    checks.append(
        {
            "id": "script_matches_narration",
            "status": "pass" if recorded and recorded == current else "fail",
            "detail": None
            if recorded == current
            else "the script changed after synthesis; re-run narration-build",
        }
    )
    checks.append(
        {
            "id": "narration_file",
            "status": "pass" if audio.is_file() else "fail",
            "detail": None if audio.is_file() else f"missing {audio}",
        }
    )
    checks.append(
        {
            "id": "assets_recorded",
            "status": "pass" if int(meta.get("schema_version") or 0) >= 3 else "warn",
            "detail": None
            if int(meta.get("schema_version") or 0) >= 3
            else "narration meta predates voice assets (schema < 3)",
        }
    )

    mapping = _map_cues(subtitles, segments)
    checks.append(
        {
            "id": "subtitles_mapped",
            "status": mapping["status"],
            "detail": mapping["detail"],
        }
    )

    return {
        "schema_version": 1,
        "lesson": paths.slug,
        "kind": "dialogue",
        "script": {"path": script_rel, "sha256": hashes["script"]},
        "narration": {
            "file": "narration/narration.wav" if audio.is_file() else None,
            "sha256": hashes["narration"],
            "duration_s": meta.get("duration_s"),
        },
        "voice_bible": assets_meta.get("voice_bible"),
        "lexicon": assets_meta.get("lexicon"),
        "tts": meta.get("tts"),
        "segments": segments,
        "subtitles": {
            "file": paths.subtitles_path().name if subtitles and subtitles.is_file() else None,
            "sha256": hashes["subtitles"],
            **mapping,
        },
        "hashes": hashes,
        "checks": checks,
    }


def write(
    paths: LessonPaths,
    *,
    approved_by: str | None = None,
    note: str | None = None,
) -> dict:
    lock = snapshot(paths)
    lock["locked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lock["review"] = {"approved_by": approved_by, "note": note}
    if not approved_by:
        lock["checks"].append(
            {
                "id": "review_recorded",
                "status": "warn",
                "detail": "no --approved-by: the lock has no listening sign-off",
            }
        )
    path = lock_path(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": path, "lock": lock}


def load(paths: LessonPaths) -> dict | None:
    path = lock_path(paths)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LockError(f"dialogue lock is unreadable: {path}: {exc}") from exc


def lock_path(paths: LessonPaths) -> Path:
    return paths.build_root / "locks" / LOCK_NAME


def _map_cues(subtitles: Path | None, segments: list[dict]) -> dict:
    """Which subtitle cues fall inside a measured narration segment."""
    if subtitles is None or not subtitles.is_file():
        return {"status": "warn", "cues": 0, "unmapped": [], "detail": "no subtitle file"}
    try:
        cues = parse_srt_strict(subtitles.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - a broken SRT is a finding, not a crash
        return {"status": "warn", "cues": 0, "unmapped": [], "detail": f"unreadable SRT: {exc}"}
    windows = [
        (float(item.get("start_s") or 0.0), float(item.get("end_s") or 0.0), item.get("id"))
        for item in segments
        if item.get("start_s") is not None and item.get("end_s") is not None
    ]
    unmapped = []
    for cue in cues:
        second = cue.start_ms / 1000.0
        if not any(start <= second < end for start, end, _id in windows):
            unmapped.append(cue.index)
    status = "pass" if not unmapped else "warn"
    return {
        "status": status,
        "cues": len(cues),
        "unmapped": unmapped[:20],
        "detail": None if not unmapped else f"{len(unmapped)} cue(s) outside every segment",
    }


def _sha(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    return sha256_file(path)
