from __future__ import annotations

from pathlib import Path

from .contracts import CheckRecord, ShotsFile, Status
from .paths import LessonPaths, path_problem
from .utils import page_budgets, probe_media


def _check(check_id: str, ok: bool, expected: str, actual: str, detail: str | None = None) -> CheckRecord:
    return CheckRecord(
        id=check_id,
        status=Status.PASS if ok else Status.FAIL,
        expected=expected,
        actual=actual,
        detail=detail,
    )


def verify(paths: LessonPaths, shots_file: ShotsFile) -> list[CheckRecord]:
    checks: list[CheckRecord] = []
    build_root = paths.build_root
    final = build_root / "final" / "course-video.mp4"
    fps = shots_file.timeline.fps
    width, height = shots_file.timeline.resolution

    missing = []
    probes = {}
    for shot in shots_file.shots:
        source = (build_root / shot.source).resolve()
        if not source.is_file():
            missing.append(shot.source)
            continue
        try:
            probes[shot.source] = probe_media(source)
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{shot.source} ({exc})")
    checks.append(
        _check(
            "V-10",
            not missing,
            "all shot sources exist and are readable",
            "ok" if not missing else ", ".join(missing),
        )
    )

    bad_media = []
    for shot in shots_file.shots:
        info = probes.get(shot.source)
        if info is None:
            continue
        if shot.kind in ("animation", "recording"):
            if info.width != width or info.height != height:
                bad_media.append(
                    f"{shot.id}: {info.width}x{info.height} != {width}x{height}"
                )
            if info.fps is not None and abs(info.fps - fps) > 0.01:
                bad_media.append(f"{shot.id}: {info.fps:.3f} fps != {fps}")
    checks.append(
        _check(
            "V-12",
            not bad_media,
            f"{width}x{height} @ {fps} fps",
            "ok" if not bad_media else "; ".join(bad_media),
        )
    )

    base = sorted(
        [shot for shot in shots_file.shots if shot.timeline_role == "base"],
        key=lambda item: item.start_s,
    )
    timeline_errors: list[str] = []
    cursor = 0.0
    for shot in base:
        if abs(shot.start_s - cursor) > 0.01:
            timeline_errors.append(f"{shot.id} starts at {shot.start_s}, expected {cursor}")
        cursor = shot.start_s + shot.duration_s
    if abs(cursor - shots_file.timeline.total_duration_s) > 0.01:
        timeline_errors.append(
            f"base ends at {cursor:.3f}, timeline says {shots_file.timeline.total_duration_s:.3f}"
        )
    overlays = [shot for shot in shots_file.shots if shot.timeline_role == "overlay"]
    for overlay in overlays:
        parent = next(
            (
                item
                for item in base
                if item.kind == "recording"
                and item.start_s - 1e-6 <= overlay.start_s
                and overlay.start_s + overlay.duration_s <= item.start_s + item.duration_s + 1e-6
            ),
            None,
        )
        if parent is None:
            parent = next(
                (
                    item
                    for item in base
                    if item.slide == overlay.slide
                    and item.start_s - 1e-6 <= overlay.start_s
                    and overlay.start_s + overlay.duration_s <= item.start_s + item.duration_s + 1e-6
                ),
                None,
            )
        if parent is None:
            timeline_errors.append(f"{overlay.id} is not inside a base segment")
    for index, first in enumerate(overlays):
        for second in overlays[index + 1:]:
            if first.start_s < second.start_s + second.duration_s - 1e-6 and second.start_s < first.start_s + first.duration_s - 1e-6:
                timeline_errors.append(f"{first.id} overlaps {second.id}")
    checks.append(
        _check(
            "V-13",
            not timeline_errors,
            "base segments are contiguous; overlays fit and do not overlap",
            "ok" if not timeline_errors else "; ".join(timeline_errors),
        )
    )

    outside = [
        shot.source
        for shot in shots_file.shots
        if Path(shot.source).is_absolute() or ".." in Path(shot.source).parts
    ]
    checks.append(
        _check(
            "V-18",
            not outside,
            "all shot sources are relative to build/<lesson>/",
            "ok" if not outside else ", ".join(outside),
        )
    )

    path_issues: list[str] = []
    declared = [shot.source for shot in shots_file.shots]
    if shots_file.narration and shots_file.narration.get("path"):
        declared.append(str(shots_file.narration["path"]))
    if shots_file.subtitles and shots_file.subtitles.get("path"):
        declared.append(str(shots_file.subtitles["path"]))
    for value in declared:
        problem = path_problem(value)
        if problem:
            path_issues.append(f"{value}: {problem}")
    checks.append(
        _check(
            "V-21",
            not path_issues,
            "all declared paths are relative, / separated, without ..",
            "ok" if not path_issues else "; ".join(path_issues),
        )
    )

    if not final.is_file():
        checks.append(
            CheckRecord(
                id="V-14",
                status=Status.NOT_RUN,
                expected="final video exists",
                actual="missing",
                detail=str(final),
            )
        )
        return checks

    try:
        final_info = probe_media(final)
    except Exception as exc:  # noqa: BLE001
        checks.append(
            CheckRecord(
                id="V-14",
                status=Status.FAIL,
                expected="readable final video",
                actual="probe failed",
                detail=str(exc),
            )
        )
        return checks
    expected_duration = paths.lesson.acceptance.notes_total_seconds
    if expected_duration is None:
        if shots_file.timeline.total_duration_s:
            expected_duration = shots_file.timeline.total_duration_s
    tolerance = paths.lesson.acceptance.duration_tolerance_seconds
    duration_ok = (
        expected_duration is None
        or abs((final_info.duration or 0.0) - expected_duration) <= tolerance
    )
    checks.append(
        _check(
            "V-14",
            duration_ok,
            f"{expected_duration} ± {tolerance}s" if expected_duration is not None else "not applicable",
            f"{final_info.duration:.3f}s" if final_info.duration is not None else "unknown",
        )
    )

    if paths.lesson.narration.enabled:
        audio_ok = final_info.has_audio and abs(
            (final_info.audio_duration or 0.0) - (final_info.duration or 0.0)
        ) <= 0.5
        checks.append(
            _check(
                "V-15",
                audio_ok,
                "audio stream present; audio/video duration delta <= 0.5s",
                f"audio={final_info.has_audio}, delta={(final_info.audio_duration or 0) - (final_info.duration or 0):.3f}s",
            )
        )
    else:
        checks.append(
            CheckRecord(id="V-15", status=Status.NOT_APPLICABLE, detail="narration disabled")
        )

    if paths.lesson.subtitles.enabled:
        subtitles = shots_file.subtitles or {}
        subtitle_path = build_root / str(subtitles.get("path", ""))
        cues = int(subtitles.get("cues", 0))
        checks.append(
            _check(
                "V-16",
                subtitle_path.is_file() and cues > 0,
                "subtitle file exists and has cues",
                f"file={subtitle_path.is_file()}, cues={cues}",
            )
        )
    else:
        checks.append(
            CheckRecord(id="V-16", status=Status.NOT_APPLICABLE, detail="subtitles disabled")
        )

    if paths.lesson.compose.mode == "recording":
        notes_path = paths.content_path(paths.lesson.content.notes)
        notes_total = sum(page_budgets(notes_path.read_text(encoding="utf-8")))
        base = next((shot for shot in shots_file.shots if shot.kind == "recording"), None)
        actual = base.duration_s if base else 0.0
        checks.append(
            _check(
                "V-20",
                abs(actual - notes_total) <= tolerance,
                f"recording duration {notes_total:.3f} ± {tolerance}s",
                f"{actual:.3f}s",
            )
        )
    else:
        checks.append(
            CheckRecord(id="V-20", status=Status.NOT_APPLICABLE, detail="deck mode")
        )

    annotations = shots_file.annotations
    if annotations:
        annotation_errors = []
        total = shots_file.timeline.total_duration_s
        for annotation in annotations:
            if annotation.kind == "text":
                if not annotation.text.strip():
                    annotation_errors.append(f"{annotation.id}: blank text")
            else:
                if annotation.max_value <= annotation.min_value:
                    annotation_errors.append(f"{annotation.id}: invalid legend range")
                if not annotation.stops:
                    annotation_errors.append(f"{annotation.id}: empty colormap stops")
                if not annotation.units.strip():
                    annotation_errors.append(f"{annotation.id}: blank legend units")
            if annotation.start_s + annotation.duration_s > total + 0.01:
                annotation_errors.append(f"{annotation.id}: ends after timeline")
            if any(
                component < 0.0 or component > 1.0 for component in annotation.position
            ):
                annotation_errors.append(f"{annotation.id}: position outside 0..1")
        checks.append(
            _check(
                "V-22",
                not annotation_errors,
                "annotations fit timeline; text and position valid",
                "ok" if not annotation_errors else "; ".join(annotation_errors),
            )
        )
    else:
        checks.append(
            CheckRecord(id="V-22", status=Status.NOT_APPLICABLE, detail="no annotations")
        )

    return checks
