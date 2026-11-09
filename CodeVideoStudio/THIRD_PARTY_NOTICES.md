# Third-party notices

## SenseNova-6.8-Code2Video

- Source: https://github.com/OpenSenseNova/SenseNova-6.8-Code2Video
- Vendored: `skills/code-video/` (SKILL.md, crafts, scripts)
- License: Apache License 2.0 (see `LICENSE.code-video`)
- Changes: none to the skill files; only path and workflow integration.

## Playwright / Chromium

- Used via the existing `RemotionStudio/node_modules` junction for local rendering.
- Playwright: Apache-2.0; Chromium: BSD-style licenses.

## FFmpeg

- External executable; license depends on the installed build.

## Three.js

- Source: https://github.com/mrdoob/three.js
- Vendored: `shots/primer-rps/three.module.js` (r160)
- Vendored: `shots/primer-aging/three.module.js` (r160, core)
- Vendored: `shots/primer-aging/vendor/three/addons/` — official
  `examples/jsm` post-processing passes and shaders from the same r160 release,
  unmodified: `EffectComposer`, `Pass`, `MaskPass`, `ShaderPass`, `RenderPass`,
  `BokehPass`, `UnrealBloomPass`, `FilmPass`, `OutputPass`, `CopyShader`,
  `LuminosityHighPassShader`, `BokehShader`, `OutputShader`, `FilmShader`,
  `ColorCorrectionShader`, `VignetteShader`, `FXAAShader`.
- Note: the addons must stay on the same release as the vendored core. The
  upstream version gap is tracked in `docs/第三方依赖准入规范.md`.
- License: MIT.
