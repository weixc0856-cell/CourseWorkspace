"""Assemble rendered shots into one animatic or film with optional labels.

This is the delivery-side counterpart to the environment/shot split: Blender
renders each shot, this script concatenates them in shot-list order and muxes
the shared audio.  It does not re-time or re-encode individual shots beyond a
common width/height/fps, so a shot stays the unit of review.

Usage:
    uv run --project CourseControl python scripts/assemble_shots.py \
        --out <content_root>/.../animatic.mp4 \
        --audio <content_root>/.../ab-audio.m4a \
        --shot <a1.mp4> --label "A1 / RIDGE" \
        --shot <a2.mp4> --label "A2 / VALLEY" \
        --shot <a3.mp4> --label "A3 / WATER"
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=width,height,r_frame_rate", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(out.stdout)
    stream = next(item for item in data["streams"] if item.get("width"))
    num, den = stream["r_frame_rate"].split("/")
    return {
        "duration": float(data["format"]["duration"]),
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "fps": float(num) / float(den),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--shot", action="append", required=True, type=Path)
    parser.add_argument("--label", action="append", default=[])
    parser.add_argument("--audio", type=Path, default=None)
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--fps", type=int, default=None)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    clips = [probe(path) for path in args.shot]
    width = args.width or clips[0]["width"]
    height = args.height or clips[0]["height"]
    fps = args.fps or round(clips[0]["fps"])

    filters = []
    for index in range(len(args.shot)):
        filters.append(
            f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[v{index}]"
        )
    filters.append("".join(f"[v{index}]" for index in range(len(args.shot)))
                   + f"concat=n={len(args.shot)}:v=1:a=0[base]")

    start = 0.0
    labels = []
    for index, (path, clip) in enumerate(zip(args.shot, clips)):
        label = args.label[index] if index < len(args.label) else path.stem
        end = start + clip["duration"] - 0.05
        safe = label.replace(":", chr(92) + ":").replace(chr(39), chr(92) + chr(39))
        labels.append(
            f"drawtext=text='{safe}':x=24:y=24:fontsize=22:fontcolor=white@0.85:"
            f"fontfile='C{chr(92)}:/Windows/Fonts/arialbd.ttf':enable='between(t,{start:.3f},{end:.3f})'"
        )
        start += clip["duration"]
    if labels:
        filters.append("[base]" + ",".join(labels) + "[vout]")
    else:
        filters.append("[base]copy[vout]")

    cmd = ["ffmpeg", "-y"]
    for path in args.shot:
        cmd += ["-i", str(path)]
    if args.audio:
        cmd += ["-i", str(args.audio)]
    cmd += ["-filter_complex", ";".join(filters), "-map", "[vout]"]
    if args.audio:
        cmd += ["-map", f"{len(args.shot)}:a"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-shortest", str(args.out)]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True)

    report = {
        "out": str(args.out),
        "width": width,
        "height": height,
        "fps": fps,
        "duration": start,
        "shots": [
            {"path": str(path), **clip, "label": args.label[i] if i < len(args.label) else path.stem}
            for i, (path, clip) in enumerate(zip(args.shot, clips))
        ],
        "audio": str(args.audio) if args.audio else None,
    }
    report_path = args.report or args.out.with_suffix(".json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
