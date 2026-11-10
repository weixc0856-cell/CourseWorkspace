"""One adjudication queue for every content finding.

ContentQA findings, cross-review claims and teaching QA notes used to live in
separate files with no record of what a human decided.  ``review/decisions.json``
records one decision per finding id:

    accepted   the issue is real and stays open (blocks a clean pass)
    rejected   the finding is wrong or out of scope (reason required)
    fixed      the content or visual was changed
    deferred   acknowledged, intentionally postponed (treated as open)

Anything without a decision is ``needs_human_review``.  The quality report
reads this file; no new reviewer is introduced.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .atomic import write_json_atomic

DECISIONS = ("accepted", "rejected", "fixed", "deferred")
OPEN_DECISIONS = {"accepted", "deferred"}


class DecisionError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def decisions_path(build_root: Path) -> Path:
    return build_root / "review" / "decisions.json"


def load_decisions(path: Path) -> dict:
    if not path.is_file():
        return {"schema_version": 1, "lesson": "", "decisions": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DecisionError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise DecisionError(f"{path} must contain an object")
    data.setdefault("schema_version", 1)
    data.setdefault("decisions", {})
    if not isinstance(data["decisions"], dict):
        raise DecisionError(f"{path}: decisions must be an object")
    return data


def _finding_id(source: str, index: int, payload: dict) -> str:
    for key in ("claim_id", "id", "finding_id"):
        if payload.get(key):
            return f"{source}:{payload[key]}"
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:10]
    return f"{source}:{index:03d}:{digest}"


def collect_findings(build_root: Path) -> list[dict]:
    findings: list[dict] = []
    review = build_root / "review" / "review.json"
    if review.is_file():
        try:
            data = json.loads(review.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        for index, item in enumerate(data.get("findings") or [], start=1):
            if not isinstance(item, dict):
                continue
            findings.append(
                {
                    "id": _finding_id("contentqa", index, item),
                    "source": "contentqa",
                    "verdict": item.get("verdict"),
                    "text": str(item.get("claim") or item.get("text") or "")[:240],
                    "slide": item.get("slide"),
                }
            )
    cross = build_root / "review" / "review_cross.json"
    if cross.is_file():
        try:
            data = json.loads(cross.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        for index, item in enumerate(data.get("claims") or [], start=1):
            if not isinstance(item, dict):
                continue
            findings.append(
                {
                    "id": _finding_id("cross", index, item),
                    "source": "cross",
                    "verdict": item.get("final_status"),
                    "risk": item.get("risk_level"),
                    "text": str(item.get("claim_text") or "")[:240],
                    "slide": item.get("slide_id"),
                }
            )
    teaching = build_root / "quality" / "teaching-qa.json"
    if teaching.is_file():
        try:
            data = json.loads(teaching.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        for index, item in enumerate(data.get("findings") or [], start=1):
            if not isinstance(item, dict):
                continue
            findings.append(
                {
                    "id": _finding_id("teaching", index, item),
                    "source": "teaching",
                    "verdict": item.get("status") or item.get("verdict"),
                    "text": str(item.get("detail") or item.get("text") or "")[:240],
                    "slide": item.get("slide"),
                }
            )
    return findings


def summarize(build_root: Path) -> dict:
    path = decisions_path(build_root)
    data = load_decisions(path)
    findings = collect_findings(build_root)
    recorded = data.get("decisions") or {}
    queues = {name: [] for name in DECISIONS}
    undecided: list[str] = []
    unknown: list[str] = []
    known_ids = {item["id"] for item in findings}
    for item in findings:
        decision = recorded.get(item["id"])
        if not isinstance(decision, dict) or not decision.get("decision"):
            undecided.append(item["id"])
            continue
        value = str(decision.get("decision"))
        if value not in DECISIONS:
            unknown.append(item["id"])
        else:
            queues[value].append(item["id"])
    stale = sorted(set(recorded) - known_ids)
    return {
        "path": str(path),
        "present": path.is_file(),
        "findings": findings,
        "counts": {name: len(ids) for name, ids in queues.items()},
        "undecided": undecided,
        "unknown_decisions": unknown,
        "stale_decisions": stale,
        "needs_human_review": bool(undecided or unknown or queues["accepted"] or queues["deferred"]),
        "clean": bool(findings)
        and not undecided
        and not unknown
        and not queues["accepted"]
        and not queues["deferred"],
    }


def record_decision(
    build_root: Path,
    lesson: str,
    finding_id: str,
    decision: str,
    *,
    by: str,
    note: str = "",
) -> dict:
    if decision not in DECISIONS:
        raise DecisionError(
            f"decision must be one of {', '.join(DECISIONS)}; got {decision!r}"
        )
    if not by.strip():
        raise DecisionError("--by must name the person making the decision")
    if decision == "rejected" and not note.strip():
        raise DecisionError("rejecting a finding requires --note with the reason")
    path = decisions_path(build_root)
    data = load_decisions(path)
    data["lesson"] = lesson
    data["updated_at"] = _now()
    entry = {
        "decision": decision,
        "by": by.strip(),
        "at": _now(),
        "note": note.strip() or None,
    }
    data["decisions"][finding_id] = entry
    write_json_atomic(path, data)
    return data


__all__ = [
    "DECISIONS",
    "DecisionError",
    "OPEN_DECISIONS",
    "collect_findings",
    "decisions_path",
    "load_decisions",
    "record_decision",
    "summarize",
]
