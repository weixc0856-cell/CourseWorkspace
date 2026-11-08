# VERIFY — Rock, Paper, Scissors world

- **Date**: 2026-11-08
- **Project**: `CodeVideoStudio/shots/primer-rps`
- **Render**: `node skills/code-video/scripts/capture.mjs . --fps 30 --dur 30 --size 1920x1080 --out out/world-1080.mp4`

## 1. File checks

| 项 | 实测 |
| --- | --- |
| Codec | h264 |
| Resolution | 1920×1080 |
| Pixel format | yuv420p |
| FPS | 30 |
| Frames | 900 |
| Duration | 30.0 s |
| Audio | 0 streams |

## 2. Must-haves

| # | Requirement | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Simulation deterministic for seed | pass | `simulation-run` same seed reproduces frames |
| 2 | 91 hex cells, species colours per frame | pass | `still4.png`, `world-1080.mp4` |
| 3 | Tile colour follows species | pass | 28% species mix in main.js |
| 4 | Slow orbit, no clipping, eyes face camera | pass | 30 s capture |
| 5 | Pure function of `t` | pass | code review; two 720p captures sha256 `7647486f…` |
| 6 | 1080p30 H.264, 900 frames, no audio | pass | ffprobe |

## 3. Notes

- The world shot is composited with ternary/payoff typography by Remotion (`PrimerPoc`).
- The adapter materializes `simulation.json` from `ShotSpec.inputs.simulation_spec` before capture.
