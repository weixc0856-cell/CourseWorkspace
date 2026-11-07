# E6 Transformer 注意力讲解制作方案

- **状态**：E6.1–E6.4 已完成（四幕 + 旁白 + 字幕 + 33.1s 成片）；E6.5/E6.6 待排期
- **日期**：2026-11-07
- **目标**：把三幕视觉基线升级为一条讲清 Self-Attention 计算关系的教学视频
- **边界**：先做 Embedding / QKV / Softmax / Weighted Value；Multi-Head 与完整 Block 留到 E6.5/E6.6

---

## 1. 镜头表

| 镜头 | 时长 | 内容 | 画面要点 |
| --- | --- | --- | --- |
| S1 Token → Embedding | 8 s | 离散 token 变成连续向量 | token 行、每列 4 维向量、`token id → embedding` |
| S2 Q / K / V | 9 s | 三组线性投影 | `Q=XW_Q`、`K=XW_K`、`V=XW_V`；cat 的 Q 高亮 |
| S3 Scores → Softmax | 10 s | 点积、缩放、归一化 | `score_i = q·k_i / √d_k`、softmax 权重柱、heatmap |
| S4 Weighted V → Context | 8 s | 权重作用于 Value，再求和 | `context = Σ α_i v_i`；逐个 V 着色、合成 context |

总时长约 35 秒。每幕之间有 0.4–0.6 秒停顿，便于旁白呼吸。

---

## 2. 数学关系（必须逐帧正确）

```text
Q = X W_Q
K = X W_K
V = X W_V

score_i = (q · k_i) / sqrt(d_k)
alpha   = softmax(scores)
context = sum_i alpha_i * v_i
```

- 权重柱对应 `alpha_i`，不是 `score_i`。
- S4 必须先展示 `alpha_i * v_i` 的加权向量，再求和；不能从权重直接跳到 context。
- `d_k` 用 4 维演示，`sqrt(4)=2`。

---

## 3. 旁白文本（中文，逐镜头）

**S1**

> Transformer 不认识文字，它先要把每个 token 映射成一个连续向量。这个向量叫 embedding。同一句话里的每个 token，都有自己的向量。

**S2**

> 接下来，模型用三组不同的权重，把同一个 embedding 投影成 Query、Key 和 Value。Query 负责提问，Key 负责被比较，Value 才是真正被加权求和的内容。

**S3**

> 对当前 token 的 Query 和每个 Key 做点积，得到相关性分数，再除以维度的平方根。Softmax 把分数变成总和为一的权重。分数越高，这个 token 在上下文里越重要。

**S4**

> 最后，用每个权重去乘对应的 Value，再把所有加权后的 Value 相加，得到 context。这个 context 才是当前 token 交给下一层的表示。Attention 不是对 Key 做平均，而是对 Value 做加权求和。

> 旁白需要在成片中明确可听；字幕与每幕动画动作同步。

---

## 4. 字幕时间轴（草稿）

| 开始 | 结束 | 文本 |
| --- | --- | --- |
| 00:00.5 | 00:07.5 | Transformer 把每个 token 映射成连续向量。 |
| 00:08.0 | 00:16.5 | 用三组权重把 embedding 投影成 Query、Key、Value。 |
| 00:17.0 | 00:26.5 | Query 与 Key 点积，缩放后由 softmax 变成权重。 |
| 00:27.0 | 00:34.5 | 权重乘 Value 再求和，得到 context。 |

实际时间以 Manim 渲染时长与旁白音频为准；若旁白超时，优先缩短文案，不压缩动画。

---

## 5. 验收标准

1. 四幕各自真实渲染，1920×1080 / 30 fps。
2. `Q/K/V` 与 `score/softmax/weighted V` 在画面上有明确对应，抽帧可核对。
3. 旁白四段生成成功，拼接后与四幕总时长一致（允许 0.5 秒静音余量）。
4. SRT 与旁白段落同步；成片含音频流与字幕文件。
5. 证据落盘：`build/manim-transformer/e6/{shots,narration,srt,final,manifest}`。
6. 不把 Multi-Head/Block 塞进本期；E6.5/E6.6 单独排期。
