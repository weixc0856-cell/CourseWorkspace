# 下一阶段路线图

- **审计日期**：2026-11-10
- **前提**：单机、单用户、CPU-only 本地模型、约 10–15 小时/周的有效开发时间；不新增团队
- **目标**：不是让系统更复杂，而是让下一支成片更好、更可信、更接近可发布
- **排序原则**：先交付，再讲真话，再做画面；最后才扩能力

> **2026-11-10 落实状态**：A-1（01 完整构建，1195.605 s，verdict=pass）、A-2（门禁语义）、A-3（06/01 字幕重排）、A-4（package/哈希）均已完成；B-1（构图）、B-3（06 QA）、B-4（nvda ASR）、B-5（05 契约）未做。详见 `docs/stabilization/MIGRATION_PLAN.md`。

---

## 0. 如果只有一周

按顺序做这三件，其他都往后放：

1. **交付 01-transformer-demo**：批准字幕 → 重渲 Blender 镜头 → 完整构建 → 媒体 QC → 人工看片。这是项目第一次真正交付 20 分钟课程。
2. **把质量门禁的语义改真**：D-071 落地；`QUALITY_PASS` 改名/拆义；`incomplete` 不再可发布。
3. **重切字幕**：01 的 357 cue 与 05 的 80 cue 按标点/词边界重切；06 的响度补到 -16 LUFS。

这三件不需要新架构，全部是"把已有的东西做对"。

---

## A. 必须解决

### A-1 交付 01-transformer-demo（20 分钟）

| 项 | 内容 |
| --- | --- |
| 为什么 | 项目从未交付过 20 分钟课程；01 的素材已完成约 90%，这是信誉与学习曲线的最大缺口 |
| 解决什么 | 验证长片 compose、burn-in、V-26..V-36、字幕批准、Blender 镜头、人工看片全链路 |
| 当前缺什么 | 成片已产出（1195.605 s，pass）；剩余人工看片、Media QC 的 ASR/package 与 review/release 签核 |
| 更简单的办法 | 先不修字幕质量，只修 2 条 policy 问题（cue 273 时长 0.94 s、cue 317 中文 3 行），批准后构建；字幕质量另开 A-3 |
| 工作量 | 1–2 天（Blender 渲染 10–30 min；compose 约 25 min；burn-in 约 1–2 min；人工看片 1–2 h） |
| 依赖 | Blender 可执行、VoxCPM2 不需要（旁白已生成）、Remotion 可用 |
| 风险 | compose 可能接近 1800 s 超时；字幕 burn-in 可能失败；20 分钟片的 V-31 可能有新问题 |
| 验收 | `final/course-video.mp4` 1195–1200 s；`course-video-captioned.mp4` 存在；`build-report.verdict=pass`；V-26..V-36 无 fail；人工完整看一遍并写下 10 条问题；`PROJECT_STATUS` 更新 |

**执行顺序**

1. 从草稿生成可接受 SRT，修 2 条 policy 问题；`subtitles-accept`。
2. `blender-render.ps1` 渲染 `stack_explode`（750 帧，25 s）。
3. `build-lesson.ps1 -Lesson 01-transformer-demo`。
4. `media-qc` → `audio-mix` → `quality-report` → `quality-gate`。
5. 人工看片，记录时间点与问题；不要用抽帧替代看片。

---

### A-2 让质量门禁说真话

| 项 | 内容 |
| --- | --- |
| 为什么 | 100/99 分、`QUALITY_PASS=True`、`releasable=true` 与 58/8 段冻结、未核实事实并存；这会误导下一轮决策 |
| 解决什么 | 把"通过"重新定义为"检查真的跑了且通过" |
| 具体改动 | 1）D-071：`beats.py` 时长/密度/长寿命/间隔改 warning，只保留结构错误为 error；2）`quality_gates.decide` 把 grammar 失败改 warning，`releasable` 只由 hard + 人工签核；3）`quality.py` 把 `QUALITY_PASS` 改名 `QUALITY_COMPLETE`，新增 `QUALITY_VERIFIED`；4）`hard_checks` 把 `incomplete` 视为阻断；5）`freeze` 分对所有 grammar 生效，`camera_moves=0` 不再给满分；6）新增 `release-approve` CLI 与 `release-approval.json` schema |
| 更简单的办法 | 先只做 1、3、4、5；2 和 6 可以第二步 |
| 工作量 | 1–2 天（含测试与文档） |
| 依赖 | 无 |
| 风险 | 改完后 05/06 的分数会下降，可能显示 fail；这是预期，不是回归 |
| 验收 | 构造"60 秒静止画面 + 满 beats"的样例，分数不得接近 100；对 nvda 跑 gate，`releasable=false`；`release-approve` 能写出可被 `quality.py` 读回的 JSON |

