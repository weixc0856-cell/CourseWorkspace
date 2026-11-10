# VERIFY — gpu-trace

Rendered 2026-11-09 with `skills/code-video/scripts/capture.mjs` (SwiftShader).

| Check | Result | Evidence |
| --- | --- | --- |
| Encoding | pass | H.264, yuv420p, 30 fps, 1920×1080, 720 frames, 24.000 s, no audio |
| Determinism | pass | frames 450–509 rendered twice: `7e8eca55d034e79e`, identical sha256 |
| Layout | pass | stills at t=2/6/11/16/21/23.5 reviewed; no text outside the 130 px safe margin |
| Must-have 1 | pass | title + subtitle fully visible at t=2.0 |
| Must-have 2 | pass | card and all three layers present at t=13.0 |
| Must-have 3 | pass | layer 3 turns accent and the "no record" line is complete at t=19.6 |
| Must-have 4 | pass | footer triad complete at t=22.8 |
| Must-have 5 | pass | `draw(t)` is a pure function of `t`; determinism row above |
| Must-have 6 | pass | smallest text 18 px (axis labels), headline 62 px |

## Notes

- The telemetry numbers `62 °C`, `684 W`, `91 %` are **illustrative**, matching SPEC.md. They are not measured values from any system.
- The serial number is fictional.
- The three layers are an analytical frame. The shot does not claim that tracking a GPU is impossible.
