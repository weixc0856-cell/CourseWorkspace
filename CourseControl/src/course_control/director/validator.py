"""Hard gates for the director plan.

Rules are split into structural checks (a plan can be validated on its own) and
contextual checks (needs the lesson, approved authoring inputs and routing
decisions). Errors block a plan; warnings are recorded and reviewed.
"""
from __future__ import annotations

import re

from .inputs import DirectorInputs
from ..layout import get_template, validate_content, validate_template
from .planners import VisualDecision, resolve_scene, scene_classes
from .schema import DirectorCheck, DirectorPlan

MANIM_DEFAULT_BACKGROUND = "#000000"
COLOR_NAMES = {"WHITE": "#FFFFFF", "BLACK": "#000000"}
BACKGROUND_RE = re.compile(r"config\.background_color\s*=\s*(?:['\"](#[0-9A-Fa-f]{6})['\"]|([A-Z_]+))")

MAX_SHOT_SECONDS = 180.0
MAX_CHAPTER_SECONDS = 420.0
MAX_SEGMENT_SECONDS = 35.0
MIN_NARRATION_COVERAGE = 0.6


class _Checks:
    def __init__(self) -> None:
        self.items: list[DirectorCheck] = []

    def add(self, rule: str, level: str, message: str, *, shot_id: str | None = None, chapter_id: str | None = None) -> None:
        self.items.append(
            DirectorCheck(
                id=f"chk{len(self.items) + 1:03d}",
                rule=rule,
                level=level,  # type: ignore[arg-type]
                message=message,
                shot_id=shot_id,
                chapter_id=chapter_id,
            )
        )


def _structural(plan: DirectorPlan) -> _Checks:
    checks = _Checks()
    duration = plan.duration
    if duration.min_seconds is not None and duration.planned_seconds < duration.min_seconds:
        checks.add("duration.minimum", "error", f"planned {duration.planned_seconds:g}s is below min {duration.min_seconds:g}s")
    if duration.max_seconds is not None and duration.planned_seconds > duration.max_seconds:
        checks.add("duration.maximum", "error", f"planned {duration.planned_seconds:g}s exceeds max {duration.max_seconds:g}s")
    if abs(duration.planned_seconds - duration.target_seconds) > duration.tolerance_seconds:
        checks.add(
            "duration.target",
            "error",
            f"planned {duration.planned_seconds:g}s differs from target {duration.target_seconds:g}s by more than {duration.tolerance_seconds:g}s",
        )

    required_roles = {"query", "key", "value", "result", "mask"}
    missing_roles = sorted(required_roles - set(plan.style.color_semantics))
    if plan.style.consistency_required and missing_roles:
        checks.add("style.missing_roles", "warning", f"color semantics missing roles: {', '.join(missing_roles)}")

    chapter_total = sum(chapter.target_seconds for chapter in plan.chapters)
    if abs(chapter_total - duration.planned_seconds) > 0.01:
        checks.add("duration.chapter_sum", "error", f"chapters total {chapter_total:g}s, plan says {duration.planned_seconds:g}s")

    slides = sorted(shot.slide for shot in plan.shots)
    if slides != list(range(1, len(slides) + 1)):
        checks.add("coverage.slides", "error", f"shots must cover slides 1..N exactly once, got {slides}")

    cursor = 0.0
    for shot in plan.shots:
        if abs(shot.start_s - cursor) > 0.01:
            checks.add("timeline.contiguous", "error", f"starts at {shot.start_s:g}s, expected {cursor:g}s", shot_id=shot.id)
        if abs(shot.duration_s - shot.target_seconds) > 0.01:
            checks.add(
                "timeline.target_span",
                "error",
                f"span {shot.duration_s:g}s does not match target {shot.target_seconds:g}s",
                shot_id=shot.id,
            )
        if shot.cue_seconds > shot.target_seconds:
            checks.add(
                "cue.out_of_page",
                "error",
                f"insert cue {shot.cue_seconds:g}s is outside the {shot.target_seconds:g}s page",
                shot_id=shot.id,
            )
        cursor = shot.end_s
    if abs(cursor - duration.planned_seconds) > 0.01:
        checks.add("timeline.total", "error", f"shots end at {cursor:g}s, plan says {duration.planned_seconds:g}s")

    shot_by_id = {shot.id: shot for shot in plan.shots}
    for chapter in plan.chapters:
        chapter_shots = [shot_by_id[sid] for sid in chapter.shot_ids if sid in shot_by_id]
        if len(chapter_shots) != len(chapter.shot_ids):
            checks.add("chapter.shots_exist", "error", "chapter references an unknown shot", chapter_id=chapter.id)
            continue
        start = min(shot.start_s for shot in chapter_shots)
        end = max(shot.end_s for shot in chapter_shots)
        if abs(start - chapter.start_s) > 0.01 or abs(end - chapter.end_s) > 0.01:
            checks.add(
                "chapter.span",
                "error",
                f"chapter spans {start:g}-{end:g}s but declares {chapter.start_s:g}-{chapter.end_s:g}s",
                chapter_id=chapter.id,
            )

    shot_ids = set(shot_by_id)
    segment_ids = {segment.id for segment in plan.narration}
    for shot in plan.shots:
        for nid in shot.narration_ids:
            if nid not in segment_ids:
                checks.add("narration.missing_segment", "error", f"references unknown narration {nid}", shot_id=shot.id)
        if plan.narration and not shot.narration_ids:
            checks.add("narration.uncovered_shot", "error", "shot has no narration segment", shot_id=shot.id)
    for segment in plan.narration:
        if segment.shot_id not in shot_ids:
            checks.add("narration.orphan", "error", f"points at unknown shot {segment.shot_id}", shot_id=segment.shot_id)
    return checks


