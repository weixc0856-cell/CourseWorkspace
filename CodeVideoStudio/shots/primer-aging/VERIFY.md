# VERIFY — Why aging evolves (Three.js)

Status: rendered and checked on 2026-11-09.

| Must-have | Result | Evidence |
| --- | --- | --- |
| Pure function of `t`, no wall-clock timers | pass | `main.js`: `window.seek(t)`; seeded RNG in `simulate.py`; `Math.random` absent |
| Scenario switch at `s08` | pass | `main.js` reads `timing.json` and splits at `s08` |
| Age-coded colour and size; deaths fade | pass | `main.js` lerps teal→orange on age and fades `alive=0` agents |
| HUD: scenario, population, mean death age, mutation load, hazard | pass | `index.html` + `drawOverlay()` in `main.js` |
| Camera keeps the world left of the HUD | pass | `camera.setViewOffset(W*0.14)` |
| 1920×1080 / 30 fps / H.264 / yuv420p / no audio | pass | `ffprobe` of the captured file (see below) |
| Deterministic capture | pass | two 10 s captures at 960×540, sha256 `60d7ceb5…` identical |

## Capture

```powershell
node ../../skills/code-video/scripts/capture.mjs . --fps 30 --dur <total> --size 1920x1080 --out out/aging.mp4
```

## Evidence

- Full plate captured by the lesson adapter: `build/aging-evolution/animation/primer-aging.mp4` — 1920×1080, 30 fps, 145.40 s, 4,362 frames, no audio stream.
- Determinism: `out/det-a.mp4` / `out/det-b.mp4` (10 s each, 960×540), sha256 `60d7ceb59ef914f1f057e79746db0f2da5a5cdba305511bca40fa1819349634b`.
- Media QC on the final cut: `build/aging-evolution/quality/media-qc.json` — freeze 0, subtitles 32 cues, ASR coverage 0.935.
