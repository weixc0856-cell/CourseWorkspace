"""Quality certificate: the machine-readable verdict attached to a delivery.

A package is releasable only when the quality gate passed and no blocking
defect is open.  The certificate records that decision together with the hash
of the report it was based on, so a later reader can tell whether the verdict
still describes the files in the package.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from course_control.content.contracts import StrictModel
from course_control.platform.artifacts import sha256_file
from course_control.platform.atomic import write_json_atomic


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


class QualityCertificate(StrictModel):
    schema_version: Literal[1] = 1
    project_id: str
    generated_at: str
    verdict: Literal["pass", "fail", "incomplete"]
    dimensions: dict[str, str] = {}
    open_defects: list[str] = []
    quality_report_sha256: str | None = None
    reason: str | None = None


def issue(build_root: Path, project_id: str) -> QualityCertificate:
    defects = _read(build_root / "quality" / "defects.json")
    gate = _read(build_root / "quality" / "gate.json")
    quality = _read(build_root / "quality" / "quality-report.json")

    open_ids = [
        str(item.get("id"))
        for item in (defects or {}).get("defects") or []
        if isinstance(item, dict)
        and str(item.get("status") or "open") in {"open", "repairing"}
    ]
    dimensions = {
        str(item.get("id")): str(item.get("status"))
        for item in (quality or {}).get("dimensions") or []
        if isinstance(item, dict)
    }

    if defects is None:
        verdict, reason = "incomplete", "no defects.json; run quality-diagnose"
    elif open_ids:
        verdict, reason = "fail", f"{len(open_ids)} open defect(s)"
    elif gate is None:
        verdict, reason = "incomplete", "no gate.json; run quality-gate"
    elif str(gate.get("verification_status") or "") != "pass":
        verdict, reason = "incomplete", "quality gate did not pass"
    else:
        verdict, reason = "pass", None

    return QualityCertificate(
        project_id=project_id,
        generated_at=_now(),
        verdict=verdict,
        dimensions=dimensions,
        open_defects=open_ids,
        quality_report_sha256=sha256_file(build_root / "quality" / "quality-report.json"),
        reason=reason,
    )


def save(certificate: QualityCertificate, path: Path) -> Path:
    write_json_atomic(path, certificate.model_dump(mode="json"))
    return path


def load(path: Path) -> QualityCertificate | None:
    data = _read(path)
    if data is None:
        return None
    return QualityCertificate.model_validate(data)


__all__ = ["QualityCertificate", "issue", "save", "load"]
