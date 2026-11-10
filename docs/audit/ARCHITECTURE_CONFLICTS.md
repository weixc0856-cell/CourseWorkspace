# 架构矛盾与生产规则冲突

> 状态说明（2026-11-10 稍后）：本文件保留审计时的证据与建议；C-01～C-30 的当前状态以 [../stabilization/MASTER_REMEDIATION.md](../stabilization/MASTER_REMEDIATION.md) 为准。

- **审计日期**：2026-11-10
- **范围**：契约、时间基元、质量门禁、自动化、交付、品牌、文档
- **原则**：只记录能从代码、配置、产物或实跑复现的问题；没有证据的写"待验证"
- **优先级**：P0 影响核心生产或导致错误交付；P1 影响重要能力或输出质量；P2 影响效率、维护或扩展；P3 优化建议

---

## 0. 结论

项目内部的主要矛盾不是"模块太多"，而是**同一件事有几套并行的权威**：

- 一门课有 6 种时间/镜头表示（storyboard、director plan、beats、production.yaml、shots.json、TimelineSpec），没有任何一门课把它们对齐；
- 质量有四套结论（`build-report.verdict`、`quality-report.QUALITY_PASS`、`quality-gate.releasable`、producer `status`），语义不同，却都读作"通过/完成"；
- 画面生产有 4 条路径（Manim、CodeVideo、Motion、Blender），验收深度不同，真实课程主要用的 Manim 反而检查最浅；
- 品牌有 2 套视觉语言（Remotion 2D、Three.js 3D），同时存在。

这些问题不是靠再引入一层抽象能解决的；需要**删减权威**，不是增加。

## 0.1 本轮落实状态（2026-11-10）

| 编号 | 状态 | 证据 |
| --- | --- | --- |
| C-01 | **部分** | `plan-audit`、`build --storyboard-source director`；05/01 迁移未做 |
| C-02 | **已实施** | `beats.py` 的 errors/warnings；`beats-validate` 只对 errors exit 1 |
| C-03 | **已实施** | `VERIFY_*` 状态；`incomplete_checks`；`release-approve` |
| C-04 | **已实施** | 05 100→84.7；无相机 0 分；无 media-qc freeze 0 分 |
| C-05 | **已实施** | ContentQA task_id 带 run_id；两次运行保留两套记录 |
| C-06 | **已实施** | `package` / `package-verify`；build-report 带 sha256/run_id |
| C-07 | **部分** | 06 SRT 已重排；01 未重排/未批准 |
| C-08 | **已实施（06）** | `subtitles.bilingual: false`；V-31 覆盖 Remotion |
| C-09 | **未实施** | 仍是手写镜头；模板/Agent 实验未做 |
| C-10 | **已实施** | `verify_media` 用于 Manim/Blender；Motion/CodeVideo 原有 |
| C-11 | **已实施** | `check_evidence.py`；178 引用 / 88 缺失 |
| C-12 | **已实施** | PROJECT_STATUS/ACCEPTANCE 增加 2026-11-10 基线 |
| C-19 | **已实施** | compose 超时按 `lesson.duration.target_seconds × 3` 推导，01 为 3600 s |
| C-22 | **已修主要项** | ARCHITECTURE/FRONTEND 的旧句仍待改；计数已更新 |
| C-27 | **已实施** | V-31 不再写 "subtitles disabled" |

---

## 1. P0：影响核心生产或导致错误交付

### C-01 六种镜头/时间表示并存，没有一门课对齐

**证据**

| 课程 | `storyboard.yaml` | 导演计划 `build/<slug>/director/director_plan.json` | 节拍表 `authoring/beats.yaml` | 生产契约 `production.yaml` | `build` 实际使用 |
| --- | ---: | ---: | ---: | ---: | --- |
| 01-transformer-demo | 5 镜头 | 12 镜头 / 5 章 | 无 | 无 | storyboard（5） |
| 05-transformer-5min | 1 镜头（292.38 s） | 3 镜头 / 1 章 | 27 个镜头条目 | 无 | storyboard（1） |
| 06-attention-sample | 0 镜头 | 未生成 | 7 镜头 | 7 镜头 | production（7） |

- `CourseControl/src/course_control/pipeline.py` 的 `run_build` 读 `LessonPaths.load(..., storyboard_override=options.storyboard)`；`storyboard_override` 默认 `None`。
- `producer-rebuild` 只在打印里建议 `build --storyboard ...`；不会自动替换。
- 05 的三个"镜头数"分别是 1、3、27；它们不是同一粒度，也不是同一份数据。

**影响**

- 导演层不驱动构建，制片层的增量重建与实际渲染单元不一致。
- 05 的"27 个镜头条目"只是节拍表里的子段，无法单独重渲染；`producer-affected` 报 3 个镜头，但三者都来自同一个 `attention_5min.py` 的 `AttentionFiveMinuteScene`，`render:manim` 仍会整场景重渲。
- 任何"重渲染一个镜头"的承诺，在 scene 模式下是名义上的。

