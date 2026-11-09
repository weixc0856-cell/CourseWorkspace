# VERIFY — Why aging evolves (Three.js)

Status: rendered and checked on 2026-11-09 (post-processing round; see D-061).

| Must-have | Result | Evidence |
| --- | --- | --- |
| Pure function of `t`, no wall-clock timers | pass | `main.js`: `window.seek(t)`; seeded RNG in `simulate.py`; `Math.random` absent; `FilmPass` grain clock is overwritten with `t` before every `composer.render(0)` |
| Scenario switch at `s08` | pass | `main.js` reads `timing.json` and splits at `s08` |
| Age-coded colour and size; deaths fade | pass | `main.js` lerps teal→orange on age and fades `alive=0` agents |
| HUD: scenario, population, mean death age, mutation load, hazard | pass | `index.html` + `drawOverlay()` in `main.js` |
| Camera keeps the world left of the HUD | pass | `camera.setViewOffset(W*0.14)` |
| 1920×1080 / 30 fps / H.264 / yuv420p / no audio | pass | `ffprobe` of the captured file (see below) |
| Deterministic capture | pass | two 30 s-range captures at 1920×1080, sha256 `b99e278227…` identical (`out/det-a.mp4` / `out/det-b.mp4`) |
| Post-processing uses shipped addons only | pass | `main.js` imports `EffectComposer/Pass/RenderPass/BokehPass/UnrealBloomPass/FilmPass/ShaderPass/OutputPass` and the shipped shaders from `vendor/three/addons/` (unmodified r160); the first-draft hand-written `postfx.js` was removed |
| Post must-haves (SPEC 7–8) | pass | Bokeh focus rides `camera.position.distanceTo(look)`; bloom threshold 1.8 in linear HDR; grain clock keyed to `t`; `capture.json` → `--gpu --jpeg` |

## Capture

```powershell
node ../../skills/code-video/scripts/capture.mjs . --fps 30 --dur <total> --size 1920x1080 --out out/aging.mp4 --gpu --jpeg
```

`capture.json` (`{"gpu": true, "jpeg": true}`) makes the lesson adapter pass the
same switches. Without them the capture falls back to SwiftShader + PNG.

| Path | Per frame | Full plate (4,362 frames) |
| --- | --- | --- |
| SwiftShader + PNG | 777 ms | ≈56 min |
| GPU + PNG | 352 ms | ≈26 min |
| GPU + JPEG | 36 ms | ≈3 min |

JPEG input is full-range `yuvj420p`; the capture converts it to limited range
(`scale=in_range=pc:out_range=tv`, `-color_range tv`) so the stream stays
`yuv420p`. Same frame vs the PNG path: PSNR 40.34 dB vs 40.56 dB.

## Evidence

- Full plate captured by the lesson adapter: `build/aging-evolution/animation/primer-aging.mp4`
  (capture stage 152 s; 4,362 frames).
- Determinism: GPU path, two 30-frame captures, sha256 identical.
- Build: `verdict=pass` (`build/aging-evolution/final/build-report.json`).
- Media QC on the final cut: `build/aging-evolution/quality/media-qc.json` — all ten checks
  PASS: decode, format, frames 4,361, loudness −16.2 LUFS / −3.2 dBTP, level policy,
  silence 0, black 0, freeze 0, subtitles 32 cues, ASR coverage 0.935.
- Quality report: `BUILD_PASS=True`, `QUALITY_PASS=True`, `RELEASE_APPROVED=False`
  (human review pending); `animation-score = 100/100`.
