"""Deterministic planners: teaching structure, visual routing, shots, narration.

The planners do not invent content. They formalise the approved brief, outline
and script into a production plan, and route each page to an engine through the
existing ``engine_router``. Narrative claims and visuals come from the outline.
"""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..authoring.models import NarrationScript, Outline, OutlineChapter, OutlinePage
from ..contracts import ShotSpec
from ..engine_router import VisualRequirement, route_engine
from ..layout import choose_template, get_template
from ..paths import LessonPaths
from .inputs import DirectorInputs
from .schema import (
    ChapterPlan,
    DurationPlan,
    NarrationSegmentPlan,
    ShotPlan,
    Typography,
    VisualStyle,
)

STOPWORDS = {
    "explain",
    "describe",
    "demonstrate",
    "summarize",
    "outline",
    "identify",
    "their",
    "these",
    "those",
    "which",
    "where",
    "while",
    "about",
    "including",
    "model",
    "models",
    "using",
    "with",
    "from",
    "that",
    "this",
    "into",
    "each",
    "such",
}

CAMERA_BY_KIND = {
    "title": "static, hold",
    "structure3d": "slow orbit, 25 degree arc",
    "matrix": "slow push in, hold on the active row",
    "chart": "static, cut on",
    "layout": "static, hold",
    "recap": "slow pull back",
    "diagram": "slow push in",
    "simulation": "slow orbit",
}

SIZE_BY_KIND = {
    "title": "wide",
    "structure3d": "wide",
    "matrix": "closeup",
    "chart": "medium",
    "layout": "wide",
    "recap": "wide",
    "diagram": "medium",
    "simulation": "wide",
}

PURPOSE_BY_KIND = {
    "title": "introduce",
    "structure3d": "explain",
    "matrix": "demonstrate",
    "chart": "demonstrate",
    "layout": "summarize",
    "recap": "recap",
    "diagram": "explain",
    "simulation": "demonstrate",
}

SPEECH_WORDS_PER_SECOND = 2.5


def default_style() -> VisualStyle:
    return VisualStyle(
        background="#FBFAF7",
        ink="#252A31",
        muted="#6B7280",
        accent="#E8733B",
        warm="#C75B55",
        green="#42A69A",
        typography=Typography(
            heading_px=56,
            body_px=32,
            label_px=24,
            heading_font="Inter",
            body_font="Inter",
        ),
        color_semantics={
            "query": "#4A82B8",
            "key": "#42A69A",
            "value": "#7A6FB0",
            "result": "#7A6FB0",
            "mask": "#6B7280",
            "attention": "#E8733B",
            "loss": "#C75B55",
            "input": "#4A82B8",
            "process": "#42A69A",
            "output": "#7A6FB0",
        },
        consistency_required=True,
    )


def duration_plan(inputs: DirectorInputs, planned: float) -> DurationPlan:
    policy = inputs.paths.lesson.duration
    if policy is None or policy.target_seconds is None:
        raise ValueError("lesson.duration.target_seconds is required for the director layer")
    return DurationPlan(
        profile=policy.profile,
        target_seconds=policy.target_seconds,
        min_seconds=policy.min_seconds,
        max_seconds=policy.max_seconds,
        planned_seconds=round(planned, 3),
        tolerance_seconds=2.0,
    )


def _page_text(page: OutlinePage) -> str:
    return f"{page.title} {page.claim} {page.visual}".lower()


def _objective_words(text: str) -> list[str]:
    words = re.findall(r"[a-z][a-z-]{4,}", text.lower())
    return [word for word in words if word not in STOPWORDS]


def assign_objectives(chapters: list[OutlineChapter], objectives: list[str]) -> dict[str, str]:
    """Map each brief objective to the chapter whose titles and claims mention it most.

    Rare words weigh more; a hit in the chapter title or a page title counts
    several times more than a passing mention in a claim.
    """
    texts = {chapter.id: " ".join(_page_text(page) for page in chapter.pages) for chapter in chapters}
    chapter_titles = {chapter.id: chapter.title.lower() for chapter in chapters}
    page_titles = {
        chapter.id: " ".join(page.title.lower() for page in chapter.pages) for chapter in chapters
    }
    document_frequency: dict[str, int] = {}
    for chapter in chapters:
        terms = set(_objective_words(texts[chapter.id] + " " + chapter_titles[chapter.id]))
        for term in terms:
            document_frequency[term] = document_frequency.get(term, 0) + 1

    assigned: dict[str, list[str]] = {chapter.id: [] for chapter in chapters}
    for objective in objectives:
        words = _objective_words(objective)
        if not words:
            continue
        scored: list[tuple[float, str]] = []
        for chapter in chapters:
            score = 0.0
            for word in words:
                weight = 1.0 / max(1, document_frequency.get(word, 0))
                boost = 1.0
                if word in chapter_titles[chapter.id]:
                    boost += 4.0
                if word in page_titles[chapter.id]:
                    boost += 6.0
                score += weight * texts[chapter.id].count(word) * boost
            scored.append((score, chapter.id))
        score, chapter_id = max(scored)
        if score > 0:
            assigned[chapter_id].append(objective)

    result: dict[str, str] = {}
    for chapter in chapters:
        picked = assigned[chapter.id][:2]
        if picked:
            result[chapter.id] = " ".join(picked)
        elif any(page.visual_kind == "recap" for page in chapter.pages):
            result[chapter.id] = (
                f"Consolidate {chapter.title.lower()} into one mental model the viewer can restate."
            )
        else:
            result[chapter.id] = f"Explain {chapter.title}."
    return result