**建议**

1. 明确一个课程只选一种时间基元：`deck/scene` 用 Page，`shots` 用 Shot；不要在同一门课里同时维护 storyboard 与 production。
2. 让 `build` 默认消费导演计划产出的 `storyboard.director.yaml`，或在 `lesson.yaml` 显式声明 `build.storyboard_source: storyboard|director`；不要让"人工加 --storyboard"成为唯一通路。
3. 如果保留 scene 模式，就把"镜头"定义成 `attention_5min.py` 里的可独立渲染函数/类，而不是节拍表里的小段；否则删除该课的"镜头级增量"表述。

**验收**：任选 05 或 01，改动一节拍后，`producer-affected` 给出的重渲命令只重渲受影响的渲染单元，且产物哈希只在该单元变化。

---

### C-02 D-071 已决定"阈值只作诊断"，代码仍在硬失败

**2026-11-10 更新：已落地。** `beats.py` 已拆 errors/warnings；`beats-validate` 只对 errors exit 1；`quality-gate` 的 grammar 只收 errors。以下为审计时的证据。

**证据**

- `docs/DECISIONS.md` D-071："语法阈值……只报告，不作放行；`beats-validate` 的硬失败只保留结构缺陷……**实施状态：决定已记录，代码未改**。"
- `CourseControl/src/course_control/beats.py:32-35`：`MAX_SHOT_SECONDS=16.0`、`MIN_SHOT_SECONDS=5.0`、`MAX_GAP_SECONDS=4.0`、`MIN_LONG_LIVED_RATIO=0.5` 仍是模块常量。
- `beats.py:58`：`beats: list[Beat] = Field(min_length=2)`；一个只有 1 个动作的镜头连加载都失败。
- `quality_gates.py:114`：`releasable = not hard_fail and not remaining`；grammar 失败仍阻止发布。

**影响**

- 一条 3 秒但讲清楚的镜头会被判失败，与 D-071 和"三条原则"直接冲突。
- 06 的 production log 记录：为了通过节拍规则补动作、调整动作间隔；这是规则在驱动创作，而不是创作驱动规则。
- 文档与代码给出相反结论，后来者无法判断哪条为准。

**建议**

- 把 `beats.py` 的时长/密度/长寿命/间隔改为 `warning`，只保留覆盖漏洞、重叠、越界、配色对比度等结构错误为 `error`。
- `quality_gates.decide` 把 grammar 失败改为 `grammar_warnings`，`releasable` 只由 hard 和人工签核决定。
- 同步更新 `docs/工业化动画工作流.md` §3、`ACCEPTANCE.md` 的门禁描述。

**验收**：构造一个 3 秒、1 个动作、但旁白覆盖完整的镜头；`beats-validate` 返回 0，`quality-gate` 不因 grammar 阻断，报告里出现 warning。

---

### C-03 "QUALITY_PASS" 与 "releasable" 可以在未验证的情况下为真

**2026-11-10 更新：已落地。** `quality.py` 新增 `VERIFY_*` / `QUALITY_VERIFIED` / `REVIEW_APPROVED`；`quality-gate` 把 `incomplete` 视为阻断，并读取 `quality-report`。nvda 现在 `releasable=no`。以下为审计时的证据。

**证据**

- `CourseControl/src/course_control/quality.py:5`：`QUALITY_PASS requires every dimension to be PASS or WARN`。
- 05 的 `quality-report.json`：Q1/Q2/Q3/Q5 全 WARN，`QUALITY_PASS=True`。
- `quality_gates.py:39,51`：hard checks 只收集 `status == "fail"`；`incomplete` 和 `warn` 不算失败。
- nvda 的 `media-qc.json` 是 `INCOMPLETE`（`ASR alignment not run`），但 `build-report.verdict=pass`；若对 nvda 跑 `quality-gate`，`hard_failures` 会是空，`releasable` 会是 `true`。

**影响**

- "QUALITY_PASS" 读起来像"质量通过"，实际是"没有 BLOCKED/INCOMPLETE"；05 带着未核实的事实和未签核的发布状态拿到了它。
- `releasable` 不区分"检查通过"和"检查没跑"，与项目自己的"skip ≠ pass"原则冲突。

**建议**

1. 把 `QUALITY_PASS` 改名为 `QUALITY_COMPLETE`；新增 `QUALITY_VERIFIED`，只有所有维度 PASS 才为真。
2. `quality_gates.hard_checks` 把 `incomplete` 视为硬失败，或在 `decide` 中新增 `incomplete` 列表并阻止 `releasable`。
3. `release-approval.json` 增加 schema 与 CLI（`course-control release-approve`），否则人工签核无法被程序读回。

**验收**：对 nvda 跑 `quality-gate`，`releasable=false`，`hard_failures` 包含 `media.speech_match: incomplete`。

---

### C-04 动画评分有 25–40 分是"免费分"，100 分不能证明画面在动

