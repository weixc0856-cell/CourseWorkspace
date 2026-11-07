"""Cross-platform QC for code-driven shots.

Adapted from the Code2Video `check_video.sh` contract and the
video-production-skill QC discipline. No Python audio dependencies; only
ffmpeg/ffprobe and Pillow (already a CourseControl dependency).
"""

from __future__ import annotations

import math
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .utils import MediaInfo, probe_media, run_command, which_command


def _check(check_id: str, ok: bool, expected: str, actual: str, detail: str | None = None) -> dict:
    return {
        "id": check_id,
        "status": "pass" if ok else "fail",
        "expected": expected,
        "actual": actual,
        "detail": detail,
    }


def _warn(check_id: str, detail: str) -> dict:
    return {"id": check_id, "status": "warn", "detail": detail}


def detect_black_freeze(path: Path, workspace: Path, log_path: Path | None = None) -> tuple[list[str], list[str]]:
    result = run_command(
        [
            *which_command("ffmpeg"),
            "-hide_banner",
            "-i",
            str(path),
            "-vf",
            "blackdetect=d=0.3:pix_th=0.06,freezedetect=n=0.002:d=1.5",
            "-an",
            "-f",
            "null",
            "-",
        ],
        workspace,
        timeout=600,
        log_path=log_path,
    )
    text = result.stderr + "\n" + result.stdout

    def pairs(kind: str) -> list[str]:
        starts = [float(value) for value in re.findall(kind + r"_start:\s*([0-9.]+)", text)]
        ends = [float(value) for value in re.findall(kind + r"_end:\s*([0-9.]+)", text)]
        return [f"{start}-{end}s" for start, end in zip(starts, ends) if end > start]

    return pairs("black"), pairs("freeze")


def check_video(
    path: Path,
    *,
    width: int,
    height: int,
    fps: float,
    min_duration: float | None = None,
    max_duration: float | None = None,
    audio: str = "any",
    workspace: Path | None = None,
    log_path: Path | None = None,
) -> dict:
    checks: list[dict] = []
    warnings: list[dict] = []
    info: MediaInfo | None = None
    try:
        info = probe_media(path)
    except Exception as exc:  # noqa: BLE001
        checks.append(_check("video_stream", False, "readable video stream", "probe failed", str(exc)))
        return {"ok": False, "checks": checks, "warnings": warnings}

    checks.append(
        _check(
            "video_stream",
            info.duration is not None and info.codec is not None,
            "readable video stream",
            f"{info.codec}, {info.duration}s" if info.duration is not None else "unknown",
        )
    )
    checks.append(
        _check(
            "resolution",
            (info.width, info.height) == (width, height),
            f"{width}x{height}",
            f"{info.width}x{info.height}",
        )
    )
    actual_fps = info.fps if info.fps is not None else 0.0
    checks.append(
        _check("fps", abs(actual_fps - fps) <= 0.01, f"{fps}", f"{actual_fps}")
    )
    duration = info.duration if info.duration is not None else 0.0
    if min_duration is not None or max_duration is not None:
        low = (min_duration or 0.0) - 0.05
        high = (max_duration or math.inf) + 0.05
        checks.append(
            _check(
                "duration",
                low <= duration <= high,
                f"{min_duration or 0}..{max_duration or '∞'}s",
                f"{duration:.3f}s",
            )
        )
    checks.append(
        _check("codec", (info.codec or "").lower() == "h264", "h264", str(info.codec))
    )
    checks.append(
        _check("pix_fmt", (info.pix_fmt or "").lower() == "yuv420p", "yuv420p", str(info.pix_fmt))
    )
    audio_ok = {
        "any": True,
        "0": not info.has_audio,
        "1": info.has_audio,
    }.get(str(audio), True)
    checks.append(
        _check("audio", audio_ok, f"audio={audio}", f"has_audio={info.has_audio}")
    )

    if workspace is not None:
        black, freeze = detect_black_freeze(path, workspace, log_path)
        if black:
            warnings.append(_warn("black_frames", ", ".join(black)))
        if freeze:
            warnings.append(_warn("frozen_frames", ", ".join(freeze)))

    return {
        "ok": all(item["status"] != "fail" for item in checks),
        "checks": checks,
        "warnings": warnings,
        "media": info.as_dict(),
    }


def contact_sheet(
    video: Path,
    out: Path,
    *,
    step: float = 2.0,
    cols: int = 5,
    thumb: int = 384,
    workspace: Path | None = None,
) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        frames = Path(tmp)
        result = run_command(
            [
                *which_command("ffmpeg"),
                "-v",
                "error",
                "-y",
                "-i",
                str(video),
                "-vf",
                f"fps=1/{step},scale={thumb}:-2",
                str(frames / "frame-%03d.png"),
            ],
            workspace or video.parent,
            timeout=300,
        )
        if result.exit_code != 0:
            raise RuntimeError(f"contact sheet extraction failed: {result.stderr[-500:]}")
        images = sorted(frames.glob("frame-*.png"))
        if not images:
            raise RuntimeError("contact sheet produced no frames")
        thumbs = [Image.open(path).convert("RGB") for path in images]
        width, height = thumbs[0].size
        rows = (len(thumbs) + cols - 1) // cols
        padding = 4
        sheet = Image.new(
            "RGB",
            (cols * width + (cols + 1) * padding, rows * height + (rows + 1) * padding),
            (128, 128, 128),
        )
        draw = ImageDraw.Draw(sheet)
        try:
            face = ImageFont.truetype("arial.ttf", 18)
        except OSError:
            face = ImageFont.load_default()
        for index, image in enumerate(thumbs):
            row, col = divmod(index, cols)
            x = padding + col * (width + padding)
            y = padding + row * (height + padding)
            sheet.paste(image, (x, y))
            draw.rectangle([x + 4, y + 4, x + 76, y + 28], fill=(0, 0, 0))
            draw.text((x + 8, y + 7), f"{index * step:.1f}s", fill=(255, 220, 0), font=face)
        sheet.save(out, quality=90)
    return out
