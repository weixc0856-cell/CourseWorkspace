# Primer-style RPS world (Three.js)

Reads `simulation.json` from `course-control simulation-run` and renders the
same 30 s hex world deterministically with `window.seek(t)`.

```powershell
# data (from repo root)
uv run --project CourseControl course-control simulation-run `
  --spec BlenderStudio/scenes/primer-poc/simulation.spec.json `
  --out build/primer-poc/simulation.json
Copy-Item build/primer-poc/simulation.json CodeVideoStudio/shots/primer-rps/simulation.json

# one-time: reuse Playwright from RemotionStudio (junction, not committed)
cmd /c mklink /J node_modules ..\..\..\RemotionStudio
ode_modules

# capture 30 s at 1280x720
cd CodeVideoStudio/shots/primer-rps
node ../../skills/code-video/scripts/capture.mjs . --fps 30 --dur 30 --size 1280x720 --out out/world.mp4
```

Measured: 900 frames in **45.7 s** (~51 ms/frame, SwiftShader), two runs byte-identical
(`sha256 7647486f…`). Blender world: ~12 min for the same 900 frames.

`three.module.js` is Three.js r160 (MIT), vendored for offline capture. See
`../../THIRD_PARTY_NOTICES.md`.