**2026-11-10 更新：已落地。** 无相机 0 分；freeze 对所有 grammar 计分；无 `media-qc` 时 freeze 0；05 从 100 降到 84.7，06 从 99 降到 98.8。以下为审计时的证据。

**证据**

- `shared/grammars/visual-grammars.yaml` 的 7 个 grammar 全部 `freeze_counts_against: false`（第 15、29、44、58、72、86 行等）。
- `animation_score.py:113-114`：`freeze_counts = any(...)`；没有 grammar 计数时 `freeze = 1.0`，直接拿满 15 分。
- `animation_score.py:101-102`：没有任何 camera move 时 `camera = 1.0`，再拿满 10 分。
- 05 的 `gate.json`：`score=100.0`，同时 `freeze_intervals=58`、`freeze_per_minute=12.16`、`camera_moves=0`。
- 06 的 `gate.json`：`score=99.0`，`freeze_intervals=8`，同样拿满 freeze 15 分。

**影响**

- 分数的主要来源是作者自己写的 `beats.yaml`，不是像素。一个镜头可以声明很多动作、实际画面却长时间静止。
- 05 的 58 段冻结和 06 的 8 段冻结都没有进入分数，评分器无法区分"稀疏但合法"和"该动没动"。
- 文档把 `animation-score` 称作"指标工具"，但实际展示时仍被当作质量证据（PROJECT_STATUS 写 94.7/100，gate 写 100）。

**建议**

- 冻结分改为真实像素指标，且对所有 grammar 生效；如果某种语法允许长时间静止，应在 profile 中写明上限，而不是永远不计。
- camera 分在 `camera_moves=0` 时应记 0 或标记 `not_applicable`，不能给满分。
- 在 UI/报告里把"分数"改成"节拍表自评 + 像素指标"两栏，避免把自评当质量结论。

**验收**：用一段 60 秒静止画面 + 一份写满 beats 的 `beats.yaml` 跑分，分数不得接近 100。

---

## 2. P1：影响重要能力或输出质量

### C-05 ContentQA 任务记录被后一次运行覆盖

**证据**

- `ContentQA/src/content_qa/review.py:209`：`task_id = f"contentqa-{lesson}-{chunk.task_id}"`，没有 run id、时间戳或内容哈希。
- `shared/ai_runtime/src/ai_runtime/tasks.py:111-116`：任务记录按 `task_id` 命名并原子覆盖。
- 05 的 `review_model_a.json` 生成于 00:45（deepseek），`review_model_b.json` 生成于 06:58（Qwen）；两次都使用 `contentqa-05-transformer-5min-slide-001-1` 这样的同一 id。运行时目录里只剩 Qwen 的记录，deepseek 的记录已被覆盖。

**影响**

- A/B 交叉审查的 `provider` 不可追溯；`review.json` 写 `model=deepseek-flash`，任务记录却是 `provider=local` / Qwen。
- 任何"哪次运行、哪个后端、花了多少"的审计都失效。

**建议**

- `task_id` 加 `run_id`（时间戳 + 随机短哈希）或 `input_sha256`；任务记录目录按 run 分子目录。
- `review.json` 写入 `run_id`、`backend`、每个 task 的 `provider` 与 `model`，与任务记录一一对应。
- 增加测试：同一 lesson 连续跑两次，任务记录应有 2 套，不互相覆盖。

**验收**：连续两次 `content-qa review` 后，`runtime/tasks/` 保留两套记录，`review.json` 的 run_id 能定位到对应一套。

---

### C-06 交付包不符合自己的交付规范

**2026-11-10 更新：已落地。** `course-control package` 生成标准包与哈希；build-report 新增 `run_id` 与 artifact `sha256`；05/06 已生成并 `package-verify` 通过；01 因缺成片正确失败。以下为审计时的证据。

**证据**

- `docs/课程生产交付物规范.md` 要求：干净母版、字幕版、`final/subtitles.srt|ass|vtt`、`build-report.json`、`burn.json`、`delivery-checklist.md`、`metadata.json`、`narration.meta.json`、`review.json`、镜头证据、日志，并记录 sha256。
- `CourseControl/src/course_control/contracts.py:424-428` 的 `Artifact` 只有 `path/kind/size_bytes/probe`，没有 `sha256`。
- 05 的 `final/` 只有 mp4、build-report、burn.json、render-props.json；06 的 `final/` 只有 mp4、build-report 和 8 张 QA 抽帧；两者都没有 `final/subtitles.*`、`metadata.json`、`delivery-checklist.md`。
- 06 没有 `audio/mix.json`，母版是 -22.8 LUFS；Q5 仍说"all release artifacts present"。

**影响**

- "交付了"无法按规范复核；哈希缺失意味着无法证明交付文件就是被验收的文件。
- 06 的响度问题在 Q5 里不可见，因为 Q5 不要求 mix。

**建议**

