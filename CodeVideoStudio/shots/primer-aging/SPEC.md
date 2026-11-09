# SPEC — Why aging evolves (Three.js)

- **Project**: `CodeVideoStudio/shots/primer-aging`
- **Purpose**: a 2.5-minute explainer plate in Primer's simulation language,
  reproducing the *mechanism* of "Simulating the Evolution of Aging": the
  declining force of selection, mutation accumulation and antagonistic
  pleiotropy, shown with an agent-based world and a live hazard overlay.
- **Stack**: Three.js r160 (vendored) + `skills/code-video/scripts/capture.mjs`;
  the page is a pure function of `t` via `window.seek(t)`.

## Format

| 项 | 值 |
| --- | --- |
| Resolution | 1920 × 1080 |
| FPS | 30 |
| Duration | `window.DUR` = `timing.json.total` |
| Audio | forbidden (`-an`) |

## Inputs

- `aging.json` from `simulate.py`: two scenarios (`danger`, `safe`), per-frame
  agents `[x, y, age, alive, ma_loci, ap_loci]`, population, mean death age and
  a hazard-by-age array.
- `timing.json` from `gen_narration.py`: segment starts, durations, total.

## Must-haves

1. Every frame is a pure function of `t`; seeded PRNG; two captures are
   byte-identical.
2. Scenario switches at the start of narration segment `s08` (danger → safe).
3. Agent colour and size follow age; dead agents fade out.
4. HUD shows scenario label, population, mean age at death and late-acting
   mutations per agent; hazard-by-age chart is binned in 5-year groups.
5. Camera holds the world left of the HUD; no clipping of the field.
6. H.264 / yuv420p / 30 fps / 1920×1080, no audio.

## Out of scope

- Verbatim reproduction of Primer's script, creatures, terrain and music.
- Empirical claims: the model is a toy, not a fitted estimate.
