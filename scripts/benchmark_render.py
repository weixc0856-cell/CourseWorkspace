"""R1-2 render benchmark: Manim / Blender / Remotion / FFmpeg.

Runs fixed scenes, samples process memory and GPU dedicated memory, and writes
one JSON per case plus a summary under build/r1/benchmark/.

Only rendering is measured. No LLM, TTS or network service is started.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "r1" / "benchmark"
GPU_COUNTER = r"\GPU Adapter Memory(*)\Dedicated Usage"


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def blender_exe() -> Path | None:
    env = os.environ.get("BLENDER_EXE")
    if env:
        return Path(env)
    cfg = ROOT / "config" / "tools.yaml"
    if cfg.is_file():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            match = re.search(r"executable:\s*\"?([^\"]+)\"?\s*$", line)
            if match and "blender" in line.lower():
                return Path(match.group(1).strip())
    return None


def tasklist_memory_kb(pid: int) -> int | None:
    try:
        raw = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
        row = next(csv.reader(io.StringIO(raw)), None)
        if not row or len(row) < 5:
            return None
        digits = re.sub(r"[^0-9]", "", row[4])
        return int(digits) if digits else None
    except Exception:
        return None


def gpu_dedicated_mb() -> float | None:
    try:
        raw = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                f"(Get-Counter -Counter '{GPU_COUNTER}' -ErrorAction SilentlyContinue)"
                ".CounterSamples | ForEach-Object { $_.CookedValue }",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
        values = [float(v) for v in raw.split() if v.replace(".", "", 1).isdigit()]
        return round(max(values) / (1024 * 1024), 1) if values else None
    except Exception:
        return None


def run(case: str, command: list[str], cwd: Path, timeout: int = 3600) -> dict:
    print(f"\n=== {case} ===\n{' '.join(command)}", flush=True)
    log_path = OUT / f"{case}.log"
    started = time.monotonic()
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        peak_mem = 0
        peak_gpu = 0.0
        last_gpu_sample = 0.0
        try:
            while True:
                if process.poll() is not None:
                    break
                if time.monotonic() - started > timeout:
                    process.kill()
                    raise TimeoutError(f"{case} exceeded {timeout}s")
                mem = tasklist_memory_kb(process.pid)
                if mem:
                    peak_mem = max(peak_mem, mem)
                if time.monotonic() - last_gpu_sample >= 5:
                    gpu = gpu_dedicated_mb()
                    if gpu is not None:
                        peak_gpu = max(peak_gpu, gpu)
                    last_gpu_sample = time.monotonic()
                time.sleep(1.0)
            code = process.returncode
        finally:
            if process.poll() is None:
                process.kill()
    elapsed = round(time.monotonic() - started, 2)
    output_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
    result = {
        "case": case,
        "command": command,
        "cwd": str(cwd),
        "exit_code": code,
        "elapsed_s": elapsed,
        "peak_process_memory_mb": round(peak_mem / 1024, 1) if peak_mem else None,
        "peak_gpu_dedicated_mb": round(peak_gpu, 1) if peak_gpu else None,
        "log": str(log_path),
        "output_tail": output_lines,
        "finished_at": now(),
    }
    print(json.dumps({k: result[k] for k in ("case", "exit_code", "elapsed_s", "peak_process_memory_mb", "peak_gpu_dedicated_mb")}, ensure_ascii=False), flush=True)
    return result


def write_case(result: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{result['case']}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def probe(path: Path) -> dict:
    raw = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
            "-show_entries", "format=duration,size", "-of", "json", str(path),
        ],
        capture_output=True,
        text=True,
    ).stdout
    try:
        data = json.loads(raw)
        stream = (data.get("streams") or [{}])[0]
        fmt = data.get("format") or {}
        return {
            "width": stream.get("width"),
            "height": stream.get("height"),
            "fps": stream.get("r_frame_rate"),
            "frames": stream.get("nb_frames"),
            "duration_s": float(fmt["duration"]) if fmt.get("duration") else None,
            "bytes": int(fmt["size"]) if fmt.get("size") else path.stat().st_size,
        }
    except Exception:
        return {"bytes": path.stat().st_size if path.exists() else None}


def write_ass(path: Path) -> None:
    path.write_text(
        """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Bilingual,Arial,46,&H001A1A1A,&H001A1A1A,&H00FFFFFF,&H00000000,0,0,0,0,100,100,0,0,1,3,0,2,80,80,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.10,0:00:02.40,Bilingual,,0,0,0,,R1 subtitle burn benchmark
