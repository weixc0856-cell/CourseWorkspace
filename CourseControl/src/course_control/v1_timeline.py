"""V1-E: normalize ``shots.json`` to ``TimelineSpec`` and back.

The existing course pipeline still produces ``shots.json`` in seconds because
Remotion consumes it. This module is the compatibility bridge:

* ``timeline_from_shots`` turns the legacy file into the integer-frame V1
  contract (the single timing fact for new adapters).
* ``shots_from_timeline`` regenerates the legacy file from a V1 timeline, so a
  future cutover can make V1 authoritative without rewriting Remotion.

Fields that V1 does not model yet (2D annotations, the exact legacy kind) are
carried in ``TimelineSpec.metadata`` and ``TimelineVideo.metadata``. They are
explicitly transitional; timing and assets remain authoritative in V1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import TypeAdapter

from .contracts import (
    Annotation,
    MotionPolicy,
    LegendAnnotation,
    Shot,
    ShotsFile,
    TextAnnotation,
    Timeline,
)
from .contracts_v1 import (
    RationalFPS,
    SubtitleCue,
    TimelineAudio,
    TimelineSpec,
    TimelineVideo,
)
from .motion import slide_motion
from .legacy_e6 import LegacyE6Error, asset_ref, parse_srt, seconds_to_ms
from .paths import ContractError, LessonPaths
from .timecode import frame_to_ms, ms_to_frame

ANNOTATION = TypeAdapter(Annotation)

TRACK_BY_ENGINE = {
    "motion_canvas": "motion_canvas",
    "manim": "manim",
    "blender": "blender",
}


class V1TimelineError(ContractError):
    """The legacy timeline cannot be represented as V1 (or vice versa)."""


def _frames(start_s: float, duration_s: float, fps_num: int, fps_den: int) -> tuple[int, int]:
    start_ms = seconds_to_ms(start_s)
    end_ms = seconds_to_ms(start_s + duration_s)
    start = ms_to_frame(start_ms, fps_num, fps_den)
    end = ms_to_frame(end_ms, fps_num, fps_den)
    if end <= start:
        raise V1TimelineError(
            f"segment {start_s:.3f}+{duration_s:.3f}s is shorter than one frame"
        )
    return start, end - start


def _shot_track(shot: Shot) -> str | None:
    if shot.kind == "slide":
        return "slide"
    if shot.kind == "recording":
        return "recording"
    return TRACK_BY_ENGINE.get(shot.engine or "")


def _asset_for(shot: Shot, workspace: Path, build_root: Path):
    path = build_root / shot.source
    if shot.kind == "slide":
        return asset_ref(path, workspace, "image", "captured")
    return asset_ref(path, workspace, "video", "rendered")


def timeline_from_shots(
    shots: ShotsFile,
    workspace: Path,
    build_root: Path,
    *,
    lesson_id: str | None = None,
    motion: MotionPolicy | None = None,
) -> TimelineSpec:
    """Build a V1 TimelineSpec from the legacy shots.json object."""
    workspace = workspace.resolve()
    build_root = build_root.resolve()
    lesson = lesson_id or shots.lesson
    fps_num = shots.timeline.fps
    fps_den = 1
    fps = RationalFPS(fps_num=fps_num, fps_den=fps_den)

    videos: list[TimelineVideo] = []
    for shot in shots.shots:
        start, duration = _frames(shot.start_s, shot.duration_s, fps_num, fps_den)
        metadata: dict = {
            "legacy_kind": shot.kind,
            "legacy_engine": shot.engine,
            "legacy_slide": shot.slide,
            "legacy_presentation": shot.presentation,
        }
        if motion is not None and shot.kind == "slide":
            spec = slide_motion(shot.slide or 0, motion)
            if spec is not None:
                metadata["legacy_motion"] = spec
        videos.append(
            TimelineVideo(
                shot_id=shot.id,
                start_frame=start,
                duration_frames=duration,
                role=shot.timeline_role,
                asset=_asset_for(shot, workspace, build_root),
                track=_shot_track(shot),
                metadata=metadata,
            )
        )

    base_ends = [
        item.start_frame + item.duration_frames
        for item in videos
        if item.role == "base"
    ]
    if not base_ends:
        raise V1TimelineError("legacy timeline has no base shot")
    total_frames = max(base_ends)
    expected = ms_to_frame(seconds_to_ms(shots.timeline.total_duration_s), fps_num, fps_den)
    if abs(expected - total_frames) > 1:
        raise V1TimelineError(
            f"legacy total {shots.timeline.total_duration_s:.3f}s maps to "
            f"{expected} frames, but base shots end at {total_frames}"
        )

    audio: list[TimelineAudio] = []
    if shots.narration:
        relative = str(shots.narration.get("path") or "")
        if not relative:
            raise V1TimelineError("narration entry has no path")
        path = build_root / relative
        duration_ms = seconds_to_ms(float(shots.narration.get("duration_s") or 0))
        duration_frames = ms_to_frame(duration_ms, fps_num, fps_den)
        if duration_frames <= 0:
            raise V1TimelineError("narration duration is shorter than one frame")
        if duration_frames > total_frames:
            raise V1TimelineError(
                f"narration {duration_frames} frames exceeds timeline {total_frames}"
            )
        audio.append(
            TimelineAudio(
                narration_id=f"{lesson}-narration",
                start_frame=0,
                duration_frames=duration_frames,
                asset=asset_ref(path, workspace, "audio", "generated"),
            )
        )

    subtitles: list[SubtitleCue] = []
    if shots.subtitles:
        relative = str(shots.subtitles.get("path") or "")
        if not relative:
            raise V1TimelineError("subtitles entry has no path")
        path = build_root / relative
        try:
            cues = parse_srt(path.read_text(encoding="utf-8"))
        except LegacyE6Error as exc:
            raise V1TimelineError(f"cannot parse {path}: {exc}") from exc
        for cue in cues:
            start = ms_to_frame(cue.start_ms, fps_num, fps_den)
            end = ms_to_frame(cue.end_ms, fps_num, fps_den)
            if end <= start:
                raise V1TimelineError(f"subtitle cue {cue.index} is shorter than one frame")
            if end > total_frames:
                raise V1TimelineError(
                    f"subtitle cue {cue.index} ends at {end}, beyond {total_frames}"
                )
            subtitles.append(
                SubtitleCue(index=cue.index, start_frame=start, end_frame=end, text=cue.text)
            )

    return TimelineSpec(
        lesson_id=lesson,
        fps=fps,
        width=shots.timeline.resolution[0],
        height=shots.timeline.resolution[1],
        total_frames=total_frames,
        video=videos,
        audio=audio,
        subtitles=subtitles,
        metadata={
            "legacy_generated_at": shots.generated_at,
            "legacy_total_duration_s": shots.timeline.total_duration_s,
            "legacy_annotations": [
                annotation.model_dump(mode="json") for annotation in shots.annotations
            ],
        },
    )


def _relative_to_build(workspace: Path, build_root: Path, asset_path: str) -> str:
    path = (workspace / asset_path).resolve()
    try:
        return path.relative_to(build_root).as_posix()
    except ValueError as exc:
        raise V1TimelineError(f"asset is outside {build_root}: {asset_path}") from exc


def _infer_kind(video: TimelineVideo) -> str:
    metadata = video.metadata or {}
    kind = metadata.get("legacy_kind")
    if kind in ("slide", "animation", "recording"):
        return kind
    if video.track == "slide" or video.shot_id.startswith("slide_"):
        return "slide"
    if video.track == "recording" or video.shot_id == "recording_base":
        return "recording"
    return "animation"


def shots_from_timeline(
    timeline: TimelineSpec,
    workspace: Path,
    build_root: Path,
) -> ShotsFile:
    """Regenerate the legacy shots.json object from a V1 TimelineSpec."""
    if timeline.fps.fps_den != 1:
        raise V1TimelineError(
            "legacy shots.json supports integer fps only; "
            f"got {timeline.fps.fps_num}/{timeline.fps.fps_den}"
        )
    workspace = workspace.resolve()
    build_root = build_root.resolve()
    fps_num = timeline.fps.fps_num

    shots: list[Shot] = []
    for video in sorted(
        timeline.video, key=lambda item: (item.role != "base", item.start_frame)
    ):
        metadata = video.metadata or {}
        start_ms = frame_to_ms(video.start_frame, fps_num, timeline.fps.fps_den)
        end_ms = frame_to_ms(
            video.start_frame + video.duration_frames, fps_num, timeline.fps.fps_den
        )
        slide = metadata.get("legacy_slide")
        shots.append(
            Shot(
                id=video.shot_id,
                kind=_infer_kind(video),
                slide=int(slide) if slide is not None else None,
                engine=metadata.get("legacy_engine"),
                source=_relative_to_build(workspace, build_root, video.asset.path),
                start_s=round(start_ms / 1000, 3),
                duration_s=round((end_ms - start_ms) / 1000, 3),
                timeline_role=video.role,
                presentation=metadata.get("legacy_presentation"),
            )
        )

    annotations = [
        ANNOTATION.validate_python(item)
        for item in (timeline.metadata or {}).get("legacy_annotations", [])
    ]

    narration = None
    if timeline.audio:
        if len(timeline.audio) > 1:
            raise V1TimelineError(
                "legacy shots.json supports a single mixed narration track"
            )
        audio = timeline.audio[0]
        narration = {
            "path": _relative_to_build(workspace, build_root, audio.asset.path),
            "duration_s": round(
                frame_to_ms(audio.duration_frames, fps_num, timeline.fps.fps_den) / 1000,
                3,
            ),
        }

    subtitles = None
    if timeline.subtitles:
        target = build_root / "subtitles.srt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(timeline.srt_text(), encoding="utf-8")
        subtitles = {"path": "subtitles.srt", "cues": len(timeline.subtitles)}

    generated_at = (timeline.metadata or {}).get("legacy_generated_at") or (
        datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    )
    total_s = round(
        frame_to_ms(timeline.total_frames, fps_num, timeline.fps.fps_den) / 1000, 3
    )
    return ShotsFile(
        lesson=timeline.lesson_id,
        generated_at=generated_at,
        timeline=Timeline(
            fps=fps_num,
            resolution=(timeline.width, timeline.height),
            total_duration_s=total_s,
        ),
        shots=shots,
        annotations=annotations,
        narration=narration,
        subtitles=subtitles,
    )


def write_timeline_contract(
    shots: ShotsFile,
    paths: LessonPaths,
    *,
    output: Path | None = None,
) -> tuple[Path, TimelineSpec]:
    """Write ``build/<slug>/contracts/timeline.spec.json`` and return it."""
    timeline = timeline_from_shots(
        shots,
        paths.workspace,
        paths.build_root,
        lesson_id=paths.slug,
        motion=getattr(getattr(paths, "lesson", None), "motion", None),
    )
    target = output or (paths.build_root / "contracts" / "timeline.spec.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        timeline.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return target, timeline


__all__ = [
    "V1TimelineError",
    "shots_from_timeline",
    "timeline_from_shots",
    "write_timeline_contract",
]
