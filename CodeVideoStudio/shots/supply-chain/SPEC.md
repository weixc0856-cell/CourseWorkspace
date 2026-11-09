# SPEC — Five hands, five partial views

- **Project**: `CodeVideoStudio/shots/supply-chain`
- **Purpose**: 22 s cutaway showing where a single GPU passes and what each party can see.
- **Stack**: Canvas 2D in a paused browser page; rendered by `skills/code-video/scripts/capture.mjs`.

## Format

| 项 | 值 |
| --- | --- |
| Resolution | 1920 × 1080 |
| FPS | 30 |
| Duration | 22.0 s (allowed 21.5–22.5) |
| Frames | 660 |
| Loop | no |
| Audio | forbidden (`-an`) |

## Exact on-screen copy

- Kicker: `THE CHAIN`
- Title: `Five hands, five partial views`
- Subtitle: `Who can see what about a single card`
- Nodes: `Chip designer` / `model, serial, licence`; `Server OEM` / `build, ship-to address`; `Data centre` / `power, capacity, tenants`; `Cloud provider` / `accounts, API calls`; `End customer` / `intent and identity`
- Band: `WHO IS IN THE DUE-DILIGENCE CHAIN` — `covered` … `the last mile`
- Closing: `Every hand sees a slice.` / `No hand sees the whole card.` / `Reviewing the customer is the only point where a card becomes a person.`

## Facts and numbers

- The five-party chain is a structural description of the industry, not an allegation about any company.
- `covered` / `the last mile` illustrate the regulatory argument; they are not a legal opinion.

## Must-haves

1. Title readable by 1.5 s.
2. All five nodes visible by 5.5 s, arrows drawn between them.
3. Coverage band grows 12.4 → 15.4 s and stops at the cloud provider.
4. `the last mile` outline appears under the end customer by 16.4 s.
5. Closing lines visible by 18.8 s; accent line by 20.0 s.
6. Every frame is a pure function of `t`.
7. Text ≥ 20 px; headline ≥ 60 px.
8. Output is H.264 / yuv420p / 30 fps / 1920×1080 / 660 frames, no audio.

## Out of scope

- Any statement that the chain is unlawful, or that a named company failed due diligence.
