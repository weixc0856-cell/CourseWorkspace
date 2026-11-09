# VERIFY — supply-chain

Rendered 2026-11-09 with `skills/code-video/scripts/capture.mjs` (SwiftShader).

| Check | Result | Evidence |
| --- | --- | --- |
| Encoding | pass | H.264, yuv420p, 30 fps, 1920×1080, 660 frames, 22.000 s, no audio |
| Determinism | pass | frames 450–509 rendered twice: `1d31c00d38162d37`, identical sha256 |
| Layout | pass | stills at t=10/20 reviewed; five nodes and the closing lines inside margins |
| Must-have 1 | pass | title visible at t=1.5 |
| Must-have 2 | pass | all five nodes and four arrows complete at t=5.5 |
| Must-have 3 | pass | coverage band grows 12.4–15.4 s and stops at the cloud provider |
| Must-have 4 | pass | `the last mile` outline complete at t=16.4 |
| Must-have 5 | pass | closing lines at t=18.8; accent line at t=20.0 |
| Must-have 6 | pass | `draw(t)` is a pure function of `t`; determinism row above |
| Must-have 7 | pass | smallest text 20 px, headline 60 px |

## Notes

- The five-party chain is a structural description of the industry, not an allegation about any company.
- `covered` / `the last mile` illustrate the regulatory argument and are not a legal opinion.
