"""Build a clean-TTS short sample from the approved storyboard text.

This script does four things and nothing else:

1. synthesize one VoxCPM segment per caption cue;
2. concatenate the segments into a narration stem and measure every cue;
3. rewrite the scene durations to the measured narration;
4. emit provenance, the timed storyboard, and the bilingual SRT.

It never takes audio from an old master.  The script text is the existing
caption set; ``script_status`` is recorded as reused, not approved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from course_control.platform.utils import probe_audio, which_command
from course_control.voice.narrate import (
    TtsService,
    load_local_paths,
    segment_cache_key,
    synthesize,
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def run(command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{result.stderr[-800:]}")


def normalize(source: Path, target: Path, workspace: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            *which_command("ffmpeg"),
            "-v", "error", "-y", "-i", str(source),
            "-af", (
                "silenceremove=start_periods=1:start_duration=0.05:start_threshold=-40dB,"
                "areverse,"
                "silenceremove=start_periods=1:start_duration=0.05:start_threshold=-40dB,"
                "areverse"
            ),
            "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(target),
        ],
        workspace,
    )


def silence(target: Path, seconds: float, workspace: Path) -> None:
    run(
        [
            *which_command("ffmpeg"),
            "-v", "error", "-y", "-f", "lavfi",
            "-i", f"anullsrc=r=48000:cl=mono", "-t", f"{seconds:.3f}",
            "-c:a", "pcm_s16le", str(target),
        ],
        workspace,
    )


def concat(paths: list[Path], target: Path, workspace: Path) -> None:
    listing = target.with_suffix(".txt")
    listing.write_text(
        "\n".join(f"file '{path.as_posix()}'" for path in paths) + "\n", encoding="utf-8"
    )
    run(
        [
            *which_command("ffmpeg"),
            "-v", "error", "-y", "-f", "concat", "-safe", "0",
            "-i", str(listing), "-c", "copy", str(target),
        ],
        workspace,
    )


def srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--storyboard", type=Path, required=True)
    parser.add_argument("--sample-id", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--gap", type=float, default=0.18)
    parser.add_argument("--tail", type=float, default=0.35)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    board = json.loads(args.storyboard.read_text(encoding="utf-8"))
    cues = board["captions"]
    scenes = board["scenes"]

    # Map each cue to the scene whose original window contains its midpoint.
    cursor = 0.0
    bounds = []
    for scene in scenes:
        bounds.append((scene["id"], cursor, cursor + float(scene["duration_s"])))
        cursor += float(scene["duration_s"])
    assigned = {scene_id: [] for scene_id, _, _ in bounds}
    for index, cue in enumerate(cues, start=1):
        midpoint = (float(cue["start_s"]) + float(cue["end_s"])) / 2
        for scene_id, start, end in bounds:
            if start <= midpoint < end:
                assigned[scene_id].append((index, cue))
                break

    config = load_local_paths(workspace)
    tts = config.get("tts") or {}
    ai_root = Path(config.get("ai_root") or "").resolve()
    runtime = Path(tts.get("runtime_dir") or (ai_root / "VoxCPM-Runtime"))
    voice = Path(tts.get("voice_ref_en") or tts.get("voice_ref"))
    prompt = str(tts.get("prompt_text_en") or tts.get("prompt_text") or "")
    if not voice.is_file():
        raise SystemExit(f"voice reference missing: {voice}")

    segments_dir = out / "narration" / "segments"
    normalized_dir = out / "narration" / "normalized"
    segments_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    service = TtsService(
        workspace,
        ai_root=ai_root,
        runtime_dir=runtime,
        log_path=out / "tts-server.log",
        start_service=True,
        wait_timeout_s=1800,
    )
    segment_records = []
    scene_segments: dict[str, list[Path]] = {scene_id: [] for scene_id in assigned}
    measured: dict[int, dict] = {}
    with service:
        health = service.status().get("health") or {}
        for scene in scenes:
            scene_id = scene["id"]
            for index, cue in assigned[scene_id]:
                text = str(cue.get("tts") or cue["en"]).strip()
                key = segment_cache_key(text, voice, prompt)
                audio = segments_dir / f"cue-{index:02d}.wav"
                meta_path = audio.with_suffix(".meta.json")
                cached = False
                if audio.is_file() and meta_path.is_file():
                    try:
                        cached = json.loads(meta_path.read_text(encoding="utf-8")).get("key") == key
                    except (OSError, ValueError):
                        cached = False
                if not cached:
                    result = synthesize(
                        service.base_url, text, voice, prompt, audio,
                        timeout_s=600, text_frontend=True,
                    )
                    meta_path.write_text(
                        json.dumps({"key": key, "result": result, "text": text}, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                norm = normalized_dir / f"cue-{index:02d}.wav"
                normalize(audio, norm, workspace)
                duration = float(probe_audio(norm))
                measured[index] = {
                    "index": index,
                    "scene_id": scene_id,
                    "text": text,
                    "zh": str(cue.get("zh") or ""),
                    "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "display_text": str(cue["en"]),
                    "audio_path": str(audio),
                    "audio_sha256": sha(audio),
                    "duration_s": round(duration, 3),
                }
                scene_segments[scene_id].append(norm)

    silence_paths: dict[float, Path] = {}
    for seconds in sorted({args.gap, args.tail}):
        target = normalized_dir / f"silence-{seconds:.3f}.wav"
        if not target.is_file():
            silence(target, seconds, workspace)
        silence_paths[seconds] = target

    stem_parts: list[Path] = []
    scene_durations: dict[str, float] = {}
    timeline_cues = []
    clock = 0.0
    for scene in scenes:
        scene_id = scene["id"]
        parts: list[Path] = []
        for offset, (index, cue) in enumerate(assigned[scene_id]):
            if offset:
                parts.append(silence_paths[args.gap])
            parts.append(normalized_dir / f"cue-{index:02d}.wav")
        parts.append(silence_paths[args.tail])
        scene_audio = normalized_dir / f"scene-{scene_id}.wav"
        concat(parts, scene_audio, workspace)
        scene_duration = float(probe_audio(scene_audio))
        scene_durations[scene_id] = round(scene_duration, 3)

        local = 0.0
        for offset, (index, cue) in enumerate(assigned[scene_id]):
            if offset:
                local += args.gap
            duration = float(measured[index]["duration_s"])
            start = round(clock + local, 3)
            end = round(start + duration, 3)
            measured[index]["measured_start_s"] = start
            measured[index]["measured_end_s"] = end
            timeline_cues.append(
                {
                    "index": index,
                    "start_s": start,
                    "end_s": end,
                    "en": measured[index]["display_text"],
                    "zh": measured[index]["zh"],
                    "tts": cue.get("tts"),
                    "scene_id": scene_id,
                }
            )
            local += duration
        clock = round(clock + scene_duration, 3)
        stem_parts.append(scene_audio)

    stem = out / "narration" / "narration.wav"
    concat(stem_parts, stem, workspace)
    normalized_stem = out / "narration" / "narration.norm.wav"
    run(
        [
            *which_command("ffmpeg"),
            "-v", "error", "-y", "-i", str(stem),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(normalized_stem),
        ],
        workspace,
    )
    normalized_stem.replace(stem)
    total = float(probe_audio(stem))
    if not (90.0 <= total <= 180.0):
        raise SystemExit(f"narration is {total:.2f}s, outside 90-180s")

    timed_scenes = []
    for scene in scenes:
        timed_scenes.append({**scene, "duration_s": scene_durations[scene["id"]]})
    audio_target = f"staging/audio/{args.sample_id}.wav"
    timed = {
        **{k: v for k, v in board.items() if k != "captions"},
        "audio": audio_target,
        "scenes": timed_scenes,
        "captions": [
            {
                "index": c["index"],
                "start_s": c["start_s"], "end_s": c["end_s"],
                "en": c["en"], "zh": c["zh"],
                **({"tts": c["tts"]} if c.get("tts") else {}),
            }
            for c in timeline_cues
        ],
    }
    timed_path = out / "storyboard.timed.json"
    timed_path.write_text(json.dumps(timed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    staging = workspace / "RemotionStudio" / "public" / "staging" / "audio" / f"{args.sample_id}.wav"
    staging.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(stem, staging)

    srt_lines = []
    for position, cue in enumerate(timeline_cues, start=1):
        srt_lines += [
            str(position),
            f"{srt_time(cue['start_s'])} --> {srt_time(cue['end_s'])}",
            cue["en"],
            cue["zh"],
            "",
        ]
    srt_path = out / "subtitles.srt"
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")

    provenance = {
        "schema_version": 1,
        "sample_id": args.sample_id,
        "script_path": str(args.storyboard.resolve()),
        "script_sha256": sha(args.storyboard),
        "script_status": "reused_existing_captions_unreviewed",
        "caption_status": "machine_translated_unreviewed",
        "provider": "voxcpm2",
        "model": health.get("model_class") or "VoxCPM2",
        "model_version": health.get("engine_version"),
        "voice_reference": str(voice),
        "voice_reference_sha256": sha(voice),
        "prompt_text_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "generated_at": now(),
        "stem": {
            "path": str(stem),
            "sha256": sha(stem),
            "duration_s": round(total, 3),
        },
        "segments": [measured[index] for index in sorted(measured)],
        "timeline": {"path": str(timed_path), "sha256": sha(timed_path)},
        "subtitles": {"path": str(srt_path), "sha256": sha(srt_path)},
    }
    provenance_path = out / "narration.provenance.json"
    provenance_path.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "sample_id": args.sample_id,
        "stem": str(stem),
        "duration_s": round(total, 3),
        "segments": len(measured),
        "timed_storyboard": str(timed_path),
        "subtitles": str(srt_path),
        "provenance": str(provenance_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
