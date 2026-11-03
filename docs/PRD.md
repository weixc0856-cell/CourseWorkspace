# CourseWorkspace 产品需求基线（PRD）

- **版本**：v1.0
- **日期**：2026-11-03
- **地位**：本文件是唯一有效的产品需求基线。任何开发任务必须能对应到本文的 `FR-*` / `NFR-*` 条目。
- **取代**：`docs/archive/CourseWorkspace-R0-R5改造PRD.md`（改造规格，已执行完毕）、`docs/archive/ContentQA_实施评估.md`（设计稿，仅保留审查内核）、`docs/archive/AI-Blender落地路线图.md`（历史状态快照）。
- **配套**：结构与契约见 [ARCHITECTURE.md](ARCHITECTURE.md)；验收命令见 [ACCEPTANCE.md](ACCEPTANCE.md)；决策理由见 [DECISIONS.md](DECISIONS.md)；真实工作流见 [WORKFLOW.md](WORKFLOW.md)；当前状态见 [PROJECT_STATUS.md](PROJECT_STATUS.md)。

---

## 1. 产品目标

把**人工撰写的课程内容**稳定、可复现地转换成**带动画与三维场景的成片视频**，并在每一步给出可核验的证据。

产品解决的是“内容已经写好，但排版、动画、三维、合成、验收仍是手工拼接”的问题；不解决“从零生成课程知识”的问题。

### 1.1 目标

1. 单一课程契约：一门课只用 `lesson.yaml` + `storyboard.yaml` + 双文件内容描述。
2. 确定性执行：同一输入重复构建得到同一文件集合与同一验收结论。
3. 证据可追溯：每个阶段的状态、日志、产物、检查结果都落盘。
4. 三维与 AI 能力可组合：三维场景由结构化任务驱动；AI 只生成候选，不直接判定完成。
5. 资源可控：本机只有一台机器、一个 8080 服务，模型调用必须串行且可恢复。

### 1.2 非目标（本版本明确不做）

- 自动语音识别（ASR）、自动整课 TTS、自动发布。
- 云端渲染、ComfyUI 图像生成流水线。
- Motion Canvas headless 自动导出（见 FR-04，人工节点是正式设计）。
- 让 LLM 直接判定课程事实正确性或替代人工审稿。
- 多用户并发、多机器调度、容器化部署。

---

## 2. 用户与场景

| 角色 | 做什么 | 系统提供 |
| --- | --- | --- |
| 课程作者 | 撰写 `slides.md` / `lecture_notes.md`，登记 `storyboard.yaml` | 契约校验、截图、时间线推导 |
| 动画作者 | 在 Motion Canvas 编辑器制作并导出动画 | 导出文件校验与自动接轨 |
| 三维作者 | 编写 IR v2 场景任务或使用 ModelingStudio | 场景执行、验收、manifest |
| 构建者 | 一键构建并验收 | `build-lesson.ps1`、`build-report.json` |
| 审稿人 | 核对内容与来源 | 在线审查报告（候选意见，人工裁决） |

主流程：

```text
作者写内容 → validate → 截图 / 动画导出 / 三维渲染 → collect → compose → verify → 交付报告
```

---

## 3. 产品范围与模块定位

| 模块 | 定位 | 是否在主流程 | 说明 |
| --- | --- | --- | --- |
| `lessons/` | 核心 | 是 | 唯一内容入口 |
| `CourseControl/` | 核心 | 是 | 唯一课程调度与验收入口 |
| `CourseSlides/` | 核心 | 是 | Reveal 预览与截图源 |
| `RemotionStudio/` | 核心 | 是 | 截图、staging、最终合成 |
| `MotionStudio/` | 核心 | 是（人工节点） | 结构动画；当前无 CLI 导出 |
| `BlenderStudio/` | 核心（三维能力） | 是（可选引擎） | IR v2 场景系统 + 课程渲染任务 |
| `ModelingStudio/` | 内部能力 | 否 | 图片→Blender 模型；产出可转为三维素材 |
| `ManimSandbox/` | 可选能力 | 否 | 数学动画备选；当前无课程使用，保活但不接入主流程 |
| `ContentQA/` | 内部能力 | 否 | 在线模型内容审查；只读课程，不影响构建判定 |
| `shared/` | 共享层 | 是 | Schema、设计令牌、AI 运行时 |
| `config/`、`scripts/` | 支撑 | 是 | 本机配置与工作区入口 |
| `docs/` | 指导 | — | 权威文档与归档 |

