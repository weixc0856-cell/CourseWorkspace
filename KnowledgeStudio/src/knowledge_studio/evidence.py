"""Claim-level evidence: each claim can only cite pages that were retrieved."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import ClaimRef, EvidenceFile, RetrievalResult


class EvidenceError(RuntimeError):
    """A claim cites a page that was not retrieved, or has no citation."""


def attach(root: Path, retrieval_path: Path, claims_path: Path) -> Path:
    result = RetrievalResult.model_validate_json(
        retrieval_path.read_text(encoding="utf-8")
    )
    raw = json.loads(claims_path.read_text(encoding="utf-8"))
    items = raw.get("claims", raw) if isinstance(raw, dict) else raw
    pool = {citation.pdf_page: citation for citation in result.citations}
    claims: list[ClaimRef] = []
    problems: list[str] = []
    for index, item in enumerate(items, start=1):
        claim_id = str(item.get("claim_id") or f"C{index:03d}")
        statement = str(item.get("statement") or "").strip()
        if not statement:
            problems.append(f"{claim_id}: empty statement")
        citations = []
        for page in item.get("pages") or []:
            citation = pool.get(int(page))
            if citation is None:
                problems.append(f"{claim_id}: page {page} was not retrieved")
                continue
            citations.append(citation)
        if not citations:
            problems.append(f"{claim_id}: no valid citation")
        claims.append(
            ClaimRef(
                claim_id=claim_id,
                statement=statement,
                citations=citations,
                verification="pending",
            )
        )
    if problems:
        raise EvidenceError("; ".join(problems))
    evidence = EvidenceFile(
        source_id=result.source_id,
        retrieval=retrieval_path.relative_to(root).as_posix(),
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        claims=claims,
        citation_pool=result.citations,
    )
    target = root / "evidence" / f"{result.query_id}.evidence.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(evidence.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target
