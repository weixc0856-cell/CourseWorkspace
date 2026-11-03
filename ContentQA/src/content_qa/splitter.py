"""Split a lesson into reviewable pages and budget-sized chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass

SLIDE_SEPARATOR = re.compile(r"^\s*---\s*$", re.M)
NOTES_HEADER = re.compile(r"^###\s+Slide\s+(\d+)[a-z]?\b.*$", re.M)


@dataclass
class Page:
    slide: int
    slide_text: str
    notes_text: str


@dataclass
class Chunk:
    slide: int
    index: int
    slide_text: str
    notes_text: str

    @property
    def task_id(self) -> str:
        return f"slide-{self.slide:03d}-{self.index}"


def split_slides(text: str) -> list[str]:
    parts = [part.strip() for part in SLIDE_SEPARATOR.split(text)]
    return [part for part in parts if part]


def split_notes(text: str) -> dict[int, str]:
    matches = list(NOTES_HEADER.finditer(text))
    blocks: dict[int, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        slide = int(match.group(1))
        blocks.setdefault(slide, text[match.start():end].strip())
    return blocks


def pair_pages(slides_text: str, notes_text: str) -> list[Page]:
    slides = split_slides(slides_text)
    notes = split_notes(notes_text)
    highest = max([len(slides), *notes.keys()], default=0)
    return [
        Page(slide=number, slide_text=slides[number - 1] if number <= len(slides) else "", notes_text=notes.get(number, ""))
        for number in range(1, highest + 1)
    ]


def _paragraphs(text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    return parts or [text.strip()]


def chunk_page(page: Page, max_chars: int = 4000) -> list[Chunk]:
    """Split long notes by paragraph, keeping the slide text in every chunk."""
    if len(page.notes_text) <= max_chars:
        return [Chunk(page.slide, 1, page.slide_text, page.notes_text)]
    chunks: list[Chunk] = []
    buffer = ""
    for paragraph in _paragraphs(page.notes_text):
        while len(paragraph) > max_chars:
            if buffer:
                chunks.append(Chunk(page.slide, len(chunks) + 1, page.slide_text, buffer))
                buffer = ""
            chunks.append(Chunk(page.slide, len(chunks) + 1, page.slide_text, paragraph[:max_chars]))
            paragraph = paragraph[max_chars:]
        candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
        if len(candidate) > max_chars and buffer:
            chunks.append(Chunk(page.slide, len(chunks) + 1, page.slide_text, buffer))
            buffer = paragraph
        else:
            buffer = candidate
    if buffer:
        chunks.append(Chunk(page.slide, len(chunks) + 1, page.slide_text, buffer))
    return chunks


def plan_chunks(pages: list[Page], max_chars: int = 4000) -> list[Chunk]:
    chunks: list[Chunk] = []
    per_slide: dict[int, int] = {}
    for page in pages:
        page_chunks = chunk_page(page, max_chars)
        for chunk in page_chunks:
            per_slide[chunk.slide] = per_slide.get(chunk.slide, 0) + 1
            chunk.index = per_slide[chunk.slide]
            chunks.append(chunk)
    return chunks
