"""Narrative plan contract and deterministic validation.

The plan is the Director's creative contract: it names the audience, the
promise, the six narrative beats and the evidence type of each beat.  The
validator checks structure and timing only; it never claims that the teaching
works.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field

from .contracts import LessonConfig, StrictModel
from .paths import LessonPaths

BEAT_ORDER = ("cold_open", "question", "intuition", "mechanism", "test", "connect")


class NarrativeBeat(StrictModel):
    id: Literal["cold_open", "question", "intuition", "mechanism", "test", "connect"]
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    summary: str = Field(min_length=1)
    evidence: Literal["real_data", "simulation", "schematic"] = "schematic"


class ShortForm(StrictModel):
    target_seconds: float = Field(ge=30, le=90)
    aspect_ratio: Literal["9:16"] = "9:16"
    independent_script: bool = True
    hook: str = Field(min_length=1)
    payoff: str = Field(min_length=1)


class NarrativePlan(StrictModel):
    schema_version: Literal[1] = 1
    form: Literal["long", "short"] = "long"
    audience: str = Field(min_length=1)
    promise: str = Field(min_length=1)
    beats: list[NarrativeBeat] = Field(min_length=1)
    payoff: str = Field(min_length=1)
    short_form: ShortForm | None = None


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def validate_plan(plan: NarrativePlan, lesson: LessonConfig | None = None) -> list[dict]:
    issues: list[dict] = []

    def error(rule: str, message: str) -> None:
        issues.append({"level": "error", "rule": rule, "message": message})

    def warning(rule: str, message: str) -> None:
        issues.append({"level": "warning", "rule": rule, "message": message})

    ids = [beat.id for beat in plan.beats]
    if len(set(ids)) != len(ids):
        error("N-01", "beat ids must be unique")

    previous_end = 0.0
    for beat in plan.beats:
        if beat.end_s <= beat.start_s:
            error("N-02", f"{beat.id}: end_s must be greater than start_s")
        if beat.start_s < previous_end - 0.001:
            error("N-03", f"{beat.id}: beats must not overlap")
        previous_end = max(previous_end, beat.end_s)

    total = plan.beats[-1].end_s if plan.beats else 0.0

    if plan.form == "long":
        if ids[0] != "cold_open":
            error("N-10", "long form must start with cold_open")
        if "question" not in ids:
            error("N-11", "long form must state the question")
        if ids[-1] != "connect":
            warning("N-12", "long form should end with connect")
        cold = next((beat for beat in plan.beats if beat.id == "cold_open"), None)
        if cold and cold.end_s > 30:
            warning("N-13", "cold_open is longer than 30 s")
        question = next((beat for beat in plan.beats if beat.id == "question"), None)
        if question and question.end_s > 90:
            warning("N-14", "the question should be clear within 90 s")
        if lesson is not None and lesson.duration and lesson.duration.target_seconds:
            target = float(lesson.duration.target_seconds)
            tolerance = max(15.0, target * 0.10)
            if abs(total - target) > tolerance:
                warning(
                    "N-15",
                    f"narrative ends at {total:.1f}s but the duration target is {target:.1f}s",
                )
    else:
        if plan.short_form is None:
            error("N-20", "short form requires short_form settings")
        else:
            if not plan.short_form.independent_script:
                error("N-21", "short form must use an independent script, not a crop")
            if not 30 <= total <= 90:
                error("N-22", f"short form duration {total:.1f}s must be 30–90 s")
        if len(plan.beats) > 4:
            warning("N-23", "short form should keep at most four beats")
        if "question" not in ids:
            error("N-24", "short form must still state the question")
        if ids[-1] != "connect":
            warning("N-25", "short form should end with a conclusion")

    return issues


def validate_lesson(workspace: Path, paths: LessonPaths) -> tuple[dict, Path]:
    workspace = workspace.resolve()
    report: dict = {
        "schema_version": 1,
        "lesson": paths.slug,
        "generated_at": _now(),
        "status": "fail",
        "form": getattr(paths.lesson, "video_form", "long"),
        "issues": [],
    }
    target = paths.build_root / "quality" / "narrative.json"

    def finish() -> tuple[dict, Path]:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return report, target

    relative = paths.lesson.authoring.narrative if paths.lesson.authoring else None
    if not relative:
        report["issues"] = [
            {
                "level": "error",
                "rule": "N-00",
                "message": "authoring.narrative is not configured",
            }
        ]
        return finish()

    plan_path = paths.content_path(relative)
    if not plan_path.is_file():
        report["issues"] = [
            {
                "level": "error",
                "rule": "N-00",
                "message": f"narrative plan not found: {relative}",
            }
        ]
        return finish()

    try:
        plan = NarrativePlan.model_validate(
            json.loads(plan_path.read_text(encoding="utf-8"))
        )
    except Exception as exc:  # noqa: BLE001 - report the contract failure
        report["issues"] = [
            {"level": "error", "rule": "N-00", "message": f"invalid narrative plan: {exc}"}
        ]
        return finish()

    issues = validate_plan(plan, paths.lesson)
    report.update(
        {
            "form": plan.form,
            "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
            "audience": plan.audience,
            "promise": plan.promise,
            "beats": [beat.model_dump(mode="json") for beat in plan.beats],
            "issues": issues,
        }
    )
    if any(issue["level"] == "error" for issue in issues):
        report["status"] = "fail"
    elif any(issue["level"] == "warning" for issue in issues):
        report["status"] = "warn"
    else:
        report["status"] = "pass"
    return finish()


__all__ = [
    "BEAT_ORDER",
    "NarrativeBeat",
    "NarrativePlan",
    "ShortForm",
    "validate_lesson",
    "validate_plan",
]
