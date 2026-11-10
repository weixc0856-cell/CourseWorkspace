"""Split a source into page-addressed knowledge units.

Units follow the TOC's top level (chapters). Each unit gets its own directory,
a page-marked Markdown file, and a figure/table/equation index — the page range
is the contract, so a lesson can cite it later.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from .extract import PAGE_MARKER, detect_figures, load_page_texts, normalize, sha256_text
from .models import FigureRecord, PageRecord, TocEntry, UnitMeta

ASCII = re.compile(r"[A-Za-z][A-Za-z\-]{3,}")
CJK = re.compile(r"[一-鿿]{2}")
CJK_STOP = {
    "一个", "我们", "可以", "这个", "以及", "因此", "如果", "没有", "不是", "进行",
    "通过", "这些", "其中", "对于", "由于", "已经", "并且", "或者", "但是", "所以",
}
EN_STOP = {
    "that", "this", "with", "from", "have", "which", "there", "their", "these",
    "those", "were", "been", "will", "would", "could", "should", "than", "then",
    "also", "such", "when", "where", "what", "into", "over", "under", "about",
    "more", "most", "other", "each", "some", "only", "very", "they", "them",
}


class SegmentError(RuntimeError):
    """Units cannot be built from the current TOC."""


def unit_slug(title: str) -> str:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return "-".join(words[:4])


def extract_terms(text: str, limit: int = 12) -> list[str]:
    counts: dict[str, int] = {}
    for word in ASCII.findall(text[:20000]):
        word = word.lower()
        if word in EN_STOP:
            continue
        counts[word] = counts.get(word, 0) + 1
    for bigram in CJK.findall(text[:20000]):
        if bigram in CJK_STOP:
            continue
        counts[bigram] = counts.get(bigram, 0) + 1
    ranked = sorted(
        ((term, count) for term, count in counts.items() if count >= 2),
        key=lambda item: (-item[1], item[0]),
    )
    return [term for term, _ in ranked[:limit]]


def top_level(entries: list[TocEntry]) -> list[TocEntry]:
    usable = [entry for entry in entries if entry.pdf_page is not None]
    if not usable:
        raise SegmentError("TOC has no entries with a PDF page")
    level = min(entry.level for entry in usable)
    chapters = [entry for entry in usable if entry.level == level]
    chapters.sort(key=lambda entry: (entry.pdf_page or 0))
    deduped: list[TocEntry] = []
    for entry in chapters:
        if deduped and entry.pdf_page == deduped[-1].pdf_page:
            continue
        deduped.append(entry)
    return deduped


def build_units(
    root: Path,
    entries: list[TocEntry],
    *,
    max_units: int | None = None,
) -> list[UnitMeta]:
    pages = load_page_texts(root)
    if not pages:
        raise SegmentError("no extracted pages; run import-source first")
    chapters = top_level(entries)
    total = max(pages)
    units: list[UnitMeta] = []
    units_dir = root / "units"
    units_dir.mkdir(parents=True, exist_ok=True)
    for stale in units_dir.glob("U*"):
        if stale.is_dir():
            for child in sorted(stale.iterdir()):
                child.unlink()
            stale.rmdir()

    printed = _printed_map(root)
    for index, chapter in enumerate(chapters, start=1):
        if max_units is not None and len(units) >= max_units:
            break
        start = int(chapter.pdf_page or 1)
        end = (
            int(chapters[index].pdf_page) - 1
            if index < len(chapters) and chapters[index].pdf_page
            else total
        )
        if end < start:
            continue
        unit_id = f"U{len(units) + 1:02d}"
        slug = unit_slug(chapter.title)
        folder = units_dir / (f"{unit_id}-{slug}" if slug else unit_id)
        folder.mkdir(parents=True, exist_ok=True)
        body = _unit_markdown(pages, start, end, printed)
        page_file = folder / f"pages_{start:03d}_{end:03d}.md"
        page_file.write_text(body, encoding="utf-8")
        figures = _unit_figures(pages, start, end)
        figures_file = folder / "figures.json"
        figures_file.write_text(
            json.dumps(
                [figure.model_dump(mode="json") for figure in figures],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        unit = UnitMeta(
            unit_id=unit_id,
            title=chapter.title,
            chapter=chapter.title,
            pdf_pages=(start, end),
            printed_pages=_printed_range(printed, start, end),
            keywords=extract_terms("\n".join(pages[number] for number in range(start, end + 1))),
            files=[page_file.name, figures_file.name],
            figure_count=len(figures),
        )
        (folder / "unit.yaml").write_text(
            yaml.safe_dump(unit.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        units.append(unit)
    if not units:
        raise SegmentError("no units were produced; check the TOC page ranges")
    return units


def _printed_map(root: Path) -> dict[int, int]:
    path = root / "metadata" / "page_map.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    mapping: dict[int, int] = {}
    for item in data.get("pages", []):
        if item.get("printed_page") is not None:
            mapping[int(item["pdf_page"])] = int(item["printed_page"])
    return mapping


def _printed_range(printed: dict[int, int], start: int, end: int) -> tuple[int, int] | None:
    values = [printed[number] for number in range(start, end + 1) if number in printed]
    if not values:
        return None
    return (min(values), max(values))


def _unit_markdown(pages: dict[int, str], start: int, end: int, printed: dict[int, int]) -> str:
    chunks = []
    for number in range(start, end + 1):
        suffix = f" printed={printed[number]}" if number in printed else ""
        chunks.append(f"<!-- ks:page pdf={number}{suffix} -->\n\n{pages.get(number, '')}")
    return "\n\n".join(chunks).strip() + "\n"


def _unit_figures(pages: dict[int, str], start: int, end: int) -> list[FigureRecord]:
    found: list[FigureRecord] = []
    for number in range(start, end + 1):
        found.extend(detect_figures(pages.get(number, ""), number))
    return found


def load_units(root: Path) -> list[UnitMeta]:
    units: list[UnitMeta] = []
    for path in sorted((root / "units").glob("U*/unit.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        units.append(UnitMeta.model_validate(data))
    return units


def unit_for_page(units: list[UnitMeta], page: int) -> UnitMeta | None:
    for unit in units:
        start, end = unit.pdf_pages
        if start <= page <= end:
            return unit
    return None


def unit_text(root: Path, unit: UnitMeta) -> str:
    folder = _unit_folder(root, unit)
    for name in unit.files:
        if name.startswith("pages_"):
            return normalize(PAGE_MARKER.sub(" ", (folder / name).read_text(encoding="utf-8")))
    start, end = unit.pdf_pages
    return "\n".join(load_page_texts(root).get(number, "") for number in range(start, end + 1))


def _unit_folder(root: Path, unit: UnitMeta) -> Path:
    for path in (root / "units").glob(f"{unit.unit_id}*"):
        if path.is_dir():
            return path
    raise SegmentError(f"unit folder missing for {unit.unit_id}")


def manifest_hash(units: list[UnitMeta]) -> str:
    payload = json.dumps(
        [unit.model_dump(mode="json") for unit in units], sort_keys=True, ensure_ascii=False
    )
    return sha256_text(payload)
