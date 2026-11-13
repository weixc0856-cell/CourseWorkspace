"""Derive a visual design for every shot, then merge authored overrides.

Everything here is a *draft*: geometry comes from the shot's layout regions,
wording comes from the outline, and identity comes from the shot title.  The
draft exists so that no shot reaches an engine without a blocking, a motion and
three keyframes.  Anything a human or an authoring pass decides replaces the
draft and flips ``authorship`` to ``authored``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from course_control.authoring.models import Outline, OutlinePage
from course_control.content.paths import ContractError
from course_control.design.schema import (
    ArtDirection,
    Beat,
    Composition,
    ContinuityPlan,
    DepthLayer,
    Keyframe,
    KeyframeObject,
    MotionPlan,
    Rect,
    ShotDesign,
    VisualDesign,
)
from course_control.direction.schema import DirectorPlan, NarrationSegmentPlan, ShotPlan
from course_control.rendering.theme import DEFAULT_THEME, load_theme, theme_names

SAFE = Rect(x=0.06, y=0.09, w=0.88, h=0.82)

FAMILY_BY_KIND: dict[str, str] = {
    "title": "editorial",
    "diagram": "geometric",
    "matrix": "geometric",
    "chart": "editorial",
    "data": "editorial",
    "structure3d": "engineering",
    "simulation": "cinematic",
    "process": "engineering",
    "layout": "editorial",
    "recap": "editorial",
}

ATMOSPHERE = {
    "editorial": "quiet, precise, unhurried",
    "geometric": "exact, diagrammatic, slightly cold",
    "engineering": "solid, industrial, measured",
    "cinematic": "spatial, immersive, low contrast around the subject",
}

# What changes at the turn of the shot.  These are transformations, not entries:
# an object that only fades in has not explained anything.
MOTION_BY_KIND: dict[str, str] = {
    "title": "the claim sets in place; one geometric mark resolves beside it",
    "diagram": "one object is drawn, then transformed in front of the viewer; nothing is replaced by a fade",
    "matrix": "values change along one row, then propagate into the aggregate",
    "chart": "the series grows into place, then one annotation locks the reading",
    "structure3d": "the camera arcs while one part separates from the stack and returns",
    "simulation": "the field evolves under one rule; the camera follows the consequence, not the particles",
    "process": "one stage hands its output to the next; the frame never resets",
    "layout": "the frame is built in blocks, then one block moves to reveal the relation",
    "recap": "the chapter's objects return to their last positions, then collapse into one frame",
}
DEFAULT_PRIMARY = "the focal object transforms continuously; labels arrive after the change"
SECONDARY = "labels follow the object they name; the background stays quiet"

ENTRY_VERBS = (
    "fade in",
    "fades in",
    "appear",
    "appears",
    "cut in",
    "pop in",
    "slide in",
    "type on",
)

# Beat kinds come from the script's own function, not from a fixed cadence.
BEAT_HINTS: tuple[tuple[str, str], ...] = (
    (r"\?", "reveal"),
    (r"\b(but|however|unlike|instead|by contrast)\b", "compare"),
    (r"\b(for example|imagine|consider)\b", "connect"),
    (r"\b(so|therefore|that means|the point is|in the end)\b", "highlight"),
    (r"\b(next|now let|let me move|turn to)\b", "camera"),
)


def _rgb(value: str) -> tuple[int, int, int]:
    return (
        int(value[1:3], 16),
        int(value[3:5], 16),
        int(value[5:7], 16),
    )


def nearest_theme(workspace: Path, background: str) -> str:
    """Pick the theme whose paper colour is closest to the lesson's page colour."""
    try:
        target = _rgb(background)
    except (ValueError, IndexError):
        return DEFAULT_THEME
    best: tuple[float, str] | None = None
    for name in theme_names(workspace):
        theme = load_theme(workspace, name)
        paper = theme.get("colors", {}).get("paper")
        if not isinstance(paper, str):
            continue
        distance = float(sum((a - b) ** 2 for a, b in zip(_rgb(paper), target)))
        if best is None or distance < best[0]:
            best = (distance, name)
    return best[1] if best else DEFAULT_THEME