---

### A-3 字幕分段与中文断行

| 项 | 内容 |
| --- | --- |
| 为什么 | 字幕是"交付做硬"的直接部分；当前断词/断句会被观众看到 |
| 解决什么 | 01 cue 2/3 在句子中间断；05 250 s"表/示，。"；06 逐词字幕从词中间开始 |
| 具体改动 | 1）`subtitles.py` 用句末标点 → 逗号/顿号 → ASR 词边界三级切分；2）中文断行禁止标点开头、禁止拆 2 字词；3）英文 cue 不以介词/冠词结尾；4）V-31 覆盖 `render: remotion`；5）06 显式声明单语或补双语 |
| 更简单的办法 | 先写一个后处理函数，对现有 SRT 重切；不碰 TTS |
| 工作量 | 2–3 天（含 01/05/06 重跑与抽查） |
| 依赖 | 01 的旁白已存在；05/06 的旁白已存在 |
| 风险 | 重切会改变 cue 时间，需要重新 burn-in；05 的 V-31 可能发现新的行宽问题 |
| 验收 | 01/05/06 各抽 20 条 cue，无断词、无标点开头；V-31 对 06 执行；人工读一遍 |

---

### A-4 交付包与哈希

| 项 | 内容 |
| --- | --- |
| 为什么 | 交付规范要求哈希与完整包；当前 build-report 没有 sha，final 没有 subtitles/metadata/checklist |
| 解决什么 | 让"交付了"可复核；让 05/06 的响度/字幕问题在 Q5 可见 |
| 具体改动 | 1）`Artifact` 加 `sha256`；`BuildReport` 加 `run_id`；2）新增 `course-control package`：生成 `final/subtitles.*`、`metadata.json`、`delivery-checklist.md`、`manifest.json`（含哈希）；3）Q5 required 增加 `audio/mix.json`（有旁白时）与 `final/subtitles.*`（字幕启用时） |
| 工作量 | 2–3 天 |
| 依赖 | A-1 的 01 构建产物（可先用 05 试） |
| 风险 | 规范与现有产物不一致，第一次跑会列出很多缺项；这是好事 |
| 验收 | 05/01 各跑一次 `package`，缺项为 0；删掉一个必需文件，命令 exit 1 并列出 |

---

## B. 值得优化

### B-1 05/06 的构图与关键帧

| 项 | 内容 |
| --- | --- |
| 为什么 | 主体偏小、留白大、38 s 边线太淡；这是"把画面做好"的直接扣分 |
| 解决什么 | 让关键机制帧真的"看得见" |
| 具体改动 | 1）05 的向量/流程图放大到画幅 50–70%，减少下半部空白；2）06 的 38 s 边线加粗/提高对比，让"重要的连接变粗"发生；3）每帧设一个视觉焦点；4）用 CodeVideo skill 的"主体 ≥1/3 画幅"作为人工检查项，不新增自动门禁 |
| 工作量 | 3–5 天（含重渲与看片） |
| 依赖 | 无 |
| 风险 | 放大后可能压字幕/越界；用 `STRICT_LAYOUT=1` 与抽帧检查 |
| 验收 | 05/06 各重渲；关键帧抽查看主体占比与焦点；人工看片无"空"的感觉 |

### B-2 06 的响度与音频完整性

- 跑 `audio-mix`（mode=loudness_only）把 06 补到 -16 LUFS；重跑 media-qc。
- 工作量：1 小时。
- 验收：06 的 `media.level_policy` PASS。

