"""Design checks: the ways a shot turns into a slide with motion.

These are advisory.  The layer exists to make design decisions visible before
rendering, not to add another gate — a warning here is a question for the person
reviewing the boards, and the final judgement is still the rendered film.
"""
from __future__ import annotations

from course_control.design.planner import ENTRY_VERBS, SAFE
from course_control.direction.beats import MAX_GAP_SECONDS, MAX_SHOT_SECONDS
from course_control.design.schema import DesignCheck, Rect, ShotDesign, VisualDesign

MOTIONLESS_CAMERAS = {"", "static", "hold", "locked"}
MAX_LABEL_WORDS = 18
MAX_OVERLAP_RATIO = 0.35


def _overlap(first: Rect, second: Rect) -> float:
    width = max(0.0, min(first.x + first.w, second.x + second.w) - max(first.x, second.x))
    height = max(0.0, min(first.y + first.h, second.y + second.h) - max(first.y, second.y))
    return width * height


def _outside_safe(rect: Rect, tolerance: float = 0.005) -> bool:
    return (
        rect.x < SAFE.x - tolerance
        or rect.y < SAFE.y - tolerance
        or rect.x + rect.w > SAFE.x + SAFE.w + tolerance
        or rect.y + rect.h > SAFE.y + SAFE.h + tolerance
    )


def _entry_only(primary: str) -> bool:
    text = primary.lower()
    return any(verb in text for verb in ENTRY_VERBS) and "transform" not in text


def _check_shot(design: ShotDesign) -> list[DesignCheck]:
    checks: list[DesignCheck] = []
    shot = design.shot_id

    if _entry_only(design.motion.primary):
        checks.append(
            DesignCheck(
                id="design.entry_only",
                level="warning",
                rule="motion is a transformation, not an entrance",
                message=f"primary motion reads as an entrance: {design.motion.primary}",
                shot_id=shot,
            )
        )

    if len(design.composition.depth_layers) < 2:
        checks.append(
            DesignCheck(
                id="design.depth_flat",
                level="warning",
                rule="a long shot needs at least two depth layers",
                message="only the background and the subject are blocked in",
                shot_id=shot,
            )
        )

    focal = design.composition.focal_object
    missing = [frame.id for frame in design.keyframes if focal not in {obj.id for obj in frame.objects}]
    if missing:
        checks.append(
            DesignCheck(
                id="design.focal_drifts",
                level="error",
                rule="the focal object keeps its identity across all three keyframes",
                message=f"focal object {focal!r} is missing from keyframes: {', '.join(missing)}",
                shot_id=shot,
            )
        )

    if design.duration_s >= 6.0 and design.motion.camera.strip().lower() in MOTIONLESS_CAMERAS:
        checks.append(
            DesignCheck(
                id="design.no_camera_motive",
                level="warning",
                rule="a shot longer than 6 s needs a camera motive or an internal change",
                message=f"camera is {design.motion.camera!r} across {design.duration_s:g}s",
                shot_id=shot,
            )
        )

    for frame in design.keyframes:
        words = sum(len(obj.label.split()) for obj in frame.objects)
        if words > MAX_LABEL_WORDS:
            checks.append(
                DesignCheck(
                    id="design.text_heavy",
                    level="warning",
                    rule=f"at most {MAX_LABEL_WORDS} label words per keyframe",
                    message=f"{frame.id} carries {words} words",
                    shot_id=shot,
                )
            )

    for frame in design.keyframes:
        for obj in frame.objects:
            if _outside_safe(obj.rect):
                checks.append(
                    DesignCheck(
                        id="design.out_of_safe",
                        level="warning",
                        rule="objects stay inside the safe area",
                        message=f"{frame.id}/{obj.id} leaves the safe margin",
                        shot_id=shot,
                    )
                )

    if design.composition.focal_object in {obj.id for frame in design.keyframes for obj in frame.objects}:
        for frame in design.keyframes:
            subject = next((obj for obj in frame.objects if obj.id == focal), None)
            others = [obj for obj in frame.objects if obj.id != focal]
            for other in others:
                if subject is None:
                    break
                ratio = _overlap(subject.rect, other.rect) / max(other.rect.area, 1e-6)
                if ratio > MAX_OVERLAP_RATIO:
                    checks.append(
                        DesignCheck(
                            id="design.overlap",
                            level="warning",
                            rule="secondary objects overlap the subject by less than a third",
                            message=f"{frame.id}/{other.id} covers {ratio:.0%} of itself with the subject",
                            shot_id=shot,
                        )
                    )

    if design.motion.end_hold_s < 0.8:
        checks.append(
            DesignCheck(
                id="design.no_hold",
                level="warning",
                rule="hold the result for at least 0.8 s",
                message=f"end hold is {design.motion.end_hold_s:g}s",
                shot_id=shot,
            )
        )

    if design.duration_s >= 20.0 and len(design.beats) < 2:
        checks.append(
            DesignCheck(
                id="design.no_beats",
                level="error",
                rule="a page longer than 20 s carries at least two beats",
                message=f"{design.duration_s:g}s with {len(design.beats)} scheduled change(s)",
                shot_id=shot,
            )
        )

    gap = design.max_beat_gap_s()
    if design.beats and gap > MAX_GAP_SECONDS:
        checks.append(
            DesignCheck(
                id="design.beat_gap",
                level="info",
                rule=f"the beat contract allows {MAX_GAP_SECONDS:g}s without a visual change",
                message=f"longest stretch with nothing scheduled is {gap:.0f}s over {design.duration_s:g}s",
                shot_id=shot,
            )
        )

    if (
        len(design.composition.depth_layers) < 2
        and len(design.composition.hierarchy) < 2
        and _entry_only(design.motion.primary)
    ):
        checks.append(
            DesignCheck(
                id="design.reads_as_slide",
                level="error",
                rule="a flat hierarchy plus entry-only motion is a slide, not a shot",
                message="block a second layer, or give the focal object a transformation",
                shot_id=shot,
            )
        )

    return checks


def check_design(document: VisualDesign, *, min_shared_objects: int = 0) -> list[DesignCheck]:
    checks: list[DesignCheck] = []
    for design in document.shots:
        checks.extend(_check_shot(design))

    derived = [design.shot_id for design in document.shots if design.authorship == "derived"]
    if derived:
        checks.append(
            DesignCheck(
                id="design.derived",
                level="info",
                rule="a derived design is a draft, not a decision",
                message=(
                    f"{len(derived)} of {len(document.shots)} shots are derived; "
                    "override them in authoring/visual-design.yaml before calling the design done"
                ),
            )
        )

    pages = [design for design in document.shots if design.duration_s > MAX_SHOT_SECONDS]
    if pages:
        checks.append(
            DesignCheck(
                id="design.page_not_shot",
                level="warning",
                rule=f"the beat contract holds one shot to {MAX_SHOT_SECONDS:g}s",
                message=(
                    f"{len(pages)} of {len(document.shots)} pages run longer; "
                    "each page is a sequence of shots, so animate its beats rather than one take"
                ),
            )
        )

    carries = [design for design in document.shots if design.continuity.carries_from]
    shared = [design for design in carries if design.continuity.persistent_objects]
    if carries and len(shared) < min_shared_objects:
        checks.append(
            DesignCheck(
                id="design.continuity_break",
                level="warning",
                rule="adjacent shots in a chapter share at least one object",
                message=f"{len(shared)} of {len(carries)} adjacent shots carry an object forward",
            )
        )
    return checks
