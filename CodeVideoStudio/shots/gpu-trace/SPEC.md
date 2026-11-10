# SPEC — Identity is not location

- **Project**: `CodeVideoStudio/shots/gpu-trace`
- **Purpose**: 24 s cutaway for the NVIDIA export-control episode; shows what a GPU record can and cannot prove.
- **Stack**: Canvas 2D in a paused browser page; rendered by `skills/code-video/scripts/capture.mjs`.

## Format

| 项 | 值 |
| --- | --- |
| Resolution | 1920 × 1080 |
| FPS | 30 |
| Duration | 24.0 s (allowed 23.5–24.5) |
| Frames | 720 |
| Loop | no |
| Audio | forbidden (`-an`) |

## Exact on-screen copy

- Kicker: `GPU TRACEABILITY`
- Title: `Identity is not location`
- Subtitle: `What the record leaves out`
- Card caption: `SN 1037 8842 A` / `one card`
- Layer 1: `HARDWARE IDENTITY` — `Where the card came from, and who owns it` — chips `serial number` `manufacturing record` `asset register` `delivery record`
- Layer 2: `OPERATING STATE` — `Telemetry, if the card sits on a management network` — `temp 62 °C` `power 684 W` `util 91 %`
- Layer 3: `END USER AND END USE` — `Who submits the work, and what the work is for` — `no record links the card to the user`
- Footer: `Identify the card.` `Locate the card.` `Attribute the use.`

## Facts and numbers

- The three layers are an analytical frame, **not** a vendor implementation.
- `62 °C`, `684 W`, `91 %` are **illustrative** telemetry values, not measured. They must be labelled schematic in VERIFY.md.
- The serial number is fictional.

## Must-haves

1. Title and subtitle readable by 2.0 s.
2. The card and all three layer panels visible by 13.0 s.
3. Layer 3 turns accent/red and the line `no record links the card to the user` appears by 19.6 s.
4. Footer triad visible by 22.8 s.
5. Every frame is a pure function of `t`; no wall-clock timers, no unseeded randomness.
6. Text ≥ 20 px at 1080p; headline ≥ 60 px.
7. Output is H.264 / yuv420p / 30 fps / 1920×1080 / 720 frames, no audio.
8. `VERIFY.md` records pass/fail with evidence.

## Out of scope

- Real telemetry, real serial numbers, any claim that tracking is impossible.
