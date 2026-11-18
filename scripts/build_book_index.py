"""Build the book index from a Docling conversion plus a curation overlay.

v2 joins each figure to its Docling asset and to the section that contains it:

* ``section_id`` is the nearest preceding numeric heading in ``document.md``;
  ``parent_section`` is its top-level section (``1.4.3`` -> ``1.4``).
* ``assets`` lists one or more panel images; ``F-1.4`` binds the two p26 panels.
* ``join_status`` is ``caption`` (a real caption), ``multi_asset`` (a figure
  with several panel images), ``reference_only`` (a prose sentence that starts
  with "Figure X" but is not a caption) or ``unassigned`` (listed separately,
  never dropped).
* ``hucho-figure-index.tsv`` is a review export, not a second source of truth.

Usage:
    uv run --project CourseControl python scripts/build_book_index.py \
        --docling <docling_output>/hucho-en-5e \
        --chapters 1,2,3 --curation <book>/curation.yaml \
        --out <book>/index.json --tsv <book>/hucho-figure-index.tsv
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

import yaml

PAGE_MARKER = re.compile(r"<!--\s*ks:page pdf=(\d+)\s*-->")
HEADING = re.compile(r"^#{1,6}\s+(\d+(?:\.\d+){0,3})\s+(.*)$")
IMAGE = re.compile(r"!\[[^\]]*\]\((assets/[^)]+)\)")
FIGURE_LINE = re.compile(r"^Figure\.?\s+(\d+\.\d+)\s+(.*)$")
CAPTION_NUMBER = re.compile(r"(?i)\bfig(?:ure)?\.?\s*(\d+\.\d+)\b")
CHAPTER = re.compile(r"^Chapter\s+(\d+)\s+(.*)$")
SECTION = re.compile(r"^(\d+(?:\.\d+)+)\s+(.*)$")


def _norm(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("­", "").replace("‐", "-").replace("‑", "-")
    return " ".join(text.split()).strip().lower()


def _number(text: str) -> str | None:
    match = CAPTION_NUMBER.search(text or "")
    return match.group(1) if match else None


def _strip_prefix(text: str) -> str:
    return re.sub(r"(?i)^\s*fig(?:ure)?\.?\s*\d+\.\d+\s*", "", text or "").strip()


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


def docling_pictures(docling: Path, offset: int) -> list[dict]:
    """Join each document.json picture to its document.md asset, page and section."""
    document = json.loads((docling / "document.json").read_text(encoding="utf-8"))
    pictures = document.get("pictures") or []
    texts = document.get("texts") or []

    metas: list[dict] = []
    page = None
    section_id = None
    parent = None
    for line in (docling / "document.md").read_text(encoding="utf-8").splitlines():
        marker = PAGE_MARKER.search(line)
        if marker:
            page = int(marker.group(1))
        heading = HEADING.match(line.strip())
        if heading:
            section_id = heading.group(1)
            parts = section_id.split(".")
            parent = ".".join(parts[:2]) if len(parts) >= 2 else section_id
        image = IMAGE.search(line)
        if image:
            metas.append(
                {
                    "asset": image.group(1),
                    "page": page,
                    "section_id": section_id,
                    "parent_section": parent,
                }
            )
    if len(metas) != len(pictures):
        raise SystemExit(
            f"document.md lists {len(metas)} images but document.json has "
            f"{len(pictures)} pictures; the asset join cannot be built"
        )
    rows: list[dict] = []
    for picture, meta in zip(pictures, metas):
        captions: list[str] = []
        for ref in picture.get("captions") or []:
            target = str(ref.get("$ref") or "")
            if not target.startswith("#/texts/"):
                continue
            try:
                item = texts[int(target.rsplit("/", 1)[1])]
            except (ValueError, IndexError):
                continue
            text = str(item.get("text") or item.get("orig") or "").strip()
            if text:
                captions.append(text)
        rows.append({**meta, "caption": " ".join(captions)})
    return rows


def pages_txt_lines(path: Path):
    page = None
    for line in path.read_text(encoding="utf-8").splitlines():
        marker = PAGE_MARKER.search(line)
        if marker:
            page = int(marker.group(1))
            continue
        yield page, line


def chapter_ranges(entries: list[dict]) -> dict[int, tuple[int, int]]:
    starts: list[tuple[int, int]] = []
    for entry in entries:
        match = CHAPTER.match(str(entry.get("title") or "").strip())
        if match and entry.get("level") == 1 and entry.get("page"):
            starts.append((int(match.group(1)), int(entry["page"])))
    starts.sort()
    ranges: dict[int, tuple[int, int]] = {}
    for index, (number, page) in enumerate(starts):
        end = starts[index + 1][1] - 1 if index + 1 < len(starts) else page + 300
        ranges[number] = (page, end)
    return ranges


def figure_rows(
    pictures: list[dict],
    pages_txt: Path,
    wanted: set[int],
    offset: int,
    curation: dict,
    entries: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Classify every figure/picture into caption, multi_asset, reference_only or unassigned."""
    true_rows: dict[str, dict] = {}
    used_assets: set[str] = set()

    for picture in pictures:
        number = _number(picture["caption"])
        if not number or int(number.split(".")[0]) not in wanted:
            continue
        row = true_rows.get(number)
        if row is None:
            row = {
                "id": "F-" + number,
                "number": number,
                "chapter": number.split(".")[0],
                "caption": _strip_prefix(picture["caption"]),
                "pdf_page": picture["page"],
                "page": picture["page"] - offset if picture["page"] else None,
                "section_id": picture["section_id"],
                "parent_section": picture["parent_section"],
                "assets": [],
                "join_status": "caption",
            }
            true_rows[number] = row
        if picture["asset"] not in row["assets"]:
            row["assets"].append(picture["asset"])
        used_assets.add(picture["asset"])
    for row in true_rows.values():
        if len(row["assets"]) > 1:
            row["join_status"] = "multi_asset"

    by_asset = {picture["asset"]: picture for picture in pictures}
    for raw_number, assets in (curation.get("figure_assets") or {}).items():
        number = str(raw_number)
        if int(number.split(".")[0]) not in wanted:
            continue
        if not isinstance(assets, list) or not assets:
            raise SystemExit(f"figure_assets[{number}] must be a non-empty list")
        for asset in assets:
            if asset not in by_asset:
                raise SystemExit(f"figure_assets[{number}]: asset not in document.md: {asset}")
        pages = {by_asset[asset]["page"] for asset in assets}
        if len(pages) != 1:
            raise SystemExit(f"figure_assets[{number}]: assets span pages {sorted(pages)}")
        row = true_rows.get(number)
        if row is None:
            page = next(iter(pages))
            first = by_asset[assets[0]]
            caption = ""
            for _, line in pages_txt_lines(pages_txt):
                match = FIGURE_LINE.match(line.strip())
                if match and match.group(1) == number:
                    caption = _strip_prefix(line.strip())
                    break
            row = {
                "id": "F-" + number,
                "number": number,
                "chapter": number.split(".")[0],
                "caption": caption,
                "pdf_page": page,
                "page": page - offset,
                "section_id": first["section_id"],
                "parent_section": first["parent_section"],
                "assets": [],
                "join_status": "multi_asset",
            }
            true_rows[number] = row
        for asset in assets:
            if asset not in row["assets"]:
                row["assets"].append(asset)
            used_assets.add(asset)
        row["join_status"] = "multi_asset" if len(row["assets"]) > 1 else "caption"

    references: list[dict] = []
    for page, line in pages_txt_lines(pages_txt):
        match = FIGURE_LINE.match(line.strip())
        if not match or page is None:
            continue
        number = match.group(1)
        if int(number.split(".")[0]) not in wanted:
            continue
        caption = _strip_prefix(line.strip())
        true_row = true_rows.get(number)
        if true_row and _norm(caption) == _norm(true_row["caption"]):
            continue
        references.append(
            {
                "id": "F-" + number,
                "number": number,
                "chapter": number.split(".")[0],
                "caption": caption,
                "pdf_page": page,
                "page": page - offset,
                "section_id": true_row["section_id"] if true_row else None,
                "parent_section": true_row["parent_section"] if true_row else None,
                "assets": [],
                "join_status": "reference_only",
            }
        )

    ranges = chapter_ranges(entries)
    wanted_ranges = [(lo, hi) for number, (lo, hi) in ranges.items() if number in wanted]
    unassigned: list[dict] = []
    for picture in pictures:
        if picture["asset"] in used_assets:
            continue
        section = picture["section_id"]
        if section:
            if int(section.split(".")[0]) not in wanted:
                continue
        elif not any(lo <= picture["page"] <= hi for lo, hi in wanted_ranges):
            continue
        unassigned.append(
            {
                "asset": picture["asset"],
                "pdf_page": picture["page"],
                "page": picture["page"] - offset if picture["page"] else None,
                "section_id": section,
                "parent_section": picture["parent_section"],
            }
        )

    figure_list = sorted(
        true_rows.values(), key=lambda row: (row["pdf_page"] or 0, row["number"])
    ) + sorted(references, key=lambda row: (row["pdf_page"] or 0, row["number"]))
    return figure_list, unassigned


