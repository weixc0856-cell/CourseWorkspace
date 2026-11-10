"""Page extraction: PDF (pypdf) or pre-extracted text with page markers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .models import FigureRecord, PageRecord

PAGE_MARKER = re.compile(r"<!--\s*ks:page\s+pdf=(\d+)[^>]*-->")
FIGURE = re.compile(
    r"^\s*(?P<label>(?:Fig(?:ure)?\.?|Table|Tab\.?|Eq(?:uation)?\.?)\s*[\dIVXivx]+(?:[.\-]\d+)?)"
    r"[\s:.,-]+(?P<caption>.{3,200})$"
)
HEADING = re.compile(r"^\s*(?P<num>\d+(?:\.\d+){0,3})\.?\s+(?P<title>[^\d\s].{1,90})$")
HEADING_WORD = re.compile(r"^\s*(?P<title>[A-Z][A-Za-z][A-Za-z\s\-&/]{3,70})$")


class ExtractorUnavailable(RuntimeError):
    """The PDF backend is not installed — never silently return empty text."""


@dataclass(frozen=True)
class ExtractedPage:
    pdf_page: int
    text: str


@dataclass(frozen=True)
class Extraction:
    pages: tuple[ExtractedPage, ...]
    extractor: str
    title: str | None = None


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    out: list[str] = []
    blank = 0
    for line in lines:
        if not line.strip():
            blank += 1
            if blank <= 1:
                out.append("")
            continue
        blank = 0
        out.append(line)
    return "\n".join(out).strip()


def detect_headings(text: str) -> list[str]:
    headings: list[str] = []
    for line in text.split("\n"):
        match = HEADING.match(line)
        if match and len(match.group("title").split()) <= 12:
            headings.append(f"{match.group('num')} {match.group('title').strip()}")
            continue
        word = HEADING_WORD.match(line)
        stripped = line.strip()
        if word and 4 <= len(stripped) <= 70 and stripped == stripped.upper():
            headings.append(stripped)
    return headings[:12]


def detect_figures(text: str, pdf_page: int) -> list[FigureRecord]:
    figures: list[FigureRecord] = []
    for line in text.split("\n"):
        match = FIGURE.match(line)
        if not match:
            continue
        label = " ".join(match.group("label").split())
        kind = "table" if label.lower().startswith(("tab", "table")) else (
            "equation" if label.lower().startswith(("eq", "equation")) else "figure"
        )
        figures.append(
            FigureRecord(
                pdf_page=pdf_page,
                kind=kind,
                label=label,
                caption=match.group("caption").strip(),
            )
        )
    return figures


def extract_pdf(path: Path) -> Extraction:
    try:
        from pypdf import PdfReader  # noqa: PLC0415 — optional backend
    except ImportError as exc:  # pragma: no cover - exercised by a patched import
        raise ExtractorUnavailable(
            "pypdf is not installed; add it to KnowledgeStudio/pyproject.toml "
            "or import pre-extracted text with `import-text`"
        ) from exc
    reader = PdfReader(str(path))
    if getattr(reader, "is_encrypted", False):
        try:
            reader.decrypt("")
        except Exception as exc:  # noqa: BLE001
            raise ExtractorUnavailable(f"encrypted PDF cannot be read: {path.name}") from exc
    pages: list[ExtractedPage] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001
            raise ExtractorUnavailable(
                f"page {index} of {path.name} could not be extracted: {exc}"
            ) from exc
        pages.append(ExtractedPage(pdf_page=index, text=normalize(text)))
    if not pages:
        raise ExtractorUnavailable(f"PDF has no pages: {path.name}")
    title = None
    try:
        title = (reader.metadata or {}).get("/Title")  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        title = None
    return Extraction(pages=tuple(pages), extractor="pypdf==6.9.2", title=title)


def extract_text(path: Path) -> Extraction:
    raw = path.read_text(encoding="utf-8")
    chunks: list[tuple[int, str]] = []
    markers = list(PAGE_MARKER.finditer(raw))
    if markers:
        for index, marker in enumerate(markers):
            start = marker.end()
            end = markers[index + 1].start() if index + 1 < len(markers) else len(raw)
            chunks.append((int(marker.group(1)), normalize(raw[start:end])))
        numbers = [number for number, _ in chunks]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ExtractorUnavailable(
                "page markers must be sequential starting at 1: "
                + ", ".join(str(number) for number in numbers[:8])
            )
    elif "\f" in raw:
        chunks = [(index, normalize(part)) for index, part in enumerate(raw.split("\f"), 1)]
    else:
        chunks = [(1, normalize(raw))]
    pages = tuple(ExtractedPage(pdf_page=number, text=text) for number, text in chunks)
    return Extraction(pages=pages, extractor="text", title=None)


def write_pages(root: Path, extraction: Extraction) -> list[PageRecord]:
    pages_dir = root / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for stale in pages_dir.glob("p*.md"):
        stale.unlink()
    records: list[PageRecord] = []
    for page in extraction.pages:
        target = pages_dir / f"p{page.pdf_page:04d}.md"
        target.write_text(
            f"<!-- ks:page pdf={page.pdf_page} -->\n\n{page.text}\n",
            encoding="utf-8",
        )
        records.append(
            PageRecord(
                pdf_page=page.pdf_page,
                chars=len(page.text),
                sha256=sha256_text(page.text),
                headings=detect_headings(page.text),
                figures=detect_figures(page.text, page.pdf_page),
            )
        )
    return records


def load_page_texts(root: Path) -> dict[int, str]:
    pages: dict[int, str] = {}
    for path in sorted((root / "pages").glob("p*.md")):
        match = PAGE_MARKER.search(path.read_text(encoding="utf-8")[:200])
        if not match:
            continue
        body = PAGE_MARKER.sub("", path.read_text(encoding="utf-8"), count=1).strip()
        pages[int(match.group(1))] = body
    return pages
