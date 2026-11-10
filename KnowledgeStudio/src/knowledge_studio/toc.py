"""Table of contents: parse, calibrate printed→PDF pages, persist."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import PageRecord, TocEntry

TOC_LINE = re.compile(
    r"^\s*(?P<num>(?:\d+\.)*\d+)?\s*(?P<title>[^\n]{2,120}?)"
    r"(?:[\s.·…]{2,}|\.{3,})(?P<page>\d{1,4})\s*$"
)
DOTTED = re.compile(r"[.·…]{3,}")
CHAPTER = re.compile(r"^\s*(?:Chapter|CHAPTER|第)\s*(\d{1,3})\s*(?:章)?[\s:.-]*(.{2,80})$")


class TocError(RuntimeError):
    """The table of contents cannot be trusted or is missing."""


def fingerprint(text: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z一-鿿]+", "", text).lower()
    return cleaned[:10]


def _clean_title(value: str) -> str:
    value = DOTTED.sub(" ", value)
    value = re.sub(r"\s{2,}", " ", value).strip(" .-·")
    return value


def parse_toc(pages: dict[int, str], scan_pages: int = 12) -> list[TocEntry]:
    """Parse the printed TOC from the front matter.

    Only lines with a clear leader and a trailing page number count, so running
    text cannot be mistaken for a TOC entry.
    """

    entries: list[TocEntry] = []
    seen: set[tuple[str, int]] = set()
    for number in sorted(pages)[:scan_pages]:
        for line in pages[number].split("\n"):
            match = TOC_LINE.match(line)
            if not match:
                continue
            title = _clean_title(match.group("title"))
            if len(title) < 2 or title.isdigit():
                continue
            printed = int(match.group("page"))
            num = match.group("num")
            level = len(num.split(".")) if num else 1
            key = (fingerprint(title), printed)
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                TocEntry(level=level, title=title, printed_page=printed)
            )
    return entries


def fallback_entries(pages: dict[int, str]) -> list[TocEntry]:
    """Derive chapter boundaries from chapter headings when no TOC parses."""

    entries: list[TocEntry] = []
    for number in sorted(pages):
        for line in pages[number].split("\n")[:40]:
            match = CHAPTER.match(line)
            if not match:
                continue
            title = _clean_title(match.group(2))
            if len(title) < 2:
                continue
            entries.append(
                TocEntry(
                    level=1,
                    title=f"{match.group(1)} {title}".strip(),
                    printed_page=None,
                    pdf_page=number,
                )
            )
            break
    return entries


def _squash(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z一-鿿]+", "", text).lower()


def page_score(text: str, title: str) -> int:
    """2 = the title opens the page, 1 = it appears somewhere, 0 = absent.

    Opening a page is what a chapter heading does; a plain substring hit also
    occurs on neighbouring pages, which is why both weights are needed to
    disambiguate a constant page offset.
    """

    token = fingerprint(title)
    if not token:
        return 0
    opening = _squash(text[:260])
    opening = re.sub(r"^[0-9]+", "", opening)
    if opening.startswith(token[:24]):
        return 2
    if token in _squash(text):
        return 1
    return 0


def calibrate(pages: dict[int, str], entries: list[TocEntry], search: int = 40) -> int:
    """Find the constant offset ``pdf_page - printed_page``.

    Every candidate offset is scored by how many entry titles appear on the
    page it predicts. Ties prefer the smaller absolute offset.
    """

    candidates = [entry for entry in entries if entry.printed_page and entry.title]
    if not candidates:
        return 0
    best_offset = 0
    best_score = -1
    total = len(pages)
    for offset in range(-search, search + 1):
        score = 0
        for entry in candidates:
            page_number = int(entry.printed_page) + offset  # type: ignore[arg-type]
            if page_number < 1 or page_number > total:
                continue
            score += page_score(pages.get(page_number, ""), entry.title)
        if score > best_score or (score == best_score and abs(offset) < abs(best_offset)):
            best_score = score
            best_offset = offset
    return best_offset


def apply_offset(entries: list[TocEntry], offset: int, total_pages: int) -> list[TocEntry]:
    applied: list[TocEntry] = []
    for entry in entries:
        if entry.pdf_page is None and entry.printed_page is not None:
            candidate = entry.printed_page + offset
            pdf_page = candidate if 1 <= candidate <= total_pages else None
            entry = entry.model_copy(update={"pdf_page": pdf_page})
        applied.append(entry)
    return applied


def resolve(pages: dict[int, str], *, scan_pages: int = 12, search: int = 40) -> tuple[list[TocEntry], dict]:
    """Parse and calibrate, falling back to chapter headings only if needed."""

    entries = parse_toc(pages, scan_pages=scan_pages)
    method = "toc"
    if not entries:
        entries = fallback_entries(pages)
        method = "headings"
    offset = calibrate(pages, entries, search=search)
    applied = apply_offset(entries, offset, len(pages))
    usable = [entry for entry in applied if entry.pdf_page is not None]
    if not usable:
        raise TocError(
            "no TOC entry maps to a PDF page; pass a manual metadata/toc.json"
        )
    return applied, {"method": method, "page_offset": offset, "entries": len(applied)}


def toc_path(root: Path) -> Path:
    return root / "metadata" / "toc.json"


def save(root: Path, entries: list[TocEntry], info: dict) -> Path:
    target = toc_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        **info,
        "entries": [entry.model_dump(mode="json") for entry in entries],
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target


def load(root: Path) -> tuple[list[TocEntry], dict]:
    path = toc_path(root)
    if not path.is_file():
        raise TocError(f"TOC missing: {path.relative_to(root).as_posix()}")
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = [TocEntry.model_validate(item) for item in data.get("entries", [])]
    info = {key: value for key, value in data.items() if key not in ("entries",)}
    return entries, info


def load_manual(path: Path) -> list[TocEntry]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("entries", data) if isinstance(data, dict) else data
    entries = [TocEntry.model_validate(item) for item in items]
    if not any(entry.pdf_page for entry in entries):
        raise TocError("manual TOC needs pdf_page on at least one entry")
    return entries


def write_page_map(root: Path, records: list[PageRecord] | None = None, offset: int = 0) -> Path:
    """Persist the PDF→printed page map; reused by the CLI and the tests."""

    target = root / "metadata" / "page_map.json"
    if records is None:
        if not target.is_file():
            raise TocError("page_map.json is missing; import the source first")
        stored = json.loads(target.read_text(encoding="utf-8")).get("pages", [])
        records = [PageRecord.model_validate(item) for item in stored]
    payload = {
        "schema_version": 1,
        "page_offset": offset,
        "pages": [
            record.model_dump(mode="json")
            | {
                "printed_page": (
                    record.pdf_page - offset
                    if offset and record.pdf_page - offset >= 1
                    else record.printed_page
                )
            }
            for record in records
        ],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8"
    )
    return target
