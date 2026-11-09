"""Independent cross-review: align two reports without letting models see each other.

The two inputs must be produced independently.  This module only aligns claims,
applies the evidence and conflict matrix, and writes an auditable report.  It
never turns agreement into factual proof.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from .claims import (
    Claim,
    ClaimRegistry,
    ClaimType,
    ReviewStatus,
    RiskLevel,
    evidence_problems,
    load_source_ids,
    registry_from_report,
    risk_for,
    write_registry,
)

ALIGN_THRESHOLD = 0.70


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _similarity(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, _tokens(left), _tokens(right)).ratio()


def align_claims(
    a_claims: list[Claim],
    b_claims: list[Claim],
    *,
    threshold: float = ALIGN_THRESHOLD,
) -> list[tuple[Claim, Claim | None, float]]:
    used: set[int] = set()
    pairs: list[tuple[Claim, Claim | None, float]] = []
    for a_claim in a_claims:
        best_index = None
        best_ratio = 0.0
        for index, b_claim in enumerate(b_claims):
            if index in used or b_claim.slide_id != a_claim.slide_id:
                continue
            ratio = _similarity(a_claim.claim_text, b_claim.claim_text)
            if ratio > best_ratio:
                best_ratio = ratio
                best_index = index
        if best_index is not None and best_ratio >= threshold:
            used.add(best_index)
            pairs.append((a_claim, b_claims[best_index], best_ratio))
        else:
            pairs.append((a_claim, None, 0.0))
    for index, b_claim in enumerate(b_claims):
        if index not in used:
            pairs.append((None, b_claim, 0.0))  # type: ignore[arg-type]
    return pairs


def decide(
    a_status: ReviewStatus | None,
    b_status: ReviewStatus | None,
    problems: list[str],
) -> tuple[ReviewStatus, RiskLevel, list[str]]:
    statuses = {status for status in (a_status, b_status) if status is not None}
    reasons: list[str] = []
    if ReviewStatus.disputed in statuses:
        return ReviewStatus.disputed, RiskLevel.high, ["one model disputes the claim"]
    if a_status is not None and b_status is not None:
        if a_status == b_status == ReviewStatus.supported:
            if problems:
                reasons.append("both models support it, but evidence is insufficient")
                return ReviewStatus.needs_human_review, RiskLevel.high, reasons
            return ReviewStatus.supported, RiskLevel.low, ["both models support; evidence present"]
        if a_status == b_status == ReviewStatus.unsupported:
            if problems:
                reasons.append("both models reject it; evidence is also missing")
            return ReviewStatus.unsupported, RiskLevel.high, reasons
        if {a_status, b_status} & {ReviewStatus.supported} and {
            a_status,
            b_status,
        } & {ReviewStatus.unsupported}:
            return ReviewStatus.disputed, RiskLevel.high, ["models disagree"]
    if ReviewStatus.not_checked in statuses:
        return ReviewStatus.needs_human_review, RiskLevel.medium, ["a model did not check it"]
    return ReviewStatus.needs_human_review, RiskLevel.high if problems else RiskLevel.medium, [
        "insufficient independent evidence"
    ]


def _claim_type(claim: Claim | None) -> ClaimType:
    return claim.claim_type if claim is not None else ClaimType.fact


def run_cross_review(
    lesson_dir: Path,
    a_report_path: Path,
    b_report_path: Path,
    *,
    out_dir: Path,
    sources_file: str = "sources.yaml",
) -> dict[str, Path]:
    a_report = json.loads(a_report_path.read_text(encoding="utf-8"))
    b_report = json.loads(b_report_path.read_text(encoding="utf-8"))
    source_ids = load_source_ids(lesson_dir, sources_file)
    a_registry = registry_from_report(a_report, source_ids=source_ids)
    b_registry = registry_from_report(b_report, source_ids=source_ids)
    pairs = align_claims(a_registry.claims, b_registry.claims)

    cross_claims: list[dict] = []
    registry_claims: list[Claim] = []
    for index, (a_claim, b_claim, ratio) in enumerate(pairs, start=1):
        text = (a_claim or b_claim).claim_text  # type: ignore[union-attr]
        slide = (a_claim or b_claim).slide_id  # type: ignore[union-attr]
        claim_type = _claim_type(a_claim or b_claim)
        problems: list[str] = []
        if a_claim is not None:
            problems.extend(f"A: {item}" for item in evidence_problems(a_claim, source_ids))
        if b_claim is not None:
            problems.extend(f"B: {item}" for item in evidence_problems(b_claim, source_ids))
        if b_claim is None:
            problems.append("not independently reviewed")
        status, risk, reasons = decide(
            a_claim.review_status if a_claim else None,
            b_claim.review_status if b_claim else None,
            problems,
        )
        claim = Claim(
            claim_id=f"C-{index:03d}",
            claim_text=text,
            claim_type=claim_type,
            source_refs=sorted(
                set((a_claim.source_refs if a_claim else []))
                | set((b_claim.source_refs if b_claim else []))
            ),
            source_location=f"slide {slide}",
            slide_id=slide,
            risk_level=risk,
            review_status=status,
            review_evidence="; ".join(reasons + problems),
        )
        registry_claims.append(claim)
        cross_claims.append(
            {
                "claim_id": claim.claim_id,
                "claim_text": text,
                "slide_id": slide,
                "claim_type": claim_type.value,
                "match_ratio": round(ratio, 3),
                "a_verdict": a_claim.review_status.value if a_claim else None,
                "b_verdict": b_claim.review_status.value if b_claim else None,
                "evidence_problems": problems,
                "final_status": status.value,
                "risk_level": risk.value,
                "reasons": reasons,
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    cross_path = out_dir / "review_cross.json"
    cross = {
        "schema_version": 1,
        "lesson": a_registry.lesson or b_registry.lesson,
        "reviewer_a": str(a_report_path),
        "reviewer_b": str(b_report_path),
        "claims": cross_claims,
        "summary": {
            "claims": len(cross_claims),
            "supported": sum(1 for c in cross_claims if c["final_status"] == "supported"),
            "needs_human_review": sum(
                1 for c in cross_claims if c["final_status"] == "needs_human_review"
            ),
            "disputed": sum(1 for c in cross_claims if c["final_status"] == "disputed"),
            "unsupported": sum(1 for c in cross_claims if c["final_status"] == "unsupported"),
            "missing_evidence": sum(
                1 for c in cross_claims if c["evidence_problems"]
            ),
        },
    }
    cross_path.write_text(
        json.dumps(cross, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    registry_path = write_registry(
        out_dir / "claim_registry.json",
        ClaimRegistry(lesson=cross["lesson"], claims=registry_claims),
    )
    report_path = out_dir / "conflict_report.md"
    _write_conflict_report(cross, report_path)
    evidence_path = out_dir / "evidence_report.md"
    _write_evidence_report(cross, evidence_path)
    return {
        "cross": cross_path,
        "registry": registry_path,
        "conflict_report": report_path,
        "evidence_report": evidence_path,
    }


def _write_conflict_report(cross: dict, path: Path) -> None:
    lines = [
        f"# Conflict report: {cross['lesson']}",
        "",
        "模型 A/B 独立审查；一致不等于事实正确，冲突必须人工裁决。",
        "",
        "| ID | slide | A | B | 最终状态 | 风险 | 说明 |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for claim in cross["claims"]:
        lines.append(
            f"| {claim['claim_id']} | {claim['slide_id']} | {claim['a_verdict']} | "
            f"{claim['b_verdict']} | {claim['final_status']} | {claim['risk_level']} | "
            f"{'; '.join(claim['reasons'] + claim['evidence_problems'])[:200]} |"
        )
    lines += ["", "## 摘要", ""]
    for key, value in cross["summary"].items():
        lines.append(f"- {key}: {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_evidence_report(cross: dict, path: Path) -> None:
    lines = [f"# Evidence report: {cross['lesson']}", ""]
    problems = [c for c in cross["claims"] if c["evidence_problems"]]
    if not problems:
        lines.append("没有发现来源缺口。仍需人工确认来源是否真正支持主张。")
    for claim in problems:
        lines.append(f"## {claim['claim_id']} slide {claim['slide_id']}")
        lines.append("")
        lines.append(claim["claim_text"])
        lines.append("")
        for problem in claim["evidence_problems"]:
            lines.append(f"- {problem}")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = [
    "ALIGN_THRESHOLD",
    "align_claims",
    "decide",
    "run_cross_review",
]
