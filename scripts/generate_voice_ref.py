"""Generate an English voice-design reference with the local VoxCPM2 model.

This uses the model's zero-shot / voice-design path (no reference audio), so it
must run in the VoxCPM runtime venv, not the workspace venv:

  <VOXCPM_RUNTIME>/venv/Scripts/python.exe scripts/generate_voice_ref.py \
    --model-dir <AI_ROOT>/models/voxcpm2 \
    --out lessons/<slug>/assets/voice/en_narrator_v1.wav

The resulting clip is used as ``tts.voice_ref_en`` for the course narration.
"""

from __future__ import annotations

import argparse
import json
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np


def write_wav(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(samples.astype(np.float32).reshape(-1), -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--reference-wav", default="", help="Timbre reference (your voice)")
    parser.add_argument("--prompt-wav", default="", help="English prosody prompt clip")
    parser.add_argument("--prompt-text", default="", help="Exact transcript of --prompt-wav")
    parser.add_argument("--style", default=(
        "American English male narrator, mid-30s, warm and clear, "
        "measured pace, natural prosody, friendly technical explainer"
    ))
    parser.add_argument("--text", default=(
        "Clear thinking starts with a question, and every good explanation "
        "begins with a simple example."
    ))
    parser.add_argument("--timesteps", type=int, default=10)
    parser.add_argument("--cfg", type=float, default=2.0)
    parser.add_argument("--max-len", type=int, default=4096)
    args = parser.parse_args()

    from voxcpm import VoxCPM

    started = time.monotonic()
    model = VoxCPM.from_pretrained(
        str(Path(args.model_dir)),
        load_denoiser=False,
        device="cpu",
        optimize=True,
    )
    load_seconds = time.monotonic() - started
    if args.prompt_wav:
        spoken = args.text
        mode = "combined_reference_prompt" if args.reference_wav else "continuation"
    else:
        spoken = f"({args.style}) {args.text}"
        mode = "reference_only" if args.reference_wav else "voice_design"
    generate_started = time.monotonic()
    kwargs = {
        "cfg_value": args.cfg,
        "inference_timesteps": args.timesteps,
        "max_len": args.max_len,
    }
    if args.reference_wav:
        kwargs["reference_wav_path"] = args.reference_wav
    if args.prompt_wav:
        kwargs["prompt_wav_path"] = args.prompt_wav
        kwargs["prompt_text"] = args.prompt_text
    wav = model.generate(text=spoken, **kwargs)
    synth_seconds = time.monotonic() - generate_started
    samples = np.asarray(wav, dtype=np.float32).reshape(-1)
    sample_rate = int(getattr(getattr(model, "tts_model", None), "sample_rate", 0) or 48000)
    output = Path(args.out)
    write_wav(output, samples, sample_rate)
    duration = len(samples) / sample_rate if sample_rate else 0.0
    meta = {
        "schema_version": 1,
        "kind": "voice_ref_en",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": "VoxCPM2",
        "model_dir": str(Path(args.model_dir)),
        "mode": mode,
        "style": args.style,
        "text": args.text,
        "reference_wav": args.reference_wav or None,
        "prompt_wav": args.prompt_wav or None,
        "prompt_text": args.prompt_text or None,
        "sample_rate": sample_rate,
        "channels": 1,
        "duration_s": round(duration, 3),
        "load_seconds": round(load_seconds, 1),
        "synth_seconds": round(synth_seconds, 1),
        "rtf": round(synth_seconds / duration, 2) if duration else None,
        "out": str(output),
    }
    output.with_suffix(".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
