"""Deterministic book map: chapters, page spans, units and figures.

The map is a navigational index, not a knowledge graph. It proves what the
source contains and where it is; deciding which concepts matter and what
depends on what remains an authoring decision (written down in the vertical
plan, not invented here).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .qa import load_page_map, load_source
from .segment import load_units
from .toc import load as load_toc


def _figure_counts(records: list[dict], start: int, end: int) -> dict[str, int]:
    counts = {"figure": 0, "table": 0, "equation": 0}
    for record in records:
        page = int(record.get("pdf_page") or 0)
        if not start <= page <= end:
            continue
        for figure in record.get("figures", []):
            kind = str(figure.get("kind") or "")
            if kind in counts:
                counts[kind] += 1
    return counts


def build(root: Path) -> dict:
    root = root.resolve()
    source = load_source(root)
    entries, info = load_toc(root)
    units = load_units(root)
    records = load_page_map(root)
    total = source.pdf_pages

    chapters = [
        entry
        for entry in entries
        if entry.level == 1 and entry.pdf_page is not None and entry.pdf_page >= 1
    ]
    rows: list[dict] = []
    for index, entry in enumerate(chapters):
        start = int(entry.pdf_page)
        end = (
            int(chapters[index + 1].pdf_page) - 1
            if index + 1 < len(chapters) and chapters[index + 1].pdf_page
            else total
        )
        if end < start:
            end = start
        matched_units = [
            unit
            for unit in units
            if unit.pdf_pages[0] <= end and unit.pdf_pages[1] >= start
        ]
        keywords: list[str] = []
        seen: set[str] = set()
        for unit in matched_units:
            for word in unit.keywords:
                key = word.casefold()
                if key not in seen:
                    seen.add(key)
                    keywords.append(word)
        counts = _figure_counts(records, start, end)
        rows.append(
            {
                "index": index + 1,
                "title": entry.title,
                "printed_page": entry.printed_page,
                "pdf_start": start,
                "pdf_end": end,
                "pages": end - start + 1,
                "units": [unit.unit_id for unit in matched_units],
                "figures": counts["figure"],
                "tables": counts["table"],
                "equations": counts["equation"],
                "keywords": keywords[:12],
            }
        )

    return {
        "schema_version": 1,
        "source_id": source.source_id,
        "title": source.title,
        "authors": source.authors,
        "year": source.year,
        "pdf_pages": total,
        "extractor": source.extractor,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "toc": info,
        "chapters": rows,
        "units_total": len(units),
        "figures_total": sum(row["figures"] for row in rows),
        "tables_total": sum(row["tables"] for row in rows),
        "equations_total": sum(row["equations"] for row in rows),
        "note": (
            "Page spans and counts are extracted, not interpreted. "
            "Concept selection and episode mapping belong in the vertical plan."
        ),
    }


def write(root: Path, report: dict) -> dict[str, Path]:
    target = root / "map" / "book-map.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        f"# Book map — {report['title']}",
        "",
        f"- source: `{report['source_id']}` · {report['pdf_pages']} pages · "
        f"{report['units_total']} units",
        f"- TOC: {report['toc'].get('method', 'unknown')} · "
        f"offset {report['toc'].get('page_offset', 0)} · "
        f"{report['toc'].get('entries', len(report['chapters']))} entries",
        f"- figures {report['figures_total']} · tables {report['tables_total']} · "
        f"equations {report['equations_total']}",
        "",
        "| # | Chapter | PDF pages | Pages | Units | Fig | Tab | Eq |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["chapters"]:
        units = ", ".join(row["units"]) or "—"
        lines.append(
            f"| {row['index']} | {row['title']} | {row['pdf_start']}–{row['pdf_end']} | "
            f"{row['pages']} | {units} | {row['figures']} | {row['tables']} | "
            f"{row['equations']} |"
        )
    lines += ["", f"> {report['note']}", ""]
    markdown = target.with_suffix(".md")
    markdown.write_text("\n".join(lines), encoding="utf-8")
    return {"json": target, "markdown": markdown}
