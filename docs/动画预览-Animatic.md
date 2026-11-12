# 动画预览（Animatic）

- **日期**：2026-11-12
- **状态**：可用。P1 完成（[工业生产线 V2.0](v2/工业化生产流程V2.0-建议稿.md) WP-2）。
- **命令**：`course-control animatic --lesson <slug>`

---

## 1. 它解决什么

正式渲染之前先看一遍：旁白走完一圈，画面够不够撑住，哪里讲得太久，哪里该换镜头。

它是决策工具，不是播放器，也不是成片。输出固定 480p，不回写 `deliver/`，不参与交付判定。看片结论仍然要人工写：叙事是否成立、画面是否有设计、节奏是否需要返工。

## 2. 用法

```powershell
# 默认：480p，用 build/<slug>/narration/narration.wav
course-control animatic --lesson a01-why-cars-need-aerodynamics

# 换一版旁白（草稿旁白、参考音频、外录）
course-control animatic --lesson <slug> --audio path/to/scratch.wav

# 只重出改过的镜头，其余走缓存
course-control animatic --lesson <slug> --shot page-005 --shot page-009

# 无声预览 / 改分辨率 / 丢掉缓存
course-control animatic --lesson <slug> --silent
course-control animatic --lesson <slug> --size 1280x720
course-control animatic --lesson <slug> --force
```

退出码：`0` 报告 `ok: true`；`1` 有 `fail` 检查项或构建失败；`2` 参数错误。

## 3. 时间线从哪来

按顺序取第一个存在的，**第一顺位是计时权威**：

| 顺序 | 来源 | 说明 |
| --- | --- | --- |
| 1 | `build/<slug>/timeline/page-plan.json` | 逐页 `start_s` / `duration_s`，旁白实测后由 `collect` 写出 |
| 2 | `build/<slug>/shots.json` 的 `base` 镜头 | 归一化时间线；`overlay` 镜头跳过并在警告里计数 |
| 3 | `build/<slug>/scenes/manifest.json` | 逐页片段，按累计时长推算起点 |

三者都没有时报错，并列出找过的位置。这也意味着 **animatic 不是 `build` 的替代**：先有 `collect`，才有预览。

## 4. 每个单元用什么画面

时间线决定"多久"，画面单独挑：

1. `scenes/pages/page-NNN.mp4` — 已渲染的逐页片段，最接近成片
2. `slides/slide-NNN.png` — 幻灯片截图
3. 占位黑帧 — 两样都没有，报告里记 `placeholder`

`shots.json` 里的镜头则按 `source` 取；文件缺失时退到同页幻灯片，并写警告。完整镜头（`kind=animation`）与幻灯片（`kind=slide`）都支持，因此静态页、动画片、渲染过的三维预览可以混在同一条时间线上。

## 5. 输出

```text
build/<slug>/animatic/
├── animatic.mp4          成片预览（480p + AAC 旁白）
├── picture.mp4           未混音的纯画面
├── animatic.json         产物清单：模式、单元、片段缓存键、音频哈希
├── timeline.json         实际使用的时间线（单元、起止、来源）
├── animatic-report.json  检查项、逐单元状态、警告
├── contact-sheet.png     等间隔抽样缩略图
├── audio/                本次使用的音频副本
├── frames/               每个单元取中点的一帧
└── cache/                concat 清单、标签图、片段缓存
```

镜号烧在画面左下角（`03/24  page-003`），避开幻灯片标题区。

## 6. 报告检查什么

| 检查 | 判据 | 失败含义 |
| --- | --- | --- |
| `pictures` | 每个单元都有画面 | 有时间线但没素材，预览会给出黑帧 |
| `picture_duration` | 与时间线总长相差 ≤ 0.10 s | 拼接丢帧或时间线本身有洞 |
| `audio_sync` | 旁白与画面相差 ≤ max(0.10 s, 总长 × 0.1%) | 旁白与画面长度对不上，通常是计时的真实问题 |
| `source_length` | 片段不短于其时段 | 源片不足，末帧被冻结填满（警告，不失败） |

`ok` 只看有没有 `fail`。`warn`（静音预览、短片段）是提示，不阻断。无旁白时 `audio_sync` 记 `warn: silent animatic`。

## 7. 缓存与局部重生成

片段缓存的键包含：单元 ID、画面类型、源文件 SHA-256、帧数、fps、分辨率、标签图 SHA-256。任一项变了才重编这一段。

`--shot <id>` 只是把指定单元排除在复用之外，其余照常命中缓存。实测：`--shot page-005` 在 24 单元上得到 `1 encoded, 23 reused`，总耗时约 2 秒。

## 8. 已知限制

- **不做叠层合成**。`overlay` 镜头不进画面，只在警告里计数。scene 模式如果叠了动画层，预览里看到的是底页。
- **不做转场**。一律硬切；占位转场留到后续。
- **480p 是预览规格，不是质量上限**。需要逐帧检查请用正式渲染。
- **短片段的末帧冻结**。`page-024` 这类片段比时段短几百毫秒时靠冻结末帧补齐；报告在 `source_length` 里点名。
- **不改课程内容**。它只读 `build/` 与旁白，不写 `lessons/`。

## 9. 实测（2026-11-12）

| 课程 | 模式 | 单元 | 时长 | 旁白 | 结果 |
| --- | --- | --- | --- | --- | --- |
| `a01-why-cars-need-aerodynamics` | pages | 24 clip | 1293.43 s | narration.wav 1292.84 s | `ok: true`；`page-024` 短 0.6 s（警告） |
| `01-transformer-demo` | pages | 12 still | 1195.60 s | 静音 | `ok: true` |
| `ai-economics-e01` | shots | 43 clip | 1200.00 s | narration.wav 1050.72 s | `ok: false` — 旁白比画面短 149 s |

第三行的失败是真实问题，不是工具噪声：`production.yaml` 排了 1200 s，旁白只有 1050.72 s，尾段 149 s 没有声音。同一条课在 `validate` 里也有 `[V-26] error: duration 1200.0s exceeds maximum 950.0s`。两个问题需要课程侧一起处理。

## 10. 在生产流程里的位置

放在 `collect` 之后、正式合成之前：

```text
design → storyboard / production.yaml → collect → animatic → 人工看片 → 修分镜或旁白 → 正式渲染
```

改分镜或旁白之后重跑一次即可，未受影响的片段直接复用。看片结论属于人工裁决，不写成程序判定。

## 11. 代码与测试

- `CourseControl/src/course_control/animatic/timeline.py` — 时间线与画面选择
- `CourseControl/src/course_control/animatic/builder.py` — 分段编码、拼接、混音、缓存
- `CourseControl/src/course_control/animatic/report.py` — 清单、检查项、contact sheet
- `CourseControl/src/course_control/cli/animatic.py` — 命令
- 测试：`CourseControl/tests/test_animatic.py`（11 例：时间线权威顺序、降级、补洞、帧网格、缓存键）