def build_chapters(inputs: DirectorInputs) -> list[ChapterPlan]:
    objectives = assign_objectives(inputs.outline.chapters, inputs.brief.objectives)
    chapters: list[ChapterPlan] = []
    cursor = 0.0
    for index, chapter in enumerate(inputs.outline.chapters, start=1):
        total = sum(page.target_seconds for page in chapter.pages)
        start = cursor
        cursor += total
        chapters.append(
            ChapterPlan(
                id=chapter.id,
                title=chapter.title,
                learning_objective=objectives[chapter.id],
                target_seconds=round(total, 3),
                start_s=round(start, 3),
                end_s=round(cursor, 3),
                shot_ids=[f"shot_{page.slide:03d}" for page in chapter.pages],
                source_refs=sorted({ref for page in chapter.pages for ref in page.source_refs}),
            )
        )
    return chapters


@dataclass
class VisualDecision:
    engine: str
    engine_profile: str
    scene: str | None
    readiness: str
    camera: str
    shot_size: str
    motion: list[str]
    notes: str = ""
    overridden: bool = False
    page: OutlinePage | None = None
    asset_seconds: float | None = None
    blend_task: str | None = None
    inputs: dict = field(default_factory=dict)


def resolve_scene(paths: LessonPaths, engine: str, scene: str | None) -> Path | None:
    if not scene or engine == "remotion":
        return None
    relative = scene.split("::", 1)[0] if engine == "manim" else scene
    return (paths.engine_root(engine) / relative).resolve()


