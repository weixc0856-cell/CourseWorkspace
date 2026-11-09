# Why aging evolves — agent simulation (Three.js)

A 2.5-minute primer-style plate: an agent-based world with genomes, aging and
reproduction, plus a live hazard overlay. The mechanism follows the classical
theory — declining force of selection with age, mutation accumulation
(Medawar 1952) and antagonistic pleiotropy (Williams 1957) — not a verbatim
copy of any script.

## Pipeline

```powershell
# 1. simulation data (deterministic)
cd CodeVideoStudio/shots/primer-aging
python simulate.py --out aging.json

# 2. narration (VoxCPM2 at 127.0.0.1:50000, reference voice)
python gen_narration.py
#    -> build/aging-evolution/audio/sXX.wav + timing.json

# 3. narration mix, subtitles, bilingual draft, shot timing
python assemble.py

# 4. capture (duration = timing.json total)
node ../../skills/code-video/scripts/capture.mjs . --fps 30 --dur <total> --size 1920x1080 --out out/aging.mp4
```

The lesson (`lessons/aging-evolution`) uses the `code_video` adapter, which runs
the same capture into `build/aging-evolution/animation/primer-aging.mp4` and
then composes narration, burned subtitles and QC.

## Data

`aging.json`: two scenarios (`danger` μ=0.030, `safe` μ=0.008), 420 steps,
recorded every 2 steps. Agents are `[x, y, age, alive, ma_loci, ap_loci]`;
frames carry population, mean age at death and a yearly hazard array.

`timing.json`: one segment per narration beat; the page switches scenario at
the start of `s08`.

## Look

ACES tone mapping, gradient dome, soft shadows, rim light, exponential fog,
a shallow basin terrain with scattered rocks, four-legged agents with a walk
cycle, camera set left of the HUD, age-coded blobs (teal → orange), HUD with
population / mean death age / late-acting mutations and a 5-year binned hazard
curve. BGM: Schubert D.664 (public domain) mixed with ducking by `audio-mix`.

Gap and next steps: `docs/evaluations/复刻-Primer衰老模拟-计划.md`.
