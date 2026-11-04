from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .contracts import Annotation, Shot, ShotsFile, Timeline
from .paths import ContractError, LessonPaths
from .utils import count_srt_cues, load_json, page_budgets, probe_audio, probe_media


def _scene_stem(paths: LessonPaths, shot) -> str:
    scene_path, _ = paths.scene_path(shot)
    return scene_path.stem


def _animation_source(paths: LessonPaths, shot) -> Path:
    if shot.engine in ("motion_canvas", "manim"):
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
        annotations.append(
            Annotation(
                id=spec.id,
                kind=spec.kind,
                text=spec.text,
                start_s=round(start, 3),
                duration_s=round(spec.duration_s, 3),
                position=spec.position,
                size=spec.size,
                align=spec.align,
                color=spec.color,
                background=spec.background,
            )
        )
    return annotations


def _relative_to_build(paths: LessonPaths, path: Path) -> str:
    try:
        return path.resolve().relative_to(paths.build_root.resolve()).as_posix()
    except ValueError as exc:
        raise ContractError(f"path is outside build/{paths.slug}: {path}") from exc


def collect(paths: LessonPaths) -> tuple[ShotsFile, list[str], list[Path]]:
    notes_path = paths.content_path(paths.lesson.content.notes)
    budgets = page_budgets(notes_path.read_text(encoding="utf-8"))
    page_starts: list[float] = []
    cursor = 0.0
    for budget in budgets:
        page_starts.append(cursor)
        cursor += budget

    warnings: list[str] = []
    shots: list[Shot] = []
    outputs: list[Path] = []
    fps = paths.lesson.outputs.fps
    resolution = paths.lesson.outputs.resolution

    if paths.lesson.compose.mode == "deck":
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
        total_duration = cursor
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

    overlays_by_slide: dict[int, list[tuple[float, float, str]]] = {}
    for spec in paths.storyboard.shots:
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

    annotations = resolve_annotations(
        paths.storyboard.annotations, page_starts, budgets, total_duration
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
    return shots_file, warnings, outputs
