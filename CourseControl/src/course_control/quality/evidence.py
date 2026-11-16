"""One evidence vocabulary for the report, certificate, gate and package.

Every consumer reads the same five Q dimensions through the same rules:

- the statuses are a closed set; a missing, duplicated or unknown dimension is
  ``INCOMPLETE``, never a silent pass;
- the content hash covers only reproducible facts (Q1-Q4 plus the Q5 artifact
  facts and their risks), so writing an approval never changes it;
- an approval is valid only when it names a person (not a role, a placeholder
  or a machine), the same lesson, the right stage slot, and the hashes of the
  build report, the film and the quality content it claims to approve.

``release-check``, ``release-approve``, ``package`` and ``package-verify`` call
``evidence_problems`` instead of copying these rules.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

Q_IDS = ("Q1", "Q2", "Q3", "Q4", "Q5")
Q_STATES = frozenset({"PASS", "WARN", "BLOCKED", "INCOMPLETE", "FAIL"})
BAD_STATES = frozenset({"BLOCKED", "INCOMPLETE", "FAIL"})
HASH_FIELDS = (
    "build_report_sha256",
    "final_video_sha256",
    "quality_report_content_sha256",
)
MACHINE_APPROVERS = {
    "",
    "owner",
    "unassigned",
    "human",
    "system",
    "claude",
    "claude code",
    "ai",
    "assistant",
    "automation",
    "bot",
    "n/a",
    "none",
    "unknown",
}


def is_named_approver(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.lower() not in MACHINE_APPROVERS


def _status(item: dict) -> str:
    return str(item.get("status") or "").upper()


def normalize_dimensions(report: dict | None) -> tuple[dict[str, str], list[str]]:
    """Return one legal status per Q id, plus every problem found.

    Missing, duplicated and unknown values become ``INCOMPLETE``; the caller
    never has to guess what an illegal status meant.
    """
    statuses: dict[str, str] = {}
    problems: list[str] = []
    dimensions = (report or {}).get("dimensions")
    if not isinstance(dimensions, list):
        return {qid: "INCOMPLETE" for qid in Q_IDS}, [
            "quality report has no dimensions"
        ]
    for item in dimensions:
        if not isinstance(item, dict):
            problems.append("quality dimension is not an object")
            continue
        qid = str(item.get("id") or "")
        if qid not in Q_IDS:
            problems.append(f"unknown quality dimension {qid!r}")
            continue
        if qid in statuses:
            problems.append(f"quality dimension {qid} appears more than once")
            continue
        status = _status(item)
        if status not in Q_STATES:
            problems.append(
                f"{qid} status {status or 'missing'!r} is not one of "
                + ", ".join(sorted(Q_STATES))
            )
            statuses[qid] = "INCOMPLETE"
            continue
        statuses[qid] = status
    for qid in Q_IDS:
        if qid not in statuses:
            problems.append(f"quality dimension {qid} is missing")
            statuses[qid] = "INCOMPLETE"
    return statuses, problems


def quality_content(report: dict | None) -> dict:
    """The reproducible part of a quality report: no approval state."""
    dimensions: list[dict] = []
    for item in (report or {}).get("dimensions") or []:
        if not isinstance(item, dict):
            continue
        qid = str(item.get("id") or "")
        record: dict = {"id": qid, "status": _status(item)}
        if qid == "Q5":
            # Q5 is the release-artifact gate; only its artifact facts are
            # content.  Its approval fields live outside this hash.
            record["artifacts"] = item.get("artifacts") or {}
        else:
            record["reason"] = item.get("reason")
            record["warning_class"] = item.get("warning_class")
        dimensions.append(record)
    dimensions.sort(key=lambda entry: str(entry.get("id")))
    return {"dimensions": dimensions, "risks": list((report or {}).get("risks") or [])}


def quality_content_sha256(report: dict | None) -> str:
    return hashlib.sha256(
        json.dumps(
            quality_content(report), ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
    ).hexdigest()


def read_json(path: Path | None) -> dict | None:
    if path is None or not Path(path).is_file():
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def file_sha256(path: Path | None) -> str | None:
    if path is None or not Path(path).is_file():
        return None
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def approval_problems(
    *,
    lesson: str,
    review: dict | None,
    release: dict | None,
    build_report_sha256: str | None,
    final_video_sha256: str | None,
    quality_content_sha256: str | None,
    require_release: bool = True,
) -> list[str]:
    """Check both approvals against the evidence they claim to approve."""
    problems: list[str] = []
    expected = {
        "build_report_sha256": build_report_sha256,
        "final_video_sha256": final_video_sha256,
        "quality_report_content_sha256": quality_content_sha256,
    }
    slots = [("review", review)]
    if require_release:
        slots.append(("release", release))
    for stage, data in slots:
        if not isinstance(data, dict):
            problems.append(f"{stage} approval missing or invalid")
            continue
        version = data.get("schema_version")
        if type(version) is not int or version != 2:
            problems.append(
                f"{stage} approval schema_version is {version!r}, not 2; "
                "re-run release-approve"
            )
        if str(data.get("decision") or "") != "approved":
            problems.append(f"{stage} approval is not an approval")
        if not is_named_approver(data.get("approved_by")):
            problems.append(
                f"{stage} approval is not signed by a named person "
                f"({data.get('approved_by')!r})"
            )
        if str(data.get("lesson") or "") != lesson:
            problems.append(
                f"{stage} approval is for {data.get('lesson')!r}, not {lesson!r}"
            )
        if str(data.get("stage") or "") != stage:
            problems.append(
                f"{stage} slot holds an approval for stage {data.get('stage')!r}"
            )
        for key, value in expected.items():
            if value is None:
                problems.append(
                    f"{stage} approval cannot be checked: {key.replace('_sha256', '')} missing"
                )
            elif data.get(key) != value:
                problems.append(
                    f"{stage} approval does not bind the current "
                    f"{key.replace('_sha256', '')}"
                )
    return problems


def evidence_problems(
    *,
    lesson: str,
    review_path: Path | None,
    release_path: Path | None,
    build_report: Path | None,
    final_video: Path | None,
    quality_report: Path | None,
    require_release: bool = True,
) -> list[str]:
    """Read the files, then apply ``approval_problems`` to what they contain."""
    quality = read_json(quality_report)
    return approval_problems(
        lesson=lesson,
        review=read_json(review_path),
        release=read_json(release_path),
        build_report_sha256=file_sha256(build_report),
        final_video_sha256=file_sha256(final_video),
        quality_content_sha256=(
            quality_content_sha256(quality) if quality is not None else None
        ),
        require_release=require_release,
    )


__all__ = [
    "BAD_STATES",
    "MACHINE_APPROVERS",
    "Q_IDS",
    "Q_STATES",
    "approval_problems",
    "evidence_problems",
    "file_sha256",
    "is_named_approver",
    "normalize_dimensions",
    "quality_content",
    "quality_content_sha256",
    "read_json",
]
