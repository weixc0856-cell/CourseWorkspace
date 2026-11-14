"""Turn a lesson or a topic project into preview units.

A unit is the smallest thing that can be rendered and cached on its own:

* an engine shot (Manim, CodeVideo, Motion Canvas, Blender), or
* a time window of a Remotion composition (slides, scenes, topic films).

Segments are groups of units.  They are authoring/review boundaries, not a
second timeline authority.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from course_control.content.paths import LessonPaths
from course_control.preview.profile import PreviewLevel

UnitKind = Literal["engine", "remotion"]
ENGINES = {"manim", "code_video", "motion_canvas", "blender"}
DESIGN_FILE = Path("design") / "visual_design.json"


@dataclass
class PreviewUnit:
    id: str
    kind: UnitKind
    start_s: float
    end_s: float
    engine: str | None = None
    scene: str | None = None
    segment: str = "part-01"
    label: str = ""
    composition: str | None = None
    entry: str | None = None
    metadata: dict = field(default_factory=dict)
    design: dict | None = None

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)

    def start_frame(self, fps: int) -> int:
        return max(0, int(round(self.start_s * fps)))

    def end_frame(self, fps: int) -> int:
        return max(self.start_frame(fps) + 1, int(round(self.end_s * fps)))

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "start_s": round(self.start_s, 3),
            "end_s": round(self.end_s, 3),
            "duration_s": round(self.duration_s, 3),
            "engine": self.engine,
            "scene": self.scene,
            "segment": self.segment,
            "label": self.label,
            "composition": self.composition,
            "entry": self.entry,
            "has_design": self.design is not None,
            "metadata": self.metadata,
        }


def load_design(build_root: Path) -> dict[str, dict]:
    path = Path(build_root) / DESIGN_FILE
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    result: dict[str, dict] = {}
    for item in data.get("shots") or []:
        if not isinstance(item, dict):
            continue
        shot_id = item.get("shot_id")
        if isinstance(shot_id, str):
            result[shot_id] = item
    return result


def _lesson_composition(paths: LessonPaths) -> tuple[str, str]:
    """Return (entry, composition) for the lesson's Remotion film."""
    timeline = paths.build_root / "contracts" / "timeline.spec.json"
    if paths.lesson.compose.renderer == "timeline" and timeline.is_file():
        return "src/index.ts", "CourseTimeline"
    return "src/index.ts", "CourseVideo"


def _from_shots_file(paths: LessonPaths, design: dict[str, dict]) -> list[PreviewUnit]:
    data = json.loads((paths.build_root / "shots.json").read_text(encoding="utf-8"))
    entry, composition = _lesson_composition(paths)
    shots_mode = paths.lesson.compose.mode == "shots"
    specs = {item.id: item for item in paths.storyboard.shots}
    units: list[PreviewUnit] = []
    cursor = 0.0
    for index, shot in enumerate(data.get("shots") or []):
        if not isinstance(shot, dict):
            continue
        start = float(shot.get("start_s", cursor))
        duration = float(shot.get("duration_s") or 0.0)
        end = start + duration
        cursor = end
        shot_id = str(shot.get("id") or f"unit-{index + 1:03d}")
        engine = shot.get("engine")
        spec = specs.get(shot_id)
        kind: UnitKind = "remotion"
        if shots_mode and shot.get("kind") == "animation" and engine in ENGINES:
            kind = "engine"
        units.append(
            PreviewUnit(
                id=shot_id,
                kind=kind,
                start_s=start,
                end_s=end,
                engine=engine if kind == "engine" else None,
                scene=(spec.scene if spec is not None else shot.get("source"))
                if kind == "engine"
                else None,
                segment=f"part-{index // 6 + 1:02d}",
                label=str(shot.get("kind") or "shot"),
                composition=composition,
                entry=entry,
                metadata={
                    "source_kind": shot.get("kind"),
                    "slide": shot.get("slide"),
                    "timeline_role": shot.get("timeline_role"),
                    "blend_task": spec.blend_task if spec is not None else None,
                },
                design=design.get(shot_id),
            )
        )
    return _apply_production_segments(paths, units)


