"""Visual events: the scheduling unit between content and renderers.

A visual event is not an animation contract.  It says what the viewer is
looking at, why it is there, which renderer produces it, which assets and
claims it carries, and which slice of the narration it serves.  It may hold a
still frame for thirty seconds; nothing here forces motion on a timer.

The compiler reads existing build data (``shots.json``) and the storyboard,
and enriches it with the episode spec's claim/page mapping.  It does not
replace either file: ``shots.json`` stays the timeline fact, the storyboard
stays the design fact, and the event plan is a normalised, checkable view.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from course_control.content.contracts import StrictModel
from course_control.production.episode_spec import EpisodeSpec

VisualType = Literal[
    "text",
    "static_image",
    "chart",
    "diagram",
    "motion_graphic",
    "paper_figure",
    "video_footage",
    "animation_2d",
    "animation_3d",
    "manim_scene",
    "blender_scene",
]

# Renderers that can own a shot.  ``remotion`` is the composition layer: slides
# and recordings are not shot-rendered, but they still have to name a renderer.
SHOT_RENDERERS = frozenset({"manim", "blender", "code_video", "motion_canvas"})
COMPOSITION_RENDERERS = frozenset({"remotion"})
EVENT_RENDERERS = SHOT_RENDERERS | COMPOSITION_RENDERERS

EVIDENCE_TYPES = frozenset({"chart", "diagram", "paper_figure"})
BASE_ROLES = frozenset({"base", None, ""})
COVERAGE_TOLERANCE_S = 0.5

PAGE_PART = re.compile(r"^page:(\d+)(?:-(\d+))?$")
SHOT_PART = re.compile(r"^shot:(\S+)$")


class NarrationRef(StrictModel):
    path: str | None = None
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self):
        if self.end_s <= self.start_s:
            raise ValueError("narration end_s must be greater than start_s")
        return self


class VisualEvent(StrictModel):
    event_id: str = Field(pattern=r"^ve-[0-9]{3,}$")
    start_s: float = Field(ge=0)
    duration_s: float = Field(gt=0)
    purpose: Literal[
        "explain", "demonstrate", "simulate", "compare",
        "narrate", "emote", "orient", "summarize",
    ]
    visual_type: VisualType
    renderer: str = Field(min_length=1)
    asset_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    narration_ref: NarrationRef | None = None
    transition: dict | None = None
    layout: str | None = None
    metadata: dict = Field(default_factory=dict)

    @property
    def end_s(self) -> float:
        return round(self.start_s + self.duration_s, 3)


class VisualEventPlan(StrictModel):
    schema_version: Literal[1] = 1
    lesson: str = Field(min_length=1)
    fps: int = Field(ge=1)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    total_duration_s: float = Field(gt=0)
    events: list[VisualEvent] = Field(min_length=1)
    sources: dict = Field(default_factory=dict)


class VisualEventError(ValueError):
    pass


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _page_claims(spec: EpisodeSpec | None) -> dict[int, list[str]]:
    """Map a slide number to the claims a beat assigns to that page."""
    mapping: dict[int, list[str]] = {}
    if spec is None:
        return mapping
    for beat in spec.beats:
        raw = (beat.visual or "").split(";")[0].strip()
        match = PAGE_PART.match(raw)
        if match is None:
            continue
        start = int(match.group(1))
        end = int(match.group(2) or start)
        for page in range(start, end + 1):
            bucket = mapping.setdefault(page, [])
            for claim in beat.claims:
                if claim not in bucket:
                    bucket.append(claim)
    return mapping


def _shot_claims(spec: EpisodeSpec | None) -> dict[str, list[str]]:
    """Map a storyboard shot id to the claims a beat assigns to that shot."""
    mapping: dict[str, list[str]] = {}
    if spec is None:
        return mapping
    for beat in spec.beats:
        raw = (beat.visual or "").split(";")[0].strip()
        match = SHOT_PART.match(raw)
        if match is None:
            continue
        bucket = mapping.setdefault(match.group(1), [])
        for claim in beat.claims:
            if claim not in bucket:
                bucket.append(claim)
    return mapping


def _visual_type(shot: dict) -> VisualType:
    kind = str(shot.get("kind") or "")
    engine = str(shot.get("engine") or "")
    if kind == "slide":
        return "static_image"
    if engine == "manim":
        return "manim_scene"
    if engine == "blender":
        return "blender_scene"
    if engine == "code_video":
        return "motion_graphic"
    if engine == "motion_canvas":
        return "animation_2d"
    if kind == "recording" or str(shot.get("source") or "").lower().endswith((".mp4", ".mov", ".webm")):
        return "video_footage"
    return "static_image"


def _renderer(shot: dict) -> str:
    engine = str(shot.get("engine") or "")
    if engine in SHOT_RENDERERS:
        return engine
    return "remotion"


def compile_plan(
    *,
    lesson: str,
    shots_path: Path,
    storyboard,
    episode: EpisodeSpec | None = None,
) -> VisualEventPlan:
    shots_path = Path(shots_path)
    if not shots_path.is_file():
        raise VisualEventError(f"shots file not found: {shots_path}")
    try:
        data = json.loads(shots_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VisualEventError(f"cannot read shots file {shots_path}: {exc}") from exc

    timeline = data.get("timeline") or {}
    fps = int(timeline.get("fps") or 30)
    resolution = timeline.get("resolution") or [1920, 1080]
    total = float(timeline.get("total_duration_s") or 0)
    if len(resolution) != 2 or total <= 0:
        raise VisualEventError("shots file has no usable timeline")

    shots = data.get("shots") or []
    if not shots:
        raise VisualEventError("shots file has no shots")

    by_id = {shot.id: shot for shot in storyboard.shots}
    pages = _page_claims(episode)
    shot_claims = _shot_claims(episode)
    narration = data.get("narration") or {}
    narration_path = narration.get("path")

    events: list[VisualEvent] = []
    for index, shot in enumerate(shots, start=1):
        shot_id = str(shot.get("id") or "")
        source = shot.get("source")
        spec_shot = by_id.get(shot_id)
        slide = shot.get("slide")
        start = float(shot.get("start_s") or 0)
        duration = float(shot.get("duration_s") or 0)

        purpose = "explain"
        if spec_shot is not None and spec_shot.purpose:
            purpose = spec_shot.purpose
        elif str(shot.get("kind")) != "slide":
            purpose = "demonstrate"

        evidence: list[str] = []
        if spec_shot is not None:
            for ref in spec_shot.evidence_refs:
                if ref not in evidence:
                    evidence.append(ref)
        if isinstance(slide, int):
            for claim in pages.get(slide, []):
                if claim not in evidence:
                    evidence.append(claim)
        for claim in shot_claims.get(shot_id, []):
            if claim not in evidence:
                evidence.append(claim)

        assets: list[str] = []
        if source:
            assets.append(str(source))
        if spec_shot is not None:
            for ref in spec_shot.asset_refs:
                if ref not in assets:
                    assets.append(ref)

        transition = shot.get("transition") or (
            spec_shot.transition.model_dump(mode="json", by_alias=True)
            if spec_shot is not None and spec_shot.transition is not None
            else None
        )
        layout = None
        if spec_shot is not None and spec_shot.is_sheet:
            layout = spec_shot.composition

        events.append(
            VisualEvent(
                event_id=f"ve-{index:03d}",
                start_s=start,
                duration_s=duration,
                purpose=purpose,
                visual_type=_visual_type(shot),
                renderer=_renderer(shot),
                asset_refs=assets,
                evidence_refs=evidence,
                narration_ref=(
                    NarrationRef(
                        path=str(narration_path),
                        start_s=round(start, 3),
                        end_s=round(min(total, start + duration), 3),
                    )
                    if narration_path and duration > 0
                    else None
                ),
                transition=transition,
                layout=layout,
                metadata={
                    "shot_id": shot_id,
                    "kind": shot.get("kind"),
                    "slide": slide,
                    "engine": shot.get("engine"),
                    "timeline_role": shot.get("timeline_role"),
                    "presentation": shot.get("presentation"),
                    "theme": shot.get("theme"),
                },
            )
        )

    return VisualEventPlan(
        lesson=lesson,
        fps=fps,
        width=int(resolution[0]),
        height=int(resolution[1]),
        total_duration_s=round(total, 3),
        events=events,
        sources={
            "shots_sha256": _sha256(shots_path),
            "episode_spec": bool(episode),
        },
    )


class VisualEventReport:
    def __init__(self, plan: VisualEventPlan):
        self.plan = plan
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def status(self) -> str:
        if self.errors:
            return "FAIL"
        if self.warnings:
            return "INCOMPLETE"
        return "PASS"

    def as_dict(self) -> dict:
        return {
            "schema_version": 1,
            "lesson": self.plan.lesson,
            "status": self.status,
            "events": len(self.plan.events),
            "total_duration_s": self.plan.total_duration_s,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_plan(
    plan: VisualEventPlan,
    *,
    build_root: Path,
    episode: EpisodeSpec | None = None,
) -> VisualEventReport:
    report = VisualEventReport(plan)
    seen: set[str] = set()
    claim_ids = {claim.id for claim in episode.claims} if episode is not None else set()

    for event in plan.events:
        if event.event_id in seen:
            report.errors.append(f"{event.event_id}: duplicate event id")
        seen.add(event.event_id)
        if event.renderer not in EVENT_RENDERERS:
            report.errors.append(
                f"{event.event_id}: renderer {event.renderer!r} is not registered"
            )
        if not event.purpose:
            report.errors.append(f"{event.event_id}: purpose is required")
        if event.end_s > plan.total_duration_s + COVERAGE_TOLERANCE_S:
            report.errors.append(
                f"{event.event_id}: ends at {event.end_s:.2f}s beyond the film "
                f"({plan.total_duration_s:.2f}s)"
            )
        if event.narration_ref is not None:
            if event.narration_ref.end_s > plan.total_duration_s + COVERAGE_TOLERANCE_S:
                report.errors.append(
                    f"{event.event_id}: narration range exceeds the narration track"
                )
        for asset in event.asset_refs:
            candidate = Path(asset)
            if not candidate.is_absolute():
                candidate = Path(build_root) / candidate
            if not candidate.exists():
                report.errors.append(
                    f"{event.event_id}: asset not found: {asset}"
                )
        if event.visual_type in EVIDENCE_TYPES and not event.evidence_refs:
            report.errors.append(
                f"{event.event_id}: {event.visual_type} needs at least one evidence ref"
            )
        if claim_ids:
            unknown = [ref for ref in event.evidence_refs if ref not in claim_ids]
            if unknown:
                report.errors.append(
                    f"{event.event_id}: evidence refs not in the episode spec: {', '.join(unknown)}"
                )

    base = [
        event
        for event in plan.events
        if str(event.metadata.get("timeline_role") or "") in BASE_ROLES
    ]
    base.sort(key=lambda event: event.start_s)
    cursor = 0.0
    for event in base:
        if event.start_s > cursor + COVERAGE_TOLERANCE_S:
            report.errors.append(
                f"timeline gap: {cursor:.2f}s -> {event.start_s:.2f}s (no base event)"
            )
        if event.start_s < cursor - COVERAGE_TOLERANCE_S:
            report.errors.append(
                f"{event.event_id}: base event overlaps the previous one by "
                f"{cursor - event.start_s:.2f}s"
            )
        cursor = max(cursor, event.start_s + event.duration_s)
    if cursor < plan.total_duration_s - COVERAGE_TOLERANCE_S:
        report.errors.append(
            f"timeline gap: film ends at {plan.total_duration_s:.2f}s but base events "
            f"stop at {cursor:.2f}s"
        )

    if episode is None:
        report.warnings.append(
            "episode spec not supplied: claim→visual coverage is not verified"
        )
    else:
        covered = {ref for event in plan.events for ref in event.evidence_refs}
        missing = [
            claim.id
            for claim in episode.claims
            if claim.status == "must_teach" and claim.id not in covered
        ]
        if missing:
            report.errors.append(
                "must_teach claims are not bound to any visual event: " + ", ".join(missing)
            )

    return report


def write_plan(plan: VisualEventPlan, target: Path) -> Path:
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def load_plan(path: Path) -> VisualEventPlan:
    path = Path(path)
    if not path.is_file():
        raise VisualEventError(f"visual-event plan not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return VisualEventPlan.model_validate(data)
    except (OSError, ValueError) as exc:
        raise VisualEventError(f"invalid visual-event plan {path}: {exc}") from exc
