"""Source QA: every page, unit, citation and claim must point at real text."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .extract import PAGE_MARKER, load_page_texts, sha256_text
from .models import EvidenceFile, RetrievalResult, SourceMeta, TocEntry, UnitMeta
from .segment import load_units, manifest_hash
from .toc import load as load_toc


def load_source(root: Path) -> SourceMeta:
    path = root / "source.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"source.yaml missing in {root}")
    return SourceMeta.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_page_map(root: Path) -> list[dict]:
    path = root / "metadata" / "page_map.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("pages", [])


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check(check_id: str, ok: bool, detail: str) -> dict:
    return {"id": check_id, "status": "pass" if ok else "blocked", "detail": detail}


def verify(root: Path) -> dict:
    checks: list[dict] = []
    try:
        source = load_source(root)
    except Exception as exc:  # noqa: BLE001
        return {
            "schema_version": 1,
            "status": "blocked",
            "checks": [_check("KS-01", False, f"source.yaml unreadable: {exc}")],
        }

    original = root / source.original
    checks.append(
        _check(
            "KS-01",
            original.is_file() and _sha_file(original) == source.original_sha256,
            f"original file present and hash matches ({source.original})",
        )
    )

    pages = load_page_texts(root)
    checks.append(
        _check(
            "KS-02",
            len(pages) == source.pdf_pages,
            f"page files {len(pages)} == pdf_pages {source.pdf_pages}",
        )
    )

    page_map = load_page_map(root)
    stored = {int(item["pdf_page"]): item for item in page_map}
    mismatched = [
        number
        for number, text in pages.items()
        if number in stored and stored[number].get("sha256") != sha256_text(text)
    ]
    checks.append(
        _check(
            "KS-03",
            len(page_map) == source.pdf_pages and not mismatched,
            f"page_map covers {len(page_map)} pages; hash mismatches: {mismatched[:5]}",
        )
    )

    try:
        entries, _ = load_toc(root)
        bad_toc = [
            entry.title
            for entry in entries
            if entry.pdf_page is not None and not 1 <= entry.pdf_page <= source.pdf_pages
        ]
        checks.append(
            _check("KS-04", bool(entries) and not bad_toc, f"TOC entries in range ({len(entries)}); out of range: {bad_toc[:3]}")
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(_check("KS-04", False, f"TOC unreadable: {exc}"))

    try:
        units = load_units(root)
    except Exception as exc:  # noqa: BLE001
        units = []
        checks.append(_check("KS-05", False, f"units unreadable: {exc}"))
    if units:
        problems = []
        previous_end = 0
        for unit in units:
            start, end = unit.pdf_pages
            if start <= previous_end:
                problems.append(f"{unit.unit_id} overlaps the previous unit")
            if end > source.pdf_pages:
                problems.append(f"{unit.unit_id} ends beyond the source")
            folder = next((root / "units").glob(f"{unit.unit_id}*"), None)
            if folder is None:
                problems.append(f"{unit.unit_id} folder missing")
                continue
            page_file = next((folder / name for name in unit.files if name.startswith("pages_")), None)
            if page_file is None or not page_file.is_file():
                problems.append(f"{unit.unit_id} page file missing")
            else:
                markers = [
                    int(match.group(1))
                    for match in PAGE_MARKER.finditer(page_file.read_text(encoding="utf-8"))
                ]
                if markers != list(range(start, end + 1)):
                    problems.append(f"{unit.unit_id} page markers do not cover {start}-{end}")
            previous_end = end
        checks.append(
            _check("KS-05", not problems, "; ".join(problems[:6]) if problems else f"{len(units)} units contiguous and in range")
        )

    index_path = root / "index" / "knowledge.db"
    index_ok = index_path.is_file()
    detail = "index/knowledge.db present" if index_ok else "index missing (run `index`)"
    if index_ok and units:
        import sqlite3  # noqa: PLC0415 — only for the meta lookup

        connection = sqlite3.connect(index_path)
        try:
            meta = {row[0]: row[1] for row in connection.execute("SELECT key, value FROM meta")}
        finally:
            connection.close()
        index_ok = (
            int(meta.get("pages", 0)) == source.pdf_pages
            and meta.get("manifest_hash") == manifest_hash(units)
        )
        detail = "index matches the current pages and units" if index_ok else (
            "index is stale: rebuild with `index`"
        )
    checks.append(_check("KS-06", index_ok, detail))

    retrieval_problems: list[str] = []
    retrieval_files = sorted((root / "retrieval").glob("*.json"))
    for path in retrieval_files:
        try:
            result = RetrievalResult.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            retrieval_problems.append(f"{path.name}: {exc}")
            continue
        for citation in result.citations:
            if citation.pdf_page not in pages:
                retrieval_problems.append(f"{path.name}: page {citation.pdf_page} missing")
                continue
            stored_sha = stored.get(citation.pdf_page, {}).get("sha256")
            if stored_sha and stored_sha != citation.page_sha256:
                retrieval_problems.append(f"{path.name}: page {citation.pdf_page} hash changed")
        for excerpt in result.excerpts:
            if sha256_text(excerpt.text) not in {c.excerpt_sha256 for c in result.citations}:
                retrieval_problems.append(f"{path.name}: excerpt {excerpt.ref} is not cited")
    checks.append(
        _check(
            "KS-07",
            not retrieval_problems,
            "; ".join(retrieval_problems[:6]) if retrieval_problems else f"{len(retrieval_files)} retrieval file(s) traceable",
        )
    )

    evidence_problems: list[str] = []
    for path in sorted((root / "evidence").glob("*.json")):
        try:
            evidence = EvidenceFile.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            evidence_problems.append(f"{path.name}: {exc}")
            continue
        pool = {citation.ref for citation in evidence.citation_pool}
        for claim in evidence.claims:
            if not claim.citations:
                evidence_problems.append(f"{claim.claim_id}: no citation")
            for citation in claim.citations:
                if citation.ref not in pool:
                    evidence_problems.append(f"{claim.claim_id}: {citation.ref} not in citation pool")
    checks.append(
        _check(
            "KS-08",
            not evidence_problems,
            "; ".join(evidence_problems[:6]) if evidence_problems else "claims cite the retrieved pool",
        )
    )

    report = {
        "schema_version": 1,
        "source_id": source.source_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "blocked" if any(check["status"] == "blocked" for check in checks) else "pass",
        "checks": checks,
        "counts": {
            "pages": len(pages),
            "units": len(units),
            "retrievals": len(retrieval_files),
        },
    }
    target = root / "qa" / "report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
