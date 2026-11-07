"""Bilingual subtitle planning, translation, ASS/SRT/VTT writing (R1-5D)."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field

from .contracts import StrictModel
from .paths import LessonPaths

ABBREV = {"mr.", "mrs.", "ms.", "dr.", "prof.", "st.", "jr.", "sr.", "vs.", "etc.", "e.g.", "i.e."}
SENTENCE_END = re.compile(r"[.!?][\"'’”)\]]*$")


class SubtitleError(RuntimeError):
    pass


class SubtitleBlocked(SubtitleError):
    pass


@dataclass(frozen=True)
class CuePolicy:
    en_max_chars_per_line: int = 42
    zh_max_chars_per_line: int = 15
    max_lines: int = 2
    min_seconds: float = 1.0
    max_seconds: float = 6.0
    zh_cps_max: float = 9.0

    def gap_ms(self, fps: float) -> int:
        return int(math.ceil(2 * 1000 / fps)) if fps > 0 else 67


class TranslatedCue(StrictModel):
    index: int = Field(ge=1)
    zh: str = Field(min_length=1)


class TranslationReply(StrictModel):
    cues: list[TranslatedCue]


class BilingualCue(StrictModel):
    index: int = Field(ge=1)
    slide: int = Field(ge=1)
    segment_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    en: str = Field(min_length=1)
    zh: str = Field(min_length=1)
    en_lines: list[str] = Field(min_length=1)
    zh_lines: list[str] = Field(min_length=1)


class BilingualDraft(StrictModel):
    schema_version: Literal[1] = 1
    lesson: str
    languages: dict[str, str]
    policy: dict
    cues: list[BilingualCue]
    counts: dict
    translation: dict


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    merged: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if merged:
            prev = merged[-1]
            bare = prev.lower().rstrip("\"'’”)]")
            if bare.split()[-1] in ABBREV if bare.split() else False:
                merged[-1] = prev + " " + part
                continue
        merged.append(part)
    return merged or [text.strip()]


def _clauses(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    pieces = re.split(r"(?<=[,;:])\s+", text)
    result: list[str] = []
    for piece in pieces:
        if len(piece) <= max_chars:
            result.append(piece)
            continue
        words = piece.split()
        current: list[str] = []
        for word in words:
            if current and len(" ".join(current + [word])) > max_chars:
                result.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            result.append(" ".join(current))
    return result or [text]


def _merge_to_fit(chunks: list[str], total_s: float, policy: CuePolicy) -> list[str]:
    """Merge chunks until every chunk's proportional duration is >= min_seconds."""
    chunks = list(chunks)
    while len(chunks) > 1:
        weights = [max(1, len(chunk)) for chunk in chunks]
        total_weight = sum(weights)
        allocations = [total_s * weight / total_weight for weight in weights]
        smallest = min(range(len(chunks)), key=lambda i: allocations[i])
        if allocations[smallest] >= policy.min_seconds:
            break
        if smallest == 0:
            partner = 1
        elif smallest == len(chunks) - 1:
            partner = len(chunks) - 2
        else:
            partner = smallest - 1 if allocations[smallest - 1] <= allocations[smallest + 1] else smallest + 1
        left, right = sorted((smallest, partner))
        chunks[left : right + 1] = [chunks[left] + " " + chunks[right]]
    return chunks


