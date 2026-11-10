"""Traceable retrieval: a topic selects pages, never the whole book."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import index as index_mod
from .extract import sha256_text
from .models import Citation, Excerpt, RetrievalResult

ASCII_TERM = re.compile(r"[A-Za-z][A-Za-z0-9\-]{2,}")
CJK_RUN = re.compile(r"[一-鿿]{2,}")
SENTENCE_END = re.compile(r"[。！？.!?]\s")


class RetrieveError(RuntimeError):
    """The query cannot be answered from the indexed pages."""


def match_expression(query: str) -> str:
    terms: list[str] = []
    for word in ASCII_TERM.findall(query):
        terms.append(f'"{word.lower()}"')
    for run in CJK_RUN.findall(query):
        terms.append('"' + " ".join(run) + '"')
    deduped: list[str] = []
    for term in terms:
        if term not in deduped:
            deduped.append(term)
    if not deduped:
        raise RetrieveError(
            "query has no searchable term (need a Latin word or a Chinese phrase)"
        )
    return " OR ".join(deduped)


def query_terms(query: str) -> list[str]:
    return [word.lower() for word in ASCII_TERM.findall(query)] + CJK_RUN.findall(query)


def query_id(query: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:40] or "query"
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:6]
    return f"{slug}-{digest}"


def _unit_boost(units: list, page: int, terms: list[str]) -> tuple[float, str | None]:
    for unit in units:
        if unit["pdf_start"] <= page <= unit["pdf_end"]:
            haystack = f"{unit['title']} {unit['keywords']}".lower()
            if any(term.lower() in haystack for term in terms):
                return 1.35, unit["unit_id"]
            return 1.0, unit["unit_id"]
    return 1.0, None


def _excerpt(text: str, terms: list[str], limit: int) -> str:
    lowered = text.lower()
    position = -1
    for term in terms:
        found = lowered.find(term.lower())
        if found != -1 and (position == -1 or found < position):
            position = found
    if position == -1:
        position = 0
    start = max(0, position - 120)
    chunk = text[start : start + limit]
    cut = None
    for match in SENTENCE_END.finditer(chunk):
        if match.end() >= limit * 0.55:
            cut = match.end()
            break
    if cut:
        chunk = chunk[:cut]
    if start > 0:
        chunk = "…" + chunk
    if start + len(chunk) < len(text) and not chunk.endswith(("。", ".", "！", "?", "？")):
        chunk = chunk + "…"
    return chunk.strip()


def retrieve(
    root: Path,
    query: str,
    *,
    max_pages: int = 18,
    excerpt_chars: int = 700,
) -> RetrievalResult:
    if max_pages < 1:
        raise RetrieveError("max_pages must be >= 1")
    connection = index_mod.connect(root)
    try:
        meta_rows = index_mod.meta(connection)
        source_id = meta_rows.get("source_id") or root.name
        total_pages = int(meta_rows.get("pages") or 0)
        units = index_mod.units(connection)
        expression = match_expression(query)
        hits = index_mod.match_pages(connection, expression)
        if not hits:
            raise RetrieveError(
                f"no page matches {query!r}; try a broader topic or another source"
            )
        terms = query_terms(query)
        scored: dict[int, float] = {}
        unit_of: dict[int, str | None] = {}
        for page, score in hits:
            boost, unit_id = _unit_boost(units, page, terms)
            scored[page] = max(scored.get(page, 0.0), score * boost)
            unit_of[page] = unit_id
        # one page of context on each side, at a discount, if the budget allows
        for page in list(scored):
            for neighbour in (page - 1, page + 1):
                if 1 <= neighbour <= total_pages and neighbour not in scored:
                    scored[neighbour] = max(scored.get(neighbour, 0.0), scored[page] * 0.4)
                    unit_of[neighbour] = _unit_boost(units, neighbour, terms)[1]
        ranked = sorted(scored.items(), key=lambda item: (-item[1], item[0]))[:max_pages]
        selected = sorted(page for page, _ in ranked)
        excerpts: list[Excerpt] = []
        citations: list[Citation] = []
        for page in selected:
            row = index_mod.page_row(connection, page)
            if row is None:
                continue
            text = _excerpt(row["text"], terms, excerpt_chars)
            if not text:
                continue
            printed = row["printed_page"]
            ref = f"{source_id}:p{printed if printed is not None else page}"
            citations.append(
                Citation(
                    ref=ref,
                    source_id=source_id,
                    pdf_page=page,
                    printed_page=printed,
                    page_sha256=row["sha256"],
                    excerpt_sha256=sha256_text(text),
                )
            )
            excerpts.append(
                Excerpt(
                    ref=ref,
                    pdf_page=page,
                    printed_page=printed,
                    unit_id=unit_of.get(page),
                    score=round(scored[page], 4),
                    text=text,
                )
            )
        if not excerpts:
            raise RetrieveError("matched pages are empty after extraction")
        used_units = sorted({item.unit_id for item in excerpts if item.unit_id})
        notes = [
            f"matched {len(hits)} page(s); read {len(excerpts)} page(s) of {total_pages}",
            f"context neighbours are added at 0.4x the seed score",
        ]
        return RetrievalResult(
            query_id=query_id(query),
            query=query,
            source_id=source_id,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            max_pages=max_pages,
            total_pages=total_pages,
            pages_read=len(excerpts),
            units=used_units,
            citations=citations,
            excerpts=excerpts,
            notes=notes,
        )
    finally:
        connection.close()


def write(root: Path, result: RetrievalResult) -> dict[str, Path]:
    folder = root / "retrieval"
    folder.mkdir(parents=True, exist_ok=True)
    json_path = folder / f"{result.query_id}.json"
    json_path.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path = folder / f"{result.query_id}.md"
    md_path.write_text(render_markdown(result), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def render_markdown(result: RetrievalResult) -> str:
    lines = [
        f"# Retrieval — {result.query}",
        "",
        f"- source: `{result.source_id}`",
        f"- pages read: **{result.pages_read} / {result.total_pages}** "
        f"({result.ratio * 100:.1f}%)",
        f"- units: {', '.join(result.units) or '(none)'}",
        f"- generated: {result.created_at}",
        "",
    ]
    current = None
    for excerpt in result.excerpts:
        heading = excerpt.unit_id or "unassigned"
        if heading != current:
            current = heading
            lines += ["", f"## {heading}", ""]
        label = f"p{excerpt.printed_page}" if excerpt.printed_page is not None else f"p{excerpt.pdf_page}"
        lines += [
            f"### {label} · PDF {excerpt.pdf_page} · score {excerpt.score}",
            "",
            f"`{excerpt.ref}`",
            "",
            excerpt.text,
            "",
        ]
    lines += ["", "## Notes", ""] + [f"- {note}" for note in result.notes] + [""]
    return "\n".join(lines)


def export_lesson(
    root: Path,
    result: RetrievalResult,
    lesson_dir: Path,
    *,
    entry_id: str | None = None,
) -> dict[str, Path]:
    """Write a lesson-ready source file plus a sources.yaml fragment.

    The lesson's own ``authoring/sources.yaml`` is never edited: the fragment is
    written next to it so a human (or an explicit merge step) decides.
    """

    sources_dir = lesson_dir / "authoring" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    name = f"KS-{result.source_id}-{result.query_id}.md"
    target = sources_dir / name
    target.write_text(_lesson_markdown(result), encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()

    if entry_id is None:
        entry_id = _next_source_id(lesson_dir)
    entry = {
        "id": entry_id,
        "kind": "markdown",
        "origin": f"KnowledgeStudio retrieval {result.query_id}",
        "local_path": f"authoring/sources/{name}",
        "sha256": digest,
        "title": f"{result.source_id} — {result.query}",
        "fetched_at": result.created_at,
        "http_status": None,
        "extractor": "knowledge-studio",
    }
    fragment = lesson_dir / "authoring" / f"sources.ks-{result.source_id}.yaml"
    payload = {
        "schema_version": 1,
        "lesson": lesson_dir.name,
        "sources": [entry],
    }
    fragment.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return {"source": target, "fragment": fragment}


def _next_source_id(lesson_dir: Path) -> str:
    path = lesson_dir / "authoring" / "sources.yaml"
    highest = 0
    if path.is_file():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for item in data.get("sources", []):
            match = re.fullmatch(r"S(\d{1,3})", str(item.get("id", "")))
            if match:
                highest = max(highest, int(match.group(1)))
    return f"S{highest + 1}"


def _lesson_markdown(result: RetrievalResult) -> str:
    lines = [
        f"# {result.source_id} — {result.query}",
        "",
        f"Retrieved with KnowledgeStudio ({result.query_id}). "
        f"{result.pages_read} of {result.total_pages} pages were read; "
        "page markers carry the original page numbers.",
        "",
    ]
    current = None
    for excerpt in result.excerpts:
        heading = excerpt.unit_id or "source"
        if heading != current:
            current = heading
            lines += ["", f"## {heading}", ""]
        printed = excerpt.printed_page if excerpt.printed_page is not None else excerpt.pdf_page
        lines += [
            f"<!-- ks:page pdf={excerpt.pdf_page} printed={printed} -->",
            "",
            excerpt.text,
            "",
        ]
    return "\n".join(lines)
