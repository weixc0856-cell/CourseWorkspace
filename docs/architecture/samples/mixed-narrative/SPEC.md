# Sample 4 · 混合叙事（多语法 / 多渲染器）

- 格式：1920×1080 · 30 fps · 12 s · 无音轨
- 渲染器：CodeVideo（标题卡） + Manim（长镜头） + CodeVideo（快切） + CodeVideo（模拟）
- 语法：`kinetic_type` → `long_take` → `kinetic_edit` → `simulation`
- 目标：证明一条时间线可以按镜头混用语法与渲染器，且每段仍按各自的语法验收。

## 时间线
| 镜头 | 时间 | 来源 | 语法 |
|---|---|---|---|
| 01 | 0–3 s | `title-card/`（CodeVideo） | kinetic_type |
| 02 | 3–6 s | Sample 1 前 3 s（Manim） | long_take |
| 03 | 6–9 s | Sample 2 第 2 镜（CodeVideo） | kinetic_edit |
| 04 | 9–12 s | Sample 3 7–10 s（CodeVideo） | simulation |

## Must-haves
1. 四段分辨率、帧率、像素格式一致。
2. 拼接后总时长 12.000 s，无丢帧。
3. 每段保留自己的语法检查，不因混剪而使用统一评分。
4. 两个 CodeVideo 段可独立重渲；Manim 段可独立重渲。
5. 不出现跨段的固定“长寿命对象”要求。

## 失败条件
- 任一段分辨率/帧率/像素格式不一致，拼接失败或时长不是 12.000 s。
- 用统一评分覆盖各段语法检查。
- 任一段无法独立重渲。