def write_tsv(path: Path, rows: list[dict]) -> None:
    columns = [
        "figure_id",
        "number",
        "section_id",
        "parent_section",
        "pdf_page",
        "printed_page",
        "join_status",
        "assets",
        "caption",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("\t".join(columns) + "\n")
        for row in rows:
            values = [
                row["id"],
                row["number"],
                row.get("section_id") or "",
                row.get("parent_section") or "",
                row.get("pdf_page") or "",
                row.get("page") or "",
                row.get("join_status") or "",
                ";".join(row.get("assets") or []),
                row.get("caption") or "",
            ]
            handle.write(
                "\t".join(str(value).replace("\t", " ").replace("\n", " ") for value in values)
                + "\n"
            )


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
    parser.add_argument("--tsv", type=Path)
    args = parser.parse_args()

    wanted = {int(item) for item in args.chapters.split(",") if item.strip()}
    entries = load_outline(args.docling / "outline.json")
    chapter_list = chapters(entries, wanted, args.offset)
    pictures = docling_pictures(args.docling, args.offset)
    curation: dict = {}
    if args.curation:
        curation = yaml.safe_load(args.curation.read_text(encoding="utf-8")) or {}
    figure_list, unassigned = figure_rows(
        pictures, args.docling / "pages.txt", wanted, args.offset, curation, entries
    )

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

    claims = [
        {**claim, "chapter": str(claim.get("chapter"))}
        for claim in (curation.get("claims") or [])
    ]
    source_edition = f"{Path(args.docling).name} (5th ed., 2016)"
    for claim in claims:
        claim.setdefault("printed_page", claim.get("page"))
        if claim.get("pdf_page") is None and claim.get("printed_page") is not None:
            claim["pdf_page"] = int(claim["printed_page"]) + int(args.offset)
        claim.setdefault("source_edition", source_edition)
    for figure in figure_list:
        figure.setdefault("printed_page", figure.get("page"))
        figure.setdefault("source_edition", source_edition)
    equations = [
        {**equation, "chapter": str(equation.get("chapter"))}
        for equation in (curation.get("equations") or [])
    ]

    sources: list[dict] = []
    for concept in concepts:
        sources.append({"chapter": concept["chapter"], "section": concept["section"], "page": concept["page"]})
    for figure in figure_list:
        if figure["join_status"] == "reference_only":
            continue
        sources.append(
            {
                "chapter": figure["chapter"],
                "section": figure.get("section_id"),
                "figure": figure["number"],
                "page": figure["page"],
            }
        )
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

    true_rows = [row for row in figure_list if row["join_status"] in ("caption", "multi_asset")]
    true_ids = [row["id"] for row in true_rows]
    if len(true_ids) != len(set(true_ids)):
        duplicate = sorted({item for item in true_ids if true_ids.count(item) > 1})
        raise SystemExit(f"duplicate true caption figure ids: {duplicate}")
    for row in true_rows:
        if not row["assets"]:
            raise SystemExit(f"{row['id']}: true figure has no asset")
        if row["join_status"] == "multi_asset" and len(row["assets"]) < 2:
            raise SystemExit(f"{row['id']}: multi_asset figure has fewer than two assets")

    index = {
        "schema_version": 2,
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
        "unassigned_pictures": unassigned,
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
    if args.tsv:
        write_tsv(args.tsv, figure_list)
    reference_count = sum(1 for row in figure_list if row["join_status"] == "reference_only")
    print(
        f"chapters: {len(chapter_list)}  concepts: {len(concepts)}  "
        f"figures: {len(true_rows)} (reference_only {reference_count})  "
        f"unassigned pictures: {len(unassigned)}  claims: {len(claims)}  "
        f"equations: {len(equations)}  sources: {len(index['sources'])}"
    )
    print(f"written: {args.out}")
    if args.tsv:
        print(f"tsv: {args.tsv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
