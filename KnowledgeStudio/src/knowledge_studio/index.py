"""SQLite + FTS5 index over extracted pages and units."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .extract import detect_figures, load_page_texts, sha256_text
from .segment import load_units, manifest_hash

CJK = re.compile(r"([一-鿿])")


class IndexError(RuntimeError):
    """The index is missing or cannot be rebuilt."""


def cjk_spaced(text: str) -> str:
    """Space every CJK character so FTS5 unicode61 can match Chinese phrases.

    unicode61 treats a run of CJK as one token; indexing each character means a
    query phrase like ``"阻 力"`` matches inside any sentence.
    """

    return CJK.sub(r" \1 ", text)


def db_path(root: Path) -> Path:
    return root / "index" / "knowledge.db"


def build(root: Path, source_id: str) -> dict:
    pages = load_page_texts(root)
    if not pages:
        raise IndexError("no pages to index")
    units = load_units(root)
    target = db_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    connection = sqlite3.connect(target)
    try:
        connection.executescript(
            """
            CREATE TABLE pages (
                pdf_page INTEGER PRIMARY KEY,
                printed_page INTEGER,
                text TEXT NOT NULL,
                sha256 TEXT NOT NULL
            );
            CREATE TABLE units (
                unit_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                pdf_start INTEGER NOT NULL,
                pdf_end INTEGER NOT NULL,
                keywords TEXT NOT NULL
            );
            CREATE TABLE figures (
                pdf_page INTEGER NOT NULL,
                kind TEXT NOT NULL,
                label TEXT NOT NULL,
                caption TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE pages_fts USING fts5(
                body, pdf_page UNINDEXED, tokenize='unicode61'
            );
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )
        printed = _printed_map(root)
        for number in sorted(pages):
            text = pages[number]
            connection.execute(
                "INSERT INTO pages (pdf_page, printed_page, text, sha256) VALUES (?, ?, ?, ?)",
                (number, printed.get(number), text, sha256_text(text)),
            )
            connection.execute(
                "INSERT INTO pages_fts (body, pdf_page) VALUES (?, ?)",
                (cjk_spaced(text), number),
            )
            for figure in detect_figures(text, number):
                connection.execute(
                    "INSERT INTO figures (pdf_page, kind, label, caption) VALUES (?, ?, ?, ?)",
                    (number, figure.kind, figure.label, figure.caption),
                )
        for unit in units:
            connection.execute(
                "INSERT INTO units (unit_id, title, pdf_start, pdf_end, keywords) VALUES (?, ?, ?, ?, ?)",
                (
                    unit.unit_id,
                    unit.title,
                    unit.pdf_pages[0],
                    unit.pdf_pages[1],
                    " ".join(unit.keywords),
                ),
            )
        meta = {
            "schema_version": "1",
            "source_id": source_id,
            "pages": str(len(pages)),
            "units": str(len(units)),
            "manifest_hash": manifest_hash(units),
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        connection.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)", list(meta.items())
        )
        connection.commit()
    finally:
        connection.close()
    return {
        "db": target,
        "pages": len(pages),
        "units": len(units),
        "meta": meta,
    }


def connect(root: Path) -> sqlite3.Connection:
    path = db_path(root)
    if not path.is_file():
        raise IndexError("index missing; run `knowledge-studio index` first")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def match_pages(connection: sqlite3.Connection, expression: str, limit: int = 400) -> list[tuple[int, float]]:
    """Return (pdf_page, score) ordered by relevance; score is positive-is-better."""

    rows = connection.execute(
        "SELECT pdf_page, bm25(pages_fts) AS rank FROM pages_fts "
        "WHERE pages_fts MATCH ? ORDER BY rank LIMIT ?",
        (expression, limit),
    ).fetchall()
    return [(int(row["pdf_page"]), -float(row["rank"])) for row in rows]


def page_row(connection: sqlite3.Connection, page: int) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT pdf_page, printed_page, text, sha256 FROM pages WHERE pdf_page = ?",
        (page,),
    ).fetchone()


def units(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT unit_id, title, pdf_start, pdf_end, keywords FROM units ORDER BY pdf_start"
    ).fetchall()


def meta(connection: sqlite3.Connection) -> dict[str, str]:
    return {row["key"]: row["value"] for row in connection.execute("SELECT key, value FROM meta")}


def _printed_map(root: Path) -> dict[int, int]:
    path = root / "metadata" / "page_map.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        int(item["pdf_page"]): int(item["printed_page"])
        for item in data.get("pages", [])
        if item.get("printed_page") is not None
    }
