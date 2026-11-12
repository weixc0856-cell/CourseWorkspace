"""Reference-driven comparison: measure a film against a named reference.

The reference record stores what is measurable (shot length, cut cadence,
motion density, camera requirement).  Composition, hierarchy and typography are
always flagged for human review; no metric may pretend to be an art director.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from course_control.content.contracts import StrictModel
from course_control.platform.workspace_layout import content_root

REFERENCES_REL = Path("docs/architecture/references")


def reference_roots(workspace: Path) -> list[Path]:
    """Reference records live with the projects; the old docs path is the fallback."""
    roots = [(content_root(workspace) / "references").resolve()]
    roots.append((Path(workspace).resolve() / REFERENCES_REL))
    return roots


class ReferenceMetrics(StrictModel):
    shot_seconds_min: float = Field(gt=0)
    shot_seconds_max: float = Field(gt=0)
    beats_per_10s_min: float = Field(ge=0)
    cut_rate_per_10s_min: float = Field(ge=0)
    camera_required: bool = False


class ReferenceRecord(StrictModel):
    schema_version: int = 1
    id: str = Field(min_length=1)
    title: str
    url: str | None = None
    duration_s: float = Field(gt=0)
    sample_interval_s: float = Field(gt=0, default=5.0)
    grammars: list[str] = Field(default_factory=list)
    metrics: ReferenceMetrics
    visual: dict = Field(default_factory=dict)
    chapters: list[dict] = Field(default_factory=list)
    acceptance: list[str] = Field(default_factory=list)


def load_reference(path: Path) -> ReferenceRecord:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ReferenceRecord.model_validate(data)


def resolve_reference(workspace: Path, name: str) -> Path:
    candidate = Path(name)
    if candidate.suffix == ".json" and candidate.is_file():
        return candidate.resolve()
    for root in reference_roots(workspace):
        path = (root / f"{name}.json").resolve()
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"reference not found: {name} (looked in "
        + ", ".join(str(root) for root in reference_roots(workspace))
        + ")"
    )


def _dimension(status: str, detail: str) -> dict:
    return {"status": status, "detail": detail}


def compare(metrics: dict, reference: ReferenceRecord) -> dict:
    average = float(metrics.get("average_shot_seconds") or 0.0)
    beats = float(metrics.get("beats_per_10s") or 0.0)
    cut_rate = float(metrics.get("cut_rate_per_10s") or 0.0)
    moves = int(metrics.get("camera_moves") or 0)
    limits = reference.metrics

    required: list[str] = []
    dimensions: dict[str, dict] = {}

    if limits.shot_seconds_min <= average <= limits.shot_seconds_max:
        dimensions["timing"] = _dimension(
            "pass", f"average shot {average:.2f}s inside {limits.shot_seconds_min}-{limits.shot_seconds_max}s"
        )
    else:
        dimensions["timing"] = _dimension(
            "fail",
            f"average shot {average:.2f}s outside {limits.shot_seconds_min}-{limits.shot_seconds_max}s",
        )
        required.append(
            f"adjust average shot length from {average:.2f}s into "
            f"[{limits.shot_seconds_min}, {limits.shot_seconds_max}]s"
        )
    if cut_rate < limits.cut_rate_per_10s_min:
        required.append(
            f"raise cut rate from {cut_rate:.2f} to >= {limits.cut_rate_per_10s_min:.2f} per 10s"
        )

    if beats >= limits.beats_per_10s_min:
        dimensions["motion_quality"] = _dimension(
            "pass", f"{beats:.2f} actions/10s >= {limits.beats_per_10s_min:.2f}"
        )
    else:
        dimensions["motion_quality"] = _dimension(
            "fail", f"{beats:.2f} actions/10s < {limits.beats_per_10s_min:.2f}"
        )
        required.append(
            f"raise action density from {beats:.2f} to >= {limits.beats_per_10s_min:.2f} per 10s"
        )

    if limits.camera_required:
        if moves > 0:
            dimensions["camera_movement"] = _dimension("pass", f"{moves} camera move(s)")
        else:
            dimensions["camera_movement"] = _dimension("fail", "reference requires camera movement")
            required.append("add a motivated camera move")
    else:
        dimensions["camera_movement"] = _dimension("pass", "static by reference")

    for name in ("composition", "visual_hierarchy", "typography"):
        dimensions[name] = _dimension("human_review", "not machine-measurable; watch the film")

    failed = any(item["status"] == "fail" for item in dimensions.values())
    return {
        "reference": reference.id,
        "reference_title": reference.title,
        "overall": "not_ready" if failed else "ready_for_human_review",
        "dimensions": dimensions,
        "required_improvements": required,
        "human_review_required": True,
        "sample_interval_s": reference.sample_interval_s,
        "acceptance": reference.acceptance,
    }


__all__ = [
    "REFERENCES_REL",
    "ReferenceMetrics",
    "ReferenceRecord",
    "compare",
    "load_reference",
    "resolve_reference",
]