def slug_id(text: str) -> str:
    """A stable object id: 'Query, Key, Value' becomes 'query_key_value'."""
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    cleaned = re.sub(r"_+", "_", cleaned)[:32].strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"object_{cleaned}"[:32].rstrip("_")
    if len(cleaned) < 2:
        cleaned = f"{cleaned}_o"
    return cleaned


STOP_TAIL = {
    "a", "an", "the", "of", "in", "on", "into", "to", "with", "for", "and", "or",
    "by", "from", "as", "that", "which", "is", "are", "was", "were", "its",
}


def _short(text: str, limit: int = 52) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip(" ,;:") + "…"


def _phrase(text: str, limit: int = 34) -> str:
    """A label-sized phrase: first clause, cut on a word boundary, no dangling stop words."""
    text = " ".join(text.split())
    clause = re.split(r"[.;:—–]", text, maxsplit=1)[0] or text
    if len(clause) > limit:
        clause = clause[:limit].rsplit(" ", 1)[0] if " " in clause[:limit] else clause[:limit]
    words = clause.split()
    while len(words) > 2 and words[-1].strip(",.;:").lower() in STOP_TAIL:
        words.pop()
    result = " ".join(words).strip(" ,;:")
    if len(result) < len(text) and not result.endswith("…"):
        result += "…"
    return result or _short(text, limit)


def _region(shot: ShotPlan, role: str) -> Rect | None:
    values = shot.layout_regions.get(role)
    if not values or len(values) != 4:
        return None
    try:
        return Rect(x=values[0], y=values[1], w=values[2], h=values[3])
    except ValueError:
        return None


def _largest_region(shot: ShotPlan) -> Rect | None:
    present = [item for item in (_region(shot, role) for role in shot.layout_regions) if item is not None]
    return max(present, key=lambda item: item.area) if present else None


def _scaled(rect: Rect, factor: float) -> Rect:
    w = rect.w * factor
    h = rect.h * factor
    x = min(max(rect.cx - w / 2, 0.0), 1.0 - w)
    y = min(max(rect.cy - h / 2, 0.0), 1.0 - h)
    return Rect(x=round(x, 4), y=round(y, 4), w=round(w, 4), h=round(h, 4))


def _family(shot: ShotPlan, page: OutlinePage | None) -> str:
    kind = page.visual_kind if page else ""
    family = FAMILY_BY_KIND.get(kind)
    if family:
        return family
    if shot.engine == "blender":
        return "engineering"
    if shot.engine == "code_video":
        return "cinematic"
    return "editorial"


def _depth_layers(shot: ShotPlan, family: str, subject: Rect, support: Rect | None) -> list[DepthLayer]:
    layers = [
        DepthLayer(
            id="bg",
            role="background",
            rect=SAFE,
            contrast="quiet",
            content=(
                "a far plane or field with one light direction"
                if family in {"engineering", "cinematic"}
                else "the page tone; nothing competes with the subject"
            ),
        )
    ]
    if family in {"engineering", "cinematic"}:
        layers.append(
            DepthLayer(
                id="mid",
                role="midground",
                rect=_scaled(subject, 1.18),
                contrast="quiet",
                content="a structure one step behind the subject, slightly dimmer",
            )
        )
    layers.append(
        DepthLayer(
            id="subject",
            role="subject",
            rect=subject,
            contrast="balanced",
            content=f"the one object the claim is about: {_short(shot.title, 36)}",
        )
    )
    if support is not None:
        layers.append(
            DepthLayer(
                id="fg",
                role="foreground",
                rect=support,
                contrast="quiet",
                content="labels and evidence, overlapping the subject by less than a third",
            )
        )
    return layers


