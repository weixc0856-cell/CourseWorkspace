# SPEC — WAYNE desktop opener (Gate 1 blockout)

- **Project**: `CodeVideoStudio/shots/brand-desktop`
- **Design**: [docs/品牌片头-3D桌面戏-设计.md](../../../docs/品牌片头-3D桌面戏-设计.md) v1.1
- **Purpose**: prove the shot, not the look. One continuous 12 s take; a pointer puts a paper desk to work and the paper becomes the WAYNE mark.
- **Stack**: three.js r160 (copied locally), no addons, no post-processing, no audio.

## Format

| 项 | 值 |
| --- | --- |
| Resolution | 1920 × 1080 |
| FPS | 30 |
| Frames | 360 (0–359) |
| Duration | 12.0 s |
| Audio | none |
| Variants | `index.html?variant=a` (pip) / `?variant=b` (dot) |

## Must-haves (Gate 1)

1. Every frame is a pure function of `t`; `window.seek(t)` is the only input; same-path renders are byte-identical.
2. One continuous camera program: no cuts, no resets, no crossfades.
3. Events land on cue frames from `cues.json` (±1 frame; overshoot ±2).
4. Exactly one orange focus at a time (design §2.3).
5. Text is English only, ≥28 px on screen, inside the 96 px safe margin.
6. W geometry reuses `W_PATH` / `CURRENT_PATH` from `RemotionStudio/src/brand/BrandMark.tsx` verbatim.
7. Camera reaches within 15° of the desk normal by f330.
8. No materials beyond flat tokens, no shadows, no bloom/DoF/vignette/grain.

## Out of scope

- Art direction (materials, paper texture, shadows), music, 8 s cut, 9:16, pipeline integration.

## Commands

```powershell
node ../../skills/code-video/scripts/capture.mjs . --page "index.html?variant=a" --fps 30 --dur 12 --size 1920x1080 --out out/gate1-a.mp4
node ../../skills/code-video/scripts/capture.mjs . --page "index.html?variant=b" --fps 30 --dur 12 --size 1920x1080 --out out/gate1-b.mp4
```