def scene_classes(path: Path) -> list[str]:
    """Return Scene subclasses declared in a Manim file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return []
    names: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [ast.unparse(base) for base in node.bases]
        if any(base.split(".")[-1].endswith("Scene") for base in bases):
            names.append(node.name)
    return names


def _camel(animation: str) -> str:
    return "".join(part.capitalize() for part in animation.split("_")) + "Scene"


def _infer_scene(paths: LessonPaths, engine: str, animation: str | None) -> str | None:
    if not animation:
        return None
    slug = paths.slug
    if engine == "manim":
        candidate = paths.engine_root("manim") / slug / f"{animation}.py"
        if not candidate.is_file():
            return None
        classes = scene_classes(candidate)
        expected = _camel(animation)
        chosen = expected if expected in classes else (classes[0] if len(classes) == 1 else None)
        if chosen is None:
            return None
        return f"{slug}/{animation}.py::{chosen}"
    if engine == "blender":
        candidate = paths.engine_root("blender") / "scenes" / slug / f"{animation}.blend"
        return f"scenes/{slug}/{animation}.blend" if candidate.is_file() else None
    if engine == "code_video":
        candidate = paths.engine_root("code_video") / "shots" / animation / "SPEC.md"
        return f"shots/{animation}/SPEC.md" if candidate.is_file() else None
    return None


def plan_visual(paths: LessonPaths, page: OutlinePage, storyboard_shots: dict[int, ShotSpec]) -> VisualDecision:
    route = route_engine(
        VisualRequirement(kind=page.visual_kind, needs_3d=page.needs_3d, duration_s=page.target_seconds)
    )
    engine, profile = route.engine, route.profile
    scene: str | None = None
    notes = route.reason
    overridden = False

    existing = storyboard_shots.get(page.slide)
    if existing is not None:
        overridden = existing.engine != engine
        engine = existing.engine
        profile = existing.engine_profile or profile
        scene = existing.scene
        notes = "storyboard override" if overridden else "storyboard scene"
    else:
        scene = _infer_scene(paths, engine, page.animation)

    inputs: dict = {}
    if existing is not None and existing.inputs:
        inputs = dict(existing.inputs)
    elif engine == "code_video" and page.animation:
        shot_spec = paths.engine_root("code_video") / "shots" / page.animation / "shot.spec.json"
        if shot_spec.is_file():
            try:
                inputs = dict(json.loads(shot_spec.read_text(encoding="utf-8")).get("inputs") or {})
            except (OSError, json.JSONDecodeError):
                inputs = {}

    resolved = resolve_scene(paths, engine, scene)
    readiness = "ready" if engine == "remotion" or (resolved is not None and resolved.is_file()) else "planned"
    if readiness == "planned" and scene:
        notes += "; scene file missing"
    elif readiness == "planned" and engine != "remotion":
        notes += "; no scene implemented yet"

    motion = [f"animate {page.animation}"] if page.animation else (
        ["fade in", "hold"] if engine == "remotion" else ["draw on", "hold"]
    )
    return VisualDecision(
        engine=engine,
        engine_profile=profile,
        scene=scene,
        readiness=readiness,
        camera=CAMERA_BY_KIND.get(page.visual_kind, "slow push in"),
        shot_size=SIZE_BY_KIND.get(page.visual_kind, "medium"),
        motion=motion,
        notes=notes,
        overridden=overridden,
        page=page,
        asset_seconds=existing.expected_duration_s if existing is not None else None,
        blend_task=existing.blend_task if existing is not None else None,
        inputs=inputs,
    )


def build_shots(
    inputs: DirectorInputs,
    chapters: list[ChapterPlan],
    decisions: dict[int, VisualDecision],
    storyboard_shots: dict[int, ShotSpec],
) -> list[ShotPlan]:
    script_by_slide = {page.slide: page for page in inputs.script.pages}
    shots: list[ShotPlan] = []
    cursor = 0.0
    previous_engine: str | None = None
    previous_chapter: str | None = None
    for chapter in inputs.outline.chapters:
        for page in chapter.pages:
            decision = decisions[page.slide]
            start = cursor
            cursor += page.target_seconds
            existing = storyboard_shots.get(page.slide)
            cue = existing.cue_seconds if existing is not None else min(30.0, max(0.0, page.target_seconds / 3))
            layout_id = choose_template(page.visual_kind, page.animation)
            layout = get_template(layout_id)
            narration_ids = (
                [segment.id for segment in script_by_slide[page.slide].segments]
                if inputs.paths.lesson.narration.enabled and page.slide in script_by_slide
                else []
            )
            same_context = decision.engine == previous_engine and chapter.id == previous_chapter
            transition = "continuous" if same_context and page.visual_kind not in {"title", "layout", "recap"} else "cut"
            shot_id = f"shot_{page.slide:03d}"
            shots.append(
                ShotPlan(
                    id=shot_id,
                    chapter_id=chapter.id,
                    slide=page.slide,
                    title=page.title,
                    purpose=PURPOSE_BY_KIND.get(page.visual_kind, "explain"),
                    engine=decision.engine,
                    engine_profile=decision.engine_profile,
                    scene=decision.scene,
                    blend_task=decision.blend_task,
                    inputs=decision.inputs,
                    asset_seconds=decision.asset_seconds,
                    readiness=decision.readiness,
                    start_s=round(start, 3),
                    end_s=round(cursor, 3),
                    cue_seconds=round(cue, 3),
                    target_seconds=round(page.target_seconds, 3),
                    transition=transition,
                    layout_template=layout_id,
                    layout_regions={
                        region.role: [region.x, region.y, region.w, region.h]
                        for region in layout.regions
                    },
                    shot_size=decision.shot_size,
                    learning_intent=page.claim,
                    visual_metaphor=page.visual,
                    composition=(
                        "single claim per frame; 96 px safe margin; heading 56-72 px; "
                        "body 30-36 px; one accent role at a time"
                    ),
                    camera=decision.camera,
                    motion=decision.motion,
                    on_screen_text=[page.title],
                    narration_ids=narration_ids,
                    source_refs=page.source_refs,
                    direction_file=f"directions/{shot_id}.json",
                    notes=decision.notes,
                )
            )
            previous_engine = decision.engine
            previous_chapter = chapter.id
    return shots


def build_narration(
    script: NarrationScript, shots: list[ShotPlan], words_per_second: float = SPEECH_WORDS_PER_SECOND
) -> list[NarrationSegmentPlan]:
    by_slide = {shot.slide: shot for shot in shots}
    segments: list[NarrationSegmentPlan] = []
    for page in script.pages:
        shot = by_slide.get(page.slide)
        if shot is None:
            continue
        for segment in page.segments:
            words = max(1, len(re.findall(r"\b[\w'-]+\b", segment.text)))
            estimated = max(1.0, words / words_per_second + segment.pause_after_ms / 1000.0)
            segments.append(
                NarrationSegmentPlan(
                    id=segment.id,
                    shot_id=shot.id,
                    page=page.slide,
                    text=segment.text,
                    style=segment.style,
                    pause_after_ms=segment.pause_after_ms,
                    estimated_seconds=round(estimated, 3),
                    emphasis=segment.emphasis,
                    source_refs=segment.source_refs,
                )
            )
    return segments


def plan_all(inputs: DirectorInputs) -> tuple[list[ChapterPlan], list[ShotPlan], list[NarrationSegmentPlan], dict[int, VisualDecision]]:
    chapters = build_chapters(inputs)
    storyboard_shots = {shot.slide: shot for shot in inputs.paths.storyboard.shots}
    decisions = {
        page.slide: plan_visual(inputs.paths, page, storyboard_shots)
        for chapter in inputs.outline.chapters
        for page in chapter.pages
    }
    shots = build_shots(inputs, chapters, decisions, storyboard_shots)
    narration = build_narration(inputs.script, shots) if inputs.paths.lesson.narration.enabled else []
    return chapters, shots, narration, decisions