def scene_background(scene_file) -> str | None:
    try:
        text = scene_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    match = BACKGROUND_RE.search(text)
    if match is None:
        return MANIM_DEFAULT_BACKGROUND
    if match.group(1):
        return match.group(1).upper()
    return COLOR_NAMES.get(match.group(2), None)


def _contextual(plan: DirectorPlan, inputs: DirectorInputs, decisions: dict[int, VisualDecision]) -> _Checks:
    checks = _Checks()
    lesson_engines = set(inputs.paths.lesson.engines) | {"remotion"}
    pages = {page.slide: page for chapter in inputs.outline.chapters for page in chapter.pages}
    scenes: dict[str, list[str]] = {}
    engine_switches = 0
    previous: str | None = None

    for shot in plan.shots:
        if shot.engine not in lesson_engines:
            checks.add("engine.not_enabled", "error", f"engine {shot.engine!r} is not listed in lesson.engines", shot_id=shot.id)
        page = pages.get(shot.slide)
        decision = decisions.get(shot.slide)
        if page is not None and page.needs_3d and shot.engine != "blender":
            if decision is None or not decision.overridden:
                checks.add("engine.3d_route", "error", "3D page must route to blender or record an explicit storyboard override", shot_id=shot.id)
        if shot.duration_s > MAX_SHOT_SECONDS:
            checks.add("shot.max_duration", "error", f"{shot.duration_s:g}s exceeds {MAX_SHOT_SECONDS:g}s single-shot cap", shot_id=shot.id)
        resolved = resolve_scene(inputs.paths, shot.engine, shot.scene)
        if shot.scene and resolved is not None and not resolved.is_file():
            checks.add("scene.exists", "error", f"scene not found: {resolved}", shot_id=shot.id)
        if shot.engine == "manim" and "::" in (shot.scene or "") and resolved is not None and resolved.is_file():
            class_name = shot.scene.split("::", 1)[1]
            if class_name not in scene_classes(resolved):
                checks.add(
                    "scene.class_missing",
                    "error",
                    f"class {class_name!r} is not declared in {resolved.name}",
                    shot_id=shot.id,
                )
        if shot.engine == "manim" and resolved is not None and resolved.is_file() and shot.readiness == "ready":
            background = scene_background(resolved)
            if background is not None and background.upper() != plan.style.background.upper():
                checks.add(
                    "style.background_mismatch",
                    "warning",
                    f"scene background {background} differs from the plan style {plan.style.background}",
                    shot_id=shot.id,
                )
        if shot.readiness == "planned":
            checks.add("production.planned", "warning", f"no renderable scene yet ({shot.engine})", shot_id=shot.id)
        if shot.asset_seconds is not None and shot.cue_seconds + shot.asset_seconds > shot.target_seconds + 2.0:
            checks.add(
                "insert.overruns_page",
                "warning",
                f"insert {shot.asset_seconds:g}s at {shot.cue_seconds:g}s exceeds the {shot.target_seconds:g}s page",
                shot_id=shot.id,
            )
        if shot.asset_seconds is not None and shot.asset_seconds < shot.target_seconds * 0.25:
            checks.add(
                "insert.short",
                "info",
                f"animation insert {shot.asset_seconds:g}s on a {shot.target_seconds:g}s page; deck mode keeps the slide around it",
                shot_id=shot.id,
            )
        if shot.scene:
            scenes.setdefault(shot.scene, []).append(shot.id)
        if previous is not None and shot.engine != previous:
            engine_switches += 1
        previous = shot.engine

    for chapter in plan.chapters:
        if chapter.learning_objective.strip() == f"Explain {chapter.title}.":
            checks.add(
                "teaching.objective_fallback",
                "warning",
                "no brief objective matched this chapter; the learning objective is a placeholder",
                chapter_id=chapter.id,
            )
        if chapter.target_seconds > MAX_CHAPTER_SECONDS:
            checks.add("chapter.max_duration", "warning", f"{chapter.target_seconds:g}s is long for one chapter", chapter_id=chapter.id)

    for scene, shot_ids in scenes.items():
        if len(shot_ids) > 1:
            checks.add("scene.duplicate", "warning", f"{scene} is reused by {', '.join(shot_ids)}")

    if engine_switches > 6:
        checks.add("engine.churn", "warning", f"{engine_switches} engine switches across the lesson")

    for shot in plan.shots:
        if not shot.source_refs:
            checks.add("source.missing", "error", "shot has no source reference", shot_id=shot.id)
        if shot.engine == "remotion" and shot.readiness != "ready":
            checks.add("remotion.readiness", "warning", "remotion layout shot is not marked ready", shot_id=shot.id)

    if not any(shot.readiness == "ready" for shot in plan.shots):
        checks.add("execution.no_ready_shot", "error", "no shot is renderable; a POC needs at least one ready shot")

    seen_layouts: set[str] = set()
    for shot in plan.shots:
        if shot.layout_template in seen_layouts:
            continue
        seen_layouts.add(shot.layout_template)
        try:
            template = get_template(shot.layout_template)
        except KeyError:
            checks.add("layout.unknown_template", "error", f"unknown layout {shot.layout_template!r}", shot_id=shot.id)
            continue
        for check in validate_template(template):
            checks.add(check.id, check.level, f"{shot.id} {template.id}: {check.message}", shot_id=shot.id)
        for check in validate_content(template, title_chars=len(shot.title)):
            checks.add(check.id, check.level, f"{shot.id} {template.id}: {check.message}", shot_id=shot.id)

    narration_by_shot: dict[str, float] = {}
    for segment in plan.narration:
        narration_by_shot[segment.shot_id] = narration_by_shot.get(segment.shot_id, 0.0) + segment.estimated_seconds
        if segment.estimated_seconds > MAX_SEGMENT_SECONDS:
            checks.add("narration.segment_long", "warning", f"{segment.estimated_seconds:g}s estimated for one segment", shot_id=segment.shot_id)
    for shot in plan.shots:
        estimated = narration_by_shot.get(shot.id, 0.0)
        if plan.narration and estimated == 0:
            continue
        if estimated > shot.target_seconds + 2.0:
            checks.add(
                "narration.overrun",
                "warning",
                f"estimated narration {estimated:.1f}s exceeds the {shot.target_seconds:g}s page budget",
                shot_id=shot.id,
            )
        elif plan.narration and estimated < shot.target_seconds * MIN_NARRATION_COVERAGE:
            checks.add(
                "narration.underfill",
                "warning",
                f"estimated narration {estimated:.1f}s fills less than {MIN_NARRATION_COVERAGE:.0%} of the page budget",
                shot_id=shot.id,
            )

    if not plan.approval.approved:
        failed = [item.kind for item in plan.approval.artifacts if item.status != "ok"]
        checks.add("source.approval", "warning", f"unapproved or changed authoring inputs: {', '.join(failed) or 'none'}")

    for slide, decision in sorted(decisions.items()):
        if decision.overridden:
            checks.add("engine.override", "info", f"slide {slide}: {decision.notes}", shot_id=f"shot_{slide:03d}")
    return checks


def validate(plan: DirectorPlan, inputs: DirectorInputs | None = None, decisions: dict[int, VisualDecision] | None = None) -> list[DirectorCheck]:
    checks = _structural(plan)
    if inputs is not None and decisions is not None:
        checks.items.extend(_contextual(plan, inputs, decisions).items)
    for index, item in enumerate(checks.items, start=1):
        item.id = f"chk{index:03d}"
    return checks.items
