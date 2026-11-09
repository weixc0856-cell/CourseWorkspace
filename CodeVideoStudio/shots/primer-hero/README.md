# Primer hero world (Three.js)

Cinematic 3D world plate in Primer's simulation language, rendered
deterministically from `simulation.json`.

- reference: Primer, *Simulating the Evolution of Aging* —
  <https://www.youtube.com/watch?v=1_JbJTeLZJs>
- look: ACES tone mapping, gradient dome, soft shadows, rim light, exponential
  fog, dust, camera vignette; wide establishing → dolly-in → slow settle.
- output: `out/hero-1080.mp4` — 1920×1080 / 30 fps / 30 s / 900 frames.

## Rebuild

```powershell
# data (from repo root)
uv run --project CourseControl course-control simulation-run `
  --spec BlenderStudio/scenes/primer-poc/simulation.spec.json `
  --out build/primer-poc/simulation.json
Copy-Item build/primer-poc/simulation.json CodeVideoStudio/shots/primer-hero/simulation.json

# one-time: reuse Playwright from RemotionStudio (junction, not committed)
cd CodeVideoStudio/shots/primer-hero
cmd /c mklink /J node_modules ..\..\..\RemotionStudio\node_modules

# capture 30 s at 1080p
node ../../skills/code-video/scripts/capture.mjs . --fps 30 --dur 30 --size 1920x1080 --out out/hero-1080.mp4
```

Measured (SwiftShader, this machine):

| run | frames | ms/frame | total |
| --- | --- | --- | --- |
| 960×540 test | 90 | ~55 | ~6 s |
| 1920×1080 | 900 | ~150 | ~2.4 min |

Determinism: two independent 1080p captures are byte-identical —
`sha256 3de0f8a57a2d4195365dfa0d5675259ee205ca25238c8b882a881d3a71fddb05`.
The dust field uses a seeded PRNG, not `Math.random`, so the plate is a pure
function of `t`.

`three.module.js` is Three.js r160 (MIT), vendored for offline capture. See
`../../THIRD_PARTY_NOTICES.md`.

Gap analysis and next steps: `docs/evaluations/评估-Primer-3D-hero-v2.md`.
