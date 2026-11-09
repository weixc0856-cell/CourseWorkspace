# VERIFY — compute-topology

Rendered 2026-11-09 with `skills/code-video/scripts/capture.mjs` (SwiftShader).

| Check | Result | Evidence |
| --- | --- | --- |
| Encoding | pass | H.264, yuv420p, 30 fps, 1920×1080, 780 frames, 26.000 s, no audio |
| Determinism | pass | frames 450–509 rendered twice: `2f6ca6e184474585`, identical sha256 |
| Layout | pass | stills at t=15/20/24 reviewed; data hall, cloud and three client cards inside margins |
| Must-have 1 | pass | title + subtitle fully visible at t=2.0 |
| Must-have 2 | pass | full card grid visible at t=5.0 |
| Must-have 3 | pass | cloud at t=7.4; three clients complete at t=10.0 |
| Must-have 4 | pass | request and return flows animated by t=13.4 |
| Must-have 5 | pass | `One country.` / `Anywhere.` / `gap` complete at t=20.4 |
| Must-have 6 | pass | travelling packets are a function of `t` only; determinism row above |
| Must-have 7 | pass | smallest text 20 px, headline 60 px |

## Notes

- The 10,000-card hall is a hypothetical scenario, marked `schematic` on screen.
- Client names and regions are placeholders; no real operator or customer is depicted.
