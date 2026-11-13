"""Defects: one vocabulary for everything that blocks a delivery.

Existing checks already say pass/fail, but each report speaks its own language.
The quality engine needs one object it can group, count, attribute and compare
across runs.  Collection is deterministic: no model decides whether something
is a defect.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from course_control.content.contracts import StrictModel
from course_control.platform.atomic import write_json_atomic

Dimension = Literal["K", "P", "N", "V", "T", "D"]
Severity = Literal["blocking", "major", "minor", "note"]
RootCause = Literal[
    "source_data",
    "evidence_collection",
    "script_length",
    "visual_grammar",
    "render_engine",
    "audio_timing",
    "contract_violation",
    "unknown",
]
DefectStatus = Literal["open", "repairing", "fixed", "accepted_risk", "unverifiable"]

DIMENSION_BY_QUALITY = {"Q1": "K", "Q2": "P", "Q3": "V", "Q4": "T", "Q5": "D"}

STAGE_BY_CHECK = {
    "V-27": "produce",
    "V-30": "produce",
    "V-31": "produce",
    "V-44": "produce",
    "V-17": "verify",
}

ROOT_CAUSE_BY_CHECK = {
    "V-27": "script_length",
    "V-30": "audio_timing",
    "V-31": "audio_timing",
    "V-44": "audio_timing",
    "V-17": "contract_violation",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def defect_id(symptom: str, dimension: str = "") -> str:
    digest = hashlib.sha256(f"{dimension}:{symptom}".encode("utf-8")).hexdigest()
    return "DEF-" + digest[:8].upper()


class Defect(StrictModel):
    id: str
    dimension: Dimension
    severity: Severity = "blocking"
    stage: str = "unknown"
    artifact_ids: list[str] = []
    symptom: str
    root_cause_hint: RootCause = "unknown"
    evidence: list[str] = []
    status: DefectStatus = "open"


class DefectReport(StrictModel):
    schema_version: Literal[1] = 1
    project_id: str
    generated_at: str
    defects: list[Defect] = []


def _from_checks(
    checks: list[dict],
    *,
    source: str,
    default_dimension: Dimension,
) -> list[Defect]:
    defects: list[Defect] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        status = str(check.get("status") or "").lower()
        if status not in {"fail", "incomplete", "not_run", "blocked"}:
            continue
        check_id = str(check.get("id") or "unknown")
        symptom = str(check.get("detail") or check.get("actual") or check_id)
        dimension = default_dimension
        defects.append(
            Defect(
                id=defect_id(f"{source}:{check_id}:{symptom}", dimension),
                dimension=dimension,
                severity="blocking",
                stage=STAGE_BY_CHECK.get(check_id, "produce"),
                symptom=f"{check_id}: {symptom}",
                root_cause_hint=ROOT_CAUSE_BY_CHECK.get(check_id, "unknown"),
                evidence=[f"{source}#{check_id}"],
            )
        )
    return defects


def collect(build_root: Path, project_id: str) -> DefectReport:
    """Collect defects from the reports a build already wrote."""
    defects: list[Defect] = []

    build = _read(build_root / "final" / "build-report.json") or {}
    defects.extend(_from_checks(build.get("checks") or [], source="build-report", default_dimension="T"))

    media = _read(build_root / "quality" / "media-qc.json") or {}
    defects.extend(_from_checks(media.get("checks") or [], source="media-qc", default_dimension="V"))

    subtitles = _read(build_root / "quality" / "subtitles-qc.json")
    if subtitles and str(subtitles.get("status") or "").upper() == "FAIL":
        detail = "; ".join((subtitles.get("errors") or [])[:3]) or "subtitle QC failed"
        defects.append(
            Defect(
                id=defect_id(f"subtitles-qc:{detail}", "V"),
                dimension="V",
                severity="blocking",
                stage="produce",
                symptom=f"subtitles-qc: {detail}",
                root_cause_hint="audio_timing",
                evidence=["quality/subtitles-qc.json"],
            )
        )
    elif subtitles is None:
        defects.append(
            Defect(
                id=defect_id("subtitles-qc:missing", "V"),
                dimension="V",
                severity="blocking",
                stage="produce",
                symptom="subtitles-qc: no report",
                root_cause_hint="unknown",
                evidence=["quality/subtitles-qc.json"],
            )
        )

    quality = _read(build_root / "quality" / "quality-report.json") or {}
    for dimension in quality.get("dimensions") or []:
        if not isinstance(dimension, dict):
            continue
        status = str(dimension.get("status") or "").upper()
        if status not in {"FAIL", "INCOMPLETE", "BLOCKED"}:
            continue
        quality_id = str(dimension.get("id") or "")
        mapped: Dimension = DIMENSION_BY_QUALITY.get(quality_id, "T")
        reason = str(dimension.get("reason") or status)
        defects.append(
            Defect(
                id=defect_id(f"quality-report:{quality_id}:{reason}", mapped),
                dimension=mapped,
                severity="blocking",
                stage="verify",
                symptom=f"{quality_id}: {reason}",
                root_cause_hint="unknown",
                evidence=["quality/quality-report.json"],
            )
        )
    return DefectReport(project_id=project_id, generated_at=_now(), defects=defects)


def save(report: DefectReport, path: Path) -> Path:
    write_json_atomic(path, report.model_dump(mode="json"))
    return path


def load(path: Path) -> DefectReport | None:
    data = _read(path)
    if data is None:
        return None
    return DefectReport.model_validate(data)


__all__ = [
    "Defect",
    "DefectReport",
    "defect_id",
    "collect",
    "save",
    "load",
    "DIMENSION_BY_QUALITY",
]
