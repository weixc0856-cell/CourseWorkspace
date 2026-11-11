# SPEC — Transformer card film

- **Project**: `CodeVideoStudio/shots/transformer-card-film`
- **Purpose**: 三分钟 Transformer 科普片。24 张卡片、深浅主题交替、硬切，验证"暗调字体 + 浅色机制图"这套新语法能不能连续撑住整片。
- **Stack**: canvas 2D + `skills/code-video/scripts/capture.mjs`；`window.seek(t)` 是唯一输入。

## Format

| 项 | 值 |
| --- | --- |
| Resolution | 1920 × 1080 |
| FPS | 30 |
| Duration | 180.0 s |
| Frames | 5400 |
| Audio | 无（旁白未生成，TTS 服务未启动） |

## Inputs

- `cards.json`：24 张卡片，每张 `t` / `dur` / `theme`（`dark` | `light`）/ `kind` / 文案与图形参数。
- 字体：`fonts/jost-latin-{200,300}-normal.woff2`（OFL-1.1）；中文走 `node_modules/@fontsource/noto-sans-sc/300.css`，`node_modules` 是指向 `RemotionStudio/node_modules` 的 junction。

## Must-haves

1. 每一帧都是 `t` 的纯函数：无 wall-clock、无未播种随机。
2. 卡片边界是硬切；每张卡在 `u = 0` 时已成立（内容 72% 起、0.5 s 内稳定到 1），不允许从空白淡入。
3. 主题按卡片切换，`dark` 用近黑底，`light` 用暖白底；切换只发生在卡片边界。
4. 字体在首帧前完成加载（`await document.fonts.ready` 后再注入 `film.js`），不得用回落字体画第一帧。
5. 事实：2017、d_model=512、8 头、每头 64 维、6 层、1/√d_k 缩放、softmax 权重和为 1、残差与层归一化、正弦位置编码、训练并行、注意力 O(n²)。
6. 输出 H.264 / yuv420p / 30 fps / 1920×1080 / 5400 帧 / 无音轨。

## Out of scope

- 旁白与字幕（需 TTS 与 ASR，两段都没跑）。
- 配乐。
- 与课程 lesson 的 storyboard 绑定（当前作为独立镜头渲染）。
