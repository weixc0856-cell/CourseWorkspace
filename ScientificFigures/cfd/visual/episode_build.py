"""Episode driver: frames -> props -> per-shot Remotion renders -> ffmpeg assembly.

Usage (all long-running, run in background and watch build/_logs/):
    python -I episode_build.py                # everything
    python -I episode_build.py --stage frames    # only VTK/matplotlib frame dirs
    python -I episode_build.py --stage composite # only Remotion per-shot mp4s
    python -I episode_build.py --stage assemble  # only ffmpeg concat
    python -I episode_build.py --only <shot>     # restrict to one shot
    python -I episode_build.py --force           # re-render even if complete

Segment boundaries are locked to BUILD-SPEC section 5: 60 / 150 / 300 / 450 / 540
/ 600 s. The driver fails immediately if the shot list does not sum to 600 s,
because the narration agent is building against those exact durations.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PY = sys.executable
WS = Path(__file__).resolve().parents[3]
VIS = WS / "ScientificFigures/cfd/visual"
REMO = WS / "RemotionStudio"
CONTENT = Path(os.environ.get("COURSEWORKSPACE_CONTENT_ROOT") or WS / "content_data")
BUILD = CONTENT / "build/t1-01-why-aerodynamics"
SHOTS_DIR = BUILD / "shots"
ANIM = BUILD / "anim"
VIDEO = BUILD / "video"
LOGS = CONTENT / "build/_logs"
PROPS = ANIM / "_episode_props.json"

# shot order == episode order; segment ids in comments
ORDER = [
    "t101_a_cp_curve",      # A 60 s
    "t101_b_geom_ground",   # B 90 s
    "t101_c_slant_vtk",     # C 150 s (90+60)
    "t101_c_slant_plot",
    "t101_d_wake_vtk",      # D 150 s (90+60)
    "t101_d_forces_plot",
    "t101_e_re_vtk",        # E 90 s
    "t101_f_25_vtk",        # F 60 s (30+30)
    "t101_f_35_vtk",
]
EXPECTED_SEGMENTS = {  # segment -> total seconds
    "A": 60.0, "B": 90.0, "C": 150.0, "D": 150.0, "E": 90.0, "F": 60.0,
}
SEG_OF = {
    "t101_a_cp_curve": "A", "t101_b_geom_ground": "B",
    "t101_c_slant_vtk": "C", "t101_c_slant_plot": "C",
    "t101_d_wake_vtk": "D", "t101_d_forces_plot": "D",
    "t101_e_re_vtk": "E", "t101_f_25_vtk": "F", "t101_f_35_vtk": "F",
}


def load_cfg(shot: str) -> dict:
    return json.loads((SHOTS_DIR / f"{shot}.json").read_text(encoding="utf-8"))


def validate_boundaries() -> list[dict]:
    cfgs = [load_cfg(s) for s in ORDER]
    seg = {}
    for c in cfgs:
        seg[SEG_OF[c["shot"]]] = seg.get(SEG_OF[c["shot"]], 0.0) + c["duration"]
    if seg != EXPECTED_SEGMENTS:
        raise SystemExit(f"FATAL segment durations {seg} != expected {EXPECTED_SEGMENTS}")
    total = sum(c["duration"] for c in cfgs)
    if abs(total - 600.0) > 0.01:
        raise SystemExit(f"FATAL total duration {total} != 600 s")
    fps = {c["fps"] for c in cfgs}
    if fps != {30}:
        raise SystemExit(f"FATAL fps set {fps} -- must be 30")
    return cfgs


def shot_is_complete(cfg: dict) -> bool:
    out = Path(cfg["out_dir"])
    n = int(round(cfg["duration"] * cfg["fps"]))
    sc = out / "anchors.json"
    if not sc.exists():
        return False
    try:
        d = json.loads(sc.read_text(encoding="utf-8"))
    except Exception:
        return False
    if d.get("shot") != cfg["shot"] or d.get("n_frames") != n or len(d.get("frames", [])) != n:
        return False
    missing = [f for f in range(n) if not (out / f"frame_{f:05d}.png").exists()]
    return not missing


def stage_frames(cfgs: list[dict], only: str | None, force: bool):
    for c in cfgs:
        if only and c["shot"] != only:
            continue
        out = Path(c["out_dir"])
        if not force and shot_is_complete(c):
            print(f"[frames] {c['shot']}: complete, skip (use --force to redo)")
            continue
        out.mkdir(parents=True, exist_ok=True)
        log = LOGS / f"render_{c['shot']}.log"
        t0 = time.time()
        print(f"[frames] {c['shot']} -> {log}")
        with log.open("w", encoding="utf-8") as fh:
            r = subprocess.run([PY, "-u", "-I", str(VIS / "shot_render.py"),
                                "--shot", str(SHOTS_DIR / f"{c['shot']}.json")],
                               stdout=fh, stderr=subprocess.STDOUT, text=True)
        if r.returncode != 0:
            raise SystemExit(f"FATAL frames {c['shot']} exit {r.returncode}; see {log}")
        print(f"[frames] {c['shot']}: done in {time.time()-t0:.0f}s")


def sync_fonts():
    src = REMO / "public/fonts"
    dst = ANIM / "fonts"
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.glob("*.woff2"):
        t = dst / f.name
        if not t.exists() or t.stat().st_size != f.stat().st_size:
            shutil.copyfile(f, t)
    print(f"[fonts] synced {len(list(dst.glob('*.woff2')))} woff2 -> {dst}")


def stage_props(cfgs: list[dict]):
    shots = []
    start = 0
    for c in cfgs:
        sc = json.loads((Path(c["out_dir"]) / "anchors.json").read_text(encoding="utf-8"))
        assert sc["shot"] == c["shot"]
        sc["start_frame"] = start
        start += sc["n_frames"]
        shots.append(sc)
    props = {"kind": "cfd_episode_props", "shots": shots, "total_frames": start}
    ANIM.joinpath("_episode").mkdir(exist_ok=True)
    PROPS.write_text(json.dumps(props, separators=(",", ":")), encoding="utf-8")
    print(f"[props] {PROPS} total_frames={start} ({start/30:.1f}s) size={PROPS.stat().st_size/1e6:.1f}MB")


def stage_composite(cfgs: list[dict], only: str | None, force: bool):
    VIDEO.mkdir(parents=True, exist_ok=True)
    sync_fonts()
    stage_props(cfgs)
    starts = {}
    acc = 0
    for c in cfgs:
        starts[c["shot"]] = acc
        acc += int(round(c["duration"] * c["fps"]))
    manifest = LOGS / "composite_manifest.json"
    done = {}
    if manifest.exists():
        done = json.loads(manifest.read_text(encoding="utf-8"))
    for c in cfgs:
        s = c["shot"]
        if only and s != only:
            continue
        mp4 = VIDEO / f"{s}.mp4"
        n = int(round(c["duration"] * c["fps"]))
        if mp4.exists() and not force and done.get(s, {}).get("frames") == n:
            print(f"[composite] {s}: exists, skip")
            continue
        log = LOGS / f"remotion_{s}.log"
        args = ["npx.cmd", "remotion", "render", "src/cfd-explainer/index.ts",
                "CfdEpisode", str(mp4),
                f"--props={PROPS}", f"--public-dir={ANIM}",
                f"--frames={starts[s]}-{starts[s] + n - 1}",
                "--codec=h264", "--image-format=png", "--crf=18",
                "--log=warn"]
        print(f"[composite] {s} frames {starts[s]}-{starts[s]+n-1} -> {log}")
        t0 = time.time()
        with log.open("w", encoding="utf-8") as fh:
            r = subprocess.run(args, cwd=str(REMO), stdout=fh, stderr=subprocess.STDOUT, text=True)
        print(f"[composite] {s}: exit {r.returncode} in {time.time()-t0:.0f}s")
        if r.returncode != 0:
            raise SystemExit(f"FATAL composite {s} exit {r.returncode}; see {log}")
        done[s] = {"frames": n, "start": starts[s], "exit": r.returncode,
                   "seconds": round(time.time() - t0, 1)}
        manifest.write_text(json.dumps(done, indent=1), encoding="utf-8")


def stage_assemble(cfgs: list[dict]):
    lst = BUILD / "anim/_assembly_concat.txt"
    lines = []
    for c in cfgs:
        p = (VIDEO / f"{c['shot']}.mp4").resolve()
        if not p.exists():
            raise SystemExit(f"FATAL missing per-shot mp4 {p}")
        lines.append(f"file '{p.as_posix()}'")
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = VIDEO / "t1-01-why-aerodynamics_EPISODE_draft.mp4"
    log = LOGS / "assemble_ffmpeg.log"
    args = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
            "-c:v", "libx264", "-preset", "medium", "-crf", "19",
            "-pix_fmt", "yuv420p", "-r", "30", "-g", "60",
            "-movflags", "+faststart", str(out)]
    with log.open("w", encoding="utf-8") as fh:
        r = subprocess.run(args, stdout=fh, stderr=subprocess.STDOUT, text=True)
    print(f"[assemble] exit {r.returncode} -> {out} (log {log})")
    if r.returncode != 0:
        raise SystemExit("FATAL assembly failed")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration:stream=width,height,avg_frame_rate,codec_name,pix_fmt",
                            "-of", "json", str(out)], capture_output=True, text=True)
    info = json.loads(probe.stdout)
    print("[assemble] ffprobe:", json.dumps(info))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all",
                    choices=["all", "frames", "composite", "assemble", "props"])
    ap.add_argument("--only", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    LOGS.mkdir(parents=True, exist_ok=True)
    cfgs = validate_boundaries()
    print(f"[validate] 9 shots sum to 600.0 s at 30 fps in segments "
          f"{'/'.join(str(EXPECTED_SEGMENTS[k]) for k in 'ABCDEF')}")
    if args.stage in ("all", "frames"):
        stage_frames(cfgs, args.only, args.force)
    if args.stage in ("all", "composite", "props"):
        sync_fonts()
        stage_props(cfgs)
    if args.stage in ("all", "composite"):
        stage_composite(cfgs, args.only, args.force)
    if args.stage in ("all", "assemble"):
        stage_assemble(cfgs)


if __name__ == "__main__":
    main()
