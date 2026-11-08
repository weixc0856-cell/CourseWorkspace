from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .colormaps import load_colormaps
from .contracts import (
    Annotation,
    LegendAnnotation,
    Shot,
    ShotsFile,
    TextAnnotation,
    Timeline,
)
from .duration import resolve, window_problem
from .paths import ContractError, LessonPaths
from .utils import count_srt_cues, load_json, page_budgets, probe_audio, probe_media


def _scene_stem(paths: LessonPaths, shot) -> str:
    scene_path, _ = paths.scene_path(shot)
    if shot.engine == "code_video":
        return scene_path.parent.name
    return scene_path.stem


def _animation_source(paths: LessonPaths, shot) -> Path:
    if shot.engine in ("motion_canvas", "manim", "code_video"):
        return paths.build_root / "animation" / f"{_scene_stem(paths, shot)}.mp4"
    task_path = paths.blend_task_path(shot)
    if task_path is None:
        raise ContractError(f"{shot.id}: blender shot requires blend_task")
    data = load_json(task_path)
    output = Path(data.get("output", ""))
    if not output:
        raise ContractError(f"{shot.id}: blender task has no output")
    if not output.is_absolute():
        output = paths.workspace / output
    return output


def resolve_annotations(
    specs,
    page_starts: list[float],
    budgets: list[float],
    total_duration: float,
    colormaps: dict | None = None,
) -> list[Annotation]:
    annotations: list[Annotation] = []
    for spec in specs:
        if spec.slide > len(budgets):
            raise ContractError(f"{spec.id}: slide {spec.slide} exceeds {len(budgets)}")
        start = page_starts[spec.slide - 1] + spec.cue_seconds
        page_end = page_starts[spec.slide - 1] + budgets[spec.slide - 1]
        end = start + spec.duration_s
        if end > page_end + 0.05:
            raise ContractError(
                f"{spec.id}: annotation {start:.3f}+{spec.duration_s:.3f}s "
                f"exceeds page {spec.slide} end {page_end:.3f}s"
            )
        if end > total_duration + 0.05:
            raise ContractError(
                f"{spec.id}: annotation ends at {end:.3f}s "
                f"beyond timeline {total_duration:.3f}s"
            )
        common = {
            "id": spec.id,
            "start_s": round(start, 3),
            "duration_s": round(spec.duration_s, 3),
            "position": spec.position,
        }
        if spec.kind == "text":
            annotations.append(
                TextAnnotation(
                    kind="text",
                    text=spec.text,
                    size=spec.size,
                    align=spec.align,
                    color=spec.color,
                    background=spec.background,
                    **common,
                )
            )
            continue
        definition = (colormaps or {}).get(spec.colormap)
        if definition is None:
            raise ContractError(
                f"{spec.id}: unknown colormap {spec.colormap!r}; "
                f"available: {sorted(colormaps or {})}"
            )
        annotations.append(
            LegendAnnotation(
                kind="legend",
                colormap=spec.colormap,
                min_value=spec.min_value,
                max_value=spec.max_value,
                units=spec.units,
                stops=[
                    (position, tuple(color)) for position, color in definition["stops"]
                ],
                bar_height=spec.bar_height,
                bar_width=spec.bar_width,
                label_size=spec.label_size,
                **common,
            )
        )
    return annotations


def _relative_to_build(paths: LessonPaths, path: Path) -> str:
    try:
        return path.resolve().relative_to(paths.build_root.resolve()).as_posix()
    except ValueError as exc:
        raise ContractError(f"path is outside build/{paths.slug}: {path}") from exc


def _page_timing(
    paths: LessonPaths, notes_text: str
) -> tuple[list[float], list[float], str, list[dict]]:
    """Resolve page durations from exactly one authority.

    ``measured`` reads the narration metadata written by ``narration-build``;
    otherwise ``lecture_notes.md`` budgets remain the planned authority.
    """
    planned = page_budgets(notes_text)
    timing = paths.lesson.narration.timing
    if timing != "measured":
        starts: list[float] = []
        cursor = 0.0
        pages: list[dict] = []
        for index, budget in enumerate(planned):
            starts.append(cursor)
            pages.append(
                {
                    "slide": index + 1,
                    "start_s": round(cursor, 3),
                    "duration_s": round(budget, 3),
                    "planned_s": round(budget, 3),
                    "drift_s": 0.0,
                }
            )
            cursor += budget
        return planned, starts, "planned", pages

    meta_path = paths.build_root / "narration" / "narration.meta.json"
    if not meta_path.is_file():
        raise ContractError(
            f"narration.timing=measured but metadata not found: {meta_path}"
        )
    meta = load_json(meta_path)
    meta_pages = meta.get("pages") or []
    if len(meta_pages) != len(planned):
        raise ContractError(
            f"narration.meta.json has {len(meta_pages)} pages but notes has {len(planned)}"
        )
    measured: list[float] = []
    starts = []
    pages = []
    cursor = 0.0
    for index, entry in enumerate(meta_pages):
        duration = entry.get("measured_s")
        if duration is None and entry.get("start_s") is not None and entry.get("end_s") is not None:
            duration = float(entry["end_s"]) - float(entry["start_s"])
        try:
            value = float(duration)
        except (TypeError, ValueError) as exc:
            raise ContractError(f"page {index + 1}: measured_s is missing") from exc
        if value <= 0:
            raise ContractError(f"page {index + 1}: measured_s must be positive")
        measured.append(value)
        starts.append(cursor)
        pages.append(
            {
                "slide": index + 1,
                "start_s": round(cursor, 3),
                "duration_s": round(value, 3),
                "planned_s": round(planned[index], 3),
                "drift_s": round(value - planned[index], 3),
            }
        )
        cursor += value
    return measured, starts, "measured", pages


