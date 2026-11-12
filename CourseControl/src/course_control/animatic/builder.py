"""Build the animatic for one lesson.

Each unit becomes one low-resolution segment; identical segments are reused
from ``animatic/cache/segments`` keyed by their inputs, so replacing a single
shot re-encodes that shot and nothing else.  The segments are concatenated
with ``-c copy`` and the narration is padded to the picture length, which
keeps the animatic on the same frame grid as the real timeline.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..paths import LessonPaths
from ..media import probe_media
from ..utils import run_command, which_command
from .timeline import AnimaticError, Timeline, Unit

LABEL_FONT = Path("assets") / "fonts" / "Manrope-SemiBold.ttf"
PAD = 14


@dataclass
class Segment:
    index: int
    unit: Unit
    path: Path
    frames: int
    key: str
    reused: bool
    status: str = "ok"
    detail: str | None = None


def build(
    paths: LessonPaths,
    timeline: Timeline,
    *,
    audio: Path | None = None,
    silent: bool = False,
    only: set[str] | None = None,
    force: bool = False,
) -> dict:
    build_root = paths.build_root
    out = build_root / "animatic"
    segments_dir = out / "cache" / "segments"
    labels_dir = out / "cache" / "labels"
    frames_dir = out / "frames"
    audio_dir = out / "audio"
    for directory in (segments_dir, labels_dir, frames_dir, audio_dir):
        directory.mkdir(parents=True, exist_ok=True)

    frames = timeline.frames()
    segments: list[Segment] = []
    for index, (unit, count) in enumerate(zip(timeline.units, frames)):
        label_png = _label_png(paths, timeline, unit, index, labels_dir)
        key = _segment_key(unit, count, label_png, timeline)
        target = segments_dir / f"seg-{index:03d}-{_safe(unit.id)}.mp4"
        meta_path = target.with_suffix(".json")
        reusable = (
            not force
            and target.is_file()
            and meta_path.is_file()
            and _read_key(meta_path) == key
            and (only is None or unit.id not in only)
        )
        if reusable:
            segments.append(Segment(index, unit, target, count, key, reused=True, status=_meta_status(meta_path)))
            continue
        status, detail = _encode_segment(
            paths, unit, target, label_png, count, timeline, labels_dir, index
        )
        meta_path.write_text(
            json.dumps({"key": key, "status": status, "detail": detail}, ensure_ascii=False),
            encoding="utf-8",
        )
        segments.append(Segment(index, unit, target, count, key, reused=False, status=status, detail=detail))

    missing = [segment.unit.id for segment in segments if not segment.path.is_file()]
    if missing:
        raise AnimaticError(f"segment encoding failed for: {', '.join(missing)}")

    picture = out / "picture.mp4"
    _concat(paths, segments, picture, out)

    audio_info = _prepare_audio(paths, audio, silent, audio_dir)
    final = out / "animatic.mp4"
    if audio_info is None:
        shutil.copyfile(picture, final)
    else:
        _mux(paths, picture, Path(audio_info["file"]), final, out)

    _extract_frames(paths, segments, frames_dir)
    return {
        "out": out,
        "video": final,
        "segments": segments,
        "audio": audio_info,
    }


def _safe(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_." else "-" for char in value)
    return cleaned[:48] or "unit"


def _sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _segment_key(unit: Unit, count: int, label_png: Path, timeline: Timeline) -> str:
    payload = {
        "id": unit.id,
        "kind": unit.kind,
        "source": _sha(unit.source) if unit.source is not None else None,
        "frames": count,
        "fps": timeline.fps,
        "size": [timeline.width, timeline.height],
        "label": _sha(label_png),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _read_key(meta_path: Path) -> str | None:
    try:
        return json.loads(meta_path.read_text(encoding="utf-8")).get("key")
    except (OSError, ValueError):
        return None


def _meta_status(meta_path: Path) -> str:
    try:
        return json.loads(meta_path.read_text(encoding="utf-8")).get("status", "ok")
    except (OSError, ValueError):
        return "ok"


def _font(paths: LessonPaths, size: int):
    candidate = paths.workspace / LABEL_FONT
    if candidate.is_file():
        try:
            return ImageFont.truetype(str(candidate), size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow without the sized default
        return ImageFont.load_default()


def _label_png(paths: LessonPaths, timeline: Timeline, unit: Unit, index: int, labels_dir: Path) -> Path:
    """A transparent full-canvas overlay carrying the shot number."""
    width, height = timeline.width, timeline.height
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _font(paths, max(9, height // 28))
    text = f"{index + 1:02d}/{len(timeline.units)}  {unit.label}"
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    margin = max(4, PAD * height // 480)
    box_height = (bottom - top) + 2 * max(2, height // 120)
    box = (
        margin,
        height - margin - box_height,
        margin + (right - left) + 2 * max(4, height // 60),
        height - margin,
    )
    draw.rounded_rectangle(box, radius=max(2, height // 80), fill=(0, 0, 0, 140))
    draw.text((box[0] + max(4, height // 60), box[1] + box_height // 5), text, font=font, fill=(255, 255, 255, 225))
    target = labels_dir / f"label-{index:03d}.png"
    image.save(target)
    return target


def _blank_source(timeline: Timeline, index: int, labels_dir: Path) -> Path:
    target = labels_dir / f"blank-{index:03d}.png"
    Image.new("RGB", (timeline.width, timeline.height), (18, 18, 18)).save(target)
    return target


def _encode_segment(
    paths: LessonPaths,
    unit: Unit,
    target: Path,
    label_png: Path,
    count: int,
    timeline: Timeline,
    labels_dir: Path,
    index: int,
) -> tuple[str, str | None]:
    width, height = timeline.width, timeline.height
    status, detail = "ok", None
    if unit.kind == "placeholder" or unit.source is None:
        source = _blank_source(timeline, index, labels_dir)
        loop = ["-loop", "1", "-framerate", str(timeline.fps)]
        status, detail = "placeholder", "no picture available for this unit"
    else:
        source = unit.source
        loop = ["-loop", "1", "-framerate", str(timeline.fps)] if unit.kind == "still" else []
        if unit.kind == "clip":
            probed = _safe_probe(source)
            if probed is not None and probed < unit.duration_s - 0.1:
                status = "short_source"
                detail = f"clip is {probed:.2f}s, slot is {unit.duration_s:.2f}s"
    scale = (
        # Cloning the last frame lets a clip that is a few frames short still
        # fill its slot exactly; -frames:v cuts the result to the slot length.
        f"tpad=stop_mode=clone:stop_duration=5,"
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={timeline.fps}"
    )
    command = [
        *which_command("ffmpeg"),
        "-v", "error", "-y",
        *loop, "-i", str(source),
        "-i", str(label_png),
        "-filter_complex",
        f"[0:v]{scale}[bg];[bg][1:v]overlay=0:0,format=yuv420p[v]",
        "-map", "[v]",
        "-frames:v", str(count),
        "-r", str(timeline.fps),
        "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(target),
    ]
    result = run_command(command, paths.build_root, timeout=1800)
    if result.exit_code != 0:
        raise AnimaticError(f"ffmpeg failed for {unit.id}: {result.stderr.strip()[-600:]}")
    return status, detail


def _safe_probe(path: Path) -> float | None:
    try:
        return probe_media(path).duration_s
    except Exception:  # noqa: BLE001 - a probe failure must not stop the animatic
        return None


def _concat(paths: LessonPaths, segments: list[Segment], target: Path, out: Path) -> None:
    listing = out / "cache" / "concat.txt"
    lines = []
    for segment in segments:
        if not segment.path.is_file():
            raise AnimaticError(f"missing segment {segment.path}")
        lines.append(f"file '{segment.path.as_posix()}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = run_command(
        [
            *which_command("ffmpeg"), "-v", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(listing),
            "-c", "copy", "-movflags", "+faststart", str(target),
        ],
        paths.build_root,
        timeout=1800,
    )
    if result.exit_code != 0:
        raise AnimaticError(f"concat failed: {result.stderr.strip()[-600:]}")


def _prepare_audio(paths: LessonPaths, audio: Path | None, silent: bool, audio_dir: Path) -> dict | None:
    if silent:
        return None
    candidate = audio
    if candidate is None:
        default = paths.build_root / "narration" / "narration.wav"
        candidate = default if default.is_file() else None
    if candidate is None:
        return None
    source = candidate if candidate.is_absolute() else (Path.cwd() / candidate)
    source = source.resolve()
    if not source.is_file():
        raise AnimaticError(f"audio not found: {source}")
    target = audio_dir / f"animatic-{source.stem}{source.suffix}"
    shutil.copyfile(source, target)
    return {
        "file": str(target),
        "source": str(source),
        "sha256": _sha(target),
        "duration_s": _safe_probe(target),
    }


def _mux(paths: LessonPaths, picture: Path, audio: Path, target: Path, out: Path) -> None:
    result = run_command(
        [
            *which_command("ffmpeg"), "-v", "error", "-y",
            "-i", str(picture),
            "-i", str(audio),
            "-filter_complex", "[1:a]apad[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-movflags", "+faststart",
            str(target),
        ],
        paths.build_root,
        timeout=1800,
    )
    if result.exit_code != 0:
        raise AnimaticError(f"audio mux failed: {result.stderr.strip()[-600:]}")


def _extract_frames(paths: LessonPaths, segments: list[Segment], frames_dir: Path) -> None:
    for segment in segments:
        target = frames_dir / f"{segment.index:03d}-{_safe(segment.unit.id)}.png"
        midpoint = max(0.0, segment.unit.duration_s / 2)
        result = run_command(
            [
                *which_command("ffmpeg"), "-v", "error", "-y",
                "-ss", f"{midpoint:.3f}", "-i", str(segment.path),
                "-frames:v", "1", str(target),
            ],
            paths.build_root,
            timeout=300,
        )
        if result.exit_code != 0 and not target.is_file():
            with (frames_dir / "failures.txt").open("a", encoding="utf-8") as handle:
                handle.write(segment.unit.id + "\n")
