"""Read-only adapter from the E6 V0 manifest to normalized RenderManifest V1.

The adapter never writes to the V0 manifest or to E6 media.  It hashes and
probes the files that already exist, converts legacy seconds to integer
frames once, and records every check it can actually perform.  The V0
``checks`` object is preserved as untrusted metadata only; it is never copied
into V1 check results.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Callable, Literal

from pydantic import Field, ValidationError, field_validator

from .contracts import StrictModel
from .contracts_v1 import (
    AssetRef,
    RationalFPS,
    RenderCheck,
    RenderManifest,
    RenderNarration,
    RenderNarrationSegment,
    RenderOutput,
    RenderShot,
    RenderSubtitles,
)
from .paths import path_problem
from .timecode import TimecodeError, frame_to_ms, ms_to_frame, parse_srt_timestamp

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class LegacyE6Error(RuntimeError):
    """Raised when the V0 manifest or its media cannot be read safely."""


class LegacyHashed(StrictModel):
    sha256: str

    @field_validator("sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not SHA256_RE.match(value):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        return value


class LegacyShot(LegacyHashed):
    id: str
    scene: str
    file: str
    duration_s: float = Field(gt=0)


class LegacyNarrationSegment(StrictModel):
    id: str
    duration_s: float = Field(ge=0)


class LegacyNarration(LegacyHashed):
    file: str
    duration_s: float = Field(gt=0)
    segments: list[LegacyNarrationSegment] = Field(min_length=1)


class LegacySubtitles(LegacyHashed):
    file: str


class LegacyVideo(LegacyHashed):
    file: str
    duration_s: float = Field(gt=0)


class LegacyManifest(StrictModel):
    schema_version: Literal[1]
    lesson: str
    resolution: tuple[int, int]
    fps: int = Field(gt=0)
    shots: list[LegacyShot] = Field(min_length=1)
    narration: LegacyNarration
    subtitles: LegacySubtitles
    video: LegacyVideo
    checks: dict[str, str] = Field(default_factory=dict)


@dataclass(frozen=True)
class MediaStream:
    codec_type: str
    codec_name: str | None = None
    width: int | None = None
    height: int | None = None
    r_frame_rate: str | None = None
    avg_frame_rate: str | None = None
    duration_s: float | None = None
    nb_frames: int | None = None
    sample_rate: int | None = None
    channels: int | None = None


@dataclass(frozen=True)
class MediaProbe:
    path: Path
    duration_s: float | None
    size: int | None
    streams: tuple[MediaStream, ...]

    def first(self, codec_type: str) -> MediaStream | None:
        return next((item for item in self.streams if item.codec_type == codec_type), None)


@dataclass(frozen=True)
class SrtCue:
    index: int
    start_ms: int
    end_ms: int
    text: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise LegacyE6Error(f"cannot read {path}: {exc}") from exc
    return digest.hexdigest()


def seconds_to_ms(value: float | int) -> int:
    """Legacy seconds -> integer milliseconds, half up, via Decimal."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LegacyE6Error(f"duration must be a number, got {value!r}")
    if value < 0:
        raise LegacyE6Error(f"duration must be non-negative, got {value!r}")
    return int(
        (Decimal(str(value)) * Decimal(1000)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def _resolve(base: Path, relative: str) -> Path:
    problem = path_problem(relative)
    if problem:
        raise LegacyE6Error(f"invalid manifest path {relative!r}: {problem}")
    return (base / relative).resolve()


def asset_ref(path: Path, workspace: Path, kind: str, origin: str = "rendered") -> AssetRef:
    resolved = path.resolve()
    root = workspace.resolve()
    try:
        relative = resolved.relative_to(root).as_posix()
        origin_value = origin
    except ValueError:
        relative = str(resolved)
        origin_value = "external"
    if not resolved.is_file():
        raise LegacyE6Error(f"asset not found: {resolved}")
    return AssetRef(
        path=relative,
        sha256=sha256_file(resolved),
        bytes=resolved.stat().st_size,
        kind=kind,
        origin=origin_value,
        version=None,
    )


def _optional_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_stream(raw: dict) -> MediaStream:
    return MediaStream(
        codec_type=str(raw.get("codec_type", "")),
        codec_name=raw.get("codec_name"),
        width=_optional_int(raw.get("width")),
        height=_optional_int(raw.get("height")),
        r_frame_rate=raw.get("r_frame_rate"),
        avg_frame_rate=raw.get("avg_frame_rate"),
        duration_s=_optional_float(raw.get("duration")),
        nb_frames=_optional_int(raw.get("nb_frames")),
        sample_rate=_optional_int(raw.get("sample_rate")),
        channels=_optional_int(raw.get("channels")),
    )


def probe_media(path: Path) -> MediaProbe:
    """Run ffprobe and return only the fields the adapter checks."""

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        (
            "format=duration,size:"
            "stream=index,codec_type,codec_name,width,height,"
            "r_frame_rate,avg_frame_rate,duration,nb_frames,sample_rate,channels"
        ),
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LegacyE6Error(f"ffprobe could not run for {path}: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise LegacyE6Error(f"ffprobe failed for {path}: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise LegacyE6Error(f"ffprobe returned invalid JSON for {path}: {exc}") from exc
    fmt = payload.get("format", {})
    return MediaProbe(
        path=path,
        duration_s=_optional_float(fmt.get("duration")),
        size=_optional_int(fmt.get("size")),
        streams=tuple(_parse_stream(raw) for raw in payload.get("streams", [])),
    )


def ffprobe_version() -> str:
    try:
        result = subprocess.run(
            ["ffprobe", "-version"], capture_output=True, text=True, check=False, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    first = (result.stdout or "").splitlines()
    return first[0] if first else "unknown"


def parse_rate(value: str | None) -> tuple[int, int] | None:
    if not value or value == "0/0":
        return None
    match = re.match(r"^(\d+)/(\d+)$", value)
    if not match:
        return None
    num, den = int(match.group(1)), int(match.group(2))
    if num <= 0 or den <= 0:
        return None
    return num, den


def parse_srt(text: str) -> list[SrtCue]:
    """Parse the small SRT subset used by E6, with explicit failures."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise LegacyE6Error("SRT file is empty")
    cues: list[SrtCue] = []
    for block in re.split(r"\n\s*\n", normalized):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            raise LegacyE6Error(f"invalid SRT block: {block!r}")
        try:
            index = int(lines[0])
        except ValueError as exc:
            raise LegacyE6Error(f"invalid SRT cue index: {lines[0]!r}") from exc
        match = re.match(r"^(\S+)\s*-->\s*(\S+)$", lines[1])
        if not match:
            raise LegacyE6Error(f"invalid SRT time line: {lines[1]!r}")
        try:
            start_ms = parse_srt_timestamp(match.group(1))
            end_ms = parse_srt_timestamp(match.group(2))
        except TimecodeError as exc:
            raise LegacyE6Error(f"invalid SRT cue {index}: {exc}") from exc
        if end_ms <= start_ms:
            raise LegacyE6Error(f"SRT cue {index} ends before it starts")
        cues.append(SrtCue(index=index, start_ms=start_ms, end_ms=end_ms, text="\n".join(lines[2:])))
    return cues


@dataclass(frozen=True)
class ShotTiming:
    shot_id: str
    start_frame: int
    duration_frames: int
    duration_ms: int


def build_shot_timings(
    shots: list[LegacyShot], fps_num: int, fps_den: int
) -> tuple[list[ShotTiming], int]:
    """Convert legacy seconds to frames from cumulative milliseconds."""

    timings: list[ShotTiming] = []
    cumulative_ms = 0
    start_frame = 0
    for shot in shots:
        duration_ms = seconds_to_ms(shot.duration_s)
        cumulative_ms += duration_ms
        end_frame = ms_to_frame(cumulative_ms, fps_num, fps_den)
        if end_frame <= start_frame:
            raise LegacyE6Error(
                f"shot {shot.id} is shorter than one frame at {fps_num}/{fps_den}"
            )
        timings.append(
            ShotTiming(
                shot_id=shot.id,
                start_frame=start_frame,
                duration_frames=end_frame - start_frame,
                duration_ms=duration_ms,
            )
        )
        start_frame = end_frame
    return timings, start_frame


def load_manifest(path: Path) -> LegacyManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise LegacyE6Error(f"cannot read manifest {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LegacyE6Error(f"invalid JSON in {path}: {exc}") from exc
    try:
        return LegacyManifest.model_validate(payload)
    except ValidationError as exc:
        raise LegacyE6Error(f"V0 manifest does not match its contract: {exc}") from exc


def adapt_e6_manifest(
    manifest_path: Path,
    workspace: Path | None = None,
    run_id: str | None = None,
    now: datetime | None = None,
    probe: Callable[[Path], MediaProbe] = probe_media,
) -> tuple[RenderManifest, list[RenderCheck]]:
    """Read a V0 manifest and its media; return a V1 RenderManifest.

    The function is read-only with respect to V0 and all E6 media.  Any file
    or probe error raises ``LegacyE6Error``; content mismatches are recorded
    as failed checks in the returned manifest instead of being hidden.
    """

    manifest_path = manifest_path.resolve()
    workspace = (workspace or Path.cwd()).resolve()
    base = manifest_path.parent
    v0 = load_manifest(manifest_path)
    fps = RationalFPS(fps_num=v0.fps, fps_den=1)
    timings, total_frames = build_shot_timings(v0.shots, v0.fps, 1)
    checks: list[RenderCheck] = []

    def add(check_id: str, ok: bool, detail: str) -> None:
        checks.append(
            RenderCheck(
                id=check_id,
                status="pass" if ok else "fail",
                detail=detail,
            )
        )

    v0_ref = asset_ref(manifest_path, workspace, "json", origin="author")
    add("v0_manifest", True, f"{v0_ref.path} sha256={v0_ref.sha256}")

    tolerance_ms = max(1, frame_to_ms(1, v0.fps, 1))
    shots: list[RenderShot] = []
    for shot, timing in zip(v0.shots, timings):
        path = _resolve(base, shot.file)
        media = probe(path)
        ref = asset_ref(path, workspace, "video")
        add(
            f"shot_asset:{shot.id}",
            ref.sha256 == shot.sha256,
            f"expected {shot.sha256}, actual {ref.sha256}",
        )
        actual_ms = seconds_to_ms(media.duration_s or 0)
        expected_ms = seconds_to_ms(shot.duration_s)
        add(
            f"shot_duration:{shot.id}",
            abs(actual_ms - expected_ms) <= tolerance_ms,
            f"expected {expected_ms} ms, actual {actual_ms} ms",
        )
        video = media.first("video")
        add(
            f"shot_resolution:{shot.id}",
            bool(video and (video.width, video.height) == v0.resolution),
            f"expected {v0.resolution}, actual {None if video is None else (video.width, video.height)}",
        )
        rate = parse_rate(video.avg_frame_rate or video.r_frame_rate) if video else None
        add(
            f"shot_fps:{shot.id}",
            rate == (v0.fps, 1),
            f"expected {v0.fps}/1, actual {None if video is None else (video.avg_frame_rate or video.r_frame_rate)}",
        )
        shots.append(
            RenderShot(
                shot_id=shot.id,
                track="manim",
                start_frame=timing.start_frame,
                duration_frames=timing.duration_frames,
                asset=ref,
            )
        )

    narration_path = _resolve(base, v0.narration.file)
    narration_media = probe(narration_path)
    narration_ref = asset_ref(narration_path, workspace, "audio")
    add(
        "narration_asset",
        narration_ref.sha256 == v0.narration.sha256,
        f"expected {v0.narration.sha256}, actual {narration_ref.sha256}",
    )
    audio = narration_media.first("audio")
    add(
        "narration_audio_format",
        bool(audio and audio.sample_rate == 48000 and audio.channels == 1),
        f"expected 48000 Hz / 1 ch, actual {None if audio is None else (audio.sample_rate, audio.channels)}",
    )
    narration_ms = seconds_to_ms(narration_media.duration_s or 0)
    expected_narration_ms = seconds_to_ms(v0.narration.duration_s)
    add(
        "narration_duration",
        abs(narration_ms - expected_narration_ms) <= tolerance_ms,
        f"expected {expected_narration_ms} ms, actual {narration_ms} ms",
    )
    add(
        "narration_mixed_extent",
        abs(narration_ms - frame_to_ms(total_frames, v0.fps, 1)) <= tolerance_ms,
        f"mixed WAV {narration_ms} ms, timeline {frame_to_ms(total_frames, v0.fps, 1)} ms",
    )

    segments: list[RenderNarrationSegment] = []
    segment_fit_ok = len(v0.narration.segments) == len(timings)
    for timing, segment in zip(timings, v0.narration.segments):
        segment_ms = seconds_to_ms(segment.duration_s)
        segment_frames = ms_to_frame(segment_ms, v0.fps, 1)
        fit_ok = segment_ms <= timing.duration_ms + tolerance_ms
        segment_fit_ok = segment_fit_ok and fit_ok
        add(
            f"narration_fit:{segment.id}",
            fit_ok,
            f"segment {segment_ms} ms, shot {timing.duration_ms} ms",
        )
        segments.append(
            RenderNarrationSegment(
                narration_id=segment.id,
                start_frame=timing.start_frame,
                duration_frames=segment_frames,
                duration_ms=segment_ms,
            )
        )
    if len(v0.narration.segments) != len(timings):
        add(
            "narration_fit:count",
            False,
            f"{len(v0.narration.segments)} segments for {len(timings)} shots",
        )
    add(
        "narration_fit",
        segment_fit_ok,
        "every legacy segment fits its shot; mixed WAV has no per-segment assets",
    )

    subtitles_path = _resolve(base, v0.subtitles.file)
    subtitles_ref = asset_ref(subtitles_path, workspace, "subtitle", origin="author")
    add(
        "subtitles_asset",
        subtitles_ref.sha256 == v0.subtitles.sha256,
        f"expected {v0.subtitles.sha256}, actual {subtitles_ref.sha256}",
    )
    try:
        cues = parse_srt(subtitles_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise LegacyE6Error(f"cannot read subtitles {subtitles_path}: {exc}") from exc
    cue_ok = bool(cues)
    for cue in cues:
        start_frame = ms_to_frame(cue.start_ms, v0.fps, 1)
        end_frame = ms_to_frame(cue.end_ms, v0.fps, 1)
        inside = any(
            timing.start_frame <= start_frame
            and end_frame <= timing.start_frame + timing.duration_frames
            for timing in timings
        )
        cue_ok = cue_ok and inside and cue.end_ms > cue.start_ms
    add(
        "subtitle_cues",
        cue_ok,
        f"{len(cues)} cues; every cue is non-empty and inside a shot",
    )

    video_path = _resolve(base, v0.video.file)
    video_media = probe(video_path)
    video_ref = asset_ref(video_path, workspace, "video")
    add(
        "final_asset",
        video_ref.sha256 == v0.video.sha256,
        f"expected {v0.video.sha256}, actual {video_ref.sha256}",
    )
    video_ms = seconds_to_ms(video_media.duration_s or 0)
    expected_video_ms = seconds_to_ms(v0.video.duration_s)
    add(
        "final_duration",
        abs(video_ms - expected_video_ms) <= tolerance_ms,
        f"expected {expected_video_ms} ms, actual {video_ms} ms",
    )
    timeline_ms = frame_to_ms(total_frames, v0.fps, 1)
    add(
        "final_timeline_extent",
        abs(video_ms - timeline_ms) <= tolerance_ms,
        f"timeline {timeline_ms} ms, actual {video_ms} ms",
    )
    final_video_stream = video_media.first("video")
    add(
        "final_resolution",
        bool(
            final_video_stream
            and (final_video_stream.width, final_video_stream.height)
            == v0.resolution
        ),
        f"expected {v0.resolution}, actual {None if final_video_stream is None else (final_video_stream.width, final_video_stream.height)}",
    )
    final_rate = (
        parse_rate(final_video_stream.avg_frame_rate or final_video_stream.r_frame_rate)
        if final_video_stream
        else None
    )
    add(
        "final_fps",
        final_rate == (v0.fps, 1),
        f"expected {v0.fps}/1, actual {None if final_video_stream is None else (final_video_stream.avg_frame_rate or final_video_stream.r_frame_rate)}",
    )
    final_audio = video_media.first("audio")
    add(
        "final_audio_format",
        bool(final_audio and final_audio.sample_rate == 48000 and final_audio.channels == 1),
        f"expected 48000 Hz / 1 ch, actual {None if final_audio is None else (final_audio.sample_rate, final_audio.channels)}",
    )
    stream_types = {stream.codec_type for stream in video_media.streams}
    add(
        "final_streams",
        {"video", "audio", "subtitle"}.issubset(stream_types),
        f"actual streams: {sorted(stream_types)}",
    )
    checks.append(
        RenderCheck(
            id="manual_checks_not_trusted",
            status="not_applicable",
            detail="V0 checks are preserved in legacy.manual_checks and are not V1 pass records",
        )
    )

    now = now or datetime.now(timezone.utc)
    run_id = run_id or (now.strftime("%Y%m%dT%H%M%SZ") + "-" + v0_ref.sha256[:8])
    legacy = {
        "v0_manifest": v0_ref.model_dump(),
        "reason": (
            "E6 V0 has a mixed narration WAV and no lesson.yaml/storyboard; "
            "normalized source contracts cannot be produced without fabricating author files."
        ),
        "manual_checks": v0.checks,
        "manual_checks_trusted": False,
        "narration_was_mixed": True,
        "narration_segments_start_inferred": True,
    }
    try:
        manifest = RenderManifest(
            lesson_id=v0.lesson,
            render_id=f"{v0.lesson}-{run_id}",
            run_id=run_id,
            created_at=now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            source=None,
            output=RenderOutput(
                fps=fps,
                width=v0.resolution[0],
                height=v0.resolution[1],
                total_frames=total_frames,
                duration_ms=timeline_ms,
            ),
            shots=shots,
            narration=RenderNarration(
                asset=narration_ref,
                duration_ms=narration_ms,
                segments=segments,
            ),
            subtitles=RenderSubtitles(
                asset=subtitles_ref,
                format="srt",
                cues=len(cues),
            ),
            video=video_ref,
            checks=checks,
            tool_versions={"ffprobe": ffprobe_version()},
            legacy=legacy,
        )
    except ValidationError as exc:
        raise LegacyE6Error(f"cannot build V1 RenderManifest: {exc}") from exc
    return manifest, checks