def _split_to_fit(chunks: list[str], total_s: float, policy: CuePolicy) -> list[str]:
    chunks = list(chunks)
    while any(total_s / len(chunks) > policy.max_seconds or len(chunk) > policy.en_max_chars_per_line * policy.max_lines for chunk in chunks):
        if len(chunks) >= 200:
            break
        if len(chunks) > 1 and total_s / (len(chunks) + 1) < policy.min_seconds:
            break
        if len(chunks) == 1 and total_s / 2 < policy.min_seconds and len(chunks[0]) <= policy.en_max_chars_per_line * policy.max_lines * 2:
            break
        target = max(range(len(chunks)), key=lambda i: len(chunks[i]))
        pieces = _clauses(chunks[target], max(20, len(chunks[target]) // 2))
        if len(pieces) <= 1:
            words = chunks[target].split()
            if len(words) <= 1:
                break
            mid = len(words) // 2
            pieces = [" ".join(words[:mid]), " ".join(words[mid:])]
        chunks[target : target + 1] = pieces
    return chunks


def _wrap(text: str, max_chars: int, max_lines: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _wrap_zh(text: str, max_chars: int, max_lines: int) -> list[str]:
    text = text.replace("\n", "").strip()
    if len(text) <= max_chars:
        return [text]
    lines: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            lines.append(remaining)
            break
        cut = max_chars
        for punct in "，；：、。！？":
            pos = remaining.rfind(punct, 0, max_chars + 1)
            if pos >= max_chars // 2:
                cut = min(pos + 1, max_chars)
                break
        # Do not split a Latin word such as "Transformer" across lines.
        while (
            0 < cut < len(remaining)
            and re.match(r"[A-Za-z0-9]", remaining[cut - 1])
            and re.match(r"[A-Za-z0-9]", remaining[cut])
        ):
            cut -= 1
        if cut <= 0:
            cut = max_chars
        lines.append(remaining[:cut])
        remaining = remaining[cut:]
    return lines or [""]


def _best_split_en(text: str) -> int:
    midpoint = len(text) // 2
    punctuation = [
        index for index, char in enumerate(text)
        if char in ",;:—" and 8 <= index <= len(text) - 8
    ]
    if punctuation:
        return min(punctuation, key=lambda index: abs(index - midpoint)) + 1
    words = text.split()
    if len(words) < 4:
        return max(1, len(text) // 2)
    cursor = 0
    best = len(text) // 2
    for word in words[:-1]:
        cursor += len(word)
        if abs(cursor - midpoint) < abs(best - midpoint):
            best = cursor
        cursor += 1
    return max(1, min(len(text) - 1, best))


def _best_split_zh(text: str, ratio: float) -> int:
    target = max(1, min(len(text) - 1, int(round(len(text) * ratio))))
    punctuation = [
        index for index, char in enumerate(text)
        if char in "，；：、。！？" and 4 <= index <= len(text) - 4
    ]
    if punctuation:
        index = min(punctuation, key=lambda item: abs(item - target))
        return min(len(text) - 1, index + 1)
    return target


def _cue_overflow(cue: dict, policy: CuePolicy) -> bool:
    duration = (cue["end_ms"] - cue["start_ms"]) / 1000.0
    if duration < policy.min_seconds - 0.05 or duration > policy.max_seconds + 0.05:
        return True
    if len(cue.get("en_lines") or []) > policy.max_lines:
        return True
    if len(cue.get("zh_lines") or []) > policy.max_lines:
        return True
    if any(len(line) > policy.en_max_chars_per_line for line in cue.get("en_lines") or []):
        return True
    if any(len(line) > policy.zh_max_chars_per_line for line in cue.get("zh_lines") or []):
        return True
    zh_chars = len(re.sub(r"\s", "", cue.get("zh", "")))
    return duration > 0 and zh_chars / duration > policy.zh_cps_max


def enforce_limits(cues: list[dict], policy: CuePolicy, fps: float) -> list[dict]:
    """Split over-long cues so the measured subtitle can pass strict policy."""
    result: list[dict] = []
    for cue in cues:
        current = dict(cue)
        for _ in range(6):
            if not _cue_overflow(current, policy):
                break
            duration = (current["end_ms"] - current["start_ms"]) / 1000.0
            if duration < policy.min_seconds * 2:
                break
            en = current["en"]
            zh = current["zh"]
            if len(en) < 12 or len(zh) < 6:
                break
            split_en = _best_split_en(en)
            ratio = split_en / max(1, len(en))
            split_zh = _best_split_zh(zh, ratio)
            split_ms = current["start_ms"] + int(
                round((current["end_ms"] - current["start_ms"]) * ratio)
            )
            if split_ms - current["start_ms"] < policy.min_seconds * 1000:
                break
            if current["end_ms"] - split_ms < policy.min_seconds * 1000:
                break
            left = {
                "index": current["index"],
                "slide": current["slide"],
                "segment_id": current["segment_id"],
                "start_ms": current["start_ms"],
                "end_ms": split_ms - policy.gap_ms(fps),
                "en": en[:split_en].strip(),
                "zh": zh[:split_zh].strip(),
            }
            right = {
                "index": current["index"] + 1,
                "slide": current["slide"],
                "segment_id": current["segment_id"],
                "start_ms": split_ms,
                "end_ms": current["end_ms"],
                "en": en[split_en:].strip(),
                "zh": zh[split_zh:].strip(),
            }
            if len(left["en"]) < 6 or len(left["zh"]) < 2 or len(right["en"]) < 6 or len(right["zh"]) < 2:
                break
            left["en_lines"] = _wrap(left["en"], policy.en_max_chars_per_line, policy.max_lines)
            left["zh_lines"] = _wrap_zh(left["zh"], policy.zh_max_chars_per_line, policy.max_lines)
            right["en_lines"] = _wrap(right["en"], policy.en_max_chars_per_line, policy.max_lines)
            right["zh_lines"] = _wrap_zh(right["zh"], policy.zh_max_chars_per_line, policy.max_lines)
            result.append(left)
            current = right
        result.append(current)
    for position, cue in enumerate(result, start=1):
        cue["index"] = position
        if "en_lines" not in cue:
            cue["en_lines"] = _wrap(cue["en"], policy.en_max_chars_per_line, policy.max_lines)
        if "zh_lines" not in cue:
            cue["zh_lines"] = _wrap_zh(cue["zh"], policy.zh_max_chars_per_line, policy.max_lines)
    return result


def plan_cues(script, meta: dict, policy: CuePolicy, fps: float) -> list[dict]:
    segments = {item["segment_id"]: item for item in meta.get("segments", [])}
    cues: list[dict] = []
    index = 1
    for page in script.pages:
        for segment in page.segments:
            info = segments.get(segment.id)
            if info is None:
                raise SubtitleError(f"segment not found in narration meta: {segment.id}")
            duration_s = float(info.get("duration_s") or 0.0)
            start_s = float(info.get("start_s") or 0.0)
            if duration_s <= 0:
                raise SubtitleError(f"segment has no duration: {segment.id}")
            chunks: list[str] = []
            for sentence in _sentences(segment.text):
                chunks.extend(_clauses(sentence, policy.en_max_chars_per_line * policy.max_lines))
            chunks = _merge_to_fit(chunks, duration_s, policy)
            chunks = _split_to_fit(chunks, duration_s, policy)
            chunks = _merge_to_fit(chunks, duration_s, policy)
            weights = [max(1, len(chunk)) for chunk in chunks]
            total_weight = sum(weights)
            cursor = start_s
            for position, (chunk, weight) in enumerate(zip(chunks, weights)):
                allocated = duration_s * weight / total_weight
                end = cursor + allocated - policy.gap_ms(fps) / 1000.0
                cues.append(
                    {
                        "index": index,
                        "slide": page.slide,
                        "segment_id": segment.id,
                        "start_ms": int(round(cursor * 1000)),
                        "end_ms": int(round(max(end, cursor + 0.3) * 1000)),
                        "en": chunk.strip(),
                    }
                )
                index += 1
                cursor += allocated
    return cues


def _normalize_terms(text: str) -> str:
    replacements = {
        "堆栈": "堆叠",
        "词元": "token",
        "令牌": "token",
        "自我注意力": "自注意力",
        "自注意力机制": "自注意力",
        "位置编码器": "位置编码",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _batch_translate(client, cues: list[dict], glossary: dict | None) -> dict[int, str]:
    from .authoring.llm import AuthoringError, extract_json
    from .authoring.pipeline import _prompt

    translated: dict[int, str] = {}
    batch_size = 20
    for start in range(0, len(cues), batch_size):
        batch = cues[start : start + batch_size]
        payload = []
        for cue in batch:
            duration = max(0.5, (cue["end_ms"] - cue["start_ms"]) / 1000.0)
            payload.append(
                {
                    "index": cue["index"],
                    "en": cue["en"],
                    "max_zh_chars": max(8, min(30, int(duration * 9))),
                }
            )
        glossary_text = ""
        if glossary:
            glossary_text = "\nGlossary:\n" + "\n".join(
                f"- {source} => {target}" for source, target in glossary.items()
            )
        messages = [
            {"role": "system", "content": _prompt("subtitle_translate.md")},
            {
                "role": "user",
                "content": (
                    f"Translate these {len(payload)} cues.{glossary_text}\n"
                    + json.dumps(payload, ensure_ascii=False, indent=2)
                ),
            },
        ]
        try:
            reply_text = client.chat(
                messages,
                task_type="authoring.translate",
                max_tokens=max(4096, min(8192, len(payload) * 400)),
                json_object=True,
            )
            reply = TranslationReply.model_validate(extract_json(reply_text))
        except (AuthoringError, Exception) as exc:  # noqa: BLE001
            raise SubtitleBlocked(f"translation failed: {exc}") from exc
        expected = {cue["index"] for cue in batch}
        got = {item.index for item in reply.cues}
        if got != expected:
            missing = sorted(expected - got)
            extra = sorted(got - expected)
            raise SubtitleBlocked(
                f"translation cue mismatch: missing={missing}, extra={extra}"
            )
        for item in reply.cues:
            translated[item.index] = _normalize_terms(item.zh.strip())
    return translated


def validate_cues(cues: list[dict], policy: CuePolicy, fps: float, total_ms: int) -> list[str]:
    problems: list[str] = []
    previous_end = -1
    for cue in cues:
        duration = (cue["end_ms"] - cue["start_ms"]) / 1000.0
        if duration < policy.min_seconds - 0.05:
            problems.append(f"cue {cue['index']}: duration {duration:.2f}s < {policy.min_seconds}s")
        if duration > policy.max_seconds + 0.05:
            problems.append(f"cue {cue['index']}: duration {duration:.2f}s > {policy.max_seconds}s")
        if previous_end >= 0 and cue["start_ms"] < previous_end + policy.gap_ms(fps) - 2:
            problems.append(f"cue {cue['index']}: gap is below {policy.gap_ms(fps)} ms")
        previous_end = cue["end_ms"]
        if cue["end_ms"] > total_ms + 50:
            problems.append(f"cue {cue['index']}: beyond timeline")
        en_lines = cue.get("en_lines") or []
        zh_lines = cue.get("zh_lines") or []
        if len(en_lines) > policy.max_lines:
            problems.append(f"cue {cue['index']}: English has {len(en_lines)} lines")
        if len(zh_lines) > policy.max_lines:
            problems.append(f"cue {cue['index']}: Chinese has {len(zh_lines)} lines")
        for line in en_lines:
            if len(line) > policy.en_max_chars_per_line:
                problems.append(f"cue {cue['index']}: English line {len(line)} chars")
        for line in zh_lines:
            if len(line) > policy.zh_max_chars_per_line:
                problems.append(f"cue {cue['index']}: Chinese line {len(line)} chars")
        zh_chars = len(re.sub(r"\s", "", cue.get("zh", "")))
        if duration > 0 and zh_chars / duration > policy.zh_cps_max:
            problems.append(
                f"cue {cue['index']}: Chinese {zh_chars / duration:.1f} CPS > {policy.zh_cps_max}"
            )
    return problems


def _ts_srt(ms: int) -> str:
    ms = max(0, ms)
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _ts_vtt(ms: int) -> str:
    return _ts_srt(ms).replace(",", ".")


def _ts_ass(ms: int) -> str:
    ms = max(0, ms)
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{millis // 10:02d}"


def write_srt(cues: list[dict], path: Path) -> None:
    blocks = []
    for cue in cues:
        text = "\n".join(cue["en_lines"] + cue["zh_lines"])
        blocks.append(f"{cue['index']}\n{_ts_srt(cue['start_ms'])} --> {_ts_srt(cue['end_ms'])}\n{text}")
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def write_vtt(cues: list[dict], path: Path) -> None:
    blocks = ["WEBVTT"]
    for cue in cues:
        text = "\n".join(cue["en_lines"] + cue["zh_lines"])
        blocks.append(f"{_ts_vtt(cue['start_ms'])} --> {_ts_vtt(cue['end_ms'])}\n{text}")
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def _ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def write_ass(cues: list[dict], path: Path, width: int, height: int) -> None:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Bilingual,Arial,44,&H001A1A1A,&H001A1A1A,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,3,1,2,80,80,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for cue in cues:
        en = "\\N".join(_ass_escape(line) for line in cue["en_lines"])
        zh = "\\N".join(_ass_escape(line) for line in cue["zh_lines"])
        text = f"{en}\\N{{\\fnMicrosoft YaHei\\fs40}}{zh}"
        lines.append(
            f"Dialogue: 0,{_ts_ass(cue['start_ms'])},{_ts_ass(cue['end_ms'])},Bilingual,,0,0,0,,{text}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_glossary(path: Path | None) -> dict[str, str] | None:
    if path is None:
        return None
    if not path.is_file():
        raise SubtitleError(f"glossary not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    terms = data.get("terms") if isinstance(data, dict) else None
    if isinstance(terms, dict):
        return {str(k): str(v) for k, v in terms.items()}
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items()}
    raise SubtitleError("glossary must be a mapping")


def synthetic_meta(script, fps: float = 30.0) -> dict:
    """Estimate segment timings from page targets before TTS exists."""
    segments: list[dict] = []
    pages: list[dict] = []
    cursor = 0.0
    for page in script.pages:
        weights = [max(1, len(re.findall(r"[A-Za-z0-9']+", segment.text))) for segment in page.segments]
        total_weight = sum(weights)
        page_start = cursor
        for segment, weight in zip(page.segments, weights):
            duration = page.target_seconds * weight / total_weight
            segments.append(
                {
                    "segment_id": segment.id,
                    "slide": page.slide,
                    "start_s": round(cursor, 3),
                    "duration_s": round(duration, 3),
                }
            )
            cursor += duration
        pages.append(
            {
                "slide": page.slide,
                "planned_s": page.target_seconds,
                "measured_s": round(cursor - page_start, 3),
                "start_s": round(page_start, 3),
                "end_s": round(cursor, 3),
            }
        )
    return {"assembly": {"duration_s": round(cursor, 3)}, "segments": segments, "pages": pages}


def build_subtitles(
    workspace: Path,
    paths: LessonPaths,
    script,
    meta: dict | None,
    client,
    *,
    glossary_path: Path | None = None,
    strict: bool = True,
) -> tuple[BilingualDraft, Path]:
    fps = float(paths.lesson.outputs.fps)
    policy = CuePolicy()
    if meta is None:
        meta = synthetic_meta(script, fps)
    cues = plan_cues(script, meta, policy, fps)
    if glossary_path is None:
        lesson_dir = getattr(paths, "lesson_dir", None)
        candidate = lesson_dir / "authoring" / "glossary.yaml" if lesson_dir else None
        if candidate is not None and candidate.is_file():
            glossary_path = candidate
    translated = _batch_translate(client, cues, _load_glossary(glossary_path))
    for cue in cues:
        zh = translated[cue["index"]]
        cue["zh"] = zh
        cue["en_lines"] = _wrap(cue["en"], policy.en_max_chars_per_line, policy.max_lines)
        cue["zh_lines"] = _wrap_zh(zh, policy.zh_max_chars_per_line, policy.max_lines)
    cues = enforce_limits(cues, policy, fps)
    total_ms = int(float(meta["assembly"]["duration_s"]) * 1000)
    problems = validate_cues(cues, policy, fps, total_ms)
    if problems and strict:
        raise SubtitleError("subtitle validation failed: " + "; ".join(problems[:8]))
    draft = BilingualDraft(
        lesson=paths.slug,
        languages={"top": paths.lesson.subtitles.top_language, "bottom": paths.lesson.subtitles.bottom_language},
        policy=policy.__dict__,
        cues=[BilingualCue(**cue) for cue in cues],
        counts={
            "cues": len(cues),
            "translated": len(cues),
            "missing": 0,
            "problems": len(problems),
        },
        translation={
            "provider": getattr(client.route, "provider", "local"),
            "model": getattr(client.route, "model", ""),
            "glossary_sha256": (
                hashlib.sha256(glossary_path.read_bytes()).hexdigest()
                if glossary_path is not None and glossary_path.is_file()
                else None
            ),
        },
    )
    target = paths.build_root / "subtitles"
    target.mkdir(parents=True, exist_ok=True)
    (target / "bilingual.draft.json").write_text(
        json.dumps(draft.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_srt([cue.model_dump() for cue in draft.cues], target / "bilingual.draft.srt")
    write_vtt([cue.model_dump() for cue in draft.cues], target / "bilingual.draft.vtt")
    manifest = {
        "schema_version": 1,
        "lesson": paths.slug,
        "cues": len(draft.cues),
        "policy": policy.__dict__,
        "problems": problems,
        "files": ["bilingual.draft.json", "bilingual.draft.srt", "bilingual.draft.vtt"],
    }
    (target / "subtitles.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return draft, target / "bilingual.draft.srt"


def accept_subtitles(workspace: Path, paths: LessonPaths) -> Path:
    from .authoring.pipeline import approve

    draft_path = paths.build_root / "subtitles" / "bilingual.draft.json"
    if not draft_path.is_file():
        raise SubtitleError(f"subtitle draft not found: {draft_path}")
    draft = BilingualDraft.model_validate(json.loads(draft_path.read_text(encoding="utf-8")))
    if paths.lesson.content.subtitles is None:
        raise SubtitleError("lesson.yaml content.subtitles must point to subtitles.srt")
    target = paths.content_path(paths.lesson.content.subtitles)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Rebuild SRT from the approved draft so no unlisted file is promoted.
    write_srt([cue.model_dump() for cue in draft.cues], target)
    approve(paths.lesson_dir, "subtitles", paths.lesson.content.subtitles)
    return target
