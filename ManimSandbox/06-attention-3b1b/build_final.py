"""Assemble the finished piece: silent Manim render + narration track.

Reads build/attention-3b1b/timing.json, lays each narration segment at its
timeline position, normalises loudness, and muxes with the rendered video.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build" / "attention-3b1b"
VIDEO_CANDIDATES = [
    OUT / "render" / "AttentionScene.mp4",
    OUT / "media" / "videos" / "attention" / "1080p60" / "AttentionScene.mp4",
    OUT / "media" / "videos" / "attention" / "1080p30" / "AttentionScene.mp4",
]
TIMING = OUT / "timing.json"
NARRATION = OUT / "narration.wav"
FINAL = OUT / "attention.mp4"


def build_narration() -> None:
    data = json.loads(TIMING.read_text(encoding="utf-8"))
    segs = data["segments"]
    args = ["ffmpeg", "-v", "error", "-y"]
    for s in segs:
        args += ["-i", str(OUT / "audio" / f"{s['id']}.wav")]
    chains, labels = [], []
    for i, s in enumerate(segs):
        ms = int(round(s["start"] * 1000))
        chains.append(f"[{i}:a]adelay={ms}:all=1[a{i}]")
        labels.append(f"[a{i}]")
    chains.append(f"{''.join(labels)}amix=inputs={len(segs)}:duration=longest:normalize=0[mix]")
    chains.append("[mix]loudnorm=I=-16:TP=-1.6:LRA=11[out]")
    args += ["-filter_complex", ";".join(chains), "-map", "[out]", "-ar", "48000", str(NARRATION)]
    subprocess.run(args, check=True)


def mux() -> None:
    dur = json.loads(TIMING.read_text(encoding="utf-8"))["total"]
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-i", str(VIDEO),
            "-i", str(NARRATION),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-t", f"{dur:.3f}",
            "-movflags", "+faststart",
            str(FINAL),
        ],
        check=True,
    )


def main() -> int:
    video = next((v for v in VIDEO_CANDIDATES if v.exists()), None)
    if video is None:
        print("missing render: " + " | ".join(str(v) for v in VIDEO_CANDIDATES))
        return 1
    globals()["VIDEO"] = video
    if not TIMING.exists():
        print(f"missing timing: {TIMING}")
        return 1
    build_narration()
    mux()
    print(f"final: {FINAL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
