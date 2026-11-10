# SPEC — attn-flow

- 1920×1080 · 30 fps · 16 s · 无音轨
- 语法：`simulation`
- 目的：权重变成连接；强连接变粗、弱连接退后；信息沿连接流动。
- 固定文案：权重让词与词交换信息 / 重要的连接变粗，不重要的退到背景里 / The animal didn't cross street
- 数据：边的权重与 `attn-matrix` 同一公式；粒子位置是 t 的纯函数。
- Must-have：无随机；同一 t 两次捕获逐字节一致；粒子不瞬移。