- `build-report.json` 为每个 artifact 增加 `sha256` 与 `run_id`；或直接复用 `RenderArtifact`。
- 增加 `course-control package`：按交付规范生成 `final/subtitles.*`、`metadata.json`、`delivery-checklist.md`、`manifest.json`（含哈希），缺项即失败。
- Q5 的 required 增加 `audio/mix.json`（当有旁白时）与 `final/subtitles.*`（当字幕启用时）。

**验收**：对 05 跑 `package`，生成完整交付包；删掉任一必需文件，命令 exit 1 并列出缺项。

---

### C-07 字幕按字符比例切分，断行会切断词和句子

**2026-11-10 更新：部分落地。** 06 已重排并通过 V-31；01 的 357 cue 草稿尚未重排/批准；05 已批准 SRT 保持原样（V-31 已 pass）。以下为审计时的证据。

**证据**

- `CourseControl/src/course_control/subtitles.py` 的策略是"段内按文本比例切分"（ARCHITECTURE §7）。
- 01 的 `bilingual.draft.srt`：cue 2 以 `In 2017, a paper titled Attention Is All` 结束，下一 cue 才接 `You Need introduced...`；cue 3 以 `and its defining choice was to replace` 结束，下一 cue 才接 `recurrence and convolution...`。
- 05 成片 250 s 的字幕：中文第二行以"单一表"结尾，第三行是"示，。"，把"表示"切断并留下孤立标点。
- 06 的 production log 自己记录：逐词字幕"常从词中间开始（如'阵每一行…'）"。
- V-31 只在 `subtitles.render == "burn_in"` 时检查（`verify.py:441` 起）；06 用 `render: remotion`，V-31 为 `not_applicable`，没有行宽/CPS/双语检查。

**影响**

- 字幕可读性低于发布水准，尤其是中文；这是"交付做硬"的直接扣分项。
- Remotion 模式完全绕过 V-31，配置 `top_language: en` 但实际只有中文，也没有任何检查报警。

**建议**

- 用标点 + ASR 词边界做分段：优先在句末标点切，其次在逗号/顿号，绝不在词中间切；中文按分词或至少按标点/助词边界。
- 增加后处理断言：中文行不以标点开头、不把 2 字词拆到两行、英文 cue 不以介词/冠词结尾。
- 把 V-31 扩展到所有字幕模式；`render: remotion` 也要检查双语完整性（或显式声明单语并关闭 top_language）。

**验收**：01 的 357 cue 与 05 的 80 cue 重新切分后，人工抽查 20 条无断词；V-31 对 06 也执行。

---

### C-08 06 的配置声明双语，实际只有中文

**2026-11-10 更新：已落地。** 06 声明 `subtitles.bilingual: false`；SRT 已重排；V-31 覆盖 Remotion 字幕并 pass。以下为审计时的证据。

**证据**

- `lessons/06-attention-sample/lesson.yaml:30-35`：`subtitles.enabled: true`、`render: remotion`，但没有 `top_language`/`bottom_language`（默认 en/zh-Hans）。
- `lessons/06-attention-sample/subtitles.srt` 只有中文；`build/06-attention-sample/subtitles.srt` 同样只有中文。
- `build-report.json` 的 V-31 是 `not_applicable: subtitles disabled`，尽管字幕是启用的；这是 V-31 只认 burn_in 的副作用。

**影响**

- 配置与产物不一致；读者会以为这是双语课。
- 与 FR-19"英文在上、简体中文在下"的默认契约冲突。

**建议**

- 要么为 06 生成双语字幕（英文翻译 + 中文原文），要么在 `lesson.yaml` 显式写 `subtitles.languages: [zh-Hans]`，并让 V-31 接受单语声明。
- 修正 V-31 的 detail 文案：不是"subtitles disabled"，而是"mode not covered"。

**验收**：06 的 `build-report.json` 不再出现"subtitles disabled"的误导性 detail；配置与 SRT 语言一致。

---

### C-09 视觉生产仍是逐镜头手写，没有 Agent 生成证据

**证据**

- `CodeVideoStudio/shots/*/main.js` 150–550 行，每个镜头独立实现；`attn-matrix/main.js` 是手写 Canvas 绘制。
- `ManimSandbox/05-transformer-5min/attention_5min.py` 1,622 行，102 个 `self.play`。
- `runtime/tasks/` 只有 `authoring.translate`（41 条）与 `contentqa.review`（23 条）；没有 `shot.generate`、`scene.code` 之类的任务记录。
- 06 的 production log：CodeVideo 源码 + 预渲染约 25 min，Manim 镜头 5 次重渲；每镜人工修改 0–5 次。

**影响**

- "Claude Code 作为默认生产后端"覆盖的是文本、翻译、审查，不覆盖画面生成。
- 视觉质量与产量线性依赖人工写代码；这就是为什么 62 秒要 25 分钟镜头源码 + 返工。
- 任何"自动化率 95%"的说法，只对渲染阶段成立。

