"""E1: display chain alignment — slides.md ↔ production.yaml ↔ narration script.

Every quantitative claim shown on a page must be spoken on that page in
normalized form (T1-01 incident: screen "one million", voice "ten million").
Citation lines and page headings are excluded: they are not claims.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_SMALL = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "single": 1, "double": 2, "twice": 2, "both": 2,
}
_SCALES = {"thousand": 1e3, "million": 1e6, "billion": 1e9}
_FRACTIONS = {"third": 1 / 3, "thirds": 1 / 3, "half": 0.5, "halves": 0.5,
              "quarter": 0.25, "quarters": 0.25}
_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")

_NUM_PATTERN = re.compile(
    r"(?P<sci>\d+(?:\.\d+)?[eE][+-]?\d+)"
    r"|(?P<pow>10\s*(?:\^|\*\*)\s*[+-]?\d+)"
    r"|(?P<sup>10[⁰¹²³⁴⁵⁶⁷⁸⁹]+)"
    r"|(?P<pct>\d+(?:\.\d+)?\s*%)"
    r"|(?P<range>\d+(?:\.\d+)?\s*[-–—]\s*\d+(?:\.\d+)?)"
    r"|(?P<mult>[~≈]?\s*\d+(?:\.\d+)?\s*[×xX])(?![A-Za-z])"
    r"|(?P<plain>\d+(?:\.\d+)?)"
)
_WORD_TOKEN = re.compile(r"[A-Za-z]+|\d+(?:\.\d+)?")
_SLIDE_SEP = re.compile(r"^\s*---\s*$", re.M)
_HEADING = re.compile(r"^#{1,6}\s+(?:(\d+)[.)]\s*)?(.*)$")
_SOURCE_LINE = re.compile(r"<small>.*?</small>", re.S)


def _values_from_numbers(text: str) -> tuple[list[float], str]:
    """Extract numeric literals; return values and the text with spans masked."""
    values: list[float] = []
    masked = []
    pos = 0
    for m in _NUM_PATTERN.finditer(text):
        masked.append(text[pos:m.start()])
        masked.append(" " * (m.end() - m.start()))
        pos = m.end()
        kind = m.lastgroup
        raw = m.group()
        if kind == "sci":
            values.append(float(raw))
        elif kind == "pow":
            values.append(10 ** float(re.search(r"[+-]?\d+$", raw).group()))
        elif kind == "sup":
            values.append(10 ** int(raw[2:].translate(_SUP)))
        elif kind == "pct":
            values.append(float(raw.rstrip("% ")) / 100)
        elif kind == "range":
            values.extend(float(part) for part in re.split(r"[-–—]", raw))
        elif kind == "mult":
            values.append(float(re.search(r"\d+(?:\.\d+)?", raw).group()))
        else:
            values.append(float(raw))
    masked.append(text[pos:])
    return values, "".join(masked)


def _values_from_words(masked: str) -> list[float]:
    values: list[float] = []
    tokens = _WORD_TOKEN.findall(masked.lower())
    cur = 0.0
    tot = 0.0
    started = False

    def flush() -> None:
        nonlocal cur, tot, started
        if started:
            values.append(tot + cur)
        cur = tot = 0.0
        started = False

    for i, tok in enumerate(tokens):
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        prev = tokens[i - 1] if i else ""
        if tok == "percent" or (tok == "cent" and prev == "per"):
            if started:
                values.append((tot + cur) / 100)
            cur = tot = 0.0
            started = False
        elif tok in _SMALL:
            cur += _SMALL[tok]
            started = True
        elif tok == "hundred":
            cur = (cur or 1) * 100
            started = True
        elif tok in _SCALES:
            tot += (cur or 1) * _SCALES[tok]
            cur = 0
            started = True
        elif tok in _FRACTIONS:
            values.append((cur or 1) * _FRACTIONS[tok])
            cur = tot = 0.0
            started = False
        elif tok in ("a", "an") and (nxt in _FRACTIONS or nxt == "hundred" or nxt in _SCALES):
            cur += 1
            started = True
        elif re.fullmatch(r"\d+(?:\.\d+)?", tok):
            cur += float(tok)
            started = True
        else:
            flush()
    flush()
    return values


def extract_numbers(text: str) -> set[float]:
    literal, masked = _values_from_numbers(text)
    return set(literal) | set(_values_from_words(masked))


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def _screen_pages(slides_text: str) -> list[tuple[int, str, str]]:
    pages = []
    for index, part in enumerate(_SLIDE_SEP.split(slides_text), start=1):
        part = part.strip()
        if not part:
            continue
        title = ""
        number = index
        body_lines = []
        for line in _SOURCE_LINE.sub("", part).splitlines():
            heading = _HEADING.match(line.strip())
            if heading:
                if heading.group(1):
                    number = int(heading.group(1))
                title = heading.group(2).strip()
            elif line.strip():
                body_lines.append(line.strip())
        pages.append((number, title, "\n".join(body_lines)))
    return pages


def _norm_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().lower()


def _display_chain(ctx: Any) -> tuple[str, Any, Any, str]:
    lesson = Path(ctx.lesson_dir)
    slides_path = lesson / "slides.md"
    script_path = lesson / "authoring" / "narration.script.json"
    prod_path = lesson / "authoring" / "production.yaml"
    for path in (slides_path, script_path, prod_path):
        if not path.is_file():
            return "not_run", None, "slides + script + production", str(path)
    try:
        import yaml

        script = json.loads(script_path.read_text(encoding="utf-8"))
        prod = yaml.safe_load(prod_path.read_text(encoding="utf-8")) or {}
        pages = _screen_pages(slides_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return "fail", str(exc), "readable display chain", str(lesson)

    script_pages = script.get("pages") or []
    sequences = prod.get("sequences") or []
    counts = {"slides": len(pages), "script": len(script_pages), "production": len(sequences)}
    if not (len(pages) == len(script_pages) == len(sequences)) or not pages:
        return "fail", counts, "equal page counts", str(lesson)

    problems: list[dict] = []
    checked = 0
    for index, (slide_no, slide_title, slide_body) in enumerate(pages):
        sp = script_pages[index]
        seq = sequences[index]
        if sp.get("slide") != index + 1:
            problems.append({"page": index + 1, "issue": f"script slide={sp.get('slide')}"})
        seq_title = seq.get("title") or ""
        if slide_title and seq_title and _norm_title(slide_title) != _norm_title(seq_title):
            problems.append({"page": index + 1, "issue": "title mismatch",
                             "slides": slide_title, "production": seq_title})
        segments = sp.get("segments") or []
        spoken_text = " ".join(str(s.get("tts_text") or s.get("text") or "") for s in segments)
        screen_extra = " ".join(str(s.get("display_text") or "") for s in segments)
        for shot in seq.get("shots") or []:
            screen_extra += " " + str(shot.get("display_text") or "")
        screen = extract_numbers(slide_body + " " + screen_extra)
        spoken = extract_numbers(spoken_text)
        missing = [v for v in sorted(screen) if not any(_close(v, w) for w in spoken)]
        checked += len(screen)
        if missing:
            problems.append({"page": slide_no, "screen_only_numbers": missing})

    if problems:
        return "fail", problems, "screen numbers spoken per page", str(lesson)
    return "pass", {"pages": len(pages), "numbers_checked": checked}, "screen numbers spoken per page", str(lesson)


DISPLAY_RULES = {"display_chain_alignment": _display_chain}