"""Lexicon: how this series says its terms.

A lexicon is a list of ``term -> say`` pairs -- acronyms, product names,
symbols, words whose pronunciation depends on the field.  It rewrites the text
just before synthesis, so the audio says "N-V-D-A" while the script, the
subtitles and the notes keep saying "NVDA".

Invalidation is per segment: the cache key records the pairs that actually
matched, so editing an entry re-synthesises only the segments that use it.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, field_validator

from ..contracts import SLUG_RE, StrictModel
from .voice_bible import AudioAssetError


class LexiconEntry(StrictModel):
    term: str
    say: str
    note: str | None = None

    @field_validator("term", "say")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class Lexicon(StrictModel):
    schema_version: Literal[1] = 1
    id: str
    language: str = Field(default="en", min_length=2, max_length=16)
    entries: list[LexiconEntry] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id_is_slug(cls, value: str) -> str:
        if not SLUG_RE.match(value):
            raise ValueError("lexicon id must be a slug")
        return value

    @field_validator("entries")
    @classmethod
    def _terms_unique(cls, value: list[LexiconEntry]) -> list[LexiconEntry]:
        seen: dict[str, str] = {}
        for entry in value:
            key = entry.term.casefold()
            if key in seen and seen[key] != entry.say:
                raise ValueError(f"term '{entry.term}' is defined twice with different readings")
            seen[key] = entry.say
        return value


@dataclass(frozen=True)
class Application:
    """The rewritten text and the pairs that rewrote it."""

    text: str
    applied: tuple[tuple[str, str], ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.applied)


def load(path: Path) -> Lexicon:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise AudioAssetError(f"cannot read lexicon {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AudioAssetError(f"lexicon {path} is not a mapping")
    try:
        return Lexicon.model_validate(data)
    except Exception as exc:  # noqa: BLE001 - surface pydantic's message verbatim
        raise AudioAssetError(f"invalid lexicon {path}: {exc}") from exc


def resolve(root: Path, ident: str) -> Path:
    """``<content_root>/audio/lexicons/<id>.yaml``."""
    return (Path(root) / "lexicons" / f"{ident}.yaml").resolve()


def digest(lexicon: Lexicon) -> str:
    payload = json.dumps(lexicon.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def apply(lexicon: Lexicon, text: str) -> Application:
    """Rewrite one pass, longest term first, so replacements are never re-read."""
    if not lexicon.entries or not text:
        return Application(text)
    ordered = sorted(lexicon.entries, key=lambda entry: len(entry.term), reverse=True)
    say_by_term = {entry.term.casefold(): entry.say for entry in ordered}
    pattern = re.compile("|".join(_branch(entry.term) for entry in ordered), re.IGNORECASE)
    applied: dict[str, str] = {}

    def _replace(match: re.Match[str]) -> str:
        term = match.group(0)
        say = say_by_term[term.casefold()]
        applied[term] = say
        return say

    rewritten = pattern.sub(_replace, text)
    pairs = tuple(sorted(applied.items(), key=lambda item: item[0].casefold()))
    return Application(rewritten, pairs)


def _branch(term: str) -> str:
    """A latin term matches whole words; a CJK or symbol term matches as-is."""
    if term[0].isascii() and term[0].isalnum() and term[-1].isascii() and term[-1].isalnum():
        return rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])"
    return re.escape(term)


def check(lexicon: Lexicon, source: Path) -> list[str]:
    problems: list[str] = []
    for entry in lexicon.entries:
        if entry.term == entry.say:
            problems.append(f"entry '{entry.term}' reads the same as it is written")
    if not lexicon.entries:
        problems.append("lexicon has no entries")
    if not Path(source).is_file():
        problems.append(f"lexicon file not found: {source}")
    return problems