### 3.1 当前版本边界（v1）

- 课程构建闭环、IR v2、ModelingStudio、本地模型串行调度、在线内容审查内核为**本期交付**。
- Motion Canvas 导出仍为人工步骤，属于正式工作流节点，不计为缺陷。
- Manim 仅保留现有 demo 与适配器，不新增课程接入。
- Blender 任务存在两代 Schema，v1/v2 分工见 FR-04 / FR-05。

---

## 4. 功能需求

### FR-01 课程内容契约

**目标**：一门课只由 `lessons/<slug>/` 下的文件描述。

- 必需：`lesson.yaml`、`slides.md`、`lecture_notes.md`、`storyboard.yaml`。
- 可选：`outline.md`、`assets/`、`subtitles.srt`。
- `lesson_id` 必须是 slug 且等于目录名。
- `slides.md` 与 `lecture_notes.md` 页数必须一致；每页口播块必须含“时长预算 / 动画切入 / 技术核查 / 逐字口播”。
- 内容正文归用户所有，任何自动化不得改写语义。

**验收**：`course-control validate --lesson <slug>` 对两门真实课程与全部夹具返回 0。

### FR-02 契约校验（V-01~V-09）

**目标**：在渲染前失败，而不是在合成后返工。

覆盖：slug 与目录一致、必需文件、页数/块数、四要素、素材路径、禁用标记（`Notes:`、`$...$`、`<video>`、`[ANIMATION`）、镜头 id/页码/引擎、场景与任务文件存在、Motion 场景已注册。

**验收**：`docs/ACCEPTANCE.md` 的 V-01~V-09 表；失败路径至少有一条自动化测试。

### FR-03 幻灯片预览与截图

**目标**：把 `slides.md` 渲染为逐页 PNG 与 manifest。

- 服务：`live-server` 监听 `8081`，复用已在运行且可访问的实例。
- 采集：Playwright（Chrome/Edge），视口 1920×1080，隐藏控件，等待字体与图片。
- 产物：`build/<slug>/slides/slide-###.png` + `capture-manifest.json`。
- 页数必须与讲师手册块数一致，否则 `collect` 失败。

**验收**：真实课程 `01-shell-for-ai-era` 采集 20/20；夹具课程走 recording 模式时该阶段为 `not_applicable`。

### FR-04 动画渲染

**目标**：每个 `storyboard` 镜头产出可校验的视频。

- **Motion Canvas（默认）**：无 CLI 导出。作者在编辑器导出到 `build/<slug>/animation/<scene-stem>.mp4`。
  - 文件全部存在且 ffprobe 通过 → `render:motion_canvas = pass`。
  - 缺失且 `build.allow_manual_animation_export=true` → `skipped`，`verdict=incomplete`，原因 `manual_export_required`。
  - 缺失且开关为 false → `fail`。
  - 禁止用截图拼帧或伪造文件冒充导出。
- **Manim**：`uv run manim render --media_dir build/<slug>/tmp/manim-media`，复制成片到 `animation/`。
- **Blender（课程任务，Schema v1）**：由 `scripts/blender-render.ps1` 调用 Blender，产物路径必须位于 `build/<lesson>/blender/`。

**验收**：夹具 `lesson-manual` 校验人工导出；真实课程如实返回 `incomplete`；Manim 适配器有可复现命令。

### FR-05 三维场景任务 IR v2

**目标**：用结构化 JSON 描述三维场景，程序执行，程序验收。

