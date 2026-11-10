"""Brand layer: plan, render and stitch the intro/outro around a lesson.

The body timeline is the single timing fact. Brand segments are rendered by
Remotion as standalone compositions and concatenated after the viewing master
(captioned or BGM-mixed) is final. Nothing here rewrites shots.json,
timeline.spec.json, narration or subtitles.

Presets, copy and durations live in ``shared/design-tokens/brand.json`` — the
same file the Remotion components import, so the two sides cannot drift.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .contracts import Branding, LessonConfig
from .paths import ContractError, LessonPaths
from .timecode import ms_to_frame
from .utils import probe_media, run_command, which_command

BRAND_SPEC_REL = Path("shared/design-tokens/brand.json")
DELIVERY_NAME = "course-video-delivery.mp4"
MASTER_CANDIDATES = (
    "course-video-mixed.mp4",
    "course-video-captioned.mp4",
    "course-video.mp4",
)
LANDSCAPE = (1920, 1080)
PORTRAIT = (1080, 1920)
ASSUMED_AUDIO = {"sample_rate": 48000, "channels": 2}


class BrandError(ContractError):
    """The brand layer cannot be planned, rendered or stitched."""


# ---------------------------------------------------------------------------
# spec / planning
# ---------------------------------------------------------------------------


def load_spec(workspace: Path) -> dict[str, Any]:
    path = workspace / BRAND_SPEC_REL
    if not path.is_file():
        raise BrandError(f"brand spec missing: {BRAND_SPEC_REL.as_posix()}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BrandError(f"brand spec is unreadable: {exc}") from exc
    for key in ("identity", "canvas", "content_kinds", "presets", "rules"):
        if key not in data:
            raise BrandError(f"brand spec is missing {key!r}")
    return data


def preset_ids(spec: dict[str, Any]) -> list[str]:
    return sorted(spec["presets"])


def resolve_preset_id(
    lesson: LessonConfig,
    segment_kind: Literal["intro", "outro"],
    segment,
    spec: dict[str, Any],
) -> str | None:
    """Resolve ``auto`` to the content-kind default, then enforce brand rules."""

    content_kind = lesson.audio.content_kind
    if segment.preset == "auto":
        if lesson.video_form == "short":
            # A short gets one signature end card, never a long intro.
            preset_id = "short_signature" if segment_kind == "outro" else None
        else:
            preset_id = spec["content_kinds"][content_kind].get(segment_kind)
    else:
        preset_id = segment.preset
    if preset_id is None:
        return None
    presets = spec["presets"]
    if preset_id not in presets:
        raise BrandError(
            f"unknown brand preset {preset_id!r}; available: {', '.join(preset_ids(spec))}"
        )
    preset = presets[preset_id]
    if lesson.video_form == "short" and preset_id != "short_signature":
        raise BrandError(
            f"short video uses short_signature only; {preset_id!r} is a long-form preset"
        )
    if lesson.video_form == "long" and preset_id == "short_signature":
        raise BrandError("short_signature is only valid when video_form is 'short'")
    if content_kind == "news" and segment_kind == "intro":
        raise BrandError(
            "news episodes start with narration; a brand intro is not allowed"
        )
    kind = preset.get("kind")
    if kind == "intro" and segment_kind != "intro":
        raise BrandError(f"preset {preset_id!r} is an intro, not an outro")
    if kind == "outro" and segment_kind != "outro":
        raise BrandError(f"preset {preset_id!r} is an outro, not an intro")
    return preset_id


def _expected_size(preset: dict[str, Any]) -> tuple[int, int]:
    return PORTRAIT if preset.get("aspect") == "portrait" else LANDSCAPE


def _segment_duration(segment, preset: dict[str, Any], preset_id: str) -> float:
    duration = segment.duration_s if segment.duration_s is not None else preset["duration_s"]
    low, high = float(preset["min_s"]), float(preset["max_s"])
    if not low <= duration <= high:
        raise BrandError(
            f"{preset_id}: duration {duration}s is outside {low}-{high}s"
        )
    return round(duration, 3)


def _props(
    lesson: LessonConfig,
    branding: Branding,
    spec: dict[str, Any],
    segment,
    duration_s: float,
) -> dict[str, Any]:
    content_kind = lesson.audio.content_kind
    meta = spec["content_kinds"][content_kind]
    # Field permissions: only these keys reach the brand components. Category
    # numbers, translated subtitles, series names and next-episode teasers are
    # not part of the brand frames.
    props = {
        "durationInSeconds": duration_s,
        "title": segment.title or lesson.title_en,
        "category": meta["label"],
        "date": branding.date,
        "showReservedArea": branding.preview_safe_area,
    }
    return props


@dataclass(frozen=True)
class BrandPlan:
    lesson_id: str
    theme: str
    fps: int
    width: int
    height: int
    content_kind: str
    master: str | None
    segments: tuple[dict[str, Any], ...]

    @property
    def brand_duration_s(self) -> float:
        return round(sum(float(item["duration_s"]) for item in self.segments), 3)

    def as_dict(self, *, generated_at: str | None = None) -> dict[str, Any]:
        payload = {
            "schema_version": 1,
            "lesson_id": self.lesson_id,
            "theme": self.theme,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "content_kind": self.content_kind,
            "master": self.master,
            "segments": list(self.segments),
            "brand_duration_s": self.brand_duration_s,
        }
        if generated_at is not None:
            payload["generated_at"] = generated_at
        return payload


def choose_master(build_root: Path) -> str | None:
    for name in MASTER_CANDIDATES:
        if (build_root / "final" / name).is_file():
            return name
    return None


def build_plan(paths: LessonPaths) -> BrandPlan:
    branding = paths.lesson.branding
    if not branding.enabled:
        raise BrandError("branding is disabled for this lesson")
    spec = load_spec(paths.workspace)
    lesson = paths.lesson
    width, height = lesson.outputs.resolution
    fps = lesson.outputs.fps
    segments: list[dict[str, Any]] = []
    for segment_kind in ("intro", "outro"):
        segment = getattr(branding, segment_kind)
        if segment is None or not segment.enabled:
            continue
        preset_id = resolve_preset_id(lesson, segment_kind, segment, spec)
        if preset_id is None:
            continue
        preset = spec["presets"][preset_id]
        expected = _expected_size(preset)
        if (width, height) != expected:
            raise BrandError(
                f"{preset_id} renders at {expected[0]}x{expected[1]}, "
                f"lesson outputs {width}x{height}; resample or pick a matching preset"
            )
        duration_s = _segment_duration(segment, preset, preset_id)
        frames = ms_to_frame(int(round(duration_s * 1000)), fps, 1)
        segments.append(
            {
                "kind": segment_kind,
                "preset": preset_id,
                "composition": preset["composition"],
                "duration_s": duration_s,
                "duration_frames": frames,
                "aspect": preset.get("aspect", "landscape"),
                "props": _props(lesson, branding, spec, segment, duration_s),
            }
        )
    if not segments:
        raise BrandError("branding is enabled but resolves to no segments")
    return BrandPlan(
        lesson_id=lesson.lesson_id,
        theme=branding.theme,
        fps=fps,
        width=width,
        height=height,
        content_kind=lesson.audio.content_kind,
        master=choose_master(paths.build_root),
        segments=tuple(segments),
    )


def plan_path(paths: LessonPaths) -> Path:
    return paths.build_root / "brand" / "plan.json"


def write_plan(paths: LessonPaths, plan: BrandPlan) -> Path:
    target = plan_path(paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = plan.as_dict(generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target


def segment_key(plan: BrandPlan, segment: dict[str, Any]) -> str:
    payload = {
        "composition": segment["composition"],
        "duration_frames": segment["duration_frames"],
        "props": segment["props"],
        "width": plan.width,
        "height": plan.height,
        "fps": plan.fps,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _segment_cache(paths: LessonPaths) -> dict[str, Any]:
    path = paths.build_root / "brand" / "segments.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def render_segment(
    paths: LessonPaths,
    plan: BrandPlan,
    segment: dict[str, Any],
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Render one brand segment; reuse a cached file when its key matches."""

    brand_dir = paths.build_root / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)
    kind = str(segment["kind"])
    output = brand_dir / f"{kind}.mp4"
    key = segment_key(plan, segment)
    cache = _segment_cache(paths)
    cached = cache.get(kind, {})
    if not force and output.is_file() and cached.get("key") == key:
        return {**cached, "status": "cached", "path": output}

    props_path = brand_dir / f"{kind}.props.json"
    props_path.write_text(
        json.dumps(segment["props"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    remotion_root = paths.workspace / "RemotionStudio"
    command = [
        *which_command("npx"),
        "remotion",
        "render",
        "src/index.ts",
        str(segment["composition"]),
        str(output),
        f"--props={props_path}",
    ]
    result = run_command(
        command,
        remotion_root,
        timeout=1800,
        log_path=paths.build_root / "logs" / f"brand-{kind}.log",
    )
    if result.exit_code != 0 or not output.is_file():
        raise BrandError(
            f"{kind}: remotion exited {result.exit_code}: {result.stderr[-1200:]}"
        )
    info = probe_media(output)
    expected = segment["duration_frames"] / plan.fps
    frame = 1.0 / plan.fps
    if info.duration is None or abs(info.duration - expected) > frame + 0.05:
        raise BrandError(
            f"{kind}: duration {info.duration} does not match {expected:.3f}s"
        )
    if (info.width, info.height) != (plan.width, plan.height):
        raise BrandError(
            f"{kind}: resolution {info.width}x{info.height} does not match lesson output"
        )
    record = {
        "key": key,
        "composition": segment["composition"],
        "duration_s": info.duration,
        "duration_frames": segment["duration_frames"],
        "width": info.width,
        "height": info.height,
        "fps": info.fps,
        "has_audio": info.has_audio,
        "sha256": sha256_file(output),
        "status": "rendered",
        "path": output,
    }
    cache[kind] = {k: v for k, v in record.items() if k != "path"}
    (paths.build_root / "brand" / "segments.json").write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return record


def render_segments(paths: LessonPaths, plan: BrandPlan, *, force: bool = False) -> list[dict[str, Any]]:
    return [render_segment(paths, plan, segment, force=force) for segment in plan.segments]


# ---------------------------------------------------------------------------
# stitch
# ---------------------------------------------------------------------------


def _audio_params(path: Path) -> dict[str, int]:
    command = which_command("ffprobe") + [
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=sample_rate,channels",
        "-of",
        "json",
        str(path),
    ]
    result = run_command(command, path.parent, timeout=60)
    if result.exit_code != 0:
        return dict(ASSUMED_AUDIO)
    try:
        stream = json.loads(result.stdout or "{}")["streams"][0]
        return {
            "sample_rate": int(stream.get("sample_rate") or ASSUMED_AUDIO["sample_rate"]),
            "channels": int(stream.get("channels") or ASSUMED_AUDIO["channels"]),
        }
    except (KeyError, IndexError, TypeError, ValueError):
        return dict(ASSUMED_AUDIO)


def _with_silence(source: Path, target: Path, audio: dict[str, int]) -> None:
    """Give a brand segment a silent track matching the body's audio params.

    The concat demuxer needs identical stream layouts; without this the intro
    would be video-only and `-c copy` would drop audio from the whole film.
    """

    layout = "mono" if audio["channels"] == 1 else "stereo"
    command = [
        *which_command("ffmpeg"),
        "-y",
        "-i",
        str(source),
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=channel_layout={layout}:sample_rate={audio['sample_rate']}",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-shortest",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        str(audio["sample_rate"]),
        "-ac",
        str(audio["channels"]),
        str(target),
    ]
    result = run_command(command, target.parent, timeout=300)
    if result.exit_code != 0 or not target.is_file():
        raise BrandError(
            f"could not add a silent track to {source.name}: {result.stderr[-800:]}"
        )


SILENCE_START = re.compile(r"silence_start:\s*(-?[0-9.]+)")
SILENCE_END = re.compile(r"silence_end:\s*([0-9.]+)")


def first_sound_s(path: Path, limit: float = 8.0, noise_db: int = 35) -> float | None:
    """Seconds until the first non-silent audio, within ``limit``.

    Returns 0.0 when sound is present from the first sample, ``None`` when the
    window is silent throughout (the caller then skips alignment rather than
    guessing).
    """

    command = [
        *which_command("ffmpeg"),
        "-hide_banner",
        "-nostats",
        "-t",
        f"{max(0.5, limit):.3f}",
        "-i",
        str(path),
        "-af",
        f"silencedetect=noise=-{noise_db}dB:d=0.15",
        "-f",
        "null",
        "-",
    ]
    result = run_command(command, path.parent, timeout=180)
    log = result.stderr or ""
    starts = [float(value) for value in SILENCE_START.findall(log)]
    ends = [float(value) for value in SILENCE_END.findall(log)]
    if starts and starts[0] <= 0.05:
        return ends[0] if ends else None
    return 0.0


def _alignment(
    body: Path,
    delivery: Path,
    body_info,
    intro_s: float,
    frame: float,
) -> dict[str, Any]:
    """Verify the body's audio starts exactly where the intro ends.

    The body is an atomic asset: it is never trimmed, faded or offset. This
    measures the first non-silent audio of the body on its own, then the same
    event in the stitched file, and compares the shift with the intro length.
    """

    body_first = first_sound_s(body, limit=min(8.0, body_info.duration or 8.0))
    if body_first is None:
        return {
            "intro_s": round(intro_s, 3),
            "body_first_sound_s": None,
            "expected_s": None,
            "actual_s": None,
            "delta_s": None,
            "status": "not_applicable",
            "note": "body is silent for the first 8 s; alignment checked structurally",
        }
    expected = intro_s + body_first
    actual = first_sound_s(delivery, limit=expected + 3.0)
    if actual is None:
        return {
            "intro_s": round(intro_s, 3),
            "body_first_sound_s": round(body_first, 3),
            "expected_s": round(expected, 3),
            "actual_s": None,
            "delta_s": None,
            "status": "fail",
            "note": "no sound detected in the delivery window",
        }
    delta = actual - expected
    tolerance = max(0.2, frame * 6)
    return {
        "intro_s": round(intro_s, 3),
        "body_first_sound_s": round(body_first, 3),
        "expected_s": round(expected, 3),
        "actual_s": round(actual, 3),
        "delta_s": round(delta, 3),
        "status": "pass" if abs(delta) <= tolerance else "fail",
        "tolerance_s": round(tolerance, 3),
    }


def video_timing_from_pts(
    pts: list[float], fps: float, expected_duration: float
) -> dict[str, Any]:
    """Detect collapsed timestamps: frames crammed into a few microseconds.

    Concatenating MP4 segments with different stream timescales and `-c copy`
    can leave every body frame at almost the same PTS. The file still reports
    the right duration and the audio stays correct, so only frame spacing
    reveals it. Normal frames are one tick apart; a collapsed stream has
    hundreds of intervals below half a frame.
    """

    ordered = sorted(value for value in pts if value == value)
    if not ordered:
        return {"status": "fail", "note": "no video timestamps"}
    frame = 1.0 / fps
    deltas = [b - a for a, b in zip(ordered, ordered[1:]) if b - a > 1e-6]
    clustered = sum(1 for delta in deltas if delta < frame * 0.5)
    expected_frames = max(1, round(expected_duration * fps))
    frames_ok = abs(len(ordered) - expected_frames) <= max(3, expected_frames * 0.02)
    return {
        "unique_frames": len(ordered),
        "expected_frames": expected_frames,
        "min_interval_s": round(min(deltas), 6) if deltas else None,
        "clustered_intervals": clustered,
        "first_pts_s": round(ordered[0], 3),
        "last_pts_s": round(ordered[-1], 3),
        "status": "pass" if clustered <= 2 and frames_ok else "fail",
    }


def video_timing(path: Path, fps: float, expected_duration: float) -> dict[str, Any]:
    command = which_command("ffprobe") + [
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "packet=pts_time",
        "-of",
        "csv=p=0",
        str(path),
    ]
    result = run_command(command, path.parent, timeout=180)
    values: list[float] = []
    for line in (result.stdout or "").splitlines():
        token = line.strip().split(",")[0]
        if not token or token == "N/A":
            continue
        try:
            values.append(float(token))
        except ValueError:
            continue
    return video_timing_from_pts(values, fps, expected_duration)


def _video_stream_duration(path: Path) -> float | None:
    command = which_command("ffprobe") + [
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=duration",
        "-of",
        "csv=p=0",
        str(path),
    ]
    result = run_command(command, path.parent, timeout=60)
    if result.exit_code != 0:
        return None
    try:
        return float((result.stdout or "").strip().splitlines()[0])
    except (IndexError, ValueError):
        return None


def _concat_list(
    entries: list[Path],
    target: Path,
    durations: list[float] | None = None,
) -> Path:
    lines: list[str] = []
    for index, entry in enumerate(entries):
        # Paths come from build/<slug>; they never contain a single quote.
        lines.append("file '" + entry.resolve().as_posix() + "'")
        # AAC priming makes an audio track slightly longer than its video.
        # An explicit duration keeps the next segment on the video boundary
        # instead of starting 60-80 ms late.
        if durations and index < len(durations):
            lines.append(f"duration {durations[index]:.6f}")
    target.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    return target


def _copy_concat(entries: list[Path], output: Path, log: Path) -> list[str]:
    """Stream-copy concat through MPEG-TS.

    Direct MP4 concat with `-c copy` does not rescale packet timestamps when
    the segments carry different timescales; the body frames then collapse onto
    one PTS. Remuxing each segment to MPEG-TS first normalises the 90 kHz clock;
    the encoded frames and audio samples are still copied, not re-encoded.
    """

    work = output.parent / "concat-ts"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    attempts: list[str] = []
    ts_files: list[Path] = []
    for index, entry in enumerate(entries):
        target = work / f"{index:02d}.ts"
        command = [
            *which_command("ffmpeg"),
            "-y",
            "-i",
            str(entry),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c",
            "copy",
            "-bsf:v",
            "h264_mp4toannexb",
            "-f",
            "mpegts",
            str(target),
        ]
        result = run_command(command, work, timeout=900, log_path=log)
        attempts.append(f"ts[{index}]: exit {result.exit_code}")
        if result.exit_code != 0 or not target.is_file():
            attempts.append(result.stderr[-800:])
            shutil.rmtree(work, ignore_errors=True)
            return attempts
        ts_files.append(target)
    durations = [
        _video_stream_duration(entry) or probe_media(entry).duration or 0.0
        for entry in entries
    ]
    listing = _concat_list(ts_files, work / "concat-ts.txt", durations)
    command = [
        *which_command("ffmpeg"),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(listing),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output),
    ]
    result = run_command(command, work, timeout=1800, log_path=log)
    attempts.append(f"ts-concat: exit {result.exit_code}")
    if result.exit_code != 0:
        attempts.append(result.stderr[-1200:])
    shutil.rmtree(work, ignore_errors=True)
    return attempts


def _reencode_concat(
    entries: list[Path],
    output: Path,
    has_audio: bool,
    audio: dict[str, int],
    log: Path,
) -> list[str]:
    inputs: list[str] = []
    for entry in entries:
        inputs += ["-i", str(entry)]
    count = len(entries)
    if has_audio:
        streams = "".join(f"[{index}:v:0][{index}:a:0]" for index in range(count))
        filter_complex = f"{streams}concat=n={count}:v=1:a=1[v][a]"
        maps = ["-map", "[v]", "-map", "[a]"]
    else:
        streams = "".join(f"[{index}:v:0]" for index in range(count))
        filter_complex = f"{streams}concat=n={count}:v=1:a=0[v]"
        maps = ["-map", "[v]"]
    command = [
        *which_command("ffmpeg"),
        "-y",
        *inputs,
        "-filter_complex",
        filter_complex,
        *maps,
        "-c:v",
        "libx264",
        "-crf",
        "20",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
    ]
    if has_audio:
        command += ["-c:a", "aac", "-b:a", "192k", "-ar", str(audio["sample_rate"]), "-ac", str(audio["channels"])]
    command.append(str(output))
    result = run_command(command, output.parent, timeout=3600, log_path=log)
    return [f"reencode: exit {result.exit_code}", result.stderr[-1200:]]


def stitch(paths: LessonPaths, plan: BrandPlan) -> dict[str, Any]:
    """Concatenate brand segments around the viewing master.

    Tries a stream-copy concat first; if the result does not line up within one
    frame per segment, re-encodes and records which path was taken.
    """

    if plan.master is None:
        raise BrandError("no viewing master: run compose before branding")
    final_dir = paths.build_root / "final"
    body = final_dir / plan.master
    body_info = probe_media(body)
    if (body_info.width, body_info.height) != (plan.width, plan.height):
        raise BrandError(
            f"master is {body_info.width}x{body_info.height}, "
            f"brand was rendered at {plan.width}x{plan.height}"
        )
    if body_info.fps is None or abs(body_info.fps - plan.fps) > 0.01:
        raise BrandError(f"master fps {body_info.fps} does not match lesson fps {plan.fps}")
    audio = _audio_params(body) if body_info.has_audio else dict(ASSUMED_AUDIO)

    brand_dir = paths.build_root / "brand"
    logs = paths.build_root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    entries: list[Path] = []
    for segment in plan.segments:
        kind = str(segment["kind"])
        source = brand_dir / f"{kind}.mp4"
        if not source.is_file():
            raise BrandError(f"{kind} segment is missing: {source.name}")
        if body_info.has_audio:
            prepared = brand_dir / f"{kind}-av.mp4"
            _with_silence(source, prepared, audio)
            entries.append(prepared)
        else:
            entries.append(source)
    # intro(s) before the body, outro(s) after.
    ordered = [entry for entry, segment in zip(entries, plan.segments) if segment["kind"] == "intro"]
    ordered.append(body)
    ordered += [entry for entry, segment in zip(entries, plan.segments) if segment["kind"] == "outro"]

    intro_s = sum(
        float(item["duration_s"]) for item in plan.segments if item["kind"] == "intro"
    )
    if body_info.has_audio:
        for entry, segment in zip(entries, plan.segments):
            if segment["kind"] != "intro":
                continue
            prepared_info = probe_media(entry)
            if (
                prepared_info.audio_duration is None
                or abs(prepared_info.audio_duration - (prepared_info.duration or 0.0))
                > 1.0 / plan.fps
            ):
                raise BrandError(
                    f"{segment['kind']}: silent track does not match the segment length"
                )

    delivery = final_dir / DELIVERY_NAME
    expected = (body_info.duration or 0.0) + plan.brand_duration_s
    frame = 1.0 / plan.fps
    alignment: dict[str, Any] | None = None
    timing: dict[str, Any] | None = None
    tolerance = frame * len(plan.segments) + 0.1
    attempts: list[str] = []
    mode = "copy"
    problems: list[str] = []
    for attempt_mode in ("copy", "reencode"):
        mode = attempt_mode
        if attempt_mode == "copy":
            attempts += _copy_concat(ordered, delivery, logs / "brand-copy.log")
        else:
            attempts += _reencode_concat(
                ordered, delivery, body_info.has_audio, audio, logs / "brand-reencode.log"
            )
        if not delivery.is_file():
            problems = [f"{attempt_mode}: output missing"]
            info = None
            continue
        try:
            info = probe_media(delivery)
        except ContractError as exc:
            problems = [f"{attempt_mode}: {exc}"]
            delivery.unlink(missing_ok=True)
            continue
        problems = []
        if info.duration is None or abs(info.duration - expected) > tolerance:
            problems.append(
                f"duration {info.duration} != expected {expected:.3f}s"
            )
        if (info.width, info.height) != (plan.width, plan.height):
            problems.append("resolution differs from the master")
        if info.fps is None or abs(info.fps - plan.fps) > 0.01:
            problems.append(f"fps {info.fps} != {plan.fps}")
        if info.has_audio != body_info.has_audio:
            problems.append("audio stream presence differs from the master")
        timing = video_timing(delivery, plan.fps, expected)
        if timing["status"] != "pass":
            problems.append(
                "video timestamps are collapsed: "
                f"{timing['clustered_intervals']} frame intervals below half a frame"
            )
        alignment = None
        if body_info.has_audio and not problems:
            alignment = _alignment(body, delivery, body_info, intro_s, frame)
            if alignment["status"] == "fail":
                problems.append(
                    "body audio starts at "
                    f"{alignment['actual_s']}s, expected {alignment['expected_s']}s "
                    f"(intro {alignment['intro_s']}s)"
                )
        if not problems:
            break
        delivery.unlink(missing_ok=True)

    record = {
        "schema_version": 1,
        "lesson": paths.slug,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "master": plan.master,
        "delivery": delivery.relative_to(paths.build_root).as_posix(),
        "mode": mode,
        "attempts": attempts,
        "body_duration_s": body_info.duration,
        "brand_duration_s": plan.brand_duration_s,
        "expected_duration_s": round(expected, 3),
        "duration_s": info.duration if info is not None else None,
        "fps": info.fps if info is not None else None,
        "resolution": [info.width, info.height] if info is not None else None,
        "has_audio": info.has_audio if info is not None else None,
        "segments": [
            {"kind": item["kind"], "preset": item["preset"], "duration_s": item["duration_s"]}
            for item in plan.segments
        ],
        "sha256": sha256_file(delivery) if delivery.is_file() else None,
        "audio_alignment": alignment,
        "video_timing": timing,
        "problems": problems,
    }
    report = final_dir / "brand.json"
    report.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if problems:
        delivery.unlink(missing_ok=True)
        raise BrandError("brand stitch failed: " + "; ".join(problems))
    return record


def delivery_path(paths: LessonPaths) -> Path:
    return paths.build_root / "final" / DELIVERY_NAME


def run_branding(paths: LessonPaths, *, force: bool = False) -> tuple[BrandPlan, dict[str, Any]]:
    """Plan, render and stitch. Used by the pipeline stage and the CLI."""

    plan = build_plan(paths)
    if plan.master is None:
        raise BrandError("no viewing master: run compose before branding")
    write_plan(paths, plan)
    render_segments(paths, plan, force=force)
    record = stitch(paths, plan)
    return plan, record


