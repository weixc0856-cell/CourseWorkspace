"""Book index and episode cards: load them, check the references.

The index is generated from the PDF (scripts/build_book_index.py) plus a
curation overlay; the cards name concepts, claims and figures from it. A card
that points at an id the book does not contain is a dead reference: it would
let an episode claim a source that does not exist, so it fails here.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

EPISODE_ID = re.compile(r"^[A-Z]\d+-\d{2}$")
MIN_SECONDS = 480
MAX_SECONDS = 900


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
    if not MIN_SECONDS <= seconds <= MAX_SECONDS:
        raise BookIndexError(f"{path}: target_seconds {seconds} outside {MIN_SECONDS}-{MAX_SECONDS}")
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
    )


def check_cards(index: dict[str, Any], cards: list[EpisodeCard]) -> list[str]:
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
    return problems


def load_card_dir(path: Path) -> list[EpisodeCard]:
    if not path.is_dir():
        raise BookIndexError(f"card directory not found: {path}")
    cards = [load_card(item) for item in sorted(path.glob("*/card.yaml"))]
    if not cards:
        raise BookIndexError(f"no cards under {path}")
    return cards