### B-3 06 的 ContentQA / Teaching QA

- 06 没有 Q1/Q2；跑 ContentQA（默认 Claude Code 或显式 API）+ `teaching-qa` + `narrative-validate`（已有 narrative plan？06 没有）。
- 工作量：0.5–1 天。
- 验收：Q1/Q2 不再是 INCOMPLETE；至少有一条真实 finding。

### B-4 nvda 的 ASR 与画面减负

- 跑 `asr-align`，关闭 media QC 的 INCOMPLETE。
- 把幻灯片底部的中文段落移除，交给字幕；每页只留英文要点 + 一个视觉焦点。
- 工作量：1–2 天。
- 验收：ASR PASS；抽帧中文不再是小字段落。

### B-5 导演计划成为 build 的默认输入

- 这不是"再造一层"，而是**删掉一个分叉**：`lesson.yaml` 增加 `build.storyboard_source: storyboard|director`，默认 `storyboard`；当存在 director plan 且用户选择 `director` 时，build 直接读 `storyboard.director.yaml`。
- 先只对 05 试：把 3 个导演镜头映射到 3 个可独立渲染的 Manim 类，或明确回到 1 个镜头；不要同时维护 1/3/27 三套。
- 工作量：3–5 天（含 05 的 scene 拆分或声明）。
- 风险：会触碰真实课程；先在 05 的副本上做。
- 验收：05 的 build 与 director 使用同一份镜头列表；`producer-affected` 的重渲命令与实际渲染单元一致。

### B-6 任务记录与证据可追溯

- ContentQA task_id 加 run_id；`review.json` 写 provider/model。
- 新增 `scripts/verify-evidence.ps1`，解析文档中的 `build/...` 路径。
- 更新 `PROJECT_STATUS.md` 的 01 状态与测试计数。
- 工作量：1–2 天。
- 验收：连续两次 review 保留两套任务记录；`verify-evidence` 列出所有缺失路径。

### B-7 CodeVideo 的三种模板

- 只做三种：标题/大字、矩阵/网格、流程/箭头。把 06 的 6 个 code_video 镜头抽象成参数化模板，下一支片子直接改文案与数据。
- 不要做通用组件库；只做这三种最常用的。
- 工作量：1 周。
- 验收：用模板重做 06 的 1 个镜头，工时比手写少 50%，画面不劣于原版。

---

## C. 暂时保留

| 模块/能力 | 为什么保留 | 不要做什么 |
| --- | --- | --- |
| `CourseControl` 主链 + 适配器 | 稳定、可测、失败可见 | 不要为了"统一"重写 |
| `shared/ai_runtime` | 全项目质量最高的模块 | 不要引入 Agent 框架 |
| `check.ps1` + Schema 同步测试 | 回归可靠 | 不要减少检查项 |
| Remotion 合成层 | 成片稳定 | 不要换合成器 |
| CodeVideo capture/QC | 镜头级证据完整 | 不要为它加更多后处理开关 |
| KnowledgeStudio | 教材场景有价值，但当前无课程 | 不要集成到所有课；先等一个真实教材需求 |
| ModelingStudio | 内部能力，POC 成立 | 不要重跑/扩展，除非课程需要 3D 资产 |
| 品牌 2D 层 | 已达到 4/5，且拼接核验严格 | 不要再改视觉语言 |
| 导演/制片层 | 设计与报告有价值 | 不要让它们继续"只报告不驱动"，也不要再加新层 |

---

## D. 应该停止

