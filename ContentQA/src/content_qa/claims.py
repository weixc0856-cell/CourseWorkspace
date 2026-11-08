"""Claim Registry: turn candidate findings into auditable claims.

A claim is not a fact.  The registry records its type, risk, sources and
review state so a human can see what is supported, what is missing evidence,
and what still needs a decision.
"""

from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

CLAIM_ID = re.compile(r"^C-\d{3,}$")


class ClaimType(str, Enum):
    fact = "fact"
    mechanism = "mechanism"
    derivation = "derivation"
    engineering = "engineering"
    opinion = "opinion"
    analogy = "analogy"
    time_sensitive = "time_sensitive"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ReviewStatus(str, Enum):
    supported = "supported"
    unsupported = "unsupported"
    disputed = "disputed"
    needs_human_review = "needs_human_review"
    not_checked = "not_checked"


class Claim(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claim_id: str = Field(pattern=r"^C-\d{3,}$")
    claim_text: str = Field(min_length=1)
    claim_type: ClaimType = ClaimType.fact
    source_refs: list[str] = Field(default_factory=list)
    source_location: str = ""
    slide_id: int = Field(ge=1)
    risk_level: RiskLevel = RiskLevel.medium
    applicability: str = ""
    review_status: ReviewStatus = ReviewStatus.needs_human_review
    review_evidence: str = ""


class ClaimRegistry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: int = 1
    lesson: str
    claims: list[Claim] = Field(default_factory=list)


ABSOLUTE_WORDS = (
    "always",
    "never",
    "all ",
    "every ",
    "proves",
    "guarantees",
    "impossible",
    "definitely",
)


def infer_type(text: str) -> ClaimType:
    value = text.lower()
    if any(word in value for word in ("i think", "we believe", "in my view", "should")):
        return ClaimType.opinion
    if any(word in value for word in ("like ", "think of", "imagine", "analogy", "metaphor")):
        return ClaimType.analogy
    if any(
        word in value
        for word in ("latest", "current version", "as of 20", "released in 20", "now supports")
    ):
        return ClaimType.time_sensitive
    if any(word in value for word in ("formula", "equation", "derivation", "derive", "proof")):
        return ClaimType.derivation
    if any(word in value for word in ("how ", "mechanism", "computes", "works by")):
        return ClaimType.mechanism
    if any(word in value for word in ("in practice", "engineering", "design rule", "tolerance")):
        return ClaimType.engineering
    return ClaimType.fact


def evidence_problems(claim: Claim, source_ids: set[str] | None) -> list[str]:
    problems: list[str] = []
    if not claim.source_refs:
        problems.append("no source_refs")
    if source_ids is not None:
        unknown = sorted(set(claim.source_refs) - source_ids)
        if unknown:
            problems.append("unknown source ids: " + ", ".join(unknown))
    text = claim.claim_text.lower()
    if any(word in text for word in ABSOLUTE_WORDS):
        problems.append("absolute wording")
    return problems


def risk_for(
    claim_type: ClaimType,
    review_status: ReviewStatus,
    problems: list[str],
) -> RiskLevel:
    if review_status in (ReviewStatus.unsupported, ReviewStatus.disputed):
        return RiskLevel.high
    if problems:
        return RiskLevel.high
    if claim_type in (ClaimType.opinion, ClaimType.analogy):
        return RiskLevel.medium
    if review_status in (ReviewStatus.needs_human_review, ReviewStatus.not_checked):
        return RiskLevel.medium
    return RiskLevel.low


def registry_from_report(
    report: dict,
    *,
    source_ids: set[str] | None = None,
) -> ClaimRegistry:
    claims: list[Claim] = []
    for index, finding in enumerate(report.get("findings") or [], start=1):
        text = str(finding.get("claim") or "").strip()
        if not text:
            continue
        refs = [str(ref) for ref in finding.get("source_refs") or [] if str(ref).strip()]
        claim_type = infer_type(text)
        verdict = str(finding.get("verdict") or "needs_human_review")
        try:
            status = ReviewStatus(verdict)
        except ValueError:
            status = ReviewStatus.needs_human_review
        claim = Claim(
            claim_id=f"C-{index:03d}",
            claim_text=text,
            claim_type=claim_type,
            source_refs=refs,
            source_location=f"slide {int(finding.get('slide') or 1)}",
            slide_id=int(finding.get("slide") or 1),
            review_status=status,
            review_evidence=str(finding.get("rationale") or ""),
        )
        problems = evidence_problems(claim, source_ids)
        claim.risk_level = risk_for(claim_type, status, problems)
        claims.append(claim)
    return ClaimRegistry(lesson=str(report.get("lesson") or ""), claims=claims)


def load_source_ids(lesson_dir: Path, sources_file: str = "sources.yaml") -> set[str] | None:
    import yaml

    path = lesson_dir / sources_file
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    entries = data.get("sources") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return None
    return {
        str(entry.get("id"))
        for entry in entries
        if isinstance(entry, dict) and entry.get("id")
    }


def write_registry(path: Path, registry: ClaimRegistry) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(registry.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


__all__ = [
    "Claim",
    "ClaimRegistry",
    "ClaimType",
    "RiskLevel",
    "ReviewStatus",
    "evidence_problems",
    "infer_type",
    "load_source_ids",
    "registry_from_report",
    "risk_for",
    "write_registry",
]
