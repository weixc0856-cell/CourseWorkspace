"""Build a review package for one rendered shot.

The package is evidence for a human decision, not an aesthetic score.  It
extracts first/middle/last frames, a contact sheet, a low-resolution preview,
metadata, technical QC and a short review.md.

No release gate is added here.  A failing QC record is reported as FAIL; the
human still decides whether the shot is acceptable.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from course_control.platform.media import probe_media, sha256_file
from course_control.platform.utils import run_command, which_command
from course_control.quality.code_video_qc import detect_black_freeze
from course_control.quality.media_qc import _measure_loudness

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
INCOMPLETE = "INCOMPLETE"


@dataclass
class ReviewResult:
    shot: str
    out_dir: Path
    metadata_path: Path
    qc_path: Path
    review_path: Path
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "shot": self.shot,
            "out_dir": str(self.out_dir),
            "metadata": str(self.metadata_path),
            "qc": str(self.qc_path),
            "review": str(self.review_path),
            "status": self.status,
        }


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _fps(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    try:
        num, den = value.split("/")
        return round(int(num) / int(den), 3) if int(den) else None
    except (ValueError, ZeroDivisionError):
        return None


def _video_info(video: Path) -> dict[str, Any]:
    probe = probe_media(video)
    stream = probe.first("video")
    if stream is None:
        raise ValueError(f"no video stream: {video}")
    audio = probe.first("audio")
    return {
        "duration_s": probe.duration_s,
        "size_bytes": probe.size,
        "width": stream.width,
        "height": stream.height,
        "fps": _fps(stream.avg_frame_rate or stream.r_frame_rate),
        "codec": stream.codec_name,
        "has_audio": audio is not None,
        "audio_codec": audio.codec_name if audio else None,
        "nb_frames": stream.nb_frames,
    }


def _extract_frame(workspace: Path, video: Path, seconds: float, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = run_command(
        [
            *which_command("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{max(0.0, seconds):.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(target),
        ],
        workspace,
        timeout=120,
    )
    if result.exit_code != 0 or not target.is_file():
        raise RuntimeError(
            f"ffmpeg frame extraction failed at {seconds:.3f}s: {result.stderr[-400:]}"
        )
    return target


def _contact_sheet(frames: list[Path], target: Path, columns: int = 3) -> Path:
    if not frames:
        raise ValueError("contact sheet needs at least one frame")
    with Image.open(frames[0]) as first:
        portrait = first.height > first.width
    cell_w, cell_h = (180, 320) if portrait else (320, 180)
    rows = (len(frames) + columns - 1) // columns
    sheet = Image.new("RGB", (cell_w * columns, cell_h * rows), (8, 12, 14))
    for index, path in enumerate(frames):
        with Image.open(path) as image:
            fitted = ImageOps.contain(image.convert("RGB"), (cell_w, cell_h))
        x = (index % columns) * cell_w + (cell_w - fitted.width) // 2
        y = (index // columns) * cell_h + (cell_h - fitted.height) // 2
        sheet.paste(fitted, (x, y))
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target, quality=88)
    return target


def _preview(workspace: Path, video: Path, info: dict[str, Any], target: Path) -> Path:
    width, height = int(info["width"] or 0), int(info["height"] or 0)
    short = min(width, height) if width and height else 0
    target.parent.mkdir(parents=True, exist_ok=True)
    if short and short <= 480:
        shutil.copy2(video, target)
        return target
    scale = "480:-2" if width >= height else "-2:480"
    command = [
        *which_command("ffmpeg"),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video),
        "-vf",
        f"scale={scale}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "24",
    ]
    if info.get("has_audio"):
        command += ["-c:a", "aac", "-b:a", "96k"]
    else:
        command += ["-an"]
    command += ["-movflags", "+faststart", str(target)]
    result = run_command(command, workspace, timeout=600)
    if result.exit_code != 0 or not target.is_file():
        raise RuntimeError(f"ffmpeg preview failed: {result.stderr[-400:]}")
    return target


def _check(check_id: str, status: str, detail: str, **values: Any) -> dict[str, Any]:
    return {"id": check_id, "status": status, "detail": detail, **values}


def _load_manifest(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _find_manifest(video: Path, shot: str, manifest_dir: Path | None) -> Path | None:
    directory = Path(manifest_dir) if manifest_dir else video.parent / "manifests"
    if not directory.is_dir():
        return None
    candidates: list[tuple[str, Path]] = []
    for path in directory.glob(f"{shot}-*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(data.get("output") or "") == str(video):
            candidates.append((str(data.get("finished_at") or ""), path))
    if not candidates:
        candidates = [
            (str(path.stat().st_mtime), path)
            for path in directory.glob(f"{shot}-*.json")
        ]
    return sorted(candidates)[-1][1] if candidates else None


def _qc(
    workspace: Path,
    video: Path,
    info: dict[str, Any],
    manifest: dict[str, Any] | None,
) -> tuple[dict[str, Any], str]:
    checks: list[dict[str, Any]] = []
    decode = run_command(
        [*which_command("ffmpeg"), "-v", "error", "-i", str(video), "-f", "null", "-"],
        workspace,
        timeout=600,
    )
    checks.append(_check(
        "decode",
        PASS if decode.exit_code == 0 and not decode.stderr.strip() else FAIL,
        decode.stderr[-500:] or "full decode ok",
    ))
    checks.append(_check(
        "video_stream",
        PASS if info.get("width") and info.get("height") and info.get("duration_s") else FAIL,
        f"{info.get('width')}x{info.get('height')} {info.get('duration_s')}s",
        **info,
    ))
    black, freeze = detect_black_freeze(video, workspace)
    checks.append(_check(
        "black",
        FAIL if black else PASS,
        f"{len(black)} black interval(s)",
        intervals=black[:20],
    ))
    checks.append(_check(
        "freeze",
        WARN if freeze else PASS,
        f"{len(freeze)} frozen interval(s); review intentional holds",
        intervals=freeze[:20],
    ))
    if not info.get("has_audio"):
        checks.append(_check("audio", WARN, "no audio stream"))
    else:
        loudness = _measure_loudness(video, workspace)
        checks.append(_check(
            "audio_loudness",
            PASS if loudness.get("integrated_lufs") is not None else INCOMPLETE,
            f"{loudness.get('integrated_lufs')} LUFS / {loudness.get('true_peak_dbfs')} dBTP",
            **loudness,
        ))
    if manifest:
        render = manifest.get("render") or {}
        expected = render.get("resolution")
        actual = [info.get("width"), info.get("height")]
        if expected:
            checks.append(_check(
                "manifest_resolution",
                PASS if actual == expected else WARN,
                f"manifest {expected}; actual {actual}",
            ))
        manifest_fps = render.get("fps")
        if manifest_fps:
            checks.append(_check(
                "manifest_fps",
                PASS if info.get("fps") and abs(float(info["fps"]) - float(manifest_fps)) < 0.01 else WARN,
                f"manifest {manifest_fps}; actual {info.get('fps')}",
            ))
    else:
        checks.append(_check("manifest", INCOMPLETE, "no build manifest supplied or found"))
    status = FAIL if any(item["status"] == FAIL for item in checks) else (
        WARN if any(item["status"] in {WARN, INCOMPLETE} for item in checks) else PASS
    )
    return {
        "schema_version": 1,
        "shot": None,
        "video": str(video),
        "status": status,
        "checks": checks,
        "generated_at": _now(),
    }, status


def build_shot_review(
    workspace: Path,
    *,
    shot: str,
    video: Path,
    out_dir: Path | None = None,
    manifest: Path | None = None,
    manifest_dir: Path | None = None,
    contact_frames: int = 9,
) -> ReviewResult:
    workspace = Path(workspace).resolve()
    video = Path(video).resolve()
    if not video.is_file():
        raise FileNotFoundError(f"video not found: {video}")
    out = Path(out_dir) if out_dir else (video.parent / "review" / shot)
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(manifest) if manifest else _find_manifest(video, shot, manifest_dir)
    manifest_data = _load_manifest(manifest_path)
    info = _video_info(video)
    duration = float(info.get("duration_s") or 0.0)

    first = _extract_frame(workspace, video, 0.05, out / "first.png")
    middle = _extract_frame(workspace, video, duration / 2 if duration else 0.0, out / "middle.png")
    last = _extract_frame(workspace, video, max(0.0, duration - 0.1), out / "last.png")

    frames = []
    count = max(3, int(contact_frames))
    for index in range(count):
        seconds = ((index + 0.5) / count) * duration if duration else 0.0
        frames.append(_extract_frame(workspace, video, seconds, out / "contact" / f"{index + 1:02d}.png"))
    contact = _contact_sheet(frames, out / "contact-sheet.jpg")
    preview = _preview(workspace, video, info, out / "preview.mp4")

    qc, status = _qc(workspace, video, info, manifest_data)
    qc["shot"] = shot
    qc["manifest"] = str(manifest_path) if manifest_path else None
    qc_path = out / "qc.json"
    qc_path.write_text(json.dumps(qc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    metadata = {
        "schema_version": 1,
        "shot": shot,
        "generated_at": _now(),
        "video": {
            "path": str(video),
            "sha256": sha256_file(video),
            "bytes": video.stat().st_size,
            **info,
        },
        "manifest": {
            "path": str(manifest_path) if manifest_path else None,
            "build_id": (manifest_data or {}).get("build_id"),
            "status": (manifest_data or {}).get("status") or INCOMPLETE,
            "profile": (manifest_data or {}).get("render_profile"),
            "engine": ((manifest_data or {}).get("render") or {}).get("engine"),
            "samples": ((manifest_data or {}).get("render") or {}).get("samples"),
            "elapsed_s": (manifest_data or {}).get("elapsed_s"),
        },
        "review": {
            "contact_sheet": str(contact),
            "preview": str(preview),
            "first": str(first),
            "middle": str(middle),
            "last": str(last),
        },
        "qc_status": status,
    }
    metadata_path = out / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    log_source = Path(str((manifest_data or {}).get("log") or ""))
    logs = out / "logs.txt"
    if log_source.is_file():
        lines = log_source.read_text(encoding="utf-8", errors="replace").splitlines()
        logs.write_text("\n".join(lines[-200:]) + "\n", encoding="utf-8")
    else:
        logs.write_text("no build log found\n", encoding="utf-8")

    review = out / "review.md"
    issues = [
        f"- {item['id']}: {item['status']} — {item['detail']}"
        for item in qc["checks"] if item["status"] != PASS
    ]
    review.write_text(
        "\n".join([
            f"# Shot review: {shot}",
            "",
            f"- Video: `{video}`",
            f"- Manifest: `{manifest_path}`" if manifest_path else "- Manifest: **missing**",
            f"- Duration: {info.get('duration_s')} s",
            f"- Resolution: {info.get('width')}x{info.get('height')} @ {info.get('fps')} fps",
            f"- QC status: **{status}**",
            "",
            "## Review",
            "",
            "- [ ] Composition has a clear subject and visual focus",
            "- [ ] Motion has a purpose; no jump or stutter",
            "- [ ] Lighting and color support the information",
            "- [ ] Picture still works with narration muted",
            "- [ ] Decision: accept / revise / reject",
            "",
            "## Non-passing checks",
            "",
            *(issues or ["- none"]),
            "",
            "This is a human review sheet, not an automatic aesthetic score.",
        ]) + "\n",
        encoding="utf-8",
    )
    return ReviewResult(
        shot=shot,
        out_dir=out,
        metadata_path=metadata_path,
        qc_path=qc_path,
        review_path=review,
        status=status,
    )
