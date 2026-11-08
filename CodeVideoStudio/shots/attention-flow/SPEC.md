# SPEC — Self-attention in one pass

- **Project**: `CodeVideoStudio/shots/attention-flow`
- **Purpose**: 30 s explainer shot for a technical course; proves the Code2Video skill workflow with local rendering.
- **Stack**: Canvas 2D in a paused browser page; rendered by `skills/code-video/scripts/capture.mjs`.

## Format

| 项 | 值 |
| --- | --- |
| Resolution | 1920 × 1080 |
| FPS | 30 |
| Duration | 30.0 s (allowed 29.5–30.5) |
| Frames | 900 |
| Loop | no |
| Audio | forbidden (`-an`) |

## Exact on-screen copy

- Title: `Self-attention in one pass`
- Subtitle: `Each token asks every token what it needs.`
- Tokens: `The` `animal` `didn't` `cross` `street`
- Projection labels: `Query` `Key` `Value`
- Score label: `attention scores for “animal”`
- Context label: `context vector`
- Summary: `Q · K decide where to look` / `V is what gets passed back`

## Facts and numbers

- The five tokens are fixed and must appear in this order.
- The score bars are **schematic**, not measured model output. They must be labeled as schematic in `VERIFY.md` and not presented as real weights.
- The video explains the mechanism: Q/K/V projections, score normalization, weighted sum of V.

## Must-haves

1. Title and subtitle readable during 0–4 s.
2. All five tokens visible by 4 s; `animal` highlighted by 5 s.
3. Q, K, V boxes and arrows from `animal` visible during 9–15 s.
4. Five score bars appear during 15–23 s; `street` is visually the largest, `animal` second.
5. Context vector appears during 23–28 s and is connected to the weighted sum.
6. Summary lines visible during 28–30 s.
7. Every frame is a pure function of `t`; no wall-clock timers, no unseeded randomness.
8. Text ≥28 px at 1080p; key subjects recognizable.
9. Output is H.264 / yuv420p / 30 fps / 1920×1080 / 900 frames, no audio.
10. `VERIFY.md` records pass/fail with timestamps or still evidence.

## Out of scope

- Real model weights or measured attention values.
- Multi-head attention, positional encoding, training.
- Audio, narration or subtitles.
