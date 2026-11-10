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
#    capture.json enables --gpu --jpeg; without it the capture falls back to
#    SwiftShader + PNG (~20x slower; same frame within 0.2 dB PSNR).
node ../../skills/code-video/scripts/capture.mjs . --fps 30 --dur <total> --size 1920x1080 --out out/aging.mp4 --gpu --jpeg
```

The lesson (`lessons/aging-evolution`) uses the `code_video` adapter, which runs
the same capture into `build/aging-evolution/animation/primer-aging.mp4` and
then composes narration, burned subtitles and QC.

## Data

`aging.json`: two scenarios (`danger` μ=0.030, `safe` μ=0.008), 420 steps,
recorded every 2 steps. Frames are a sliding tail of the roster, so agents are
`[id, x, y, age, alive, ma_loci, ap_loci]` and must be matched by `id`;
frames carry population, mean age at death and a yearly hazard array.

`timing.json`: one segment per narration beat; the page switches scenario at
the start of `s08`.

## Look

Scene: gradient dome, soft shadows, rim light, exponential fog, a shallow basin
terrain with a lake hollow (official `Water` addon), scattered rocks, instanced
grass tufts and shrubs, four-legged agents (capsule body, head with muzzle
and ears, tapered tail, two-segment legs) whose gait is driven by the recorded
speed, heads that dip while nearly still (a visual idiom, not a modelled
variable), newborn scale-in, camera left of the HUD panel, age-coded blobs
(teal to orange).

HUD: drawn by the Remotion overlay (`compose.overlay: aging_hud`) from the same
`aging.json` + `timing.json`; the plate carries no HUD, so the chart and
typography can change without re-rendering 4,000 frames.

Post: the official three.js r160 addon chain — `BokehPass` (depth of field
focused on the world centre), `UnrealBloomPass`, `ColorCorrectionShader`
(ACES-friendly warm/cool split), `FilmPass` (grain keyed to `t`), `VignetteShader`,
`OutputPass` (ACES + sRGB), `FXAAShader` (the render targets are not
multisampled). All addons live in `vendor/three/addons/` and are unmodified;
`index.html` maps the bare `three` specifier to `./three.module.js`. Dependency
vetting and the version gap (r160 vs upstream 0.187.0) are tracked in
`docs/第三方依赖准入规范.md`.

`capture.json` opts this shot into `--gpu` and `--jpeg`; `VERIFY.md` records the
determinism check that this switch requires.

Gap and next steps: `docs/evaluations/复刻-Primer衰老模拟-计划.md`.
