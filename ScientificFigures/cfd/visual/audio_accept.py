"""Audio-side acceptance: level, silence gaps, and subtitle alignment against energy.

Positive assertions, not 'it played'. Reads the delivered wav and srt only.
"""
import re
import sys
import wave
from pathlib import Path

import numpy as np

wav_path, srt_path = Path(sys.argv[1]), Path(sys.argv[2])
with wave.open(str(wav_path), "rb") as w:
    sr, n, ch, sw = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
    raw = w.readframes(n)
x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
if ch > 1:
    x = x.reshape(-1, ch).mean(axis=1)
dur = len(x) / sr
print(f"wav {dur:.2f}s  sr {sr}  ch {ch}  peak {np.abs(x).max():.4f}  clipped {(np.abs(x) > 0.999).sum()}")

win = int(0.25 * sr)
rms = np.sqrt(np.mean(x[: len(x) // win * win].reshape(-1, win) ** 2, axis=1))
quiet = rms < 0.005
runs, start = [], None
for i, q in enumerate(quiet):
    if q and start is None:
        start = i
    elif not q and start is not None:
        runs.append((start * 0.25, (i - start) * 0.25))
        start = None
if start is not None:
    runs.append((start * 0.25, (len(quiet) - start) * 0.25))
long_gaps = [(t, d) for t, d in runs if d >= 2.0]
print(f"silence gaps >=2s: {len(long_gaps)} -> " + ", ".join(f"{t:.1f}s/{d:.1f}s" for t, d in long_gaps[:12]))


def ts(s):
    h, m, rest = s.split(":")
    sec, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000


cues = []
blocks = re.split(r"\n\s*\n", srt_path.read_text(encoding="utf-8").strip())
for b in blocks:
    lines = b.strip().splitlines()
    if len(lines) >= 3 and "-->" in lines[1]:
        a, bb = lines[1].split("-->")
        cues.append((ts(a.strip()), ts(bb.strip()), " ".join(lines[2:])))
print(f"cues {len(cues)}  first {cues[0][0]:.2f}s  last end {cues[-1][1]:.2f}s")

bad = []
for a, b, txt in cues:
    i0, i1 = int(a / 0.25), min(int(b / 0.25), len(rms))
    if i1 <= i0:
        bad.append((a, b, "zero-length", txt[:40]))
        continue
    seg = rms[i0:i1]
    if seg.max() < 0.01:
        bad.append((a, b, "no audio energy", txt[:40]))
    if b > dur + 0.05:
        bad.append((a, b, "past end of audio", txt[:40]))
print(f"cues with no matching audio: {len(bad)}")
for r in bad[:10]:
    print("  ", r)
overlap = sum(1 for i in range(1, len(cues)) if cues[i][0] < cues[i - 1][1] - 1e-6)
print(f"overlapping cues: {overlap}")
print("VERDICT:", "FAIL" if (bad or overlap or np.abs(x).max() > 0.999) else "PASS")