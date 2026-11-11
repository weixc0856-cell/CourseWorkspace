"""Mechanical check that a claim's cited page contains the claimed span.

This is deliberately narrower than fact checking. It answers three questions:

- does every cited page still exist with the recorded hash?
- does the claim's optional verbatim quote appear on a cited page?
- do the numbers in the claim statement appear on the cited pages?

It never sets ``verification``. Whether a quote supports a claim is a human
decision; the tool only proves that the text being cited is actually there.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .extract import load_page_texts, sha256_text
from .models import EvidenceFile

NUMBER = re.compile(
    r"(?<![\w.])(?:US\$|\$|€|£)?\d+(?:[.,]\d+)*(?:\s?%|\s?(?:million|billion|trillion|thousand|x|×))?",
    re.IGNORECASE,
)
CORE = re.compile(r"\d+(?:\.\d+)*")
TRANSLATION = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "–": "-",
        "—": "-",
        "−": "-",
        " ": " ",
        "­": "",
    }
)


def normalize(text: str) -> str:
    """Case-fold, join hyphenated line breaks and collapse whitespace."""
    text = text.translate(TRANSLATION)
    text = re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[a-z])", "", text)
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def _quote_present(quote: str, pages: list[str]) -> bool:
    needle = normalize(quote)
    return bool(needle) and any(needle in normalize(page) for page in pages)


def _numbers(statement: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for match in NUMBER.finditer(statement):
        value = match.group(0).strip()
        core = CORE.search(value.replace(",", ""))
        key = core.group(0) if core else normalize(value)
        if key and key not in seen:
            seen.add(key)
            values.append(value)
    return values


def _number_present(value: str, pages: list[str]) -> bool:
    core = CORE.search(value.replace(",", ""))
    if core is None:
        return any(normalize(value) in normalize(page) for page in pages)
    pattern = re.compile(r"(?<![\d.])" + re.escape(core.group(0)) + r"(?![\d.])")
    return any(pattern.search(normalize(page)) for page in pages)


def _load_quotes(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("claims", raw) if isinstance(raw, dict) else raw
    quotes: dict[str, str] = {}
    for item in items:
        claim_id = str(item.get("claim_id") or "").strip()
        quote = str(item.get("quote") or "").strip()
        if claim_id and quote:
            quotes[claim_id] = quote
    return quotes


def check(
    root: Path,
    evidence_path: Path,
    *,
    claims_path: Path | None = None,
    strict_numbers: bool = False,
) -> dict:
    root = root.resolve()
    evidence = EvidenceFile.model_validate_json(evidence_path.read_text(encoding="utf-8"))
    page_texts = load_page_texts(root)
    quotes = _load_quotes(claims_path)

    results: list[dict] = []
    for claim in evidence.claims:
        quote = (claim.quote or quotes.get(claim.claim_id) or "").strip() or None
        cited_pages: list[int] = []
        problems: list[str] = []
        page_bodies: list[str] = []
        for citation in claim.citations:
            body = page_texts.get(citation.pdf_page)
            if body is None:
                problems.append(f"page {citation.pdf_page} missing")
                continue
            if sha256_text(body) != citation.page_sha256:
                problems.append(f"page {citation.pdf_page} hash changed")
                continue
            cited_pages.append(citation.pdf_page)
            page_bodies.append(body)

        numbers = _numbers(claim.statement)
        missing_numbers = [
            value for value in numbers if not _number_present(value, page_bodies)
        ]

        if problems:
            status = "blocked"
            detail = "; ".join(problems)
        elif quote is None:
            status = "no_quote"
            detail = "no quote supplied; presence cannot be checked"
        elif not _quote_present(quote, page_bodies):
            status = "quote_missing"
            detail = "quote not found on any cited page"
        elif missing_numbers:
            status = "numbers_missing"
            detail = "numbers not found: " + ", ".join(missing_numbers)
        else:
            status = "ok"
            detail = "quote and numbers found on cited pages"

        results.append(
            {
                "claim_id": claim.claim_id,
                "statement": claim.statement,
                "quote": quote,
                "cited_pages": cited_pages,
                "numbers": numbers,
                "missing_numbers": missing_numbers,
                "status": status,
                "detail": detail,
            }
        )

    blocking = [
        item for item in results if item["status"] in {"blocked", "quote_missing"}
    ]
    warnings = [
        item for item in results if item["status"] in {"no_quote", "numbers_missing"}
    ]
    if strict_numbers:
        blocking.extend(
            item for item in results if item["status"] == "numbers_missing"
        )
        warnings = [item for item in results if item["status"] == "no_quote"]
    if blocking:
        overall = "blocked"
    elif warnings:
        overall = "warn"
    else:
        overall = "pass"

    return {
        "schema_version": 1,
        "source_id": evidence.source_id,
        "evidence": evidence_path.name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "strict_numbers": strict_numbers,
        "status": overall,
        "claims": results,
        "counts": {
            "claims": len(results),
            "ok": sum(1 for item in results if item["status"] == "ok"),
            "warnings": len(warnings),
            "blocking": len(blocking),
        },
        "note": (
            "Presence only. This does not prove the quote supports the claim, "
            "and never marks a claim verified."
        ),
    }


def write(root: Path, report: dict, evidence_path: Path) -> dict[str, Path]:
    stem = evidence_path.name.replace(".evidence.json", "").replace(".json", "")
    target = root / "evidence" / f"{stem}.spancheck.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        f"# Span check — {report['source_id']} / {report['evidence']}",
        "",
        f"- status: **{report['status']}**",
        f"- claims: {report['counts']['claims']} · ok {report['counts']['ok']} · "
        f"warnings {report['counts']['warnings']} · blocking {report['counts']['blocking']}",
        "",
        "| claim | status | pages | detail |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["claims"]:
        pages = ", ".join(str(page) for page in item["cited_pages"]) or "—"
        detail = item["detail"].replace("|", "\\|")
        lines.append(f"| {item['claim_id']} | {item['status']} | {pages} | {detail} |")
    lines += ["", f"> {report['note']}", ""]
    markdown = target.with_suffix(".md")
    markdown.write_text("\n".join(lines), encoding="utf-8")
    return {"json": target, "markdown": markdown}
