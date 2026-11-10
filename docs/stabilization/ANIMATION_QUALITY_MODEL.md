# 动画质量模型（Animation Quality Model）

- 日期：2026-11-10
- 状态：已实现 D-071 与评分修正；05/06 已重算
- 关联审计：`docs/audit/ARCHITECTURE_CONFLICTS.md` C-02、C-04
- 关联文档：`docs/工业化动画工作流.md`、`docs/DECISIONS.md` D-065/D-066/D-071

---

## 1. 问题

旧评分把三类东西压成一个 0–100：

- 结构性：旁白覆盖、镜头重叠、越界；
- 创作阈值：5–16 秒、2.5 动作/10 秒、长寿命对象 ≥50%；
- 像素证据：冻结段。

结果是 05 拿到 100 分，同时媒体 QC 记录 58 段冻结。100 分里最多 40 分是免费分：

- 无相机运动：10 分；
- `freeze_counts_against: false`：15 分；
- 构建通过：15 分。

其余 60 分来自作者自己写的 `beats.yaml`。

## 2. 现在的三分法

| 维度 | 数据来源 | 能证明什么 | 不能证明什么 |
| --- | --- | --- | --- |
| 结构完整性 | `beats.yaml` / `production.yaml` / `build-report` | 覆盖、重叠、越界、构建 | 画面是否在动 |
| 画面运动 | `media-qc.json` 的 `freeze_intervals` | 像素是否变化 | 变化是否有意义 |
| 视觉质量 | 人工看片 | 构图、层级、节奏、可读性 | 不能自动打分 |

`animation-score` 仍然保留，但它是**诊断工具**，`release_gate=metric_only`，不是发布门禁。发布只看 `quality-gate` 的 hard + 人工签核。

## 3. D-071 的落地

`beats.py` 现在返回结构化诊断：

| 检查 | 旧行为 | 新行为 |
| --- | --- | --- |
| 旁白段落未覆盖 | error | error |
| 镜头重叠 / 间隙 | error | error |
| 镜头结束不在 1.0 | error | error |
| 未知 grammar | error | error |
| 字幕带未预留 | error | error |
| 配色对比度 | error | error |
| 单镜头 <5s / >16s | error | **warning** |
| 动作数 < grammar 要求 | error | **warning** |
| 第一个动作晚于 35% | error | **warning** |
| 动作间隔 >4s | error | **warning** |
| 相机移动缺动机 | **schema error** | **warning** |
| 长寿命对象比例不足 | error | **warning** |

`beats-validate` 只在 `errors` 非空时 exit 1；`quality-gate` 的 `grammar_failures` 只收 errors，warnings 进入 `grammar_warnings`。

`CameraMove.motive` 从 `min_length=8` 改为普通字符串，短动机不再导致加载失败；`BeatShot.beats` 从 `min_length=2` 改为 1，单动作镜头可以存在并被警告。

## 4. 评分修正

`animation_score.py`：

- **freeze**：不再看 `freeze_counts_against`；所有 grammar 都按 9 段/分钟计分。`media_qc` 缺失时 freeze=0，没有像素证据就没有分。
- **camera**：没有 camera move 时 camera=0，不再给 10 分免费分。
- **gates**：只有结构 errors 或 build fail 才归零；creative warnings 不影响 gates。
- **verdict**：只有 errors 或 build fail 才 fail；warnings 不 fail。
- **输出**：新增 `errors`、`issue_errors`、`issue_warnings`、`freeze_evidence`、`score_source`。

重算结果：

| 课程 | 旧分 | 新分 | 变化 |
| --- | ---: | ---: | --- |
| 05 | 100.0 | 84.7 | 相机 0（原 10）、冻结 9.7（原 15） |
| 06 | 99.0 | 98.8 | 有 1 次相机；audio-mix 后 9 段冻结（9.1/分钟） |

05 的 84.7 仍然偏高，因为 motion/continuity/pacing 来自节拍表自报；它只说明"节拍表写得很满"，不说明"画面在动"。这正是 `score_source` 要提示的。

## 5. 不新增评分器

- 不新增第二个 0–100。
- 不把视觉美感变成程序分数；构图、层级、字体、节奏仍由人看片。
- 冻结检测只作为像素证据；阈值 9 段/分钟来自自家参考样片，不是普适标准。不同 grammar 的合法静止由人解释，不由程序豁免。
- 需要新指标时，先证明它能区分"好/坏"的真实样本，再加；否则只报告。

## 6. 验收

1. 一个 60 秒静止画面 + 写满 beats 的样例，分数不得接近 100。
2. 一个没有 camera move 的样例，`components.camera=0`，不再拿 10 分。
3. 一个没有 `media-qc` 的样例，`components.freeze=0`，`freeze_evidence=missing`。
4. 长寿命对象不足只产生 warning，`components.gates` 仍为 15，`verdict=pass`。
5. `beats-validate` 对 3 秒 1 动作、但覆盖完整的镜头 exit 0，并打印 warning。