- 顶层：`schema_version: 2`、`task_id`、`lesson`、`scene`、`collections`、`world`、`materials`、`objects`、`cameras`、`lights`、`animations`、`base_blend`、`render`。
- 双端校验：外部 Pydantic（`course_control.blender_scene`）与 Blender 内置 `scene_system/task_schema.py` 必须对同一任务给出一致结论。
- 执行：`course-control scene-run` → 校验 → Blender → 输出检查 → 场景验收 → manifest。
- 验收项：退出码、PNG 分辨率/大小/黑帧、MP4 编码/分辨率/时长、场景问题、活动相机、对象数、GN 修改器数、F-Curve 数。
- 路径约束：输出与 `.blend` 必须位于 `build/<lesson>/blender/`，禁止绝对路径、反斜杠、`..`。

**验收**：`check-scene-system.ps1`（5 合法 + 6 非法）、`test_blender_scene.py` 全部通过；4 个 demo 任务真实渲染通过（`-Render`，资源允许时执行）。

### FR-06 本地自动建模（ModelingStudio）

**目标**：单张图片 → 可编辑 Blender 模型，全流程本机完成。

阶段：视觉分析（Qwen3-VL）→ 建模规划（Qwen3）→ 脚本生成（Qwen3-Coder）→ Blender 执行 → 程序验收 →（可选）视觉修正建议。

- 生成脚本必须通过 AST 静态检查后才可执行。
- 计划是变换的最终依据；包装器按 `model_plan.json` 重设尺寸、位置、旋转、父子关系与取景。
- Coder 连续失败时回退到确定性图元构建器，并在 `job.json` 标记 `fallback`。
- 作业目录：`ModelingStudio/workspace/jobs/<job>/`，不入库。

**验收**：`modeling-studio` 单测通过；至少一个真实作业记录六阶段状态；失败阶段必须落盘（FR-10）。

### FR-07 时间线收集

**目标**：把页面预算与镜头转换成唯一时间线 `build/<slug>/shots.json`。

- 页面时长来自讲师手册 `时长预算`；overlay 起点 = 页起点 + `cue_seconds`。
- overlay 必须落在页内且互不重叠。
- 旁白、字幕以文件形式进入时间线。
- 路径必须相对 `build/<slug>/`，禁止绝对路径与 `..`。

**验收**：夹具构建后 `shots.json` 通过 `verify`；越界路径有失败测试。

### FR-08 合成与成片验收（V-10~V-21）

**目标**：Remotion 合成最终视频，并以程序检查判定。

覆盖：源文件存在、分辨率/帧率、时间线连续性、成片可读与时长、音画差、字幕、报告一致性、产物边界、适用性、recording 时长、路径合法性。

- 合成失败保留 `RemotionStudio/public/staging/<slug>/`；成功清理。
- 报告 `verdict` 只能是 `pass` / `fail` / `incomplete`。

**验收**：夹具 `lesson-smoke` 全链路 `pass`；V-10~V-21 有实现与至少一条失败注入证据。

### FR-09 本地模型统一调度与严格串行

**目标**：本机所有本地模型调用共享一个入口、一个锁、一个服务。

- 唯一入口：`shared/ai_runtime`。
- **跨进程互斥**：锁文件 + 原子创建 + PID/时间戳 + 陈旧锁回收；进程内锁不足以满足要求。
- 任务在执行全程持锁；异常、超时、Ctrl-C 必须释放。
- 服务生命周期：健康检查 → 别名匹配 → 复用或启动 → 结束时只停止自己启动的实例。
- 8080 被其他模型占用时：等待（有超时）或明确 `blocked`，不得杀死他人进程。
- 模型切换顺序：停止旧实例 → 等待端口释放 → 启动新实例 → 健康且别名匹配。
- 不改变用户既有启动方式与硬件配置（`start_server.bat` 仍可用）。

**验收**：多进程竞争测试（两个进程同时申请，必须串行）；超时释放测试；他人占用时 `blocked` 测试。

### FR-10 模型任务状态与恢复

**目标**：任何模型任务都有可查询、可恢复的状态。

状态集（模型任务）：`pending` / `running` / `completed` / `failed` / `blocked` / `needs_review` / `skipped`。

任务记录字段：`task_id`、`task_type`、`assigned_model`、`input_artifacts`、`output_artifacts`、`context_budget`、`timeout_s`、`retry_policy`、`status`、`error`、`started_at`、`finished_at`。