| 事项 | 为什么停 | 替代 |
| --- | --- | --- |
| 新增视觉 grammar / quality profile | 现有 7 个已经够用；D-071 还没落地 | 先把 grammar 阈值改成诊断 |
| 新增渲染后端（HyperFrames/VideoZero/ManimGL/Godot） | 没有交付需求；每加一个都增加验收分叉 | 用现有四引擎 |
| 4K/60 整课 | 只有 60 帧基准；当前瓶颈是构图不是分辨率 | 1080p30 先做到位 |
| 品牌 3D 片头的美术探索 | 灰盒角色、黑 W、暖灰背景；项目自己的 Gate 未过；与 20 分钟课交付无关 | 暂停，或只做到"Gate 1 角色静帧"就停 |
| 再叠一层质量报告/评分器 | 已有三套结论，语义冲突 | 合并/改名，不新增 |
| 用 automation % / agent 数量 / 代码行数作为目标 | 代理指标，会诱导做无用的架构 | 用"交付了几门课、人工介入几次、观众能否看懂" |
| 继续扩 `VERIFY.md` 的字符串门禁 | 只查 `| fail |` 太弱 | 改成逐条证据 + 人工签核 |
| 给所有内容类型做通用模板 | 会把系统拉成无边界的低代码平台 | 先做技术/新闻两条线 |

---

## E. 未来再考虑

| 能力 | 触发条件 | 预估 |
| --- | --- | --- |
| Shorts 端到端 | 有一集长视频的素材可复用，且需要竖屏 | 1–2 周（含 9:16 时间线、独立脚本、样片） |
| 经济学/商业系列 | 技术线稳定交付 2 门课之后 | 先 1 集 8 分钟样片，2–3 周 |
| KnowledgeStudio 接入课程 | 有一本真实教材、需要按页引用 | 1–2 周 |
| ModelingStudio 真实资产 | 课程需要定制 3D 物体，且 Blender 手工建模成本高 | 2–4 周 |
| 多课队列/调度 | 同时在制 ≥3 门，且需要夜间排队 | 1–2 周（只做串行队列，不做分布式） |
| 只读生产面板 | 报告字段稳定 1 个月，且非开发者需要看 | 1–2 周 |
| 4K/60 | 平台明确要求，且 1080p 构图已达标 | 按需 |
| Agent 生成镜头 | 单镜头对照实验证明不劣于人工 | 先做实验，不排期 |

---

## F. 推荐执行顺序（约 6 周）

| 周 | 主任务 | 产出 | 验收 |
| --- | --- | --- | --- |
| 1 | A-1 交付 01 | 20 分钟成片 + 报告 + 看片记录 | V-26..V-36 无 fail；人工 10 条问题 |
| 1–2 | A-2 门禁语义 | D-071 落地；QUALITY_* 拆义；release-approve | 静止画面样例分数不接近 100；nvda gate 不 releasable |
| 2–3 | A-3 字幕 | 01/05/06 重切；V-31 覆盖 remotion | 20 条抽查无断词；06 响度 -16 |
| 3–4 | A-4 交付包 | `package` 命令 + 哈希 | 05/01 缺项 0 |
| 4–5 | B-1 构图 | 05/06 重渲 | 关键帧主体占比 ≥50%；38 s 边线可见 |
| 5 | B-2/B-3/B-4 | 06 响度/QA；nvda ASR/画面 | Q1/Q2 不再 INCOMPLETE；ASR PASS |
| 6 | B-5/B-6 | 05 的导演/build 对齐；任务记录/证据 | 05 只有一套镜头列表；两次 review 两套记录 |

> 如果只有 2 周：只做 A-1 + A-2 + A-3 + B-2。不要碰 B-5，它会触碰真实课程。

---

## G. 下一阶段的"完成"定义

不是"新增了多少能力"，而是：

1. `01-transformer-demo` 有 20 分钟成片，`RELEASE_APPROVED=true`，有人完整看过并留下记录。
2. 任意一门课的质量报告里，`PASS` 只表示"检查跑了且通过"；`INCOMPLETE` 不再能发布。
3. 01/05/06 的字幕抽 20 条无断词；06 的响度在 -16 LUFS ±0.5。
4. `course-control package` 能生成完整交付包，缺项即失败；build-report 有 sha256 与 run_id。
5. `PROJECT_STATUS.md` 与真实产物一致；不再出现"文档说 blocked、产物已完成"。
6. 至少一个机制镜头被重做成"主体占满、变化可见"的版本，并有人看过说"比原来清楚"。

这六条做到，项目就从"样片工厂"变成"能交付长课的工作室"。然后再谈 Shorts、经济学、3D 片头。