def _shot_objects(shot: ShotPlan, page: OutlinePage | None) -> tuple[KeyframeObject, KeyframeObject | None, KeyframeObject]:
    subject_rect = _region(shot, "main_visual") or _largest_region(shot) or Rect(x=0.06, y=0.18, w=0.58, h=0.58)
    focal = KeyframeObject(
        id=slug_id(shot.title),
        label=_phrase(shot.title, 26),
        rect=subject_rect,
        color_role="accent",
        emphasis=True,
    )
    support_rect = _region(shot, "explanation") or _region(shot, "caption")
    if support_rect is None:
        scaled = _scaled(subject_rect, 0.45)
        support_rect = Rect(
            x=round(min(subject_rect.x + subject_rect.w - scaled.w, 1 - scaled.w), 4),
            y=round(max(subject_rect.y, 0.09), 4),
            w=scaled.w,
            h=scaled.h,
        )
    support = KeyframeObject(
        id="support",
        label=_phrase(page.visual if page and page.visual else "supporting evidence", 28),
        rect=support_rect,
        color_role="teal",
    )
    text = _phrase(page.claim, 26) if page else _short(shot.learning_intent, 26)
    # The result label sits in the caption band under the subject: it names what
    # the turned frame means without covering the evidence it refers to.
    label_w = round(min(subject_rect.w * 0.6, 0.45), 4)
    label_rect = Rect(
        x=round(min(subject_rect.x + 0.02, 1 - label_w), 4),
        y=SAFE.y,
        w=label_w,
        h=0.055,
    )
    annotation = KeyframeObject(
        id="label",
        label=_short(text, 30),
        rect=label_rect,
        color_role="ink",
    )
    return focal, support, annotation


def _keyframes(
    shot: ShotPlan,
    page: OutlinePage | None,
    focal: KeyframeObject,
    support: KeyframeObject | None,
    annotation: KeyframeObject,
) -> list[Keyframe]:
    duration = shot.duration_s
    hold = min(1.5, round(duration * 0.12, 2))
    turn_at = round(min(max(duration * 0.55, 0.5), max(duration - hold - 0.5, 0.5)), 2)
    end_at = round(max(duration - hold, turn_at + 0.2), 2)
    claim = _short(page.claim if page else shot.learning_intent, 96)
    change = page.animation if page and page.animation else _short(claim, 64)

    start_focal = focal.model_copy(
        update={"rect": _scaled(focal.rect, 0.86), "opacity": 0.9, "emphasis": False}
    )
    turn_objects = [focal] + ([support] if support else [])
    return [
        Keyframe(
            id="start",
            at_s=0.0,
            purpose=f"the viewer meets one object: {focal.label}",
            camera=shot.camera,
            change="the frame starts empty except for the subject; no supporting object yet",
            objects=[start_focal],
        ),
        Keyframe(
            id="turn",
            at_s=turn_at,
            purpose=f"the change the narration describes: {claim}",
            camera=shot.camera,
            change=change,
            objects=turn_objects,
        ),
        Keyframe(
            id="end",
            at_s=end_at,
            purpose="the result settles; nothing new enters, so the frame can be read",
            camera=shot.camera,
            change="the last state holds; the annotation does not move again",
            objects=[focal] + ([support] if support else []) + [annotation],
        ),
    ]


def _motion(shot: ShotPlan, page: OutlinePage | None) -> MotionPlan:
    kind = page.visual_kind if page else ""
    return MotionPlan(
        primary=MOTION_BY_KIND.get(kind, DEFAULT_PRIMARY),
        secondary=SECONDARY,
        camera=shot.camera or "static",
        end_hold_s=min(1.5, round(shot.duration_s * 0.12, 2)),
    )


def _beat_kind(text: str) -> str:
    for pattern, kind in BEAT_HINTS:
        if re.search(pattern, text.lower()):
            return kind
    return "transform"


