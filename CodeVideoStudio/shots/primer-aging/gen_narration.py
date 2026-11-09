"""Synthesize the aging-evolution narration with the local VoxCPM2 service.

Reads ``narration/sXX.txt``, writes ``build/aging-evolution/audio/sXX.wav`` and
``build/aging-evolution/timing.json`` (start/duration per segment).  The world
shot reads the same timing file, so picture and voice share one clock.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NARR = Path(__file__).resolve().parent / "narration"
OUT = ROOT / "build" / "aging-evolution"
AUDIO = OUT / "audio"
VOICE = Path(
    os.environ.get(
        "VOICE_REF_WAV",
        str(ROOT / "lessons" / "02-car-aerodynamics" / "assets" / "voice" / "my_voice_en_ref_norm.wav"),
    )
)
PROMPT_TEXT = "Welcome to this lesson. Today, we will look at how the model works."
API = "http://127.0.0.1:50000/tts"
GAP = 0.55
STYLE = os.environ.get("NARRATION_STYLE", "(clear, measured pace)")


def wait_ready(timeout: float = 300.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:50000/health", timeout=3) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                if payload.get("status") == "ready":
                    return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    raise RuntimeError("VoxCPM2 service did not become ready")


def synth(text: str, dest: Path) -> None:
    spoken = f"{STYLE} {text}" if STYLE else text
    body = {
        "text": spoken,
        "reference_wav": str(VOICE),
        "speed": 1.0,
        "text_frontend": True,
    }
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(API, data=payload, headers={"Content-Type": "application/json"})
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=3600) as resp:
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
    if not VOICE.is_file():
        print(f"voice reference missing: {VOICE}", file=sys.stderr)
        return 1
    AUDIO.mkdir(parents=True, exist_ok=True)
    wait_ready()
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
        timeline.append(
            {"id": txt.stem, "text": text, "start": round(start, 3), "duration": round(dur, 3)}
        )
        cursor = start + dur
    total = cursor + 2.0
    (OUT / "timing.json").write_text(
        json.dumps({"segments": timeline, "total": round(total, 3)}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[done] {len(timeline)} segments, total {total:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
