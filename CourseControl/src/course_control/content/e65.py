"""Generate V1 contracts for the standalone E6.5 Multi-Head track.

E6.5 has no author lesson.yaml/storyboard, but it does have real per-beat
narration segments. This adapter therefore emits NarrationSpec, TimelineSpec,
ShotSpec files and a RenderManifest with ``lesson_spec=None``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml

from pydantic import Field, ValidationError

from course_control.content.contracts import StrictModel
from course_control.content.contracts_v1 import (
    AssetRef,
    NarrationGenerator,
    NarrationSegment,
    NarrationSpec,
    NarrationTotal,
    NarrationVoice,
    RationalFPS,
    RenderCheck,
    RenderManifest,
    RenderNarration,
    RenderNarrationSegment,
    RenderOutput,
    RenderShot,
    RenderSource,
    RenderSubtitles,
    ShotSpecV1,
    SubtitleCue,
    TimelineAudio,
    TimelineSpec,
    TimelineVideo,
)
from course_control.platform.media import (
    MediaError,
    asset_ref,
    ffprobe_version,
    probe_media,
    seconds_to_ms,
)
from course_control.voice.srt import parse_srt_strict as parse_srt
from course_control.content.timecode import frame_to_ms, ms_to_frame

BEATS = ("b1", "b2", "b3", "b4", "b5")
LESSON = "e65-multi-head"
SCENE_FILE = "ManimSandbox/05-multi-head/multi_head.py"
TEXT_DIR = Path("ManimSandbox/05-multi-head/narration")


class E65Error(RuntimeError):
    pass


class E65Check(StrictModel):
    status: Literal["pass", "fail"]
    detail: str = ""


class E65Segment(StrictModel):
    beat: str
    file: str
    start_s: float = Field(ge=0)
    duration_s: float = Field(gt=0)
    sha256: str


class E65Narration(StrictModel):
    file: str
    duration_s: float = Field(gt=0)
    sha256: str
    segments: list[E65Segment] = Field(min_length=1)


class E65Subtitles(StrictModel):
    file: str
    sha256: str
    cues: int = Field(ge=1)


class E65Video(StrictModel):
    file: str
    duration_s: float = Field(gt=0)
    sha256: str


class E65Shot(StrictModel):
    id: str
    scene: str
    file: str
    duration_s: float = Field(gt=0)
    sha256: str


class E65Manifest(StrictModel):
    schema_version: Literal[1]
    lesson: str
    resolution: tuple[int, int]
    fps: int = Field(gt=0)
    beats: dict[str, float]
    shots: list[E65Shot] = Field(min_length=1)
    narration: E65Narration
    subtitles: E65Subtitles
    video: E65Video
    checks: dict[str, E65Check]
    all_ok: bool


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _path(base: Path, relative: str) -> Path:
    path = (base / relative).resolve()
    if not path.is_file():
        raise E65Error(f"file not found: {path}")
    return path


def _load(path: Path) -> E65Manifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise E65Error(f"cannot read E6.5 manifest {path}: {exc}") from exc
    try:
        return E65Manifest.model_validate(payload)
    except ValidationError as exc:
        raise E65Error(f"E6.5 manifest does not match its contract: {exc}") from exc


def _beat_frames(manifest: E65Manifest, total_frames: int) -> list[tuple[str, int, int]]:
    starts = []
    for beat in BEATS:
        key = f"{beat}_start"
        if key not in manifest.beats:
            raise E65Error(f"missing beat mark: {key}")
        starts.append(ms_to_frame(seconds_to_ms(manifest.beats[key]), manifest.fps, 1))
    starts.append(total_frames)
    result = []
    for index, beat in enumerate(BEATS):
        start = starts[index]
        end = starts[index + 1]
        if end <= start:
            raise E65Error(f"beat {beat} has no frames")
        result.append((beat, start, end))
    return result


def _default_voice(workspace: Path) -> Path:
    """Resolve the reference voice from local config; never hard-code a machine path."""
    config_path = workspace / "config" / "local-paths.yaml"
    if config_path.is_file():
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        value = (data.get("tts") or {}).get("voice_ref")
        if value:
            path = Path(value)
            return path if path.is_absolute() else (workspace / path)
    raise E65Error(
        "voice reference not provided; pass --voice-ref or set tts.voice_ref "
        "in config/local-paths.yaml"
    )


def adapt_e65(
    manifest_path: Path,
    workspace: Path | None = None,
    *,
    voice_ref: Path | None = None,
    run_id: str | None = None,
    now: datetime | None = None,
    output_dir: Path | None = None,
) -> dict:
    manifest_path = manifest_path.resolve()
    workspace = (workspace or Path.cwd()).resolve()
    base = manifest_path.parent
    output_dir = (output_dir or (base / "contracts")).resolve()
    manifest = _load(manifest_path)
    voice_ref = (voice_ref or _default_voice(workspace)).resolve()
    if not voice_ref.is_file():
        raise E65Error(f"voice reference not found: {voice_ref}")

    video_probe = probe_media(_path(workspace, manifest.video.file))
    video_stream = video_probe.first("video")
    if video_stream is None or not video_stream.nb_frames:
        raise E65Error("final video has no frame count")
    total_frames = video_stream.nb_frames
    if total_frames <= 0:
        raise E65Error("final video has no frames")
    fps = RationalFPS(fps_num=manifest.fps, fps_den=1)
    beats = _beat_frames(manifest, total_frames)
    visual_path = _path(workspace, manifest.shots[0].file)
    visual_ref = asset_ref(visual_path, workspace, "video")
    final_ref = asset_ref(_path(workspace, manifest.video.file), workspace, "video")
    narration_ref = asset_ref(_path(workspace, manifest.narration.file), workspace, "audio")
    subtitles_path = _path(workspace, manifest.subtitles.file)
    subtitles_ref = asset_ref(subtitles_path, workspace, "subtitle")
    voice_ref_asset = asset_ref(voice_ref, workspace, "audio")

    segments: list[NarrationSegment] = []
    render_segments: list[RenderNarrationSegment] = []
    timeline_audio: list[TimelineAudio] = []
    shots: list[ShotSpecV1] = []
    render_shots: list[RenderShot] = []
    for beat, start_frame, end_frame in beats:
        segment = next((item for item in manifest.narration.segments if item.beat == beat), None)
        if segment is None:
            raise E65Error(f"missing narration segment for {beat}")
        duration_ms = seconds_to_ms(segment.duration_s)
        start_ms = seconds_to_ms(segment.start_s)
        segment_start = ms_to_frame(start_ms, manifest.fps, 1)
        segment_frames = ms_to_frame(duration_ms, manifest.fps, 1)
        text_path = workspace / TEXT_DIR / f"{beat}.txt"
        if not text_path.is_file():
            raise E65Error(f"missing narration text: {text_path}")
        text = text_path.read_text(encoding="utf-8").strip()
        audio_path = _path(workspace, segment.file)
        audio_ref = asset_ref(audio_path, workspace, "audio")
        narration_id = f"e65-{beat}"
        segments.append(
            NarrationSegment(
                narration_id=narration_id,
                shot_id=beat,
                text=text,
                text_sha256=_sha(text),
                audio=audio_ref,
                duration_ms=duration_ms,
                start_frame=segment_start,
                duration_frames=segment_frames,
                fit="ok",
            )
        )
        render_segments.append(
            RenderNarrationSegment(
                narration_id=narration_id,
                start_frame=segment_start,
                duration_frames=segment_frames,
                duration_ms=duration_ms,
            )
        )
        timeline_audio.append(
            TimelineAudio(
                narration_id=narration_id,
                start_frame=segment_start,
                duration_frames=segment_frames,
                asset=audio_ref,
            )
        )
        timing = {"start_frame": start_frame, "duration_frames": end_frame - start_frame}
        shots.append(
            ShotSpecV1(
                lesson_id=LESSON,
                shot_id=beat,
                track="manim",
                source={
                    "kind": "manim",
                    "file": SCENE_FILE,
                    "class": "MultiHeadScene",
                },
                timing=timing,
                narration_id=narration_id,
                asset=visual_ref,
            )
        )
        render_shots.append(
            RenderShot(
                shot_id=beat,
                track="manim",
                start_frame=start_frame,
                duration_frames=end_frame - start_frame,
                asset=visual_ref,
            )
        )

    narration_spec = NarrationSpec(
        lesson_id=LESSON,
        fps=fps,
        voice=NarrationVoice(
            provider="voxcpm2",
            ref_audio=voice_ref_asset,
            language="zh",
            speed=1.0,
        ),
        segments=segments,
        total=NarrationTotal(
            duration_ms=frame_to_ms(total_frames, manifest.fps, 1),
            total_frames=total_frames,
        ),
        generator=NarrationGenerator(
            name="course-control-e65",
            version="1",
            generated_at=(now or datetime.now(timezone.utc)).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z"),
        ),
    )

    cues = parse_srt(subtitles_path.read_text(encoding="utf-8"))
    subtitle_cues = []
    for cue in cues:
        start = ms_to_frame(cue.start_ms, manifest.fps, 1)
        end = ms_to_frame(cue.end_ms, manifest.fps, 1)
        subtitle_cues.append(
            SubtitleCue(
                index=cue.index,
                start_frame=start,
                end_frame=end,
                text=cue.text,
            )
        )

    timeline = TimelineSpec(
        lesson_id=LESSON,
        fps=fps,
        width=manifest.resolution[0],
        height=manifest.resolution[1],
        total_frames=total_frames,
        video=[
            TimelineVideo(
                shot_id=beat,
                start_frame=start,
                duration_frames=end - start,
                asset=visual_ref,
            )
            for beat, start, end in beats
        ],
        audio=timeline_audio,
        subtitles=subtitle_cues,
    )

    checks = [
        RenderCheck(id=check_id, status=value.status, detail=value.detail)
        for check_id, value in manifest.checks.items()
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    narration_path = output_dir / "narration.spec.json"
    timeline_path = output_dir / "timeline.spec.json"
    narration_path.write_text(
        narration_spec.model_dump_json(indent=2) + chr(10), encoding="utf-8"
    )
    timeline_path.write_text(
        timeline.model_dump_json(indent=2) + chr(10), encoding="utf-8"
    )
    shot_paths = []
    for shot in shots:
        shot_path = output_dir / f"shot-{shot.shot_id}.spec.json"
        shot_path.write_text(
            shot.model_dump_json(indent=2) + chr(10), encoding="utf-8"
        )
        shot_paths.append(shot_path)
    narration_contract_ref = asset_ref(narration_path, workspace, "json", origin="generated")
    timeline_contract_ref = asset_ref(timeline_path, workspace, "json", origin="generated")

    now = now or datetime.now(timezone.utc)
    manifest_ref = asset_ref(manifest_path, workspace, "json", origin="author")
    run_id = run_id or (
        now.strftime("%Y%m%dT%H%M%SZ") + "-" + manifest_ref.sha256[:8]
    )
    render = RenderManifest(
        lesson_id=LESSON,
        render_id=f"{LESSON}-{run_id}",
        run_id=run_id,
        created_at=now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        source=RenderSource(
            lesson_spec=None,
            timeline=timeline_contract_ref,
            narration=narration_contract_ref,
        ),
        output=RenderOutput(
            fps=fps,
            width=manifest.resolution[0],
            height=manifest.resolution[1],
            total_frames=total_frames,
            duration_ms=frame_to_ms(total_frames, manifest.fps, 1),
        ),
        shots=render_shots,
        narration=RenderNarration(
            asset=narration_ref,
            duration_ms=seconds_to_ms(manifest.narration.duration_s),
            segments=render_segments,
        ),
        subtitles=RenderSubtitles(
            asset=subtitles_ref,
            format="srt",
            cues=len(cues),
        ),
        video=final_ref,
        checks=checks,
        tool_versions={"ffprobe": ffprobe_version()},
        legacy={
            "e65_manifest": manifest_ref.model_dump(),
            "checks_are_automatic": True,
            "note": "standalone E6.5 track; no lesson.yaml/storyboard",
        },
    )
    render_path = output_dir / "render.manifest.json"
    render_path.write_text(
        render.model_dump_json(indent=2) + chr(10), encoding="utf-8"
    )
    return {
        "manifest": render,
        "narration": narration_spec,
        "timeline": timeline,
        "shots": shots,
        "paths": {
            "narration": narration_path,
            "timeline": timeline_path,
            "shots": shot_paths,
            "render": render_path,
        },
        "sources": {
            "visual": visual_ref,
            "final": final_ref,
            "subtitles": subtitles_ref,
        },
    }
