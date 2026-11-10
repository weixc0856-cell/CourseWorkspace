"""Extraction quality report.

Proof of completeness, not of meaning: every page present, every page carrying
text (or explicitly declared blank), and every suspicious page surfaced for a
human. The page hashes in ``qa.verify`` prove the text did not change; they do
not prove it was extracted correctly. This module fills that gap.

Read-only: it never rewrites pages, units or the index. It writes
``qa/extraction.json`` and ``qa/extraction.md`` only.
"""

from __future__ import annotations

import json
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path

from .extract import load_page_texts
from .qa import load_page_map, load_source
from .segment import load_units
from .toc import TocError
from .toc import load as load_toc

HYPHEN_BREAK = re.compile(r"[A-Za-z]-\n[a-z]")
REPLACEMENT = "�"
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
MAX_LISTED = 40


def parse_pages(spec: str | None) -> set[int]:
    """Parse ``"12,13-15"`` into {12, 13, 14, 15}."""
    if not spec:
        return set()
    pages: set[int] = set()
    for chunk in spec.replace(" ", "").split(","):
        if not chunk:
            continue
        if "-" in chunk:
            start, end = chunk.split("-", 1)
            pages.update(range(int(start), int(end) + 1))
        else:
            pages.add(int(chunk))
    return pages


def _norm_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip().lower()


def _toc_key(text: str) -> str:
    return re.sub(r"[^0-9a-z一-鿿]+", "", text.lower())


def _missing_pages(pages: dict[int, str], total: int) -> list[int]:
    return [number for number in range(1, total + 1) if number not in pages]


def _ordered_pages(pages: dict[int, str], total: int) -> list[int]:
    return [number for number in range(1, total + 1) if number in pages]


def _repeated_lines(pages: dict[int, str], ratio: float) -> list[dict]:
    seen: dict[str, set[int]] = {}
    for number, text in pages.items():
        for raw in text.splitlines():
            line = _norm_line(raw)
            if not 2 <= len(line) <= 120:
                continue
            seen.setdefault(line, set()).add(number)
    threshold = max(5, int(ratio * len(pages)))
    repeated = [
        {"line": line, "pages": len(numbers), "ratio": round(len(numbers) / max(len(pages), 1), 3)}
        for line, numbers in seen.items()
        if len(numbers) >= threshold
    ]
    repeated.sort(key=lambda item: (-item["pages"], item["line"]))
    return repeated[:20]


def analyse(
    root: Path,
    *,
    min_chars: int = 200,
    allow_empty: set[int] | None = None,
    header_ratio: float = 0.8,
    long_line: int = 200,
) -> dict:
    """Scan extracted pages and classify every anomaly by severity."""
    root = root.resolve()
    allow_empty = set(allow_empty or set())
    source = load_source(root)
    pages = load_page_texts(root)
    total = source.pdf_pages

    missing = _missing_pages(pages, total)
    order = _ordered_pages(pages, total)
    stripped = {number: text.strip() for number, text in pages.items()}
    chars = {number: len(text) for number, text in stripped.items()}
    non_empty_chars = [count for count in chars.values() if count > 0]
    median = int(statistics.median(non_empty_chars)) if non_empty_chars else 0

    empty = sorted(number for number, count in chars.items() if count == 0)
    allowed_empty = sorted(set(empty) & allow_empty)
    fatal_empty = sorted(set(empty) - allow_empty)
    sparse = sorted(number for number, count in chars.items() if 0 < count < min_chars)
    long_threshold = max(median * 3, min_chars * 4)
    oversized = sorted(number for number, count in chars.items() if median and count > long_threshold)

    hyphenated: list[int] = []
    replacements: list[int] = []
    controls: list[int] = []
    long_lines: list[int] = []
    for number, text in pages.items():
        if HYPHEN_BREAK.search(text):
            hyphenated.append(number)
        if REPLACEMENT in text:
            replacements.append(number)
        if CONTROL.search(text):
            controls.append(number)
        if any(len(line) > long_line for line in text.splitlines()):
            long_lines.append(number)

    hyphen_pages = sorted(hyphenated)

    page_map = load_page_map(root)
    mapped = {int(item["pdf_page"]): item for item in page_map}
    unmapped = [number for number in order if number not in mapped]
    inversions: list[int] = []
    previous: int | None = None
    for number in order:
        printed = mapped.get(number, {}).get("printed_page")
        if printed is None:
            continue
        if previous is not None and printed < previous:
            inversions.append(number)
        previous = printed
    null_printed = sum(1 for number in order if mapped.get(number, {}).get("printed_page") is None)

    toc_entries: list = []
    toc_info: dict = {}
    toc_error = None
    try:
        toc_entries, toc_info = load_toc(root)
    except (TocError, OSError, ValueError) as exc:  # noqa: BLE001
        toc_error = str(exc)

    anchor_misses: list[dict] = []
    for entry in toc_entries:
        if entry.pdf_page is None or entry.pdf_page not in stripped:
            continue
        key = _toc_key(entry.title)
        if len(key) < 4:
            continue
        if key not in _toc_key(stripped[entry.pdf_page]):
            anchor_misses.append({"title": entry.title, "pdf_page": entry.pdf_page})

    units = []
    try:
        units = load_units(root)
    except Exception:  # noqa: BLE001 - units are optional for this report
        units = []
    covered: set[int] = set()
    for unit in units:
        start, end = unit.pdf_pages
        covered.update(range(start, end + 1))
    uncovered = [number for number in order if number not in covered] if units else []

    fatal: list[str] = []
    if missing:
        fatal.append(f"{len(missing)} page file(s) missing (first: {missing[:5]})")
    if fatal_empty:
        fatal.append(f"{len(fatal_empty)} extracted page(s) have no text (first: {fatal_empty[:5]})")
    serious: list[str] = []
    if hyphen_pages:
        serious.append(f"{len(hyphen_pages)} page(s) contain a hyphenated line break")
    if replacements:
        serious.append(f"{len(replacements)} page(s) contain U+FFFD replacement characters")
    if controls:
        serious.append(f"{len(controls)} page(s) contain control characters")
    if unmapped:
        serious.append(f"{len(unmapped)} page(s) missing from page_map (first: {unmapped[:5]})")
    if inversions:
        serious.append(f"printed page numbers go backwards on {len(inversions)} page(s)")
    if anchor_misses:
        serious.append(f"{len(anchor_misses)} TOC entr(ies) not found on their page")

    cosmetic: list[str] = []
    if sparse:
        cosmetic.append(f"{len(sparse)} short page(s) below {min_chars} chars (plates, figures, chapter openers)")
    if oversized:
        cosmetic.append(f"{len(oversized)} unusually long page(s) above {long_threshold} chars")
    if long_lines:
        cosmetic.append(f"{len(long_lines)} page(s) contain an unwrapped line over {long_line} chars")
    if allowed_empty:
        cosmetic.append(f"{len(allowed_empty)} empty page(s) allow-listed: {allowed_empty[:10]}")
    if uncovered:
        cosmetic.append(f"{len(uncovered)} page(s) outside every unit")
    if toc_error:
        cosmetic.append(f"TOC unavailable: {toc_error}")

    return {
        "schema_version": 1,
        "source_id": source.source_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "blocked" if fatal else "pass",
        "settings": {
            "min_chars": min_chars,
            "allow_empty": sorted(allow_empty),
            "header_ratio": header_ratio,
            "long_line": long_line,
        },
        "counts": {
            "pdf_pages": total,
            "page_files": len(pages),
            "chars_total": sum(chars.values()),
            "chars_median": median,
            "units": len(units),
            "toc_entries": len(toc_entries),
            "null_printed": null_printed,
        },
        "fatal": fatal,
        "serious": serious,
        "cosmetic": cosmetic,
        "pages": {
            "missing": missing,
            "empty": fatal_empty,
            "allow_empty": allowed_empty,
            "sparse": sparse,
            "oversized": oversized,
            "hyphenated": hyphen_pages,
            "replacement": sorted(replacements),
            "control": sorted(controls),
            "long_lines": sorted(long_lines),
            "unmapped": unmapped,
            "uncovered": uncovered,
        },
        "repeated_lines": _repeated_lines(pages, header_ratio),
        "toc": {
            "entries": len(toc_entries),
            "method": toc_info.get("method"),
            "anchor_misses": anchor_misses[:50],
        },
    }


