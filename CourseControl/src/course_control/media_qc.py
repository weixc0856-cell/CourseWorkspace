"""Deterministic full-file audio/video/subtitle QC for a finished lesson.

Every check reports PASS / WARN / BLOCKED / INCOMPLETE with the observed value.
It never replaces human viewing; it only proves that the file decodes, meets
the declared format, and that the subtitle track is structurally sound.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .code_video_qc import detect_black_freeze
from .paths import LessonPaths
from .utils import probe_media, run_command, which_command

PASS = "PASS"
WARN = "WARN"
BLOCKED = "BLOCKED"
INCOMPLETE = "INCOMPLETE"


def _check(check_id: str, status: str, detail: str, **values) -> dict:
    return {"id": check_id, "status": status, "detail": detail, **values}


def _ffprobe_frames(video: Path, workspace: Path) -> tuple[int | None, str]:
    result = run_command(
        [
            *which_command("ffprobe"),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=nb_read_frames,nb_frames",
            "-of",
            "json",
            str(video),
        ],
        workspace,
        timeout=1200,
    )
    if result.exit_code != 0:
        return None, result.stderr[-500:]
    try:
        data = json.loads(result.stdout)
        stream = (data.get("streams") or [{}])[0]
        value = stream.get("nb_read_frames") or stream.get("nb_frames")
        return (int(value) if value not in (None, "N/A") else None), ""
    except (ValueError, IndexError, TypeError) as exc:
        return None, str(exc)


def _measure_loudness(video: Path, workspace: Path) -> dict:
    result = run_command(
        [
            *which_command("ffmpeg"),
            "-hide_banner",
            "-nostats",
            "-i",
            str(video),
            "-map",
            "0:a:0",
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ],
        workspace,
        timeout=1200,
    )
    text = result.stderr + "\n" + result.stdout
    summary = text[text.rfind("Summary:") :] if "Summary:" in text else text
    integrated = re.search(r"I:\s*(-?[0-9.]+)\s*LUFS", summary)
    peak = re.search(r"Peak:\s*(-?[0-9.]+)\s*dBFS", summary)
    lra = re.search(r"LRA:\s*(-?[0-9.]+)\s*LU", summary)
    return {
        "integrated_lufs": float(integrated.group(1)) if integrated else None,
        "true_peak_dbfs": float(peak.group(1)) if peak else None,
        "lra_lu": float(lra.group(1)) if lra else None,
        "exit_code": result.exit_code,
    }


def _silence_intervals(video: Path, workspace: Path) -> list[dict]:
    result = run_command(
        [
            *which_command("ffmpeg"),
            "-hide_banner",
            "-nostats",
            "-i",
            str(video),
            "-map",
            "0:a:0",
            "-af",
            "silencedetect=noise=-50dB:d=2.0",
            "-f",
            "null",
            "-",
        ],
        workspace,
        timeout=1200,
    )
    text = result.stderr + "\n" + result.stdout
    starts = [float(v) for v in re.findall(r"silence_start:\s*([0-9.]+)", text)]
    ends = [float(v) for v in re.findall(r"silence_end:\s*([0-9.]+)", text)]
    return [
        {"start_s": start, "end_s": end, "duration_s": round(end - start, 3)}
        for start, end in zip(starts, ends)
        if end > start
    ]


def _parse_srt(text: str) -> list[dict]:
    cues = []
    blocks = re.split(r"\r?\n\s*\r?\n", text.strip())
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        match = re.match(
            r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)",
            lines[1],
        )
        if not match:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = (int(part) for part in match.groups())
        start = ((h1 * 60 + m1) * 60 + s1) * 1000 + ms1
        end = ((h2 * 60 + m2) * 60 + s2) * 1000 + ms2
        cues.append({"start_ms": start, "end_ms": end, "text": "\n".join(lines[2:])})
    return cues


def run_media_qc(
    workspace: Path,
    paths: LessonPaths,
    *,
    video_name: str = "course-video-mixed.mp4",
) -> tuple[dict, Path]:
    workspace = workspace.resolve()
    final_dir = paths.build_root / "final"
    video = final_dir / video_name
    if not video.is_file():
        alternative = final_dir / "course-video.mp4"
        video = alternative if alternative.is_file() else video

    report: dict = {
        "schema_version": 1,
        "lesson": paths.slug,
        "video": str(video),
        "checks": [],
        "status": INCOMPLETE,
    }
    target = paths.build_root / "quality" / "media-qc.json"

    def finish(status: str) -> tuple[dict, Path]:
        report["status"] = status
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return report, target

    if not video.is_file():
        report["checks"].append(
            _check("media.file", INCOMPLETE, f"no final video found under {final_dir}")
        )
        return finish(INCOMPLETE)

    info = probe_media(video)
    report["info"] = info.as_dict()
    checks = report["checks"]

    ok = (info.duration or 0) > 0 and info.width and info.height
    checks.append(
        _check(
            "media.decode",
            PASS if ok else BLOCKED,
            "decoded by ffprobe" if ok else "ffprobe did not return usable streams",
            duration_s=info.duration,
            width=info.width,
            height=info.height,
            fps=info.fps,
            has_audio=info.has_audio,
        )
    )

    width, height = paths.lesson.outputs.resolution
    format_ok = info.width == width and info.height == height
    fps_ok = info.fps is not None and abs(float(info.fps) - paths.lesson.outputs.fps) < 0.01
    checks.append(
        _check(
            "media.format",
            PASS if format_ok and fps_ok else BLOCKED,
            f"declared {width}x{height}@{paths.lesson.outputs.fps}; "
            f"actual {info.width}x{info.height}@{info.fps}",
        )
    )

    frames, frame_error = _ffprobe_frames(video, workspace)
    expected_frames = (
        round((info.duration or 0) * paths.lesson.outputs.fps)
        if info.duration
        else None
    )
    frames_ok = (
        frames is not None
        and expected_frames is not None
        and abs(frames - expected_frames) <= 2
    )
    checks.append(
        _check(
            "media.frames",
            PASS if frames_ok else WARN,
            f"frames={frames}, expected≈{expected_frames}"
            + (f" ({frame_error})" if frame_error else ""),
        )
    )

    if not info.has_audio:
        checks.append(
            _check("media.audio", BLOCKED, "final video has no audio stream")
        )
    else:
        loudness = _measure_loudness(video, workspace)
        checks.append(
            _check(
                "media.loudness",
                PASS
                if loudness["integrated_lufs"] is not None
                else INCOMPLETE,
                "EBU R128 integrated loudness",
                **loudness,
            )
        )
        integrated = loudness["integrated_lufs"]
        peak = loudness["true_peak_dbfs"]
        loud_ok = (
            integrated is not None
            and -18.0 <= integrated <= -14.0
            and (peak is None or peak <= -1.0)
        )
        if loudness["integrated_lufs"] is not None:
            checks.append(
                _check(
                    "media.level_policy",
                    PASS if loud_ok else WARN,
                    "target -16 LUFS, true peak <= -1 dBFS",
                    integrated_lufs=integrated,
                    true_peak_dbfs=peak,
                )
            )
        silences = _silence_intervals(video, workspace)
        report["silences"] = silences
        checks.append(
            _check(
                "media.silence",
                PASS if not silences else WARN,
                f"{len(silences)} silence interval(s) >= 2 s at -50 dB",
                intervals=silences[:20],
            )
        )

    black, freeze = detect_black_freeze(
        video, workspace, paths.build_root / "logs" / "media-qc-blackfreeze.log"
    )
    report["black_intervals"] = black
    report["freeze_intervals"] = freeze
    checks.append(
        _check(
            "media.black",
            PASS if not black else BLOCKED,
            f"{len(black)} black interval(s)",
            intervals=black[:20],
        )
    )
    checks.append(
        _check(
            "media.freeze",
            PASS if not freeze else WARN,
            f"{len(freeze)} frozen interval(s)",
            intervals=freeze[:20],
        )
    )

    subtitle_rel = paths.lesson.content.subtitles
    subtitle_path = paths.subtitles_path() if paths.lesson.subtitles.enabled else None
    if not paths.lesson.subtitles.enabled or not subtitle_rel or subtitle_path is None:
        checks.append(
            _check("media.subtitles", INCOMPLETE, "subtitles are disabled")
        )
    elif not subtitle_path.is_file():
        checks.append(
            _check(
                "media.subtitles",
                INCOMPLETE,
                f"subtitle file not found: {subtitle_rel}",
            )
        )
    else:
        cues = _parse_srt(subtitle_path.read_text(encoding="utf-8"))
        duration_ms = int((info.duration or 0) * 1000)
        overlaps = 0
        too_short = 0
        out_of_range = 0
        previous_end = -1
        for cue in cues:
            if cue["start_ms"] < previous_end:
                overlaps += 1
            previous_end = max(previous_end, cue["end_ms"])
            if cue["end_ms"] - cue["start_ms"] < 500:
                too_short += 1
            if cue["end_ms"] > duration_ms + 500:
                out_of_range += 1
        subtitle_status = PASS
        if not cues or out_of_range or overlaps:
            subtitle_status = WARN
        if too_short:
            subtitle_status = WARN
        checks.append(
            _check(
                "media.subtitles",
                subtitle_status,
                f"{len(cues)} cues; overlaps={overlaps}; too_short={too_short}; "
                f"out_of_range={out_of_range}",
                cue_count=len(cues),
                overlaps=overlaps,
                too_short=too_short,
                out_of_range=out_of_range,
            )
        )

    statuses = [check["status"] for check in checks]
    if BLOCKED in statuses:
        return finish(BLOCKED)
    if INCOMPLETE in statuses:
        return finish(INCOMPLETE)
    if WARN in statuses:
        return finish(WARN)
    return finish(PASS)


__all__ = ["BLOCKED", "INCOMPLETE", "PASS", "WARN", "run_media_qc"]
