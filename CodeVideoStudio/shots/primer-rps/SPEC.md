# SPEC — Rock, Paper, Scissors world

- **Project**: `CodeVideoStudio/shots/primer-rps`
- **Purpose**: 30 s simulation shot; the hex world consumed by a course/essay edit.
- **Stack**: Three.js + `skills/code-video/scripts/capture.mjs`; deterministic `window.seek(t)`.

## Format

| 项 | 值 |
| --- | --- |
| Resolution | 1920 × 1080 |
| FPS | 30 |
| Duration | 30.0 s |
| Frames | 900 |
| Audio | forbidden (`-an`) |

## Inputs

- `simulation_spec`: `BlenderStudio/scenes/primer-poc/simulation.spec.json`
- `simulation_out`: `simulation.json` (written into this project by the adapter)

## Must-haves

1. `simulation-run` output is deterministic for the given seed.
2. 91 hex cells; every blob's colour follows its species in the current frame.
3. Tile colour follows the occupant species (28% mix).
4. Slow orbit; no clipping; eyes face the camera.
5. Every frame is a pure function of `t`; no wall-clock timers.
6. H.264 / yuv420p / 30 fps / 1920×1080 / 900 frames, no audio.

## Out of scope

- Overlay typography, ternary plot and payoff table (Remotion composition `PrimerPoc`).
- Music/narration.
