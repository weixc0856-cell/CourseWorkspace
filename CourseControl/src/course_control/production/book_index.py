"""Book index and episode cards: load them, check the references.

The index is generated from the PDF (scripts/build_book_index.py) plus a
curation overlay; the cards name concepts, claims and figures from it. A card
that points at an id the book does not contain is a dead reference: it would
let an episode claim a source that does not exist, so it fails here.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

EPISODE_ID = re.compile(r"^[A-Z]\d+-\d{2}$")
MIN_SECONDS = 480


class BookIndexError(ValueError):
    pass


@dataclass
class EpisodeCard:
    path: Path
    episode: str
    title: str
    core_question: str
    target_seconds: int
    concepts: list[str]
    claims: list[str]
    figures: list[str]
    prerequisites: list[str]
    cut_list: list[str]
    section: str | None = None
    borrow_from: list[dict] = field(default_factory=list)


def load_book_index(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BookIndexError(f"book index not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise BookIndexError(f"invalid book index {path}: {exc}") from exc
    for key in ("concepts", "claims", "figures", "sources"):
        if not isinstance(data.get(key), list):
            raise BookIndexError(f"book index {path}: missing list {key!r}")
    return data


def load_card(path: Path) -> EpisodeCard:
    if not path.is_file():
        raise BookIndexError(f"episode card not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise BookIndexError(f"invalid YAML in {path}: {exc}") from exc
    missing = [
        key
        for key in ("episode", "title", "core_question", "target_seconds", "concepts", "cut_list")
        if key not in data or data[key] in (None, "", [])
    ]
    if missing:
        raise BookIndexError(f"{path}: missing {', '.join(missing)}")
    episode = str(data["episode"])
    if not EPISODE_ID.match(episode):
        raise BookIndexError(f"{path}: invalid episode id {episode!r}")
    seconds = int(data["target_seconds"])
    if seconds < MIN_SECONDS:
        raise BookIndexError(f"{path}: target_seconds {seconds} below the {MIN_SECONDS}s floor")
    return EpisodeCard(
        path=path,
        episode=episode,
        title=str(data["title"]),
        core_question=str(data["core_question"]),
        target_seconds=seconds,
        concepts=[str(item) for item in data["concepts"]],
        claims=[str(item) for item in data.get("claims") or []],
        figures=[str(item) for item in data.get("figures") or []],
        prerequisites=[str(item) for item in data.get("prerequisites") or []],
        cut_list=[str(item) for item in data["cut_list"]],
        section=str(data["section"]).strip() if data.get("section") not in (None, "") else None,
        borrow_from=[dict(item) for item in (data.get("borrow_from") or []) if isinstance(item, dict)],
    )


COURSE_MAP_EPISODE = re.compile(r"^T\d+-\d{2}$")
COURSE_MAP_MINUTES = re.compile(r"^(\d+)\s*(?:min)?$")
# A legacy map spells the section as "1.1 Scope"; the English section name is
# prose, not part of the id. v5.2 ranges ("1.2.5–1.2.6"), unions ("1.9 & 1.11")
# and Chinese markers ("6.3.3 扩展") are part of the id and must survive.
COURSE_MAP_SECTION_PROSE = re.compile(r"\s+[A-Za-z][A-Za-z0-9 ,\-/'()]*$")
# LaTeX in a summary cell escapes its pipes ("\|A_F\|"); those are not columns.
COURSE_MAP_CELL_SPLIT = re.compile(r"(?<!\\)\|")


def _map_cells(line: str) -> list[str]:
    parts = COURSE_MAP_CELL_SPLIT.split(line)
    return [item.strip().replace("**", "").strip() for item in parts[1:-1]]


def load_course_map(path: Path) -> list[dict]:
    """Read the episode table from COURSE_MAP.md; the map is the source of truth.

    Two table shapes are accepted: the legacy 5-column row and the v5.2-Freeze
    7-column row (which adds a page column, a source tag and a "N min" unit).
    Cells are matched by shape rather than by position so a column added later
    does not silently shift the parse. Other tables in the same document reuse
    episode ids (the T2 theory-to-engineering mapping table is 3-column), so a
    row only counts when it has a known column count *and* a minutes cell.
    """
    if not path.is_file():
        raise BookIndexError(f"course map not found: {path}")
    text = path.read_text(encoding="utf-8")
    rows: list[dict] = []
    seen: set[str] = set()
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = _map_cells(line)
        if len(cells) not in (5, 7):
            continue
        episode = cells[0]
        if not COURSE_MAP_EPISODE.match(episode) or episode in seen:
            continue
        minutes = None
        for cell in cells[3:]:
            match = COURSE_MAP_MINUTES.match(cell.strip("`"))
            if match:
                minutes = int(match.group(1))
        if minutes is None:
            continue
        section = COURSE_MAP_SECTION_PROSE.sub("", cells[2]).strip()
        rows.append(
            {
                "episode": episode,
                "title": cells[1],
                "section": section,
                "minutes": minutes,
            }
        )
        seen.add(episode)
    if not rows:
        raise BookIndexError(f"{path}: no episode rows found")
    return rows


def check_cards(
    index: dict[str, Any],
    cards: list[EpisodeCard],
    map_episodes: list[dict] | None = None,
) -> list[str]:
    concept_ids = {str(item["id"]) for item in index["concepts"]}
    claim_ids = {str(item["id"]) for item in index["claims"]}
    figure_ids = {str(item["id"]) for item in index["figures"]}
    problems: list[str] = []
    episodes = [card.episode for card in cards]
    for duplicate in sorted({item for item in episodes if episodes.count(item) > 1}):
        problems.append(f"duplicate episode id: {duplicate}")
    known = set(episodes)
    for card in cards:
        name = card.path.name
        for concept in card.concepts:
            if concept not in concept_ids:
                problems.append(f"{card.episode} ({name}): unknown concept {concept}")
        for claim in card.claims:
            if claim not in claim_ids:
                problems.append(f"{card.episode} ({name}): unknown claim {claim}")
        for figure in card.figures:
            if figure not in figure_ids:
                problems.append(f"{card.episode} ({name}): unknown figure {figure}")
        for prerequisite in card.prerequisites:
            if prerequisite not in known:
                problems.append(f"{card.episode} ({name}): unknown prerequisite {prerequisite}")

    # Structural checks for the schema-2 index. The old schema has no
    # join_status/parent_section and is kept readable for archived material.
    if int(index.get("schema_version") or 0) >= 2:
        true_rows = [
            row
            for row in index["figures"]
            if str(row.get("join_status") or "") in {"caption", "multi_asset"}
        ]
        true_ids = [str(row["id"]) for row in true_rows]
        for duplicate in sorted({item for item in true_ids if true_ids.count(item) > 1}):
            problems.append(f"duplicate true caption figure id: {duplicate}")
        for row in true_rows:
            assets = row.get("assets")
            if not isinstance(assets, list) or not assets:
                problems.append(f"{row['id']}: true caption has no asset")
            elif str(row.get("join_status")) == "multi_asset" and len(assets) < 2:
                problems.append(f"{row['id']}: multi_asset figure needs at least two assets")
        if not isinstance(index.get("unassigned_pictures"), list):
            problems.append("book index schema 2 needs an unassigned_pictures list")
        parent_by_figure = {
            str(row["id"]): str(row.get("parent_section") or "") for row in true_rows
        }
        for card in cards:
            if not card.section:
                problems.append(f"{card.episode}: card has no section")
                continue
            for figure in card.figures:
                parent = parent_by_figure.get(figure)
                if not parent or parent == card.section:
                    continue
                borrowed = any(
                    str(item.get("section") or "") == parent
                    and str(item.get("reason") or "").strip()
                    for item in card.borrow_from
                )
                if not borrowed:
                    problems.append(
                        f"{card.episode}: figure {figure} belongs to {parent}, "
                        f"not {card.section}; add borrow_from "
                        f"{{section: {parent}, reason: ...}}"
                    )

    if map_episodes is not None:
        # The map may detail a module before its cards exist; a card, however,
        # may never point outside the map. Count equality would force all 180
        # cards to exist at once and turn a planned episode into a failure.
        map_by_id = {str(row["episode"]): row for row in map_episodes}
        card_ids = [card.episode for card in cards]
        for duplicate in sorted({item for item in card_ids if card_ids.count(item) > 1}):
            problems.append(f"duplicate card for episode {duplicate}")
        for extra in sorted(set(card_ids) - set(map_by_id)):
            problems.append(f"card {extra} is not in the map")
        for card in cards:
            row = map_by_id.get(card.episode)
            if row is None:
                continue
            if card.section and card.section != row["section"]:
                problems.append(
                    f"{card.episode}: card section {card.section} != map section {row['section']}"
                )
            if card.title and card.title.strip() != str(row["title"]).strip():
                problems.append(
                    f"{card.episode}: card title {card.title!r} != map title {row['title']!r}"
                )
            expected_seconds = int(row["minutes"]) * 60
            if card.target_seconds != expected_seconds:
                problems.append(
                    f"{card.episode}: card target_seconds {card.target_seconds} "
                    f"!= map row {row['minutes']} minutes"
                )
    return problems


def load_card_dir(path: Path) -> list[EpisodeCard]:
    if not path.is_dir():
        raise BookIndexError(f"card directory not found: {path}")
    cards = [load_card(item) for item in sorted(path.glob("*/card.yaml"))]
    if not cards:
        raise BookIndexError(f"no cards under {path}")
    return cards