def _beats(
    shot: ShotPlan,
    page: OutlinePage | None,
    segments: list | None,
    focal: KeyframeObject,
) -> list[Beat]:
    """One change per narrated paragraph, or an even cadence when nothing is written.

    A page of 120 s is a sequence of shots; three keyframes only anchor its ends.
    """
    beats: list[Beat] = []
    if segments:
        cursor = 0.0
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            beats.append(
                Beat(
                    at_s=round(min(cursor, shot.duration_s), 3),
                    kind=_beat_kind(text),  # type: ignore[arg-type]
                    action=_short(text, 80),
                    object=focal.id,
                )
            )
            cursor += segment.estimated_seconds
    else:
        cadence = max(6.0, min(12.0, shot.duration_s / 8))
        count = max(2, int(shot.duration_s // cadence) + 1)
        step = shot.duration_s / count
        for index in range(count):
            kind = "reveal" if index == 0 else ("highlight" if index == count - 1 else "transform")
            beats.append(
                Beat(
                    at_s=round(index * step, 3),
                    kind=kind,  # type: ignore[arg-type]
                    action=(
                        "the page opens; the subject enters"
                        if index == 0
                        else "a further state of the subject is shown"
                    ),
                    object=focal.id,
                )
            )
    return beats[:40]


def derive_shot(
    shot: ShotPlan,
    page: OutlinePage | None,
    theme: str,
    previous: ShotDesign | None,
    segments: list[NarrationSegmentPlan] | None = None,
) -> ShotDesign:
    family = _family(shot, page)
    focal, support, annotation = _shot_objects(shot, page)
    composition = Composition(
        focal_object=focal.id,
        focal_point=(round(focal.rect.cx, 4), round(focal.rect.cy, 4)),
        negative_space="left" if focal.rect.cx >= 0.5 else "right",
        hierarchy=[focal.id] + (["support"] if support else []) + ["label"],
        depth_layers=_depth_layers(shot, family, focal.rect, support.rect if support else None),
        rule="one focal object; type lives in the negative space; nothing enters after the result",
    )
    shared: list[str] = []
    if previous is not None:
        previous_ids = {obj.id for frame in previous.keyframes for obj in frame.objects}
        shared = [focal.id] if focal.id in previous_ids else []
    continuity = ContinuityPlan(
        persistent_objects=shared,
        carries_from=previous.shot_id if previous is not None else None,
        spatial_rule=(
            "the subject keeps its side of the frame and its colour role from the previous shot; "
            "only the camera moves it"
        ),
    )
    return ShotDesign(
        shot_id=shot.id,
        title=shot.title,
        duration_s=round(shot.duration_s, 3),
        concept=page.claim if page else shot.learning_intent,
        art_direction=ArtDirection(
            theme=theme,  # type: ignore[arg-type]
            family=family,  # type: ignore[arg-type]
            atmosphere=ATMOSPHERE[family],
            contrast=(
                "dramatic"
                if family == "cinematic" or (page is not None and page.visual_kind == "title")
                else "balanced"
            ),
            note=f"derived from visual_kind={page.visual_kind if page else 'unknown'} and engine={shot.engine}",
        ),
        composition=composition,
        motion=_motion(shot, page),
        keyframes=_keyframes(shot, page, focal, support, annotation),
        beats=_beats(shot, page, segments, focal),
        continuity=continuity,
        on_screen_text=list(shot.on_screen_text),
        authorship="derived",
    )


def load_authored(lesson_dir: Path, name: str = "authoring/visual-design.yaml") -> dict[str, Any]:
    path = lesson_dir / name
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ContractError(f"cannot read visual design override {path}: {exc}") from exc
    shots = data.get("shots")
    if shots is not None and not isinstance(shots, dict):
        raise ContractError(f"{path}: `shots` must be a mapping of shot id to overrides")
    return {str(key): value for key, value in (shots or {}).items() if isinstance(value, dict)}


def apply_override(design: ShotDesign, override: dict[str, Any]) -> ShotDesign:
    """Replace top-level decisions; keep every field the author did not restate."""
    data = design.model_dump(mode="json")
    data.update(override)
    data["shot_id"] = design.shot_id
    data["duration_s"] = design.duration_s
    data["authorship"] = "authored"
    return ShotDesign.model_validate(data)


def build_design(
    workspace: Path,
    plan: DirectorPlan,
    outline: Outline,
    authored: dict[str, Any] | None = None,
) -> VisualDesign:
    pages = {page.slide: page for chapter in outline.chapters for page in chapter.pages}
    segments_by_shot: dict[str, list[NarrationSegmentPlan]] = {}
    for segment in plan.narration:
        segments_by_shot.setdefault(segment.shot_id, []).append(segment)
    theme = nearest_theme(workspace, plan.style.background)
    designs: list[ShotDesign] = []
    previous: ShotDesign | None = None
    for shot in plan.shots:
        design = derive_shot(
            shot,
            pages.get(shot.slide),
            theme,
            previous,
            segments_by_shot.get(shot.id, []),
        )
        override = (authored or {}).get(shot.id)
        if override:
            design = apply_override(design, override)
        designs.append(design)
        previous = design
    return VisualDesign(
        lesson_id=plan.lesson_id,
        theme_default=theme,  # type: ignore[arg-type]
        lesson_style_background=plan.style.background,
        shots=designs,
        checks=[],
    )