Dialogue: 0,0:00:02.40,0:00:04.80,Bilingual,,0,0,0,,{\\fnMicrosoft YaHei}字幕烧录基准测试
""",
        encoding="utf-8",
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    exe = blender_exe()
    if exe is None or not exe.is_file():
        print("ERROR: Blender executable not found; set config/tools.yaml or BLENDER_EXE", file=sys.stderr)
        return 3

    cases: list[tuple[str, list[str], Path]] = [
        (
            "blender-eevee",
            [str(exe), "-b", "--factory-startup", "--python-exit-code", "1",
             "--python", str(ROOT / "BlenderStudio/scripts/render_smoke.py"), "--",
             "--lesson", "r1-smoke", "--out", str(ROOT / "build/r1-smoke/blender/bench-eevee.mp4"),
             "--engine", "BLENDER_EEVEE", "--samples", "8", "--seconds", "2"],
            ROOT,
        ),
        (
            "blender-cycles-cpu",
            [str(exe), "-b", "--factory-startup", "--python-exit-code", "1",
             "--python", str(ROOT / "BlenderStudio/scripts/render_smoke.py"), "--",
             "--lesson", "r1-smoke", "--out", str(ROOT / "build/r1-smoke/blender/bench-cycles-cpu.mp4"),
             "--engine", "CYCLES", "--device", "CPU", "--samples", "8", "--seconds", "2"],
            ROOT,
        ),
        (
            "blender-cycles-gpu",
            [str(exe), "-b", "--factory-startup", "--python-exit-code", "1",
             "--python", str(ROOT / "BlenderStudio/scripts/render_smoke.py"), "--",
             "--lesson", "r1-smoke", "--out", str(ROOT / "build/r1-smoke/blender/bench-cycles-gpu.mp4"),
             "--engine", "CYCLES", "--device", "GPU", "--samples", "8", "--seconds", "2"],
            ROOT,
        ),
        (
            "manim-draft",
            ["uv", "run", "--project", "ManimSandbox", "manim", "render", "-ql", "--fps", "15",
             "--media_dir", str(ROOT / "build/r1/benchmark/manim-draft"),
             "ManimSandbox/00-r1-smoke/smoke_scene.py", "SmokeScene"],
            ROOT,
        ),
        (
            "manim-final",
            ["uv", "run", "--project", "ManimSandbox", "manim", "render", "-r", "1920,1080",
             "--fps", "30", "--media_dir", str(ROOT / "build/r1/benchmark/manim-final"),
             "ManimSandbox/00-r1-smoke/smoke_scene.py", "SmokeScene"],
            ROOT,
        ),
        (
            "remotion-c1",
            ["npx.cmd", "remotion", "render", "src/index.ts", "R1Smoke",
             str(ROOT / "build/r1/benchmark/remotion-c1.mp4"), "--concurrency=1", "--log=error"],
            ROOT / "RemotionStudio",
        ),
        (
            "remotion-c4",
            ["npx.cmd", "remotion", "render", "src/index.ts", "R1Smoke",
             str(ROOT / "build/r1/benchmark/remotion-c4.mp4"), "--concurrency=4", "--log=error"],
            ROOT / "RemotionStudio",
        ),
    ]

    summary = []
    for case, command, cwd in cases:
        try:
            result = run(case, command, cwd)
            output = ROOT / "build/r1-smoke/blender" / f"bench-{case.split('-', 1)[1]}.mp4" \
                if case.startswith("blender-") else None
            if case.startswith("manim-"):
                media = ROOT / "build/r1/benchmark" / case / "videos/smoke_scene"
                matches = sorted(media.glob("*/SmokeScene.mp4"))
                output = matches[-1] if matches else None
            elif case.startswith("remotion-"):
                output = ROOT / "build/r1/benchmark" / f"{case}.mp4"
            result["output"] = str(output) if output else None
            result["media"] = probe(output) if output and output.exists() else None
            summary.append(result)
        except Exception as exc:  # noqa: BLE001
            result = {"case": case, "command": command, "exit_code": None, "error": f"{type(exc).__name__}: {exc}"}
            summary.append(result)
        write_case(result)

    # FFmpeg burn-in comparison on the 5 s Remotion smoke.
    smoke = ROOT / "build/r1/remotion/smoke.mp4"
    ass = OUT / "bench.ass"
    write_ass(ass)
    for encoder, args in (
        ("ffmpeg-qsv", ["-c:v", "h264_qsv", "-global_quality", "20", "-preset", "medium"]),
        ("ffmpeg-libx264", ["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p"]),
    ):
        out = OUT / f"{encoder}.mp4"
        # Windows: the colon in <WORKSPACE>/... would be parsed as an option separator.
        ass_filter = "ass='" + ass.as_posix().replace(":", "\\:") + "'"
        command = ["ffmpeg", "-y", "-i", str(smoke), "-vf", ass_filter,
                   *args, "-c:a", "copy", "-movflags", "+faststart", str(out)]
        try:
            result = run(encoder, command, ROOT)
            result["output"] = str(out)
            result["media"] = probe(out) if out.exists() else None
        except Exception as exc:  # noqa: BLE001
            result = {"case": encoder, "command": command, "exit_code": None, "error": f"{type(exc).__name__}: {exc}"}
        summary.append(result)
        write_case(result)

    (OUT / "summary.json").write_text(
        json.dumps(
            {
                "generated_at": now(),
                "blender_exe": str(exe),
                "cases": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nWROTE {OUT / 'summary.json'}")
    return 0 if all(c.get("exit_code") == 0 for c in summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())
