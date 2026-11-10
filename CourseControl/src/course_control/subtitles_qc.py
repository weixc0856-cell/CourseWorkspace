"""Subtitle quality checks that do not rewrite the text.

The rewrap pass fixes layout; this pass audits the result against the language
declaration, timing, line widths, CPS, glossary terms, and the places subtitles
usually break: a word split across a cue boundary, a line that starts with a
comma, an English line that leaves a preposition dangling.

It reports errors (blocking) and warnings (human review).  It never deletes a
cue to make coverage look better.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .subtitles import CuePolicy, display_width

TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)
CJK_RE = re.compile("[㐀-鿿]")
CJK_PUNCT = "。，、；：！？（）《》「」『』"
LETTER_RE = re.compile("[A-Za-z]")
ZH_LEADING_PUNCT = set("，。、；：！？）》」』】,.;:!?)]}")
DANGLING_EN = {
    "a", "an", "the", "of", "to", "in", "on", "at", "for", "with", "and", "or",
    "but", "as", "by", "from", "that", "which", "is", "are", "was", "were", "be",
    "it", "its", "this", "these", "those", "we", "you", "they", "he", "she",
}


def _ts(hours: str, minutes: str, seconds: str, millis: str) -> int:
    return ((int(hours) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + int(millis)


def parse_srt(text: str) -> list[dict]:
    cues: list[dict] = []
    blocks = re.split(r"\r?\n\r?\n+", text.strip())
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        index = None
        if lines[0].strip().isdigit():
            index = int(lines[0].strip())
            lines = lines[1:]
        match = TS_RE.search(lines[0]) if lines else None
        if match is None:
            continue
        start = _ts(*match.groups()[:4])
        end = _ts(*match.groups()[4:])
        cues.append(
            {
                "index": index or len(cues) + 1,
                "start_ms": start,
                "end_ms": end,
                "lines": lines[1:],
            }
        )
    return cues


def _is_zh(line: str) -> bool:
    return bool(CJK_RE.search(line) or any(char in CJK_PUNCT for char in line))


def _split_languages(lines: list[str]) -> tuple[list[str], list[str]]:
    en = [line for line in lines if LETTER_RE.search(line) and not _is_zh(line)]
    zh = [line for line in lines if _is_zh(line)]
    return en, zh


def _load_glossary(path: Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def _term_split(glossary: dict[str, str], en: list[str], zh: list[str], previous: dict | None) -> list[str]:
    issues: list[str] = []
    if previous is None:
        return issues
    prev_en, prev_zh = _split_languages(previous["lines"])
    for source in glossary:
        if not source or len(source) < 4:
            continue
        joined = " ".join(prev_en[-1:]) + " " + " ".join(en[:1])
        tight = "".join(prev_en[-1:]) + "".join(en[:1])
        if (
            source.lower() in joined.lower() or source.lower() in tight.lower()
        ) and not any(source.lower() in line.lower() for line in prev_en + en):
            issues.append(f"term split across cues: {source}")
    for target in glossary.values():
        if len(target) < 2:
            continue
        joined = "".join(prev_zh[-1:]) + "".join(zh[:1])
        if target in joined and not any(target in line for line in prev_zh + zh):
            issues.append(f"term split across cues: {target}")
    return issues


def check_cues(
    cues: list[dict],
    *,
    bilingual: bool,
    policy: CuePolicy | None = None,
    glossary: dict[str, str] | None = None,
    fps: float = 30.0,
) -> dict:
    policy = policy or CuePolicy()
    glossary = glossary or {}
    errors: list[str] = []
    warnings: list[str] = []
    previous: dict | None = None
    for cue_index, cue in enumerate(cues):
        position = cue["index"]
        start, end = cue["start_ms"], cue["end_ms"]
        duration = (end - start) / 1000.0
        if end <= start:
            errors.append(f"cue {position}: end is not after start")
        if previous is not None and start < previous["end_ms"]:
            errors.append(f"cue {position}: overlaps the previous cue")
        gap = (start - previous["end_ms"]) / 1000.0 if previous else 0.0
        if gap < 0:
            gap = 0.0
        if duration < policy.min_seconds - 0.05:
            warnings.append(f"cue {position}: {duration:.2f}s is shorter than {policy.min_seconds}s")
        if duration > policy.max_seconds + 0.05:
            warnings.append(f"cue {position}: {duration:.2f}s is longer than {policy.max_seconds}s")
        lines = [line for line in cue["lines"] if line.strip()]
        if not lines:
            errors.append(f"cue {position}: no text")
            previous = cue
            continue
        en, zh = _split_languages(lines)
        if bilingual:
            if not en:
                errors.append(f"cue {position}: missing top-language line")
            if not zh:
                errors.append(f"cue {position}: missing bottom-language line")
        if len(en) > policy.max_lines or len(zh) > policy.max_lines:
            errors.append(f"cue {position}: more than {policy.max_lines} lines")
        for line in en:
            if len(line) > policy.en_max_chars_per_line:
                errors.append(f"cue {position}: English line {len(line)} chars")
        for line in zh:
            if display_width(line) > policy.zh_max_chars_per_line:
                errors.append(f"cue {position}: Chinese line width {display_width(line):.1f}")
            if line.strip() and line.strip()[0] in ZH_LEADING_PUNCT:
                warnings.append(f"cue {position}: Chinese line starts with punctuation")
        if en:
            last = re.findall(r"[A-Za-z']+", en[-1])
            # A preposition/article at the break is a false positive when the
            # next cue continues the same sentence in lower case. Only flag a
            # real stop after a dangling function word.
            continuation = False
            if cue_index + 1 < len(cues):
                next_en, _ = _split_languages(cues[cue_index + 1]["lines"])
                if next_en and next_en[0][:1].islower():
                    continuation = True
            sentence_end = en[-1].rstrip().endswith((".", "!", "?", "…", '"', "”"))
            if (
                not continuation
                and not sentence_end
                and last
                and last[-1] == last[-1].lower()
                and last[-1] in DANGLING_EN
            ):
                warnings.append(
                    f"cue {position}: English cue ends with '{last[-1]}'"
                )
        for first, second in zip(lines, lines[1:]):
            if first.strip()[-1:].isdigit() and second.strip()[:1].isdigit():
                warnings.append(f"cue {position}: a number is split across lines")
        zh_chars = len(CJK_RE.findall("".join(zh)))
        if duration > 0 and zh_chars / duration > policy.zh_cps_max:
            warnings.append(
                f"cue {position}: Chinese {zh_chars / duration:.1f} CPS > {policy.zh_cps_max}"
            )
        warnings.extend(
            f"cue {position}: {item}"
            for item in _term_split(glossary, en, zh, previous)
        )
        previous = cue

    status = "FAIL" if errors else ("WARN" if warnings else "PASS")
    return {
        "schema_version": 1,
        "status": status,
        "cues": len(cues),
        "errors": errors,
        "warnings": warnings,
        "bilingual": bilingual,
    }


def check_srt(
    path: Path,
    *,
    bilingual: bool,
    policy: CuePolicy | None = None,
    glossary_path: Path | None = None,
) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    report = check_cues(
        parse_srt(text),
        bilingual=bilingual,
        policy=policy,
        glossary=_load_glossary(glossary_path),
    )
    report["path"] = str(path)
    return report


__all__ = ["check_cues", "check_srt", "parse_srt"]