def _apply_production_segments(paths: LessonPaths, units: list[PreviewUnit]) -> list[PreviewUnit]:
    if paths.production is None:
        return units
    sequence_of: dict[str, str] = {}
    for sequence in paths.production.sequences:
        for shot in sequence.shots:
            sequence_of[shot.id] = sequence.id
    for unit in units:
        unit.segment = sequence_of.get(unit.id, unit.segment)
    return units


def _from_storyboard(paths: LessonPaths, design: dict[str, dict]) -> list[PreviewUnit]:
    entry, composition = _lesson_composition(paths)
    units: list[PreviewUnit] = []
    cursor = 0.0
    for index, shot in enumerate(paths.storyboard.shots):
        start = max(cursor, float(shot.cue_seconds or 0.0))
        duration = shot.expected_duration_s
        if duration is None:
            next_cue = None
            for later in paths.storyboard.shots[index + 1 :]:
                if later.cue_seconds and later.cue_seconds > start:
                    next_cue = float(later.cue_seconds)
                    break
            duration = (next_cue - start) if next_cue and next_cue > start else 5.0
        end = start + float(duration)
        cursor = end
        units.append(
            PreviewUnit(
                id=shot.id,
                kind="engine",
                start_s=start,
                end_s=end,
                engine=shot.engine,
                scene=shot.scene,
                segment=f"part-{index // 6 + 1:02d}",
                label="storyboard",
                composition=composition,
                entry=entry,
                metadata={
                    "slide": shot.slide,
                    "source_kind": "animation",
                    "blend_task": shot.blend_task,
                },
                design=design.get(shot.id),
            )
        )
    return _apply_production_segments(paths, units)


def _from_production(paths: LessonPaths, design: dict[str, dict]) -> list[PreviewUnit]:
    entry, composition = _lesson_composition(paths)
    units: list[PreviewUnit] = []
    cursor = 0.0
    for sequence in paths.production.sequences if paths.production else []:
        for shot in sequence.shots:
            start = cursor
            end = start + shot.duration_s
            cursor = end
            remotion = shot.renderer == "remotion"
            units.append(
                PreviewUnit(
                    id=shot.id,
                    kind="remotion" if remotion else "engine",
                    start_s=start,
                    end_s=end,
                    engine=None if remotion else shot.renderer,
                    scene=None if remotion else shot.source,
                    segment=sequence.id,
                    label=shot.purpose,
                    composition=composition,
                    entry=entry,
                    metadata={
                        "visual_type": shot.visual_type,
                        "grammar": shot.grammar,
                        "camera": shot.camera.model_dump(mode="json"),
                        "blend_task": shot.source if shot.renderer == "blender" else None,
                    },
                    design=design.get(shot.id),
                )
            )
    return units


def plan_lesson_units(
    paths: LessonPaths,
    level: PreviewLevel | str = PreviewLevel.SHOT,
    selection: set[str] | None = None,
) -> list[PreviewUnit]:
    """Return units for a lesson, filtered by level and an optional selection.

    ``selection`` holds shot ids for ``shot`` and segment ids for ``segment``.
    """
    level = PreviewLevel(level)
    design = load_design(paths.build_root)
    if paths.production is not None:
        units = _from_production(paths, design)
        # A shots-mode lesson may already have a normalized timeline; prefer it
        # because it carries measured timing and overlays.
        if (paths.build_root / "shots.json").is_file():
            units = _from_shots_file(paths, design)
    elif (paths.build_root / "shots.json").is_file():
        units = _from_shots_file(paths, design)
    else:
        units = _from_storyboard(paths, design)

    if level is PreviewLevel.PROJECT:
        return units
    if level is PreviewLevel.SEGMENT and selection:
        return [unit for unit in units if unit.segment in selection]
    if level is PreviewLevel.SHOT and selection:
        return [unit for unit in units if unit.id in selection]
    return units


def segments(units: list[PreviewUnit]) -> dict[str, list[PreviewUnit]]:
    result: dict[str, list[PreviewUnit]] = {}
    for unit in units:
        result.setdefault(unit.segment, []).append(unit)
    return result


__all__ = [
    "ENGINES",
    "PreviewUnit",
    "load_design",
    "plan_lesson_units",
    "segments",
]
