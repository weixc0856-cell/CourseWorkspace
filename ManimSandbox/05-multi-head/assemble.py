"""Assemble E6.5: narration WAV + SRT + final mux, with real checks.

The scene is rendered separately. This script only uses ffmpeg/ffprobe and
standard library. It writes build/manim-multi-head/e6.5/manifest.json and
exits 1 if any automatic check fails.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "manim-multi-head" / "e6.5"
VIDEO = BUILD / "media" / "videos" / "multi_head" / "1080p30" / "MultiHeadScene.mp4"
TIMING = BUILD / "timing.json"
SEGMENTS = BUILD / "narration" / "segments"
NARRATION = BUILD / "narration.wav"
SUBTITLES = BUILD / "subtitles.srt"
FINAL = BUILD / "final.mp4"
MANIFEST = BUILD / "manifest.json"

CUES = [
    (0.5, 7.5, "同一个输入 X，同时送进两个头。"),
    (7.5, 15.0, "两个头共享输入，但各自拥有独立的 Q、K、V 权重。"),
    (16.5, 26.0, "头 1 用 W_Q1、W_K1、W_V1 把 X 投影成 Q1、K1、V1。"),
    (26.0, 35.5, "每个头 d_k = 2，投影矩阵是 4×2。"),
    (36.4, 46.0, "头 2 用另一组权重，得到 Q2、K2、V2。"),
    (46.0, 55.7, "以 cat 为例：头 1 关注 The，头 2 关注 sat。"),
    (56.7, 61.5, "两个头各得 2 维 context，按列拼接成 4 维。"),
    (61.5, 66.8, "拼接不是相加：2 + 2 = 4。"),
    (67.8, 76.0, "输出投影 W_O 把 4 维重新混合成 4 维。"),
    (76.0, 84.4, "最终每个 token 仍得到一个 4 维表示。"),
]

BEATS = ["b1", "b2", "b3", "b4", "b5"]


def run(argv: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(argv)}\n{detail}")
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path) -> dict:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            (
                "format=duration,size:"
                "stream=codec_type,codec_name,width,height,r_frame_rate,"
                "avg_frame_rate,duration,nb_frames,sample_rate,channels"
            ),
            "-of",
            "json",
            str(path),
        ]
    )
    return json.loads(result.stdout)


def stream(payload: dict, kind: str) -> dict | None:
    return next((item for item in payload.get("streams", []) if item.get("codec_type") == kind), None)


def duration_s(payload: dict) -> float:
    return float(payload.get("format", {}).get("duration") or 0.0)


def srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hours, remainder = divmod(ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def build_narration(timing: dict, video_duration: float) -> list[dict]:
    starts = [float(timing[f"{beat}_start"]) for beat in BEATS]
    segment_paths = [SEGMENTS / f"e65-{beat}.wav" for beat in BEATS]
    for path in segment_paths:
        if not path.is_file():
            raise RuntimeError(f"missing narration segment: {path}")
    segment_probes = [probe(path) for path in segment_paths]
    durations = [duration_s(item) for item in segment_probes]

    inputs: list[str] = [
        "-f",
        "lavfi",
        "-t",
        f"{video_duration:.3f}",
        "-i",
        "anullsrc=r=48000:cl=mono",
    ]
    for path in segment_paths:
        inputs.extend(["-i", str(path)])
    filters = []
    labels = ["[0:a]"]
    for index, start in enumerate(starts, start=1):
        delay_ms = int(round(start * 1000))
        filters.append(f"[{index}:a]adelay={delay_ms}|{delay_ms}[a{index}]")
        labels.append(f"[a{index}]")
    filters.append(
        "".join(labels)
        + f"amix=inputs={len(labels)}:duration=first:normalize=0[out]"
    )
    run(
        [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[out]",
            "-c:a",
            "pcm_s16le",
            str(NARRATION),
        ]
    )
    return [
        {
            "beat": beat,
            "file": path.relative_to(ROOT).as_posix(),
            "start_s": round(start, 3),
            "duration_s": round(dur, 3),
            "sha256": sha256_file(path),
        }
        for beat, path, start, dur in zip(BEATS, segment_paths, starts, durations)
    ]


def write_srt() -> None:
    blocks = []
    for index, (start, end, text) in enumerate(CUES, start=1):
        blocks.append(f"{index}\n{srt_time(start)} --> {srt_time(end)}\n{text}")
    SUBTITLES.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def mux() -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(VIDEO),
            "-i",
            str(NARRATION),
            "-i",
            str(SUBTITLES),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-map",
            "2:s:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=chi",
            "-movflags",
            "+faststart",
            str(FINAL),
        ]
    )


def main() -> int:
    for path in (VIDEO, TIMING):
        if not path.is_file():
            raise RuntimeError(f"missing render input: {path}")
    timing = json.loads(TIMING.read_text(encoding="utf-8"))
    video_probe = probe(VIDEO)
    video_dur = duration_s(video_probe)
    checks: dict[str, dict] = {}

    def add(check_id: str, ok: bool, detail: str) -> None:
        checks[check_id] = {"status": "pass" if ok else "fail", "detail": detail}

    video_stream = stream(video_probe, "video")
    add("video_exists", VIDEO.is_file(), VIDEO.relative_to(ROOT).as_posix())
    add(
        "video_format",
        bool(
            video_stream
            and video_stream.get("width") == 1920
            and video_stream.get("height") == 1080
            and video_stream.get("r_frame_rate") == "30/1"
        ),
        f"1920x1080/30 expected, actual "
        f"{None if video_stream is None else (video_stream.get('width'), video_stream.get('height'), video_stream.get('r_frame_rate'))}",
    )
    add(
        "beats",
        all(f"{beat}_start" in timing and f"{beat}_end" in timing for beat in BEATS),
        "five beats with start/end marks",
    )

    segments = build_narration(timing, video_dur)
    for segment in segments:
        start = float(segment["start_s"])
        end = start + float(segment["duration_s"])
        beat_end = float(timing[f"{segment['beat']}_end"])
        add(
            f"narration_fit:{segment['beat']}",
            end <= beat_end + 0.05,
            f"segment {start:.3f}..{end:.3f}s, beat end {beat_end:.3f}s",
        )
    add(
        "narration_duration",
        abs(duration_s(probe(NARRATION)) - video_dur) <= 0.1,
        f"video {video_dur:.3f}s",
    )

    write_srt()
    beat_windows = [
        (float(timing[f"{beat}_start"]), float(timing[f"{beat}_end"]))
        for beat in BEATS
    ]
    cues_ok = len(CUES) == 10
    for start, end, text in CUES:
        inside = any(left <= start and end <= right for left, right in beat_windows)
        cues_ok = cues_ok and inside and end - start >= 1.5 and bool(text.strip())
    add("srt_cues", cues_ok, f"{len(CUES)} cues; every cue is inside a beat and >=1.5s")

    mux()
    final_probe = probe(FINAL)
    final_dur = duration_s(final_probe)
    final_video = stream(final_probe, "video")
    final_audio = stream(final_probe, "audio")
    final_subtitle = stream(final_probe, "subtitle")
    add(
        "final_duration",
        abs(final_dur - video_dur) <= 0.1,
        f"video {video_dur:.3f}s, final {final_dur:.3f}s",
    )
    add(
        "final_streams",
        final_video is not None and final_audio is not None and final_subtitle is not None,
        f"streams={[item.get('codec_type') for item in final_probe.get('streams', [])]}",
    )
    add(
        "final_format",
        bool(
            final_video
            and final_video.get("width") == 1920
            and final_video.get("height") == 1080
            and final_video.get("r_frame_rate") == "30/1"
        ),
        f"1920x1080/30 expected",
    )
    add(
        "final_audio_format",
        bool(final_audio and final_audio.get("sample_rate") == "48000" and final_audio.get("channels") == 1),
        f"{None if final_audio is None else (final_audio.get('sample_rate'), final_audio.get('channels'))}",
    )

    manifest = {
        "schema_version": 1,
        "lesson": "e6.5-multi-head",
        "resolution": [1920, 1080],
        "fps": 30,
        "beats": timing,
        "shots": [
            {
                "id": "multi-head",
                "scene": "MultiHeadScene",
                "file": VIDEO.relative_to(ROOT).as_posix(),
                "duration_s": round(video_dur, 3),
                "sha256": sha256_file(VIDEO),
            }
        ],
        "narration": {
            "file": NARRATION.relative_to(ROOT).as_posix(),
            "duration_s": round(duration_s(probe(NARRATION)), 3),
            "sha256": sha256_file(NARRATION),
            "segments": segments,
        },
        "subtitles": {
            "file": SUBTITLES.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(SUBTITLES),
            "cues": len(CUES),
        },
        "video": {
            "file": FINAL.relative_to(ROOT).as_posix(),
            "duration_s": round(final_dur, 3),
            "sha256": sha256_file(FINAL),
        },
        "checks": checks,
        "all_ok": all(item["status"] == "pass" for item in checks.values()),
    }
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for check_id, check in checks.items():
        print(f"[{check_id}] {check['status']}: {check['detail']}")
    print(f"wrote {FINAL}")
    print(f"wrote {MANIFEST}")
    return 0 if manifest["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