**建议**

- 不急着造 Agent；先把"一个镜头从 SPEC 到 VERIFY"的模板固化（参数化的标题/矩阵/流程图三种），让人写得更快。
- 如果要试 Agent 生成，选一个镜头做对照实验，记录任务记录、返工次数、帧审结果；没有这组数据前，不要写进路线图。

**验收**：同一 SPEC 由人和 Agent 各生成一版，记录工时、返工、人工评分；只有 Agent 版不劣于人工版才扩大。

---

### C-10 四个渲染器的验收深度不一致，主力引擎反而最浅

**2026-11-10 更新：已落地。** 新增 `verify_media`；Manim/Blender 现在检查分辨率/帧率/时长；lesson-smoke 的 Blender 构建通过。Motion/CodeVideo 保持原有。以下为审计时的证据。

**证据**

- Motion：`adapters/motion_canvas.py` 校验分辨率、帧率、时长（±25%）、重试 2 次。
- CodeVideo：`adapters/code_video.py` + `code_video_qc.py` 校验分辨率、帧率、时长、codec、pix_fmt、audio、黑帧、冻结。
- Manim：`adapters/manim.py` 只 `probe_media` 后复制；没有逐镜头时长/分辨率检查，没有重试。
- Blender：`adapters/blender.py` 只检查退出码与输出文件存在；连 `probe_media` 都没有。
- 后续 V-12 会检查所有 animation/recording 镜头的分辨率/帧率，但不检查时长、黑帧、冻结、音频流。

**影响**

- 05 用的 Manim、01 用的 Manim+Blender，恰好是检查最浅的两条路径。
- 一个 Manim 镜头如果比旁白短，collect/verify 可能靠时间线兜底，但不一定有明确失败。
- "统一动画适配器"只统一了接口，没有统一验收。

**建议**

- 把 CodeVideo QC 的核心检查（分辨率/帧率/时长/codec/pix_fmt/audio/黑帧）抽成共享函数，四个适配器都调用；冻结保持 warning。
- Manim 增加与 Motion 相同的时长容差检查；Blender 至少 `probe_media` 并校验分辨率/帧率/时长。
- 在 `StageOutcome` 里记录每个镜头的 QC 摘要，便于报告对比。

**验收**：四个适配器对同一段坏视频（错分辨率、短 2 秒、黑帧）都给出 fail 或 warning，而不是只有 CodeVideo 报。

---

### C-11 证据路径被文档引用，但产物已不存在

**证据**

- `docs/ACCEPTANCE.md` 引用 `build/blender-scene-acceptance/`、`build/p1b-annotation-evidence/`、`build/p3-legend-evidence/`、`build/manim-fft/`、`build/manim-transformer/`、`build/manim-multi-head/`、`build/r1/`、`build/r1-smoke/`、`build/code-video-studio/`、`build/code-video-qc2/`、`build/videozero-poc/`；本次检查时这些目录均不存在。
- `lessons/02-car-aerodynamics/delivery-checklist.md` 勾选"clean master + captioned master"，但 `build/02-car-aerodynamics/` 不存在。
- `docs/PROJECT_STATUS.md` 的 292.367 s、307.367 s 等数字仍有产物支持，但大量 POC 证据没有。

**影响**

- 文档的"已验证"无法从本机回读；新接手的人只能相信文字。
- 与项目自己的"证据可追溯"原则冲突。

**建议**

- 新增 `scripts/verify-evidence.ps1`：解析文档中的 `build/...` 路径，检查存在性与 sha256；缺失的标 `MISSING`，不 blocking，但生成清单。
- 对关键证据（成片、manifest、build-report）做归档副本，至少保留哈希与 30 秒样片。
- 文档引用证据时写日期与哈希，不只写路径。

**验收**：`verify-evidence` 输出一张表，列出所有被引用但缺失的路径；下一次审计不再需要手工发现。

---

### C-12 项目状态落后于产物，路线图会重复劳动

**证据**

- `docs/PROJECT_STATUS.md` 与 `docs/项目差距清单.md` 仍写"01-transformer 整课旁白缺失/blocked"；实际 `build/01-transformer-demo/narration/narration.wav` 已存在，1195.61 s，54 段，生成于 2026-11-09。
- 01 的 12 页截图、7 个已渲染 Manim 文件（storyboard 使用其中 4 个）也已存在；`build/01-transformer-demo/blender/` 与 `lessons/01-transformer-demo/subtitles.srt` 缺失。
- `docs/项目差距清单.md` 的 P0 第 1 条"整课旁白"已完成；第 2 条"实测字幕"已生成草稿；第 3 条"完整构建"仍未做。

**影响**

- 下一轮如果照差距清单执行，会重复做已经完成的 TTS。
- "当前状态"不可信，审计与决策都失去基线。

**建议**