- 失败、阻塞、中断都必须落盘为终态；不得只写成功。
- 已完成阶段可被 `--resume` 跳过；产物存在且校验通过才算完成。

**验收**：任务状态 schema 与单测；ModelingStudio 失败注入后 `job.json` 有 `failed` 记录。

### FR-11 上下文预算

**目标**：在请求发出前控制上下文，而不是事后截断。

- 硬上限 64K；默认 8K–16K；复杂任务可到 16K–32K。
- 预算必须计入：系统提示词、输入资料、历史轮次、图片/多模态、输出预留。
- 超限必须拆分任务并保留来源关联；禁止静默截断重要资料。
- 图片按分辨率与 `--image-min-tokens` 估算，不只按文本长度。

**验收**：预算单测（文本、CJK、图片、超限拆分）；ModelingStudio 每次请求记录估算值与上限。

### FR-12 在线内容审查（ContentQA）

**目标**：让在线模型成为正式工作流的一部分，负责事实与一致性核查的**候选**意见。

- 输入：`lessons/<slug>/` 的 `slides.md`、`lecture_notes.md`、可选 `sources.yaml`。
- 按页/按段拆分，逐任务调用，任务级上下文预算。
- 输出：`build/<slug>/review/review.json` + `review.md`（人工可读）。
- 结论状态：`completed` / `blocked` / `failed`；单条意见：`supported` / `unsupported` / `disputed` / `needs_human_review` / `not_checked`。
- **凭据**：只从环境变量或本机忽略配置读取；缺失时 `blocked`，退出码 3，绝不静默改用本地模型。
- **只读**：不得修改 `lessons/`、`shots.json`、`build-report.json`，不得影响构建 `verdict`。
- 在线模型不可用时明确标记，不降级冒充同等质量。

**验收**：mock 服务下的成功、不可用、非法 JSON、超预算测试；无凭据时 `blocked`。

### FR-13 报告与可追溯

- 课程构建：`build/<slug>/final/build-report.json`（阶段、检查、产物、verdict、failures）。
- 三维任务：`build/<lesson>/blender/manifests/<task_id>.json`。
- 模型任务：任务记录文件（FR-10）。
- 审查：`build/<slug>/review/review.json`。
- 所有报告都记录工具链版本、时间、输入哈希或任务哈希。

### FR-14 一键回归与环境自检

`scripts/check.ps1` 必须在 PowerShell 5.1 下可重复执行并打印 `check ok`，覆盖：

1. 工具链探测；
2. CourseControl / ModelingStudio / shared / ContentQA 单测；
3. 5 个课程/夹具契约校验；
4. IR v2 契约校验（不渲染）；
5. 无网络依赖。

**验收**：在干净 shell 中 exit 0 且输出 `check ok`。

---

## 5. 非功能需求

| 编号 | 要求 |
| --- | --- |
| NFR-01 | 可复现：同一输入重复构建，文件集合与 verdict 一致 |
| NFR-02 | 失败可见：任何跳过、缺失、阻塞都必须出现在报告与 failures 中 |
| NFR-03 | 隔离：不全局安装、不改 PATH、不写 `<AI_ROOT>` |
| NFR-04 | 路径安全：所有声明路径相对、`/` 分隔、无 `..`；输出限制在 `build/<slug>/` |
| NFR-05 | 资源串行：同一时刻只有一个本地模型任务；同一时刻只有一个 llama-server |
| NFR-06 | 可中断：Ctrl-C、超时、进程被杀后，锁与服务不残留（陈旧锁可回收） |
| NFR-07 | 最小依赖：优先标准库与既有依赖，不引入 Agent 框架 |
| NFR-08 | 文档一致：测试数量、命令、状态以实际运行为准 |

---

## 6. 模型职责

