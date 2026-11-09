# Vendored three.js r160 addons

Official `examples/jsm` post-processing passes and shaders from three.js **r160**
— the same release as the `../../three.module.js` core this shot already used.

- **Source**: <https://github.com/mrdoob/three.js> (npm package `three@0.160.0`)
- **License**: MIT, Copyright 2010-2023 Three.js Authors — see
  `CodeVideoStudio/THIRD_PARTY_NOTICES.md` and the root `NOTICE`.
- **Modifications**: none. Every file is byte-for-byte from the npm tarball.

## Files

```text
addons/postprocessing/  EffectComposer, Pass, MaskPass, ShaderPass, RenderPass,
                        BokehPass, UnrealBloomPass, FilmPass, OutputPass
addons/shaders/         CopyShader, LuminosityHighPassShader, BokehShader,
                        OutputShader, FilmShader, ColorCorrectionShader,
                        VignetteShader, FXAAShader
```

`index.html` maps the bare `three` specifier to `../../three.module.js` with an
import map, so the addons resolve to the vendored core (and to the same module
instance as `main.js`).

## Why these and not hand-written passes

Depth of field, bloom, film grain, vignette and antialiasing all have shipped,
widely used implementations in three.js. Hand-written replacements would be
unverified code with the same maintenance cost; see D-061/D-062 in
`docs/DECISIONS.md` and `docs/第三方依赖准入规范.md`.

## Updating

1. Check upstream (`npm view three version`, `gh api repos/mrdoob/three.js`).
2. Replace **core and addons together** — the addons target the matching core
   release; mixing versions breaks `EffectComposer` and the shader contracts.
3. Re-run the shot: `VERIFY.md` must be re-verified (real render, determinism
   hash, final media QC).
4. Record the new version and date in `docs/第三方依赖准入规范.md`.

**Current gap**: local r160 vs upstream 0.187.0 (checked 2026-11-09). The upgrade
is a tracked P1 task; until it lands, no report may call this dependency current.
