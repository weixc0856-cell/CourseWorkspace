"""Whole-course narration orchestration (R1-5C).

One TTS service holds the 50000 lock for the whole run. Each segment is cached
by text/style/mode/reference hashes; audio is normalized to 48 kHz mono and
assembled with explicit pauses. The resulting page spans feed ``collect``.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import wave
from datetime import datetime
from pathlib import Path

from .narrate import (
    TtsError,
    TtsService,
    load_local_paths,
    segment_cache_key,
    synthesize,
)
from .paths import ContractError, LessonPaths
from .utils import notes_blocks, probe_audio, run_command, which_command

SCHEMA_VERSION = 2
DEFAULT_PAGE_PAUSE_MS = 600
SAMPLE_RATE = 48000


class NarrationCourseError(RuntimeError):
    pass


class NarrationCourseBlocked(NarrationCourseError):
    pass


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_page_texts(notes_text: str) -> list[str]:
    """Extract the verbatim narration body for each page.

    Supports both ``#### 逐字口播`` prose blocks (real lessons) and the inline
    ``- **逐字口播**：...`` form used by fixtures.
    """
    texts: list[str] = []
    for label, block in notes_blocks(notes_text):
        match = re.search(
            r"^####\s*逐字口播\s*\n+(.*?)(?=\n####\s|\n###\s|\Z)",
            block,
            re.S | re.M,
        )
        if match:
            value = re.sub(r"(?m)^\s*---\s*$", "", match.group(1))
            texts.append(normalize_text(value))
            continue
        match = re.search(
            r"[-*]\s*\*\*逐字口播\*\*\s*[：:]\s*(.+)",
            block,
        )
        if match:
            value = re.sub(r"(?m)^\s*---\s*$", "", match.group(1))
            texts.append(normalize_text(value))
            continue
        raise NarrationCourseError(f"Slide {label} has no parseable 逐字口播")
    return texts


def check_script_against_notes(notes_text: str, script) -> None:
    page_texts = extract_page_texts(notes_text)
    if len(page_texts) != len(script.pages):
        raise NarrationCourseError(
            f"script has {len(script.pages)} pages but notes has {len(page_texts)}"
        )
    for page, expected in zip(script.pages, page_texts):
        actual = normalize_text(" ".join(segment.text for segment in page.segments))
        if actual != expected:
            raise NarrationCourseError(
                f"slide {page.slide}: script text does not match 逐字口播"
            )


def _normalize_wav(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = run_command(
        [
            *which_command("ffmpeg"),
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(target),
        ],
        source.parent,
        timeout=120,
        log_path=target.with_suffix(".log"),
    )
    if result.exit_code != 0:
        raise NarrationCourseError(
            f"ffmpeg normalize failed for {source}: {result.stderr[-800:]}"
        )
    return target


def _read_frames(path: Path) -> tuple[int, bytes]:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if (channels, width, rate) != (1, 2, SAMPLE_RATE):
        raise NarrationCourseError(
            f"WAV is not 48 kHz mono s16: {path} ({channels}ch, {width * 8}bit, {rate}Hz)"
        )
    return rate, frames


def _silence(ms: int) -> bytes:
    samples = int(SAMPLE_RATE * max(0, ms) / 1000)
    return b"\x00\x00" * samples


def _write_meta(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dry_run(script, rtf_low: float = 9.0, rtf_high: float = 12.5) -> dict:
    words = sum(
        len(re.findall(r"[A-Za-z0-9']+", segment.text))
        for page in script.pages
        for segment in page.segments
    )
    pauses = sum(
        segment.pause_after_ms
        for page in script.pages
        for segment in page.segments
    )
    pauses += DEFAULT_PAGE_PAUSE_MS * len(script.pages)
    audio_seconds = words / 150.0 * 60.0 + pauses / 1000.0
    return {
        "words": words,
        "estimated_audio_seconds": round(audio_seconds, 1),
        "estimated_wall_seconds_low": round(audio_seconds * rtf_low, 1),
        "estimated_wall_seconds_high": round(audio_seconds * rtf_high, 1),
        "pages": len(script.pages),
        "segments": sum(len(page.segments) for page in script.pages),
    }


def _voice_config(lesson, tts: dict) -> tuple[Path, str | None, str]:
    reference = tts.get("voice_ref_en")
    if reference:
        prompt_text = str(tts.get("prompt_text_en") or tts.get("prompt_text") or "").strip() or None
    else:
        reference = tts.get("voice_ref")
        prompt_text = str(tts.get("prompt_text") or "").strip() or None
    if not reference:
        raise NarrationCourseBlocked("config tts.voice_ref_en / tts.voice_ref is empty")
    mode = lesson.narration.mode if lesson.narration else "reference_only"
    return Path(reference), prompt_text, mode


def synthesize_course(
    workspace: Path,
    paths: LessonPaths,
    script,
    *,
    start_service: bool = True,
    wait_timeout_s: int = 1800,
    force: bool = False,
    only_segment: str | None = None,
    sample: bool = False,
    page_limit: int | None = None,
) -> dict:
    workspace = workspace.resolve()
    lesson = paths.lesson
    notes_path = paths.content_path(lesson.content.notes)
    notes_text = notes_path.read_text(encoding="utf-8")
    check_script_against_notes(notes_text, script)

    config = load_local_paths(workspace)
    tts = config.get("tts") or {}
    ai_root = Path(config.get("ai_root") or "").resolve()
    runtime = Path(tts.get("runtime_dir") or (ai_root / "VoxCPM-Runtime"))
    voice_ref, prompt_text, mode = _voice_config(lesson, tts)
    style_enabled = bool(lesson.narration.style_enabled)
    text_frontend = bool(lesson.narration.text_frontend)

    narration_dir = paths.build_root / "narration"
    target_dir = narration_dir / "sample" if sample else narration_dir
    segments_dir = target_dir / "segments"
    normalized_dir = target_dir / "normalized"
    meta_path = target_dir / ("sample.meta.json" if sample else "narration.meta.json")
    narration_path = target_dir / ("sample.wav" if sample else "narration.wav")
    segments_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    script_path = (
        paths.content_path(lesson.authoring.script)
        if lesson.authoring and lesson.authoring.script
        else None
    )
    script_sha = _sha(script_path) if script_path and script_path.is_file() else None

    page_pause_ms = int((script.policy or {}).get("page_pause_ms") or DEFAULT_PAGE_PAUSE_MS)
    segment_records: list[dict] = []
    page_records: list[dict] = []
    cache_hits = 0
    synth_seconds = 0.0
    started = time.monotonic()

    with TtsService(
        workspace,
        ai_root=ai_root,
        runtime_dir=runtime,
        log_path=narration_dir / "tts-server.log",
        start_service=start_service,
        wait_timeout_s=wait_timeout_s,
    ) as service:
        health = service.status() or {}
        engine_version = str(health.get("engine_version") or "")
        sample_rate = int(health.get("sample_rate") or SAMPLE_RATE)
        offset_s = 0.0
        pages = script.pages[:page_limit] if page_limit else script.pages
        for page in pages:
            page_start = offset_s
            for index, segment in enumerate(page.segments):
                normalized = normalized_dir / f"{segment.id}.wav"
                if only_segment and segment.id != only_segment:
                    if not normalized.is_file():
                        raise NarrationCourseBlocked(
                            f"--segment-id {only_segment} requires existing segment {segment.id}"
                        )
                    old_meta = segments_dir / f"{segment.id}.meta.json"
                    details = (
                        json.loads(old_meta.read_text(encoding="utf-8"))
                        if old_meta.is_file()
                        else {}
                    )
                    duration = probe_audio(normalized)
                    details.update(
                        {
                            "segment_id": segment.id,
                            "slide": page.slide,
                            "pause_after_ms": segment.pause_after_ms,
                            "duration_s": round(duration, 3),
                            "start_s": round(offset_s, 3),
                            "end_s": round(offset_s + duration, 3),
                            "cache_hit": True,
                        }
                    )
                    segment_records.append(details)
                    offset_s += duration
                    pause_ms = segment.pause_after_ms
                    if index == len(page.segments) - 1:
                        pause_ms = page_pause_ms
                    offset_s += pause_ms / 1000.0
                    continue
                style = segment.style if (style_enabled and mode == "reference_only") else None
                key = segment_cache_key(
                    segment.text,
                    voice_ref,
                    prompt_text or "",
                    mode=mode,
                    style=style,
                    text_frontend=text_frontend,
                )
                raw = segments_dir / f"{segment.id}.wav"
                meta_file = segments_dir / f"{segment.id}.meta.json"
                cache_hit = False
                details: dict = {}
                if not force and raw.is_file() and meta_file.is_file():
                    old = json.loads(meta_file.read_text(encoding="utf-8"))
                    if old.get("cache_key") == key:
                        cache_hit = True
                        details = old
                        cache_hits += 1
                if not cache_hit:
                    try:
                        details = synthesize(
                            service.base_url,
                            segment.text,
                            voice_ref,
                            prompt_text,
                            raw,
                            mode=mode,
                            reference_wav=voice_ref,
                            style=style,
                            text_frontend=text_frontend,
                        )
                    except TtsError as exc:
                        raise NarrationCourseError(
                            f"segment {segment.id} failed: {exc}"
                        ) from exc
                    synth_seconds += float(details.get("synth_seconds") or 0.0)
                    details = {
                        "schema_version": SCHEMA_VERSION,
                        "lesson": paths.slug,
                        "segment_id": segment.id,
                        "slide": page.slide,
                        "text_sha256": _sha_text(segment.text),
                        "voice_ref": str(voice_ref),
                        "voice_ref_sha256": _sha(voice_ref),
                        "prompt_text_sha256": _sha_text(prompt_text or ""),
                        "cache_key": key,
                        "cache_hit": False,
                        "mode": mode,
                        "style": style,
                        "style_applied": bool(style),
                        "text_frontend": text_frontend,
                        "pause_after_ms": segment.pause_after_ms,
                        "model": "VoxCPM2",
                        "timesteps": 10,
                        "raw_wav": str(raw.relative_to(paths.build_root).as_posix()),
                        **{k: v for k, v in details.items() if k not in {"mode", "style", "style_applied"}},
                    }
                    _write_meta(meta_file, details)
                normalized = normalized_dir / f"{segment.id}.wav"
                _normalize_wav(raw, normalized)
                duration = probe_audio(normalized)
                details["segment_id"] = segment.id
                details["slide"] = page.slide
                details["pause_after_ms"] = segment.pause_after_ms
                details["duration_s"] = round(duration, 3)
                details["start_s"] = round(offset_s, 3)
                details["end_s"] = round(offset_s + duration, 3)
                details["cache_hit"] = cache_hit
                _write_meta(meta_file, details)
                segment_records.append(details)
                offset_s += duration
                pause_ms = segment.pause_after_ms
                if index == len(page.segments) - 1:
                    pause_ms = page_pause_ms
                offset_s += pause_ms / 1000.0
            page_records.append(
                {
                    "slide": page.slide,
                    "planned_s": page.target_seconds,
                    "measured_s": round(offset_s - page_start, 3),
                    "start_s": round(page_start, 3),
                    "end_s": round(offset_s, 3),
                    "drift_s": round((offset_s - page_start) - page.target_seconds, 3),
                }
            )

    # Assemble normalized segments with their pauses.
    with wave.open(str(narration_path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        for index, record in enumerate(segment_records):
            _, frames = _read_frames(normalized_dir / f"{record['segment_id']}.wav")
            out.writeframes(frames)
            last_in_page = (
                index + 1 == len(segment_records)
                or segment_records[index + 1]["slide"] != record["slide"]
            )
            pause_ms = page_pause_ms if last_in_page else int(record.get("pause_after_ms") or 0)
            out.writeframes(_silence(pause_ms))

    total_duration = probe_audio(narration_path)
    meta = {
        "schema_version": SCHEMA_VERSION,
        "lesson": paths.slug,
        "generated_at": _now(),
        "mode": mode,
        "style_enabled": style_enabled,
        "text_frontend": text_frontend,
        "voice": {
            "ref_audio": str(voice_ref),
            "ref_audio_sha256": _sha(voice_ref),
            "language": script.language,
            "prompt_text_sha256": _sha_text(prompt_text or ""),
        },
        "tts": {
            "model": "VoxCPM2",
            "engine_version": engine_version,
            "timesteps": 10,
            "cfg": 2.0,
            "sample_rate": sample_rate,
        },
        "source": {
            "script_path": (
                script_path.relative_to(paths.lesson_dir).as_posix() if script_path else None
            ),
            "script_sha256": script_sha,
            "notes_sha256": _sha(notes_path),
        },
        "pages": page_records,
        "segments": segment_records,
        "assembly": {
            "file": "sample.wav" if sample else "narration.wav",
            "duration_s": round(total_duration, 3),
            "timeline_duration_s": round(total_duration, 3),
            "tail_pad_s": 0.0,
            "sha256": _sha(narration_path),
        },
        "sample": {
            "enabled": sample,
            "pages": len(pages),
            "page_limit": page_limit,
        },
        "totals": {
            "segments": len(segment_records),
            "cache_hits": cache_hits,
            "synth_seconds": round(synth_seconds, 1),
            "audio_seconds": round(total_duration, 3),
            "wall_seconds": round(time.monotonic() - started, 1),
        },
    }
    _write_meta(meta_path, meta)
    return meta
