"""Independent ASR verification for a clean-narration sample.

The final master is the only input: its audio is extracted, transcribed with
word timestamps, and compared with the approved script and the timed cues.
A saved ASR report is evidence, never proof; package verification calls this
module again on the packaged master.

Thresholds live here, once, and are copied into the report.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from course_control.platform.utils import run_command, which_command
from course_control.platform.workspace_layout import runtime_root
from course_control.voice.alignment import Word, _tokens

PASS = "PASS"
FAIL = "FAIL"
INCOMPLETE = "INCOMPLETE"

DEFAULT_MODEL = "small.en"
WER_MAX = 0.10
NUMERIC_WER_MAX = 0.25
TIMING_MAX_S = 0.60
UNCOVERED_MAX_S = 0.30
WORD_MARGIN_MS = 200
GAP_MERGE_MS = 600

STOPWORDS = {
    "a", "an", "the", "of", "but", "and", "for", "those", "that",
    "to", "in", "on", "at", "as", "it", "this", "these", "they", "their",
    "all", "about", "0",
}

THRESHOLDS = {
    "wer_max": WER_MAX,
    "numeric_wer_max": NUMERIC_WER_MAX,
    "timing_deviation_max_s": TIMING_MAX_S,
    "uncovered_speech_max_s": UNCOVERED_MAX_S,
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_audio(master: Path, target: Path, workspace: Path) -> tuple[Path | None, str | None]:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = run_command(
        [
            *which_command("ffmpeg"),
            "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(master), "-vn", "-ac", "1", "-ar", "16000",
            str(target),
        ],
        workspace,
        timeout=1800,
    )
    if result.exit_code != 0 or not target.is_file():
        return None, f"could not extract audio: {result.stderr[-500:]}"
    return target, None


def _transcribe(
    audio: Path,
    workspace: Path,
    *,
    model_size: str,
    language: str,
    device: str,
    compute_type: str,
) -> tuple[list[Word] | None, float | None, str | None, str | None]:
    try:
        import faster_whisper
        from faster_whisper import WhisperModel
    except ImportError:
        return None, None, None, "faster-whisper is not installed"
    download_root = runtime_root(workspace) / "asr" / "models"
    download_root.mkdir(parents=True, exist_ok=True)
    try:
        model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            download_root=str(download_root),
        )
        segments, info = model.transcribe(
            str(audio),
            language=language,
            word_timestamps=True,
            beam_size=5,
            vad_filter=True,
        )
        words = [
            Word(
                start_ms=int(round(word.start * 1000)),
                end_ms=int(round(word.end * 1000)),
                text=word.word,
                probability=float(word.probability or 0.0),
            )
            for segment in segments
            for word in (segment.words or [])
        ]
    except Exception as exc:  # noqa: BLE001 - model/runtime failure is INCOMPLETE
        return None, None, None, f"ASR failed: {exc}"
    version = getattr(faster_whisper, "__version__", None) or "unknown"
    return words, float(info.duration or 0.0), version, None


def _wer_tokens(text: str) -> list[str]:
    # Whisper may split a decimal into separate words; canonicalise both sides
    # to digit strings before comparing.
    text = text.replace(",", "")
    text = re.sub(r"(\d)\s*\.\s*(\d)", lambda m: m.group(1) + m.group(2), text)
    text = re.sub(r"(?<!\d)0\s+(\d)", lambda m: "0" + m.group(1), text)
    text = re.sub(r"(\d{1,3})\s+(\d{3})(?!\d)", lambda m: m.group(1) + m.group(2), text)
    tokens = []
    for token in _tokens(text):
        if token in STOPWORDS:
            continue
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        if token.isdigit():
            token = token.lstrip("0") or "0"
        tokens.append(token)
    return tokens


def _wer(reference: list[str], hypothesis: list[str]) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0
    rows = len(reference) + 1
    cols = len(hypothesis) + 1
    table = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        table[i][0] = i
    for j in range(cols):
        table[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if reference[i - 1] == hypothesis[j - 1] else 1
            table[i][j] = min(
                table[i - 1][j] + 1,
                table[i][j - 1] + 1,
                table[i - 1][j - 1] + cost,
            )
    return table[rows - 1][cols - 1] / len(reference)


def _uncovered(words: list[Word], assigned: set[int]) -> list[dict]:
    groups: list[list[Word]] = []
    current: list[Word] = []
    for index, word in enumerate(words):
        if index in assigned:
            continue
        if current and word.start_ms - current[-1].end_ms > GAP_MERGE_MS:
            groups.append(current)
            current = []
        current.append(word)
    if current:
        groups.append(current)
    uncovered = []
    for group in groups:
        start = group[0].start_ms / 1000
        end = group[-1].end_ms / 1000
        if end - start > UNCOVERED_MAX_S:
            uncovered.append(
                {
                    "start_s": round(start, 3),
                    "end_s": round(end, 3),
                    "duration_s": round(end - start, 3),
                    "text": " ".join(item.text for item in group)[:300],
                }
            )
    return uncovered


def evaluate(cues: list[dict], words: list[Word], audio_duration_s: float | None) -> dict:
    assigned: set[int] = set()
    segments = []
    for cue in cues:
        start_ms = int(round(float(cue["start_s"]) * 1000))
        end_ms = int(round(float(cue["end_s"]) * 1000))
        chosen = []
        for index, word in enumerate(words):
            midpoint = (word.start_ms + word.end_ms) / 2
            if start_ms - WORD_MARGIN_MS <= midpoint <= end_ms + WORD_MARGIN_MS:
                chosen.append(index)
                assigned.add(index)
        reference = _wer_tokens(str(cue.get("tts") or cue.get("en") or ""))
        hypothesis = _wer_tokens(" ".join(words[index].text for index in chosen))
        wer = round(_wer(reference, hypothesis), 4)
        timing = 0.0
        if chosen:
            first = min(words[index].start_ms for index in chosen) / 1000
            last = max(words[index].end_ms for index in chosen) / 1000
            timing = round(max(abs(first - cue["start_s"]), abs(last - cue["end_s"])), 3)
        limit = NUMERIC_WER_MAX if re.search(r"\d", str(cue.get("tts") or cue.get("en") or "")) else WER_MAX
        segments.append(
            {
                "index": cue.get("index"),
                "start_s": cue["start_s"],
                "end_s": cue["end_s"],
                "normalized_text": " ".join(reference),
                "asr_text": " ".join(hypothesis),
                "wer": wer,
                "wer_max": limit,
                "timing_deviation_s": timing,
                "word_count": len(chosen),
            }
        )
    uncovered = _uncovered(words, assigned)
    bad_segments = [
        item
        for item in segments
        if item["wer"] > item["wer_max"] or item["timing_deviation_s"] > TIMING_MAX_S
    ]
    status = PASS if not bad_segments and not uncovered and words else FAIL
    return {
        "status": status,
        "thresholds": dict(THRESHOLDS),
        "audio_duration_s": round(audio_duration_s, 3) if audio_duration_s else None,
        "word_count": len(words),
        "cue_count": len(cues),
        "segments": segments,
        "bad_segments": bad_segments,
        "uncovered_speech": uncovered,
        "uncovered_speech_s": round(sum(item["duration_s"] for item in uncovered), 3),
    }


def run_alignment(
    master: Path,
    cues: list[dict],
    script_path: Path,
    workspace: Path,
    *,
    model_size: str = DEFAULT_MODEL,
    language: str = "en",
    device: str = "cpu",
    compute_type: str = "int8",
    report_path: Path | None = None,
) -> dict:
    workspace = Path(workspace).resolve()
    master = Path(master)
    report = {
        "schema_version": 1,
        "kind": "clean_asr_alignment",
        "generated_at": _now(),
        "engine": "faster-whisper",
        "model": model_size,
        "model_version": None,
        "language": language,
        "audio_source": str(master),
        "master_sha256": _sha(master) if master.is_file() else None,
        "script_path": str(script_path),
        "script_sha256": _sha(script_path) if Path(script_path).is_file() else None,
        "status": INCOMPLETE,
        "errors": [],
        "thresholds": dict(THRESHOLDS),
    }
    target = report_path or (Path(workspace) / "build" / "asr" / "clean-asr-alignment.json")
    if not master.is_file():
        report["errors"].append(f"master not found: {master}")
        _write(report, target)
        return report
    audio = target.parent / "clean-asr-input.wav"
    extracted, error = _extract_audio(master, audio, workspace)
    if extracted is None:
        report["errors"].append(error or "audio extraction failed")
        _write(report, target)
        return report
    words, duration, version, error = _transcribe(
        extracted, workspace,
        model_size=model_size, language=language,
        device=device, compute_type=compute_type,
    )
    if words is None:
        report["errors"].append(error or "ASR returned no words")
        _write(report, target)
        return report
    report["model_version"] = version
    report.update(evaluate(cues, words, duration))
    _write(report, target)
    return report


def _write(report: dict, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
