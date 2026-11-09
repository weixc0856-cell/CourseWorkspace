# SPEC — Primer hero world (Three.js)

- **Project**: `CodeVideoStudio/shots/primer-hero`
- **Purpose**: a cinematic 3D simulation world in the visual language of Primer
  (`Simulating the Evolution of Aging`, YouTube `1_JbJTeLZJs`); the world plate
  for a course/essay edit.
- **Stack**: Three.js r160 (vendored) + `skills/code-video/scripts/capture.mjs`;
  the page is a pure function of `t` via `window.seek(t)`.

## Format

| 项 | 值 |
| --- | --- |
| Resolution | 1920 × 1080 |
| FPS | 30 |
| Duration | 30.0 s |
| Frames | 900 |
| Audio | forbidden (`-an`) |

## Inputs

- `simulation.json` (from `course-control simulation-run`; 91 hex cells, 900
  frames of species states, seed 7).

## Must-haves

1. Every frame is a pure function of `t`; no wall-clock timers, no unseeded RNG.
2. 91 hex cells; body and tile colour follow the occupant species.
3. Creatures face the camera and breathe; contact shadows ground them.
4. Cinematic look: ACES tone mapping, gradient dome, soft directional shadows,
   rim light, exponential fog, dust, camera vignette.
5. Motivated camera: wide establishing → dolly-in → slow settle, no clipping.
6. H.264 / yuv420p / 30 fps / 1920×1080 / 900 frames, no audio.
7. Two captures with the same inputs are byte-identical (sha256).

## Out of scope

- Overlay typography, charts and captions (Remotion composition).
- The aging simulation itself (this shot is about the world look).
- Music and narration.