- 把 `PROJECT_STATUS.md` 的 01 状态改为：`narration=done`、`slides=done`、`manim=done`、`blender=missing`、`subtitles_draft=done`、`subtitles_accept=missing`、`final=missing`。
- 把差距清单的 P0 改为剩余项，而不是历史项。
- 每次真实产物变化时更新一行，不要求全量重写。

**验收**：`PROJECT_STATUS.md` 与 `build/01-transformer-demo/` 的文件状态逐项一致。

---

## 3. P2：影响效率、维护或扩展

### C-13 两代 Blender Schema，IR v2 没有进入真实课程

- v1 课程任务（`BlenderStudio/tasks/<lesson>/*.json`）由 `adapters/blender.py` 调用；v2 场景（`BlenderStudio/tasks/scene-system/*.json`）由 `scene-run` 调用。
- 01 的 storyboard 有 1 个 v1 Blender 镜头；v2 只用于 8 个 demo。
- 两套 schema 的校验器、路径约束、验收项不同；新作者很难判断该用哪套。
- **建议**：在 `docs/Blender场景任务IR-v2.md` 顶部写清"课程镜头用 v1 还是 v2"的决策树；如果 v2 一年内不进入课程，标为 POC，不再扩展示例。

### C-14 V1 时间线是并行产物，Remotion 仍读 legacy 字段

- `collect` 同时写 `shots.json` 与 `contracts/timeline.spec.json`；`CourseTimeline` 读 `metadata.legacy_transition`、`legacy_motion`、`legacy_presentation`、`legacy_annotations`。
- V1 的 `ShotSpec`/`TimelineSpec` 是规范化视图，但没有成为唯一输入。
- **建议**：要么把 legacy 字段迁进 V1 的正式字段并删除桥接，要么在文档里明确"V1 只读视图，不承诺消费"；不要让读者以为已经原生。

### C-15 `build-report` 没有 run_id 与输入哈希

- `contracts.py:424` 的 Artifact 无 sha；`BuildReport` 无 `run_id`、无输入哈希。
- 交付规范 §3 要求 `run_id` 与 `hashes`；producer manifest 有 sha，但 build-report 没有。
- **建议**：给 BuildReport 加 `run_id`、`inputs_sha256`、artifact `sha256`；这比新增一层报告更便宜。

### C-16 品牌有三套视觉语言，3D 与 2D 不一致

- Remotion `BrandMark`：`W_PATH = M24 44 L66 132 L120 68 L174 132 L216 44`，中间有橙色 `CURRENT_PATH`。
- 3D opener（`CodeVideoStudio/shots/brand-intro/out/wayne-opener.mp4`，19 s 帧）：巨幅黑 W 没有橙色电流，背景是暖灰（约 `#E8E3D8`），与 `paper #FBFAF7` 不同。
- `BrandIntro/README.md` 自己说 Gate 1 的灰盒"不作为下一版的视觉基础"；20 s opener 是"可看的 v1"。
- **建议**：在 3D 片头通过 Gate 3 之前，不要把它当作品牌资产；如果保留，至少让 W 的橙色电流与 2D 一致，背景回到 `paper`。

### C-17 three.js 在 5 个 shot 里重复 vendored

- `CodeVideoStudio/shots/{attention-flow? no, brand-desktop, brand-intro, primer-aging, primer-hero, primer-rps}/three.module.js` 各 53,044 行；合计约 26.5 万行。
- `.gitattributes` 已标记 linguist-vendored，但磁盘与升级仍是 5 份。
- **建议**：抽一个 `CodeVideoStudio/vendor/three/` 共享目录，shot 用相对路径或构建时复制；升级只改一处。

### C-18 Remotion Root 里同时有生产合成与探针

- `Root.tsx` 注册了 `CourseVideo`、`CourseTimeline`、`ScenePage`、`PrimerPoc`、`PrimerQuad`、`R1Smoke`、`FormulaProbe`、`AccessProbe`、`ChapterCard`、`BrandPreview` 等。
- `ChapterCard` 已实现但没有进入时间线；`PrimerPoc/PrimerQuad/R1Smoke` 是 POC。
- **建议**：把探针移到 `src/probes/` 并在文档标注"非生产"；生产构建只暴露需要的 composition，减少误用。

### C-19 固定 1800 s 超时对 20 分钟课程偏紧

- `adapters/remotion.py` 的 `run_command(..., timeout=1800)`；05 的 compose 是 371.5 s / 292.4 s ≈ 1.27× 实时。
- 01 的 1195.6 s 旁白按 1.27× 估算约 1518 s，距离 1800 s 只有 18% 余量；如果 deck 模式 + 多 overlay 更慢，可能超时。
- **建议**：按 `lesson.duration.target_seconds` 推导超时（例如 `max(1800, 3 × target)`），或在 01 构建时实测并记录。

### C-20 没有顶层恢复/调度，producer 只报告不执行

- `pipeline.run_build` 在第一个失败阶段返回；没有 `--resume`。
- `producer-run` 只生成 order/state/manifest；`producer-rebuild --execute` 才调用 build，且需要 `allow_render`。
- **建议**：短期不要造调度器；在 `build` 里加 `--resume-from <stage>`，复用已有产物；长期再考虑队列。

