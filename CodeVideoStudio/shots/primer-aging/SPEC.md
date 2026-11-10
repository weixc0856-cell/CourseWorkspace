# SPEC — Why aging evolves (Three.js)

- **Project**: `CodeVideoStudio/shots/primer-aging`
- **Purpose**: a 2.5-minute explainer plate in Primer's simulation language,
  reproducing the *mechanism* of "Simulating the Evolution of Aging": the
  declining force of selection, mutation accumulation and antagonistic
  pleiotropy, shown with an agent-based world and a live hazard overlay.
- **Stack**: Three.js r160 (vendored) + official r160 addons (vendored, unmodified)
  for post-processing + `skills/code-video/scripts/capture.mjs`; the page is a
  pure function of `t` via `window.seek(t)`.

## Format

| 项 | 值 |
| --- | --- |
| Resolution | 1920 × 1080 |
| FPS | 30 |
| Duration | `window.DUR` = `timing.json.total` |
| Audio | forbidden (`-an`) |

## Inputs

- `aging.json` (schema 2) from `simulate.py`: two scenarios (`danger`, `safe`),
  per-frame agents `[id, x, y, age, alive, ma_loci, ap_loci]`, population, mean
  death age and a hazard-by-age array. Frames are a sliding tail of the roster,
  so agents must be matched by `id`, never by array index.
- `timing.json` from `gen_narration.py`: segment starts, durations, total.

## Must-haves

1. Every frame is a pure function of `t`; seeded PRNG; two captures are
   byte-identical.
2. Scenario switches at the start of narration segment `s08` (danger → safe).
3. Agent colour and size follow age; dead agents fade out; agents are matched
   by stable `id` between frames (no index interpolation), and newborns scale in.
4. The HUD (scenario label, population, mean age at death, late-acting mutations
   per agent, hazard-by-age chart binned in 5-year groups) is drawn by the
   Remotion overlay from `compose.overlay: aging_hud`; the plate itself carries
   no HUD so the chart and typography can change without a re-render.
5. Camera holds the world left of the HUD; the right ~31% stays clear for the overlay; no clipping of the field.
6. H.264 / yuv420p / 30 fps / 1920×1080, no audio.
7. Post-processing is the official addon chain (`BokehPass`, `UnrealBloomPass`,
   `ColorCorrectionShader`, `FilmPass`, `VignetteShader`, `OutputPass`,
   `FXAAShader`); no hand-written shader replaces a shipped one, and the grain
   clock is set from `t` so `FilmPass` cannot accumulate its own time.
8. `capture.json` may switch the capture to `--gpu` and `--jpeg`; the switch
   must keep two captures byte-identical and is recorded in `VERIFY.md`.
9. The world is grounded: a lake hollow with the official `Water` addon and
   instanced grass/shrub vegetation; the water drives its ripple clock from `t`.

## Out of scope

- Verbatim reproduction of Primer's script, creatures, terrain and music.
- Empirical claims: the model is a toy, not a fitted estimate.
