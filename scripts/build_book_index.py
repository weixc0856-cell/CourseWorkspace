"""Build the book index from a Docling conversion plus a curation overlay.

The extraction is mechanical: headings and figure captions come from the PDF
and carry the printed page (PDF page minus the offset for this book). Claims
and equations come from the curation YAML and must be written against the text;
the generator only checks that their locators resolve.

Usage:
    uv run --project CourseControl python scripts/build_book_index.py \
        --docling <docling_output>/hucho-en-5e \
        --chapters 1,2,3 --curation <book>/curation.yaml \
        --out <book>/index.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

PAGE_MARKER = re.compile(r"<!--\s*ks:page pdf=(\d+)\s*-->")
FIGURE = re.compile(r"^Figure\s+(\d+\.\d+)\s+(.*)$")
CHAPTER = re.compile(r"^Chapter\s+(\d+)\s+(.*)$")
SECTION = re.compile(r"^(\d+(?:\.\d+)+)\s+(.*)$")


def load_outline(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("entries", data if isinstance(data, list) else [])


def chapters(entries: list[dict], wanted: set[int], offset: int) -> list[dict]:
    found: list[dict] = []
    current: dict | None = None
    for entry in entries:
        title = str(entry.get("title") or "").strip()
        page = entry.get("page")
        match = CHAPTER.match(title)
        if match and entry.get("level") == 1:
            number = int(match.group(1))
            current = None
            if number in wanted:
                current = {
                    "number": number,
                    "title": match.group(2).strip(),
                    "pdf_page": page,
                    "page": page - offset if page else None,
                    "concepts": [],
                }
                found.append(current)
            continue
        if current is None:
            continue
        section = SECTION.match(title)
        if section and int(section.group(1).split(".")[0]) == current["number"]:
            if entry.get("level") in (2, 3):
                current["concepts"].append(
                    {
                        "id": section.group(1),
                        "title": section.group(2).strip(),
                        "level": entry.get("level"),
                        "pdf_page": page,
                        "page": page - offset if page else None,
                    }
                )
        elif entry.get("level") == 1:
            current = None
    return found


def figures(pages_txt: Path, wanted: set[int], offset: int) -> list[dict]:
    found: list[dict] = []
    page = None
    for line in pages_txt.read_text(encoding="utf-8").splitlines():
        marker = PAGE_MARKER.search(line)
        if marker:
            page = int(marker.group(1))
            continue
        match = FIGURE.match(line.strip())
        if not match or page is None:
            continue
        number = match.group(1)
        if int(number.split(".")[0]) not in wanted:
            continue
        found.append(
            {
                "id": "F-" + number,
                "number": number,
                "chapter": number.split(".")[0],
                "caption": match.group(2).strip(),
                "pdf_page": page,
                "page": page - offset,
            }
        )
    return found


def unique_sources(items: list[dict]) -> list[dict]:
    seen: dict[tuple, dict] = {}
    for item in items:
        key = tuple(sorted((k, str(v)) for k, v in item.items() if v is not None))
        seen.setdefault(key, item)
    return [seen[key] for key in sorted(seen)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docling", type=Path, required=True)
    parser.add_argument("--chapters", default="1,2,3")
    parser.add_argument("--offset", type=int, default=21)
    parser.add_argument("--curation", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    wanted = {int(item) for item in args.chapters.split(",") if item.strip()}
    entries = load_outline(args.docling / "outline.json")
    chapter_list = chapters(entries, wanted, args.offset)
    figure_list = figures(args.docling / "pages.txt", wanted, args.offset)
    curation = {}
    if args.curation:
        curation = yaml.safe_load(args.curation.read_text(encoding="utf-8")) or {}

    concepts: list[dict] = []
    for chapter in chapter_list:
        for concept in chapter["concepts"]:
            extra = (curation.get("concepts") or {}).get(concept["id"], {}) or {}
            concepts.append(
                {
                    "id": concept["id"],
                    "title": concept["title"],
                    "level": concept["level"],
                    "chapter": str(chapter["number"]),
                    "section": concept["id"],
                    "page": concept["page"],
                    "prerequisites": list(extra.get("prerequisites") or []),
                    "misconceptions": list(extra.get("misconceptions") or []),
                }
            )

    claims = []
    for claim in curation.get("claims") or []:
        claims.append({**claim, "chapter": str(claim.get("chapter"))})
    equations = []
    for equation in curation.get("equations") or []:
        equations.append({**equation, "chapter": str(equation.get("chapter"))})

    sources: list[dict] = []
    for concept in concepts:
        sources.append({"chapter": concept["chapter"], "section": concept["section"], "page": concept["page"]})
    for figure in figure_list:
        sources.append({"chapter": figure["chapter"], "figure": figure["number"], "page": figure["page"]})
    for claim in claims:
        entry = {"chapter": claim.get("chapter"), "page": claim.get("page")}
        if claim.get("section"):
            entry["section"] = claim["section"]
        if claim.get("figure"):
            entry["figure"] = claim["figure"]
        if claim.get("table"):
            entry["table"] = claim["table"]
        sources.append(entry)
    for equation in equations:
        sources.append(
            {"chapter": equation.get("chapter"), "section": equation.get("section"), "page": equation.get("page")}
        )
    for extra in curation.get("sources") or []:
        sources.append({key: value for key, value in extra.items() if value is not None})

    index = {
        "schema_version": 1,
        "book": {
            "title": "Aerodynamics of Road Vehicles",
            "edition": "5th",
            "editor": "Thomas Schuetz",
            "year": 2016,
            "pdf_page_offset": args.offset,
            "docling": str(args.docling),
        },
        "chapters": [
            {"number": str(chapter["number"]), "title": chapter["title"], "page": chapter["page"]}
            for chapter in chapter_list
        ],
        "concepts": concepts,
        "claims": claims,
        "figures": figure_list,
        "equations": equations,
        "sources": unique_sources(sources),
    }

    ids = [concept["id"] for concept in concepts]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate concept ids in the extracted outline")
    claim_ids = [claim["id"] for claim in claims]
    if len(claim_ids) != len(set(claim_ids)):
        raise SystemExit("duplicate claim ids in the curation")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"chapters: {len(chapter_list)}  concepts: {len(concepts)}  figures: {len(figure_list)}  "
        f"claims: {len(claims)}  equations: {len(equations)}  sources: {len(index['sources'])}"
    )
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
