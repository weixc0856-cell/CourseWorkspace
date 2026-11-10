"""ASR-based speech/subtitle alignment.

The ASR transcript is used as *evidence*, not as subtitle text: it checks that
what the narrator actually says inside each cue window matches the cue's
English text.  A missing ASR run is INCOMPLETE, never PASS.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .paths import LessonPaths
from .utils import run_command, which_command

PASS = "PASS"
WARN = "WARN"
BLOCKED = "BLOCKED"
INCOMPLETE = "INCOMPLETE"

DEFAULT_MODEL = "small.en"
COVERAGE_THRESHOLD = 0.60
WORD_MARGIN_MS = 120


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


_TRAD_TO_SIMP = str.maketrans(
    {
        "麼": "么", "實": "实", "讓": "让", "個": "个", "詞": "词", "這": "这",
        "時": "时", "會": "会", "對": "对", "於": "于", "與": "与", "從": "从",
        "進": "进", "過": "过", "還": "还", "為": "为", "說": "说", "見": "见",
        "點": "点", "數": "数", "據": "据", "強": "强", "連": "连", "變": "变",
        "權": "权", "裡": "里", "層": "层", "問": "问", "應": "应", "該": "该",
        "們": "们", "來": "来", "現": "现", "際": "际", "開": "开", "關": "关",
        "並": "并", "嗎": "吗", "著": "着", "夠": "够", "樣": "样", "後": "后",
        "錯": "错", "陣": "阵", "話": "话", "歸": "归", "訊": "讯", "帶": "带",
        "誰": "谁", "長": "长", "間": "间", "題": "题", "種": "种", "幾": "几",
        "幹": "干", "麼": "么", "個": "个", "麼": "么",
    }
)


def _tokens(text: str) -> list[str]:
    """Tokenize English words or CJK characters for coverage comparison.

    CJK ASR often returns traditional characters while the approved script is
    simplified; normalize the common variants before comparing, otherwise every
    Chinese cue scores zero coverage.
    """
    if re.search(r"[一-鿿]", text):
        normalized = text.translate(_TRAD_TO_SIMP)
        return [ch for ch in normalized if "一" <= ch <= "鿿" or ch.isalnum()]
    cleaned = re.sub(r"[^a-z0-9']+", " ", text.lower())
    return [token for token in cleaned.split() if token]


@dataclass
class Word:
    start_ms: int
    end_ms: int
    text: str
    probability: float

    def as_dict(self) -> dict:
        return {
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "text": self.text,
            "probability": round(self.probability, 3),
        }


def align_cues(
    cues: list[dict],
    words: list[Word],
    *,
    coverage_threshold: float = COVERAGE_THRESHOLD,
    margin_ms: int = WORD_MARGIN_MS,
) -> dict:
    """Assign ASR words to cue windows and measure text coverage."""
    assigned: set[int] = set()
    mismatches: list[dict] = []
    coverages: list[float] = []

    for cue in cues:
        start = int(cue["start_ms"])
        end = int(cue["end_ms"])
        chosen = []
        for index, word in enumerate(words):
            midpoint = (word.start_ms + word.end_ms) / 2
            if start - margin_ms <= midpoint <= end + margin_ms:
                chosen.append(index)
                assigned.add(index)
        reference = _tokens(str(cue.get("en") or cue.get("text") or ""))
        hypothesis = _tokens(" ".join(words[index].text for index in chosen))
        if reference:
            matcher = difflib.SequenceMatcher(None, reference, hypothesis)
            matched = sum(block.size for block in matcher.get_matching_blocks())
            coverage = matched / len(reference)
        else:
            coverage = 0.0
        coverages.append(coverage)
        if coverage < coverage_threshold:
            mismatches.append(
                {
                    "index": cue.get("index"),
                    "start_ms": start,
                    "end_ms": end,
                    "coverage": round(coverage, 3),
                    "cue": " ".join(reference)[:200],
                    "asr": " ".join(hypothesis)[:200],
                }
            )

    uncovered_words = [word for index, word in enumerate(words) if index not in assigned]
    uncovered: list[dict] = []
    current: list[Word] = []
    for word in uncovered_words:
        if current and word.start_ms - current[-1].end_ms > 600:
            if current[-1].end_ms - current[0].start_ms >= 1500:
                uncovered.append(
                    {
                        "start_s": round(current[0].start_ms / 1000, 3),
                        "end_s": round(current[-1].end_ms / 1000, 3),
                        "text": " ".join(item.text for item in current)[:300],
                    }
                )
            current = []
        current.append(word)
    if current and current[-1].end_ms - current[0].start_ms >= 1500:
        uncovered.append(
            {
                "start_s": round(current[0].start_ms / 1000, 3),
                "end_s": round(current[-1].end_ms / 1000, 3),
                "text": " ".join(item.text for item in current)[:300],
            }
        )

    return {
        "cue_count": len(cues),
        "word_count": len(words),
        "mean_coverage": round(sum(coverages) / len(coverages), 3) if coverages else 0.0,
        "mismatches": mismatches,
        "uncovered_speech": uncovered,
    }


def _audio_source(paths: LessonPaths) -> tuple[Path | None, str | None]:
    narration = paths.build_root / "narration" / "narration.wav"
    if narration.is_file():
        return narration, None
    final = paths.build_root / "final" / "course-video-mixed.mp4"
    if not final.is_file():
        final = paths.build_root / "final" / "course-video.mp4"
    if not final.is_file():
        return None, "no narration.wav or final video to transcribe"
    target = paths.build_root / "quality" / "asr-input.wav"
    target.parent.mkdir(parents=True, exist_ok=True)
    result = run_command(
        [
            *which_command("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(final),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(target),
        ],
        paths.workspace,
        timeout=600,
    )
    if result.exit_code != 0 or not target.is_file():
        return None, f"could not extract audio: {result.stderr[-500:]}"
    return target, None


def _load_cues(paths: LessonPaths) -> tuple[list[dict] | None, str | None]:
    # The delivered subtitles are the accepted SRT, not an older bilingual
    # draft left under build/. Audit what was shipped.
    srt_path = paths.subtitles_path()
    if srt_path is not None and srt_path.is_file():
        from .subtitles_qc import CJK_RE, parse_srt

        cues = []
        for cue in parse_srt(srt_path.read_text(encoding="utf-8", errors="replace")):
            en = [line for line in cue["lines"] if not CJK_RE.search(line)]
            cues.append(
                {
                    "index": cue["index"],
                    "start_ms": int(cue["start_ms"]),
                    "end_ms": int(cue["end_ms"]),
                    "en": " ".join(en).strip(),
                }
            )
        if cues:
            return cues, None
    draft_path = paths.build_root / "subtitles" / "bilingual.draft.json"
    if draft_path.is_file():
        try:
            draft = json.loads(draft_path.read_text(encoding="utf-8"))
            return [
                {
                    "index": cue.get("index"),
                    "start_ms": int(cue["start_ms"]),
                    "end_ms": int(cue["end_ms"]),
                    "en": str(cue.get("en") or ""),
                }
                for cue in draft.get("cues", [])
            ], None
        except (OSError, ValueError, KeyError) as exc:
            return None, f"cannot read bilingual draft: {exc}"
    return None, "no subtitles/bilingual.draft.json"


def run_alignment(
    workspace: Path,
    paths: LessonPaths,
    *,
    model_size: str = DEFAULT_MODEL,
    language: str = "en",
    device: str = "cpu",
    compute_type: str = "int8",
) -> tuple[dict, Path]:
    workspace = workspace.resolve()
    report: dict = {
        "schema_version": 1,
        "lesson": paths.slug,
        "generated_at": _now(),
        "model": model_size,
        "language": language,
        "status": INCOMPLETE,
        "errors": [],
    }
    target = paths.build_root / "quality" / "asr-alignment.json"

    def finish() -> tuple[dict, Path]:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return report, target

    cues, error = _load_cues(paths)
    if cues is None:
        report["errors"].append(error or "no cues")
        return finish()
    report["cue_count"] = len(cues)

    audio, error = _audio_source(paths)
    if audio is None:
        report["errors"].append(error or "no audio")
        return finish()
    report["audio"] = str(audio)
    report["audio_sha256"] = _sha(audio)

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        report["errors"].append(
            "faster-whisper is not installed; run `uv sync --project CourseControl "
            "--extra asr`"
        )
        return finish()

    download_root = workspace / "runtime" / "asr" / "models"
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
        report["errors"].append(f"ASR failed: {exc}")
        return finish()

    report["audio_duration_s"] = round(float(info.duration or 0.0), 3)
    result = align_cues(cues, words)
    report.update(result)
    report["words"] = [word.as_dict() for word in words]

    mismatch_ratio = len(result["mismatches"]) / max(1, result["cue_count"])
    uncovered_s = sum(
        item["end_s"] - item["start_s"] for item in result["uncovered_speech"]
    )
    duration_s = max(1.0, float(report["audio_duration_s"] or 1.0))
    if mismatch_ratio > 0.20 or uncovered_s > duration_s * 0.10:
        report["status"] = BLOCKED
    elif result["mismatches"] or result["uncovered_speech"]:
        report["status"] = WARN
    else:
        report["status"] = PASS
    return finish()


__all__ = [
    "BLOCKED",
    "COVERAGE_THRESHOLD",
    "DEFAULT_MODEL",
    "INCOMPLETE",
    "PASS",
    "WARN",
    "Word",
    "align_cues",
    "run_alignment",
]
