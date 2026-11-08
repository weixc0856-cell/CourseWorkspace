"""Synthesize the narration segments through the local VoxCPM2 service.

Writes build/attention-3b1b/audio/sXX.wav and timing.json (start/duration per
segment). The scene reads timing.json so picture and voice share one clock.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NARR = Path(__file__).resolve().parent / "narration"
OUT = ROOT / "build" / "attention-3b1b"
AUDIO = OUT / "audio"
VOICE = ROOT / "lessons" / "02-car-aerodynamics" / "assets" / "voice" / "my_voice_en_ref_short.wav"
PROMPT_TEXT = "Welcome to this lesson. Today, we will look at how the model works."
API = "http://127.0.0.1:50000/tts"
GAP = 0.55

# NARRATION_MODE=hifi keeps the verified prompt_wav/prompt_text cloning.
# NARRATION_MODE=controllable uses reference_wav only, so a bracketed style
# instruction at the front of the text is honoured (Hi-Fi ignores it).
MODE = os.environ.get("NARRATION_MODE", "hifi").strip().lower()
STYLE = os.environ.get("NARRATION_STYLE", "").strip()


def synth(text: str, dest: Path) -> None:
    spoken = f"({STYLE}) {text}" if STYLE else text
    body = {"text": spoken, "speed": 1.0, "text_frontend": True}
    if MODE == "controllable":
        body["reference_wav"] = str(VOICE)
    else:
        body["prompt_wav"] = str(VOICE)
        body["prompt_text"] = PROMPT_TEXT
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(API, data=payload, headers={"Content-Type": "application/json"})
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=1800) as resp:
                dest.write_bytes(resp.read())
            with wave.open(str(dest)) as w:
                if w.getnframes() == 0:
                    raise RuntimeError("empty wav")
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] {dest.stem} attempt {attempt} failed: {exc}", flush=True)
            if attempt == 3:
                raise
            time.sleep(5)


def wav_seconds(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def main() -> int:
    AUDIO.mkdir(parents=True, exist_ok=True)
    segs = sorted(NARR.glob("s??.txt"))
    timeline, cursor = [], 0.0
    for i, txt in enumerate(segs):
        out = AUDIO / f"{txt.stem}.wav"
        text = txt.read_text(encoding="utf-8").strip()
        if not out.exists() or out.stat().st_size == 0:
            t0 = time.time()
            synth(text, out)
            print(f"[ok] {txt.stem} {wav_seconds(out):.2f}s in {time.time()-t0:.0f}s", flush=True)
        dur = wav_seconds(out)
        start = cursor + (1.0 if i == 0 else GAP)
        timeline.append({"id": txt.stem, "text": text, "start": round(start, 3), "duration": round(dur, 3)})
        cursor = start + dur
    total = cursor + 2.0
    (OUT / "timing.json").write_text(
        json.dumps({"segments": timeline, "total": round(total, 3)}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[done] total {total:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