### C-21 音频与参考音依赖工作区外路径

- 05 的 `audio/mix.json` 引用 `<bgm_root>/commons/schubert_d664_piano.wav`；06 的 `narration.meta.json` 引用 `<voice_ref>`。
- 这些路径不在 `CourseWorkspace` 内，也不在仓库；换机或目录变动后无法复现同一母版。
- **建议**：在 `config/local-paths.yaml` 记录资产根目录，并在 `audio/mix.json`/`narration.meta.json` 写 `asset_sha256` 与 `license_status`；归档时复制或至少保留哈希。

### C-22 文档过期点集中出现

- `ARCHITECTURE.md:58` MotionStudio"不自动导出"；`FRONTEND_ASSESSMENT.md:34,65` 无 CLI/人工导出；`PRD.md:27` ASR 非目标；`ACCEPTANCE.md` 计数 412/550 vs 实际 438/585；`提交前检查清单.md` 五套 vs 六套。
- **建议**：把"最近核实日期"写进每份文档头部，并在 `check.ps1` 里加一个文档计数测试（可选）。

### C-23 五层审查没有统一裁决队列

- 05 的 `build/05-transformer-5min/review/` 同时有 `review.json`（23 findings）、`review_cross.json`（43 claims）、`claim_registry.json`、`review_model_a.json`、`review_model_b.json`、`conflict_report.md`、`evidence_report.md`；`quality/` 还有 `teaching-qa.json`。
- 这些输出由 ContentQA、claims、cross_review、teaching_qa、quality-report 五个环节分别产生；没有一份 `decisions.json` 把"某条 finding 被接受/驳回/已修"记录下来。
- 结果是：同一条 claim 可能在 review 里 supported、在 cross_review 里 disputed、在 quality-report 里 WARN；人需要自己对照三份文件。
- **建议**：不新增第六个审查器；增加一个 `review/decisions.json`（finding_id → accepted/rejected/fixed + by/at + note），由人填写，`quality-report` 读取它作为 Q1/Q2 的输入。没有裁决的 finding 一律算 `needs_human_review`。

### C-24 同一个生产行为有多个配置源

| 行为 | 配置源 | 冲突表现 |
| --- | --- | --- |
| 课程时长 | `lesson.yaml.duration`、`lecture_notes.md` 的"时长预算"、`narration.meta.json` 的 measured、`shots.json`/`timeline.spec.json` | D-032 规定"measured 单向权威"，但四个文件都能读；05 的 target 293 / 旁白 292.38 / 时间线 292.37 / 节拍表 286.08 |
| 模型路由 | `config/model-routing.yaml`、`.env`、`config/content-qa.yaml`、`ModelingStudio/config/workflow.yaml` | 环境变量覆盖 YAML；不同工程的默认模型不同；读者要拼四份文件才知道实际 provider |
| 字幕语言 | `lesson.yaml.subtitles.top/bottom_language`、实际 SRT 内容、06 的默认值 | 06 配置默认双语，SRT 只有中文；没有一致性检查 |
| 合成模式 | `lesson.yaml.compose.mode`、`compose.renderer`、adapter 的 timeline 存在性回退 | `mode=shots` 时 renderer 仍可为 timeline；timeline 缺失时静默回退 shots.json |
| 验收口径 | `build-report.verdict`、`quality-report.QUALITY_PASS`、`quality-gate.releasable`、producer `status` | 四个"通过"语义不同 |

- **建议**：在 `build` 开始时打印一份"生效配置报告"（每个值 + 来源文件 + 是否被环境变量覆盖），写进 `build-report` 或 `logs/config-resolution.json`。这比新增配置层便宜，也能让 05 的四个时长值有唯一解释。

---

## 3.1 P0 新发现（2026-11-10 实跑）

### C-30 20 分钟 compose 在 frame 3,879 停滞（已修复）

- 01-transformer-demo 的 build 已通过 validate/capture/manim/blender/collect；compose 启动后 Remotion 进度停在 **3,879 / 35,868**（约 129.3 s，slide 2 base），`stdout` 最后更新后 25 分钟无推进；8 个 `chrome-headless-shell` 仍在，`pre-encode.mp4` 停在 15:10，最终未生成 `course-video.mp4`；build-report 记录 `compose: remotion exited 4294967295`（stderr 为空）。
- 这不是超时：compose 超时已按 `target_seconds × 3` 改为 3600 s；这是渲染停摆。
- 影响：20 分钟课程无法交付；5 分钟课程不受影响。
- **根因（2026-11-10 复核）**：同一门课同时跑了多个 build。第二个 build 的 `stage-assets` 覆盖 `RemotionStudio/public/staging/01-transformer-demo`，而第一个 Remotion 仍在读同一目录，进度停摆。单 build + 干净 staging 后连续渲染超过 13k 帧，未再停。
- **最小修复**：
  1. `BuildLock`（`runtime/locks/build-<slug>.lock`）禁止同课并发 build；
  2. `run_command` 超时/Ctrl-C 时 `taskkill /T` 杀进程树，避免 chrome/node 残留；
  3. Blender 输出缓存 + MP4 收尾等待，坏文件自动重渲；
  4. 清理残留 chrome/node 后再跑，不并发测试/构建。