| 工作 | 在线模型 | 本地模型 | 程序 | 人工 |
| --- | --- | --- | --- | --- |
| 课程资料理解、知识体系、复杂分析 | 是 | 否 | 拆分与预算 | 采纳 |
| 事实/公式/参数/引用核查 | 是（候选） | 否 | 结构与证据定位 | 最终裁决 |
| 多来源交叉验证 | 是 | 否 | 来源清单与哈希 | 裁决 |
| 文档预处理、结构化提取、格式转换 | 否 | 是 | 校验 | 抽查 |
| 建模规划、脚本生成 | 否 | 是 | AST 检查、执行、验收 | 审阅结果 |
| 常规规则检查 | 否 | 可用 | 是 | — |
| 最终内容正确性 | 否 | 否 | 否 | 是 |

在线模型与本地模型不得互相冒充。在线不可用时记录 `blocked`；本地模型失败时记录 `failed`。

---

## 7. 阶段工作流（含人工节点）

> 详细输入、输出、失败恢复与真实证据见 [WORKFLOW.md](WORKFLOW.md)。

```text
[人工] 撰写 slides.md / lecture_notes.md / storyboard.yaml
   ↓
validate（程序，任意失败即中止）
   ↓
[自动] capture_slides ─────────────────────┐
[人工] Motion Canvas 导出 → render:motion_canvas
[自动] render:manim（可选）                 ├→ collect → compose → verify
[自动] render:blender（可选，v1）           │
[独立] scene-run（IR v2）───────────────────┘（产物可被课程引用）
[独立] modeling-studio（图片→模型）
[独立] content-qa review（在线审查，不影响 verdict）
```

人工节点必须出现在交付报告中：未导出 = `skipped` + `incomplete`；未配置凭据 = `blocked`。

---

## 8. 异常与恢复

| 场景 | 行为 |
| --- | --- |
| 上游失败 | 下游 `not_run`，verdict `fail`，记录 `upstream_failed` |
| 人工步骤缺失 | `skipped` + `incomplete`，记录缺失文件 |
| 合成失败 | 保留 staging 与日志，verdict `fail` |
| 本地模型超时/中断 | 释放锁；任务记录 `failed`；服务只停自己启动的实例 |
| 8080 被他人占用 | 等待到超时；仍不可用 → `blocked`，不杀进程 |
| 陈旧锁 | 超过阈值且 PID 不存在时回收 |
| 在线模型无凭据 | `blocked`，退出码 3 |
| 在线模型返回非法 JSON | 重试后 `failed`，保存原始响应 |
| 上下文超限 | 报错并要求拆分，禁止静默截断 |

---

## 9. 验收标准与完成条件

本期 v1 完成需同时满足：

1. `scripts/check.ps1` 在 PowerShell 5.1 下 exit 0 并打印 `check ok`。
2. 全部单测真实通过，数量与 `docs/ACCEPTANCE.md` 一致。
3. 5 个课程/夹具 validate 通过；11 个 IR v2 夹具结论正确。
4. 夹具 `lesson-smoke` 全链路 `verdict=pass`（真实 Blender + Remotion）。
5. 真实课程 `01-shell-for-ai-era` 至少完成截图与全部可自动阶段，并如实输出 `incomplete` 及原因（Motion 未导出）。
6. 本地模型串行有真实多进程测试证据。
7. 在线审查在 mock 服务下通过；无凭据时 `blocked`。
8. 维度预算测试通过，所有模型调用记录预算。
9. 失败/取消/阻塞状态均可从任务记录读回。
10. 文档与代码一致，无 P0 遗留。

---

## 10. OPEN 项（不影响本期验收，但必须记录）

| 编号 | 事项 | 当前处理 |
| --- | --- | --- |
| OPEN-01 | Motion Canvas 是否自建 headless 导出 | 本期不做；人工节点是正式设计 |
| OPEN-02 | 真实课程内容补全（4 页占位、3 页中文、8 段动画导出） | 用户负责；系统如实报告 `incomplete` |
| OPEN-03 | 在线模型供应商与凭据 | 由用户配置；未配置时 `blocked` |
| OPEN-04 | Manim 是否接入课程 | 保持可选，不强行接入 |
| OPEN-05 | 完整 ContentQA（ASR/TTS/公式验证/证据语料） | 本期只交付审查内核 |
| OPEN-06 | 多课程并行构建 | 不设计；构建串行即可 |
