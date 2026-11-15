"""Detect static holds in a sampled frame sequence.

Frames are dumped every N frames by RemotionStudio/scripts/frame-audit.mjs
(`--dump ... --step 15`). Consecutive frames whose mean pixel difference is
below EPSILON count as a hold; a hold of MIN_FRAMES or more is reported.
The report also carries the longest hold inside every beat, which says more
about pacing than a single red/green.

Usage:
    uv run --project CourseControl python scripts/static_hold.py --dir <frames> \
        --beats <episode-timing.json>
    uv run --project CourseControl python scripts/static_hold.py --selftest
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

EPSILON = 0.0002
DEFAULT_CUTS = (0, 18, 48, 88, 123, 153)  # chapter scene starts, seconds


def mean_diff(a: Path, b: Path) -> float:
    first = Image.open(a).convert("RGB")
    second = Image.open(b).convert("RGB")
    if second.size != first.size:
        second = second.resize(first.size)
    channels = ImageStat.Stat(ImageChops.difference(first, second)).mean
    return sum(channels) / (3 * 255)


def frame_number(path: Path) -> int:
    return int(path.stem.split("-")[1])


def analyse(paths: list[Path], step: int, fps: int, min_frames: int, cuts: tuple[float, ...]) -> dict:
    paths = sorted(paths, key=frame_number)
    holds: list[dict] = []
    run_start: int | None = None
    run_last: int | None = None
    for first, second in zip(paths, paths[1:]):
        frame_a = frame_number(first)
        frame_b = frame_number(second)
        static = mean_diff(first, second) <= EPSILON
        if static:
            if run_start is None:
                run_start = frame_a
            run_last = frame_b
            continue
        if run_start is not None and run_last is not None:
            holds.append({"start_frame": run_start, "end_frame": run_last})
        run_start = run_last = None
    if run_start is not None and run_last is not None:
        holds.append({"start_frame": run_start, "end_frame": run_last})

    durations = []
    for hold in holds:
        frames = hold["end_frame"] - hold["start_frame"]
        hold["seconds"] = round(frames / fps, 3)
        durations.append((hold["start_frame"], hold["end_frame"], hold["seconds"]))

    beats = []
    for index, start in enumerate(cuts):
        end = cuts[index + 1] if index + 1 < len(cuts) else None
        longest = 0.0
        for hold_start, hold_end, seconds in durations:
            start_frame = int(start * fps)
            end_frame = int(end * fps) if end is not None else 10**9
            if hold_end < start_frame or hold_start > end_frame:
                continue
            overlap = min(hold_end, end_frame) - max(hold_start, start_frame)
            longest = max(longest, overlap / fps)
        beats.append(
            {
                "index": index + 1,
                "start_s": start,
                "end_s": end,
                "max_static_s": round(longest, 3),
            }
        )

    violations = [item for item in holds if item["end_frame"] - item["start_frame"] >= min_frames]
    return {
        "schema_version": 1,
        "step_frames": step,
        "fps": fps,
        "min_frames": min_frames,
        "sampled": len(paths),
        "holds": holds,
        "violations": violations,
        "beats": beats,
    }


def selftest(root: Path) -> int:
    folder = root / "static-hold-selftest"
    folder.mkdir(parents=True, exist_ok=True)
    static = Image.new("RGB", (64, 64), (10, 10, 12))
    for index in range(6):
        static.save(folder / f"frame-{index * 15:05d}.png")
    moving = []
    for index in range(6):
        image = Image.new("RGB", (64, 64), (10, 10, 12))
        image.putpixel((index * 5, index * 5), (240, 120, 40))
        path = folder / f"m-{index * 15:05d}.png"
        image.save(path)
        moving.append(path)
    static_paths = sorted(folder.glob("frame-*.png"))
    report = analyse(static_paths, 15, 30, 60, (0, 90))
    moving_report = analyse(moving, 15, 30, 60, (0, 90))
    caught = len(report["violations"]) == 1
    no_false = not moving_report["violations"]
    print(f"static caught: {caught}  moving false positive: {not no_false}  (selftest {'PASS' if caught and no_false else 'FAIL'})")
    return 0 if caught and no_false else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path)
    parser.add_argument("--film", type=Path)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--beats", type=Path)
    parser.add_argument("--step", type=int, default=15)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--min-seconds", type=float, default=2.0)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        return selftest(Path(args.dir) if args.dir else Path.cwd() / "build")

    source = "audit-render"
    expected = None
    if args.film:
        film = args.film
        if not film.is_file():
            print(f"film not found: {film}")
            return 2
        work = args.work or (film.parent / "static-hold")
        work.mkdir(parents=True, exist_ok=True)
        for stale in work.glob("frame-*.png"):
            stale.unlink()
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            print("ffmpeg not found on PATH")
            return 2
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=nb_frames,r_frame_rate,duration", "-of", "json", str(film)],
            capture_output=True, text=True, check=False,
        )
        try:
            info = json.loads(probe.stdout)["streams"][0]
            fps = int(round(eval(info["r_frame_rate"])))
            frames = int(info.get("nb_frames") or 0) or int(float(info["duration"]) * fps)
        except Exception as exc:  # noqa: BLE001
            print(f"cannot probe {film}: {exc}")
            return 2
        expected = math.ceil(frames / args.step)
        extract = subprocess.run(
            [ffmpeg, "-y", "-i", str(film), "-vf",
             "select='not(mod(n" + chr(92) + "," + str(args.step) + "))'",
             "-vsync", "0", str(work / "frame-%05d.png")],
            capture_output=True, text=True, check=False,
        )
        if extract.returncode != 0:
            print(extract.stderr[-800:])
            return 2
        args.dir = work
        source = "film"

    if not args.dir or not args.dir.is_dir():
        print("frame directory not found")
        return 2
    cuts = DEFAULT_CUTS
    if args.beats and args.beats.is_file():
        data = json.loads(args.beats.read_text(encoding="utf-8"))
        starts = [0.0]
        for beat in data.get("beats") or []:
            starts.append(float(beat.get("start_s") or 0))
        cuts = tuple(sorted(set(starts)))
    report = analyse(
        list(args.dir.glob("frame-*.png")),
        args.step,
        args.fps,
        int(args.min_seconds * args.fps),
        cuts,
    )
    report["source"] = source
    report["expected"] = expected
    report["incomplete"] = expected is not None and report["sampled"] < expected
    report["coverage"] = (
        f"{report['sampled']}/{expected} sampled frames" if expected else f"{report['sampled']} sampled frames"
    )
    out = args.dir / "static-hold.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for beat in report["beats"]:
        print(f"  beat {beat['index']}: max_static {beat['max_static_s']}s")
    print(f"source: {source}  coverage: {report['coverage']}")
    print(f"violations: {len(report['violations'])}  sampled: {report['sampled']}  report: {out}")
    if report["incomplete"]:
        print(f"incomplete: sampled {report['sampled']}/{expected} - result is not a conclusion")
        return 2
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