- **验收**：**2026-11-10 已通过**。单一 build + 清理后，01 输出 `1195.605 s / 1920×1080 / 30 fps`，`build-report.verdict=pass`，compose/burn/verify 全 pass。

---

## 4. P3：优化建议

### C-25 内容层的小矛盾

- 06 标题 `Attention in Ninety Seconds` / `九十秒看懂注意力`，实际 62.17 s；`duration.target_seconds: 62.3`。标题里的时长是计划值，不是实测值。
- 06 旁白说"注意力只能看它前面"（cue 11），这是 decoder 因果遮罩，不是所有注意力；01 的技术核查明确要求"Decoder self-attention must be masked/causal... do not describe it as ordinary self-attention"。
- 06 的矩阵标注"数值为示意，不是模型输出"是诚实的，但也意味着画面没有真实数据支撑。
- **建议**：标题不写时长，或写成范围；因果遮罩加一句"在解码器里"；如果矩阵只是示意，考虑用真实小模型输出（成本高）或明确标为"示意"并配一个真实例子。

### C-26 新闻片的幻灯片密度

- nvda 的 slides 是 8 页英文要点 + 每页底部一段 80–120 字中文 `zh-sub`；抽帧显示中文段落字号小、行距紧，视频里几乎不可读。
- 这与"把画面做好"和"deck 模式不再用于机制解释"（D-057）的精神冲突，但新闻片确实以 deck 为主。
- **建议**：新闻片把中文段落从幻灯片里移除，交给字幕；幻灯片只留英文要点与一个视觉焦点。

### C-27 验收文档的算术错误

- `ACCEPTANCE.md` §1：CourseControl 412 + ModelingStudio 33 + ai_runtime 50 + ContentQA 24 + Manim 18 + KnowledgeStudio 21 = 558，但写"合计 550"。
- **建议**：用一个脚本生成计数表，不手写。

### C-28 未提交的品牌工作

- 工作树有 `BrandIntro/`、`CodeVideoStudio/shots/brand-{intro,desktop}/`、`docs/品牌片头-3D桌面戏-设计.md` 未提交；分支也未合并。
- **建议**：在暂停 3D 片头前，至少提交"设计稿 + 失败记录 + 当前 v1"；否则下一次会话无法判断哪些是已决定的。

### C-29 06 的 `subtitle disabled` 文案

- `verify.py:500` 在非 burn_in 时写 `detail="subtitles disabled"`；当字幕启用但 render=remotion 时，这句话是错的。
- **建议**：改为 `detail="V-31 only covers burn_in subtitles"`，并把 remotion 字幕纳入检查。

---

## 5. 优先级汇总

| 优先级 | 编号 | 一句话 |
| --- | --- | --- |
| P0 | C-01 | 六种镜头表示，没有一门课对齐 |
| P0 | C-02 | D-071 已决定，代码仍硬失败 |
| P0 | C-03 | QUALITY_PASS / releasable 可在未验证时为真 |
| P0 | C-04 | 评分 100 含免费分，不能证明画面在动 |
| P0 | C-30 | 20 分钟 compose 在 frame 3,879 停滞 |
| P1 | C-05 | ContentQA 任务记录被覆盖 |
| P1 | C-06 | 交付包不符合自己的规范 |
| P1 | C-07 | 字幕断词、断句 |
| P1 | C-08 | 06 声明双语，实际单语 |
| P1 | C-09 | 视觉生产仍手写，无 Agent 证据 |
| P1 | C-10 | 四个渲染器验收深度不一致 |
| P1 | C-11 | 文档引用的证据已丢失 |
| P1 | C-12 | 项目状态落后于产物 |
| P2 | C-13..C-24 | Blender 双 schema、V1 并行、无 run_id、品牌不一致、three.js 重复、探针混入、超时、无恢复、外部资产、文档过期、审查无裁决队列、多配置源 |
| P3 | C-25..C-29 | 内容小矛盾、新闻密度、算术、未提交、文案 |

---

## 6. 不建议做的事

- 不要为 C-01 新增第七种"统一生产计划"抽象；先删掉或合并现有的两种。
- 不要为 C-04 再加一个评分器；先把现有评分里永远给满的分量去掉。
- 不要为 C-09 直接上 Agent 框架；先用模板和对照实验证明收益。
- 不要为 C-20 造调度服务；单机单用户，`--resume-from` 足够。
- 不要把 C-25 的内容问题变成新的硬门禁；它们需要编辑判断，不是程序判断。
