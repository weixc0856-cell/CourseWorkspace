# VERIFY — Self-attention in one pass

- **Date**: 2026-11-07
- **Project**: `CodeVideoStudio/shots/attention-flow`
- **Render**: `node skills/code-video/scripts/capture.mjs . --fps 30 --dur 30 --size 1920x1080 --out out/final.mp4`
- **File**: `out/final.mp4`

## 1. File checks

`check_video.sh out/final.mp4 1920 1080 30 29.5 30.5 0` → **OK**

| 项 | 实测 |
| --- | --- |
| Codec | h264 |
| Resolution | 1920×1080 |
| Pixel format | yuv420p |
| FPS | 30.000 |
| Frames | 900 |
| Duration | 30.000 s |
| Audio | 0 streams (forbidden) |
| Frozen warnings | 0.63–3.20, 3.20–8.80, 10.03–15.40, 16.47–23.13, 23.73–28.40, 28.40–30.00 |
| Black warnings | none |

Frozen segments are **deliberate holds** between explanatory beats, not accidental stalls. The progress bar and highlighted-token pulse keep the page alive; the checker still classifies the holds as frozen because the change is small.

## 2. Must-haves

| # | Requirement | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Title and subtitle readable 0–4 s | pass | `frame-0` / contact 0 s, 2 s |
| 2 | All five tokens visible by 4 s; `animal` highlighted by 5 s | pass | contact 4 s, 6 s; frame at 6 s |
| 3 | Q/K/V boxes and arrows visible 9–15 s | pass | contact 10 s, 12 s, 14 s |
| 4 | Five score bars visible 15–23 s; `street` largest, `animal` second | pass | `frame-20.png` |
| 5 | Context vector visible 23–28 s and connected to scores | pass | `frame-24.png` |
| 6 | Summary lines visible 28–30 s | pass | `frame-29.png` |
| 7 | Every frame a pure function of `t`; no wall-clock, no unseeded randomness | pass | code review; two independent renders |
| 8 | Text ≥28 px at 1080p; key subjects recognizable | pass | full-res frames |
| 9 | H.264 / yuv420p / 30 fps / 1920×1080 / 900 frames / no audio | pass | `check_video.sh` |
| 10 | `VERIFY.md` with timestamps/stills | pass | this file |

## 3. Determinism

Two independent renders were captured with the same page:

```powershell
node .../capture.mjs . --out out/final.mp4
node .../capture.mjs . --out out/final-2.mp4
```

`ffmpeg -f framemd5` for all 900 frames:

- **900/900 frame hashes identical**
- `diff final.hashes final-2.hashes` → no output

This satisfies the Code2Video “frame(t) is a pure function” requirement.

## 4. Visual review

- Contact sheet: `out/contact.jpg` (15 frames, 5 columns × 3 rows, 2 s step).
- Full-res stills: `out/frame-20.png`, `out/frame-24.png`, `out/frame-29.png`.
- Layout issue found and fixed: the original token row overlapped the score panel; token boxes were reduced to 170 px and the row was constrained to the left 1100 px.
- Alpha issue found and fixed: `label()` used to override the inherited `globalAlpha`; it now multiplies it, so early summary/context text no longer ghosts.

## 5. Known gaps / portability notes

1. **`contact_sheet.sh` is not portable to this Windows ffmpeg build**: `drawtext` fails with `Fontconfig error ...` and a segfault. Fallback used: `CodeVideoStudio/scripts/contact_sheet.py` (Pillow).
2. **`python3` is not on PATH** in Git Bash; a local shim `CodeVideoStudio/bin/python3` calls `python`. The skill scripts use `python3`.
3. Score bars are **schematic** and labeled as such; they are not measured attention weights.
4. No audio: this POC only validates the visual pipeline. Course audio remains VoxCPM2.
5. No 27B model was deployed; the code was authored in the existing Claude Code + DeepSeek harness and rendered locally with Playwright/SwiftShader + ffmpeg.

## 6. Reproduction

```powershell
cd CodeVideoStudio/shots/attention-flow
node ../../upstream/skills/code-video/scripts/capture.mjs . --fps 30 --dur 30 --size 1920x1080 --out out/final.mp4
PATH="../../bin:$PATH" sh ../../upstream/skills/code-video/scripts/check_video.sh out/final.mp4 1920 1080 30 29.5 30.5 0
uv run --project CourseControl python ../../scripts/contact_sheet.py out/final.mp4 out/contact.jpg --step 2 --cols 5 --thumb 384
```
