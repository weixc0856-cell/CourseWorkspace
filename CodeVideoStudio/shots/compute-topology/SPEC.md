# SPEC — The card stays. The work travels.

- **Project**: `CodeVideoStudio/shots/compute-topology`
- **Purpose**: 26 s cutaway showing a physical data hall, a cloud API layer and remote users in other regions.
- **Stack**: Canvas 2D in a paused browser page; rendered by `skills/code-video/scripts/capture.mjs`.

## Format

| 项 | 值 |
| --- | --- |
| Resolution | 1920 × 1080 |
| FPS | 30 |
| Duration | 26.0 s (allowed 25.5–26.5) |
| Frames | 780 |
| Loop | no |
| Audio | forbidden (`-an`) |

## Exact on-screen copy

- Kicker: `PHYSICAL BOUNDARY`
- Title: `The card stays. The work travels.`
- Subtitle: `Illustrative scenario: one data hall, many remote users`
- Data hall: `DATA HALL  SINGAPORE` / `10,000 cards, none in transit` / `schematic`
- Cloud: `CLOUD` / `API gateway` / `remote clusters`
- Clients: `Client A` `region one`, `Client B` `region two`, `Client C` `region three`
- Verdict: `PHYSICAL LOCATION` `One country.` · `WHO IS USING IT` `Anywhere.` · `gap`
- Footer: `The hardware record stops at the hall.`

## Facts and numbers

- The 10,000-card hall is a **hypothetical scenario**; the grid is a schematic, not a real fleet count.
- Client names and regions are placeholders.
- The claim being illustrated is structural: physical location and user location are different facts.

## Must-haves

1. Title and subtitle readable by 2.0 s.
2. Data hall with the full card grid visible by 5.0 s.
3. Cloud node visible by 7.4 s; three clients visible by 10.0 s.
4. Request flows (clients → cloud → hall) and the return flow visible by 13.4 s.
5. `One country.` / `Anywhere.` and the `gap` marker visible by 20.4 s.
6. Every frame is a pure function of `t`; travelling packets must be deterministic.
7. Text ≥ 20 px; headline ≥ 60 px.
8. Output is H.264 / yuv420p / 30 fps / 1920×1080 / 780 frames, no audio.

## Out of scope

- Naming a real operator, a real client, or a real deployment.
