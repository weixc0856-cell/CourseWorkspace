"""Regression: compare two defect reports.

A fix is not done when the targeted defect disappears; it is done when the new
defect set contains nothing that was not there before.  Comparison is by stable
defect id, so the same symptom keeps the same identity across runs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from course_control.content.contracts import StrictModel
from course_control.quality.defect import DefectReport


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class Regression(StrictModel):
    schema_version: Literal[1] = 1
    project_id: str
    generated_at: str
    fixed: list[str] = []
    still_open: list[str] = []
    introduced: list[str] = []
    regressed: bool = False


def compare(before: DefectReport, after: DefectReport) -> Regression:
    before_ids = {item.id for item in before.defects}
    after_ids = {item.id for item in after.defects}
    introduced = sorted(after_ids - before_ids)
    return Regression(
        project_id=after.project_id,
        generated_at=_now(),
        fixed=sorted(before_ids - after_ids),
        still_open=sorted(before_ids & after_ids),
        introduced=introduced,
        regressed=bool(introduced),
    )


__all__ = ["Regression", "compare"]