def _write_page_plan(
    paths: LessonPaths,
    timing: str,
    pages: list[dict],
    total: float,
) -> Path | None:
    policy = resolve(paths.lesson)
    if policy is None:
        return None
    problem = window_problem(total, policy) if timing == "measured" else None
    if problem is not None:
        raise ContractError(f"DURATION_WINDOW: {problem.message}")
    target = paths.build_root / "timeline" / "page-plan.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "lesson": paths.slug,
                "timing": timing,
                "fps": paths.lesson.outputs.fps,
                "pages": pages,
                "total_s": round(total, 3),
                "duration": {
                    **policy.as_dict(),
                    "pass": True,
                    "problem": None,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def collect(paths: LessonPaths) -> tuple[ShotsFile, list[str], list[Path]]:
    notes_path = paths.content_path(paths.lesson.content.notes)
    notes_text = notes_path.read_text(encoding="utf-8")
    budgets, page_starts, timing, page_plan_pages = _page_timing(paths, notes_text)

    warnings: list[str] = []
    shots: list[Shot] = []
    outputs: list[Path] = []
    skip_overlays = False
    fps = paths.lesson.outputs.fps
    resolution = paths.lesson.outputs.resolution

    if paths.lesson.compose.mode == "scene":
        manifest_path = paths.build_root / "scenes" / "manifest.json"
        manifest = load_json(manifest_path)
        pages = manifest.get("pages", [])
        if len(pages) < len(budgets):
            raise ContractError(
                f"scene manifest has {len(pages)} pages but notes has {len(budgets)}"
            )
        total_duration = sum(budgets)
        base_file = manifest.get("base_file")
        if base_file:
            # A single base video already carries the whole course animation.
            # Storyboard shots are authoring metadata, not overlays to stack on
            # top of it.
            skip_overlays = True
            shots.append(
                Shot(
                    id="scene_base",
                    kind="animation",
                    source=str(base_file),
                    start_s=0.0,
                    duration_s=round(total_duration, 3),
                    timeline_role="base",
                    presentation=None,
                )
            )
        else:
            for index, budget in enumerate(budgets):
                entry = pages[index]
                shots.append(
                    Shot(
                        id=f"scene_{index + 1:03d}",
                        kind="animation",
                        slide=index + 1,
                        source=str(entry["file"]),
                        start_s=round(page_starts[index], 3),
                        duration_s=round(budget, 3),
                        timeline_role="base",
                        presentation=None,
                    )
                )
    elif paths.lesson.compose.mode == "deck":
        manifest_path = paths.build_root / "slides" / "capture-manifest.json"
        manifest = load_json(manifest_path)
        pages = manifest.get("pages", [])
        if len(pages) < len(budgets):
            raise ContractError(
                f"capture manifest has {len(pages)} pages but notes has {len(budgets)}"
            )
        for index, budget in enumerate(budgets):
            file_name = pages[index]["file"]
            shots.append(
                Shot(
                    id=f"slide_{index + 1:03d}",
                    kind="slide",
                    slide=index + 1,
                    source=f"slides/{file_name}",
                    start_s=round(page_starts[index], 3),
                    duration_s=round(budget, 3),
                    timeline_role="base",
                    presentation=None,
                )
            )
        total_duration = sum(budgets)
    else:
        base = paths.base_video_path()
        if base is None or not base.is_file():
            raise ContractError(f"base video not found: {base}")
        info = probe_media(base)
        if info.duration is None:
            raise ContractError(f"cannot read duration of base video: {base}")
        shots.append(
            Shot(
                id="recording_base",
                kind="recording",
                source=_relative_to_build(paths, base),
                start_s=0.0,
                duration_s=round(info.duration, 3),
                timeline_role="base",
                presentation=None,
            )
        )
        total_duration = info.duration

    if paths.lesson.compose.mode in {"deck", "scene"}:
        plan_path = _write_page_plan(paths, timing, page_plan_pages, total_duration)
        if plan_path is not None:
            outputs.append(plan_path)

    overlays_by_slide: dict[int, list[tuple[float, float, str]]] = {}
    for spec in ([] if skip_overlays else paths.storyboard.shots):
        if spec.slide > len(budgets):
            raise ContractError(f"{spec.id}: slide {spec.slide} exceeds {len(budgets)}")
        source = _animation_source(paths, spec)
        if not source.is_file():
            raise ContractError(f"{spec.id}: rendered source not found: {source}")
        info = probe_media(source)
        if info.duration is None:
            raise ContractError(f"{spec.id}: cannot read duration: {source}")
        start = page_starts[spec.slide - 1] + spec.cue_seconds
        page_end = page_starts[spec.slide - 1] + budgets[spec.slide - 1]
        if start + info.duration > page_end + 0.05:
            raise ContractError(
                f"{spec.id}: overlay {start:.3f}+{info.duration:.3f}s exceeds page {spec.slide} end {page_end:.3f}s"
            )
        if spec.expected_duration_s:
            drift = abs(info.duration - spec.expected_duration_s)
            if drift > max(2.0, spec.expected_duration_s * 0.2):
                warnings.append(
                    f"{spec.id}: duration {info.duration:.3f}s differs from expected {spec.expected_duration_s:.3f}s"
                )
        span = (start, start + info.duration, spec.id)
        for other_start, other_end, other_id in overlays_by_slide.get(spec.slide, []):
            if start < other_end - 1e-6 and other_start < start + info.duration - 1e-6:
                raise ContractError(
                    f"{spec.id} overlaps {other_id} on slide {spec.slide}"
                )
        overlays_by_slide.setdefault(spec.slide, []).append(span)
        shots.append(
            Shot(
                id=spec.id,
                kind="animation",
                slide=spec.slide,
                engine=spec.engine,
                source=_relative_to_build(paths, source),
                start_s=round(start, 3),
                duration_s=round(info.duration, 3),
                timeline_role="overlay",
                presentation="cutaway",
            )
        )

    narration = None
    if paths.lesson.narration.enabled:
        if not paths.lesson.narration.source:
            raise ContractError("narration.enabled=true but narration.source is null")
        narration_path = paths.narration_path(paths.lesson.narration.source)
        if not narration_path.is_file():
            raise ContractError(f"narration not found: {narration_path}")
        duration = probe_audio(narration_path)
        narration = {
            "path": _relative_to_build(paths, narration_path),
            "duration_s": round(duration, 3),
        }

    subtitles = None
    if paths.lesson.subtitles.enabled:
        subtitle_path = paths.subtitles_path()
        if subtitle_path is None or not subtitle_path.is_file():
            raise ContractError(f"subtitles enabled but file not found: {subtitle_path}")
        target = paths.build_root / "subtitles.srt"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(subtitle_path, target)
        outputs.append(target)
        subtitles = {"path": "subtitles.srt", "cues": count_srt_cues(target)}
        if paths.lesson.subtitles.render == "burn_in":
            from .subtitles import BilingualDraft, write_ass

            draft_path = paths.build_root / "subtitles" / "bilingual.draft.json"
            if not draft_path.is_file():
                raise ContractError(
                    "subtitles.render=burn_in requires subtitles/bilingual.draft.json"
                )
            draft = BilingualDraft.model_validate(load_json(draft_path))
            ass_path = paths.build_root / "subtitles.ass"
            write_ass(
                [cue.model_dump(mode="json") for cue in draft.cues],
                ass_path,
                resolution[0],
                resolution[1],
            )
            outputs.append(ass_path)
            subtitles.update(
                {
                    "ass": "subtitles.ass",
                    "render": "burn_in",
                    "languages": draft.languages,
                }
            )

    colormaps = None
    if any(spec.kind == "legend" for spec in paths.storyboard.annotations):
        colormaps = load_colormaps(paths.workspace)
    annotations = resolve_annotations(
        paths.storyboard.annotations,
        page_starts,
        budgets,
        total_duration,
        colormaps,
    )

    shots_file = ShotsFile(
        lesson=paths.slug,
        generated_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        timeline=Timeline(
            fps=fps,
            resolution=resolution,
            total_duration_s=round(total_duration, 3),
        ),
        shots=shots,
        annotations=annotations,
        narration=narration,
        subtitles=subtitles,
    )

    output_path = paths.build_root / "shots.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(shots_file.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    outputs.append(output_path)

    # V1-E compatibility view: write the integer-frame TimelineSpec alongside
    # shots.json. The old file remains the Remotion input until the cutover.
    from .v1_timeline import write_timeline_contract

    v1_path, _timeline = write_timeline_contract(shots_file, paths)
    outputs.append(v1_path)
    return shots_file, warnings, outputs
