from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from course_control.production.episode_spec import (
    EpisodeSpec,
    EpisodeSpecError,
    load_episode_spec,
)
from course_control.production.quality_rubric import (
    QualityRubricError,
    load_quality_rubric,
)


@dataclass
class PreflightReport:
    lesson: str
    spec: EpisodeSpec | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def run_preflight(lesson_dir: Path, strict: bool = False) -> PreflightReport:
    report = PreflightReport(lesson=lesson_dir.name)
    spec_path = lesson_dir / "authoring" / "episode.spec.yaml"
    rubric_path = lesson_dir / "authoring" / "quality.rubric.yaml"

    try:
        rubric = load_quality_rubric(rubric_path)
    except QualityRubricError as exc:
        report.errors.append(str(exc))
        rubric = None

    try:
        spec = load_episode_spec(spec_path)
        report.spec = spec
    except EpisodeSpecError as exc:
        report.errors.append(str(exc))
        spec = None

    if spec is not None:
        if not (spec.min_seconds <= spec.total_seconds <= spec.max_seconds):
            report.errors.append(
                f"beat total {spec.total_seconds}s outside [{spec.min_seconds}, {spec.max_seconds}]"
            )
        voice_status = str((spec.voice or {}).get("status") or "").strip()
        if not voice_status:
            report.errors.append("voice.status is required (owner|cloud|local|tbd|none)")
        elif voice_status == "tbd":
            report.warnings.append("voice.status is tbd; final render requires a decision")
        elif voice_status in {"none", "local"}:
            report.warnings.append(f"voice.status={voice_status}; check delivery requirements")
        rights = spec.rights or {}
        if not rights.get("figures_checked"):
            report.warnings.append("rights.figures_checked is false; publication gate will block")
        for asset in spec.assets or []:
            role = str(asset.get("role") or "").strip()
            if role not in {"render_only", "book_figure", "paper_figure", "data", "schematic"}:
                report.errors.append(f"asset role invalid: {asset}")
            if "drivaer" in str(asset.get("source") or "").lower() and role != "render_only":
                report.errors.append(
                    "DrivAer assets are render-only; they cannot be used as data"
                )
        if rubric is not None and "content" not in rubric.dimensions:
            report.warnings.append("rubric has no content dimension")

    if strict and report.warnings:
        report.errors.extend(report.warnings)
        report.warnings = []
    return report