def _short_list(values: list[int]) -> str:
    if not values:
        return "—"
    shown = ", ".join(str(value) for value in values[:MAX_LISTED])
    return shown + (f" …(+{len(values) - MAX_LISTED})" if len(values) > MAX_LISTED else "")


def render_markdown(report: dict) -> str:
    counts = report["counts"]
    lines = [
        f"# Extraction report — {report['source_id']}",
        "",
        f"- generated: {report['generated_at']}",
        f"- status: **{report['status']}**",
        f"- pages: {counts['page_files']}/{counts['pdf_pages']} · median {counts['chars_median']} chars"
        f" · units {counts['units']} · TOC entries {counts['toc_entries']}",
        "",
        "## 必须处理（fatal）",
        "",
    ]
    lines += [f"- {item}" for item in report["fatal"]] or ["- 无"]
    lines += ["", "## 需要人工确认（serious）", ""]
    lines += [f"- {item}" for item in report["serious"]] or ["- 无"]
    lines += ["", "## 报告项（cosmetic）", ""]
    lines += [f"- {item}" for item in report["cosmetic"]] or ["- 无"]
    pages = report["pages"]
    lines += [
        "",
        "## 页清单",
        "",
        f"- 缺失：{_short_list(pages['missing'])}",
        f"- 空页：{_short_list(pages['empty'])}",
        f"- 允许为空：{_short_list(pages['allow_empty'])}",
        f"- 短页：{_short_list(pages['sparse'])}",
        f"- 超长页：{_short_list(pages['oversized'])}",
        f"- 断词页：{_short_list(pages['hyphenated'])}",
        f"- 替换字符：{_short_list(pages['replacement'])}",
        f"- 控制字符：{_short_list(pages['control'])}",
        f"- 未换行长行：{_short_list(pages['long_lines'])}",
        f"- 未映射：{_short_list(pages['unmapped'])}",
        f"- 不在单元内：{_short_list(pages['uncovered'])}",
        "",
        "## 重复行（页眉/页脚候选）",
        "",
    ]
    if report["repeated_lines"]:
        lines += [
            f"- {item['ratio'] * 100:.0f}% ({item['pages']} 页)：`{item['line']}`"
            for item in report["repeated_lines"]
        ]
    else:
        lines.append("- 无")
    lines += ["", "## 目录锚点", ""]
    if report["toc"]["anchor_misses"]:
        lines += [
            f"- p{item['pdf_page']}：`{item['title']}` 未在当页找到"
            for item in report["toc"]["anchor_misses"]
        ]
    else:
        lines.append("- 所有目录条目都在其页面上找到")
    lines.append("")
    return "\n".join(lines)


def write(root: Path, report: dict) -> dict[str, Path]:
    target = root.resolve() / "qa"
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "extraction.json"
    md_path = target / "extraction.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
