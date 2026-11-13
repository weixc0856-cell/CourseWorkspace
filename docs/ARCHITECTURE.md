# CourseWorkspace 架构与数据契约

- **版本**：v1.0（2026-11-03）
- **上游**：[PRD.md](PRD.md)
- 本文件描述“系统如何组成、模块如何调用、数据如何流动”。需求本身以 PRD 为准。

---

## 1. 总体结构

```text
CourseWorkspace/
├── CourseControl/      控制层：校验、调度、收集、报告（Python 3.12 + uv）
├── CourseSlides/       展示层：Reveal.js 外壳（Node）
├── MotionStudio/       动画层：Motion Canvas（Node，无头自动导出）
├── ManimSandbox/       动画层：Manim（Python，可选）
├── BlenderStudio/      三维层：Blender 5.2 + 场景系统 + 渲染脚本
├── RemotionStudio/     合成层：截图采集、staging、Remotion 合成（Node）
├── ModelingStudio/     三维内部能力：图片 → Blender（Python）
├── ContentQA/          审查内部能力：Claude Code 默认 / API 可选（Python）
├── KnowledgeStudio/    教材知识库：PDF 拆页、目录校准、按页检索与引用（Python）
├── shared/
│   ├── ai_runtime/     AI 运行时：跨进程锁、服务生命周期、任务状态、上下文预算
│   ├── scene_expr/     受限表达式：AST 白名单 + 解释器（控制层与 Blender 共用）
│   ├── schemas/        JSON Schema（由 Pydantic 导出）
│   └── design-tokens/  设计令牌
├── config/             本机配置（*.yaml 本地文件不入库）
├── scripts/            PowerShell 工作区入口
└── docs/               权威文档与生产规范（项目材料与归档不在这里）

<内容根>/                 课程内容；默认等于工作区，取值见 config/local-paths.yaml 的 content_root
├── engines/            课程场景：manim/、blender/scenes/、code_video/shots/
├── lessons/            内容层：唯一的课程输入
├── build/              全部生成物（不入库）
├── deliver/            最终交付包（不入库）
├── runtime/            锁与模型任务记录（不入库）
├── knowledge/          教材区（不入库）
├── audio/              共享声音资产：voice-bibles/、lexicons/（人工维护）
├── references/         参考库：对标影片记录、Golden Sample 哈希（不入库）
├── projects/           各系列项目材料：生产方向、分集方案、研究（不入库）
└── archive/            历史记录：一次性报告、证据、旧方案（不入库）
```

### 1.1 写入归属

| 位置 | 写入方 | 内容 |
| --- | --- | --- |
| `<内容根>/lessons/` | 人工 | 课程正文与契约 |
| `<内容根>/build/<slug>/` | CourseControl 及其适配器 | 截图、动画、三维、时间线、日志、报告 |
| `<内容根>/audio/` | 人工 | Voice Bible 与 Lexicon；按哈希标识，课程用 id 引用 |
| `RemotionStudio/public/staging/<slug>/` | Remotion staging | 合成期临时素材（成功后清理） |
| `<内容根>/runtime/locks/` | `shared/ai_runtime` | 跨进程锁 |
| `<内容根>/runtime/tasks/` | `shared/ai_runtime` | 模型任务记录 |
| `ModelingStudio/workspace/jobs/` | ModelingStudio | 建模作业 |
| `BlenderStudio/scenes/`、`assets/` | 人工 | `.blend` 与 GN 资产 |
| `<AI_ROOT>` | **任何人都不写** | 模型与运行时 |

---

## 2. 模块职责

| 模块 | 职责 | 不做什么 |
| --- | --- | --- |
| `CourseControl` | 命令层与组合根：参数解析、阶段编排（`pipeline.py`） | 不改课程正文；不判定内容正确性 |
| `CourseControl/content` | 课程契约、校验、路径、计时、shots 契约、时间线 | 不渲染、不判断质量 |
| `CourseControl/direction` | 导演计划、节拍、叙事、镜头表编译与设计指纹 | 不写场景代码、不调用引擎 |
| `CourseControl/rendering` | 适配器、引擎路由、Blender/Manim/CodeVideo、版式、公式、主题、品牌 | 不改课程内容、不判定合格 |
| `CourseControl/voice` | 旁白合成、Voice Bible / Lexicon、字幕、混音 | 不写画面、不签核 |
| `CourseControl/quality` | 验收、媒体 QC、质量报告、对标、仓库分离检查 | 不改产物、不自动放行 |
| `CourseControl/delivery` | 订单、授权、交付清单、增量重建 | 不渲染、不读密钥、不自动发布 |
| `CourseControl/platform` | 路径解析、原子写、锁、检查点、媒体探测、配置 | 不含业务规则 |
| `CourseControl/authoring` | 摄取、摘要、brief / outline / script、镜头表编译 | 不改课程正文 |
| `CourseControl/animatic` | 480p 预览：单元解析、分段编码、拼接混音、预览报告 | 不写 `deliver/`；不做正式合成 |
| `CourseControl/locks` | Picture / Dialogue 锁定快照、哈希比对与失效映射 | 不阻止修改、不自动重建、不产出交付物 |
| `CourseSlides` | 加载指定课程为 Reveal 页面 | 不写 `build/` |
| `MotionStudio` | 动画场景源码 | 不做最终合成；无头导出由 `render-headless.mjs` 完成（D-054） |
| `ManimSandbox` | 数学动画备选 | 不进入主流程 |
| `BlenderStudio` | v1 课程渲染任务、v2 场景系统、GN 资产、场景验收 | 不读取 `lesson.yaml` |
| `RemotionStudio` | 截图、staging、合成、字幕/旁白渲染 | 不做时间线推导 |
| `ModelingStudio` | 图片→分析→规划→脚本→Blender→验收 | 不写 `lessons/` 与课程 `build/` |
| `ContentQA` | 审查候选意见与报告（默认 Claude Code） | 不改课程、不影响 verdict |
| `KnowledgeStudio` | 教材拆页、单元、索引、按页检索与 claim 引用 | 不生成课程内容、不判断结论真伪、不改 `lessons/` |
| `CourseDemo` | 驱动 VS Code 终端会话并回收退出码/输出 | 不做执行证据的唯一来源 |
| `shared/ai_runtime` | 锁、服务生命周期、任务状态、预算 | 不含业务逻辑 |

`CourseControl/direction` 与 `CourseControl/delivery` 是 CourseControl 内部的设计层与制片层：前者把批准的 brief/outline/script 收敛成章节、镜头、引擎与旁白计划；后者管订单、授权、用量、交付清单和增量指纹。两者都不新增独立进程，也不写课程正文。上下文的划分、聚合与依赖方向见 [架构-DDD上下文与边界.md](架构-DDD上下文与边界.md)。

---

## 3. 调用关系

> 面向操作的完整流程（输入、输出、人工节点、失败恢复）见 [WORKFLOW.md](WORKFLOW.md)。

### 3.1 课程构建

```text
course-control build
  ├─ LessonPaths.load(lesson.yaml, storyboard.yaml)
  ├─ validate()                        # V-01..V-09
  ├─ adapters.slides.capture_slides()  # live-server 8081 + playwright
  ├─ adapters.motion_canvas.run()      # 无头渲染 + ffprobe 校验
  ├─ adapters.manim.run()              # uv run manim
  ├─ adapters.blender.run()            # scripts/blender-render.ps1（v1）
  ├─ collect()                         # → shots.json
  ├─ adapters.remotion.compose()       # stage-assets.mjs + npx remotion
  └─ verify()                          # V-10..V-21 → build-report.json
```

阶段依赖见 `platform/checkpoint.py` 的 `STAGE_DEPS`：四个渲染阶段都依赖 `capture_slides`，`collect` 汇合后再流向下游。`--resume-from` 只强制受影响子图，不再按线性顺序连带兄弟渲染阶段。

### 3.2 三维场景

```text
course-control scene-run
  ├─ blender_scene.validate_scene_task()      # Pydantic
  ├─ scripts/blender-render.ps1               # 超时/日志/路径约束
  │    └─ render_shot.py → scene_system.executor.execute()
  │         └─ task_schema.validate_task()    # Blender 内置 Python 再校验
  ├─ 输出检查（PNG/MP4）
  ├─ verify_scene.py --strict                 # 场景报告
  └─ manifest（哈希、版本、种子、耗时、检查）
```

### 3.3 本地建模

```text
modeling-studio run
  ├─ create_job()
  ├─ analyze  → ai_runtime.ModelService("vision")  → LLM
  ├─ plan     → ai_runtime.ModelService("planner") → LLM
  ├─ generate → ai_runtime.ModelService("coder")   → LLM → AST guard
  ├─ build    → Blender execute_build.py
  ├─ validate → validator.py
  └─ revise   → ai_runtime.ModelService("vision")  → LLM
```

每个阶段：申请跨进程锁 → 确保模型在 8080 → 发送请求（预算检查）→ 写任务记录 → 释放锁/停止自有服务。

### 3.4 内容审查

```text
content-qa review
  ├─ 读取 lessons/<slug>/slides.md、lecture_notes.md、sources.yaml（可选）
  ├─ 按页拆分 + 预算
  ├─ Claude Code 默认；显式 API 时走 OpenAI 兼容接口
  ├─ 结构校验（Pydantic）
  └─ build/<slug>/review/review.json + review.md
```

ContentQA 不读取也不写 `shots.json` / `build-report.json`。

### 3.5 动画预览

```text
animatic
  ├─ 读时间线：build/<slug>/timeline/page-plan.json → shots.json(base) → scenes/manifest.json
  ├─ 每单元选画面：scenes/pages/page-NNN.mp4 → slides/slide-NNN.png → 占位黑帧
  ├─ 480p 分段编码（片段按内容哈希缓存）→ concat -c copy → 旁白 apad 混音
  └─ build/<slug>/animatic/{animatic.mp4, animatic.json, timeline.json, animatic-report.json, contact-sheet.png}
```

预览是决策工具：不写 `deliver/`，`overlay` 镜头不合成（只在报告里计数），分辨率与时长都不作为通过条件。

### 3.6 声音资产

```text
narration-build
  ├─ 解析：<内容根>/audio/voice-bibles/<id>.yaml、lexicons/<id>.yaml（lesson.yaml 声明）
  ├─ 校验：参考音频存在 + 声明哈希一致 + 模式与 prompt 匹配
  ├─ 改写：Lexicon 单次扫描替换送 TTS 的文本；讲稿与字幕保持原文
  ├─ 合成：缓存键 = 文本 + 声线哈希 + 本段命中词条 + 模型与参数
  └─ build/<slug>/narration/narration.meta.json（schema v3，含 assets 与逐段 lexicon_applied）
```

不声明资产的课完全走原路径，缓存键不变。

### 3.7 镜头表

```text
storyboard.yaml (schema_version: 2)
  ├─ continuity 对象表 → continuity_refs 校验（V-45）
  ├─ asset_refs  → lesson 目录 / assets/ 解析与哈希（V-46）
  ├─ evidence_refs → id 格式（V-47）
  └─ shot-sheet 命令 → build/<slug>/shot-sheet/{plan.json, review.md}
                       逐镜头设计指纹（设计字段 + 资产哈希）
```

v1 镜头表原样通过；v2 字段只在 `schema_version: 2` 下可用。导演计划仍是视图，编译器不重写它。

### 3.8 锁定与失效

```text
lock
  ├─ picture.lock.json：画面单元哈希 + 镜头表版本 + 设计指纹 + 场景/资产哈希 + 审核记录
  └─ dialogue.lock.json：脚本/旁白/声音资产哈希 + 逐段测量 + 字幕 cue 对应

lock-status
  └─ 当前哈希 vs 锁定哈希 → 每处差异映射到下游（locks/dependencies.py: RULES）

subtitles-build
  └─ 旁白 meta 的脚本哈希与当前脚本不一致 → blocked（3）
```

锁是快照不是禁令：它报告失效范围，重建仍由 `producer-rebuild` 等显式命令执行。

---

## 4. 数据契约

### 4.1 课程契约（`schema_version: 1`）

| 文件 | 契约 | Schema |
| --- | --- | --- |
| `lessons/<slug>/lesson.yaml` | 课程配置 | `shared/schemas/lesson.schema.json` |
| `lessons/<slug>/storyboard.yaml` | 镜头表；`schema_version: 2` 起即镜头表（Shot Sheet） | `shared/schemas/storyboard.schema.json` |
| `build/<slug>/shots.json` | 时间线（生成物） | `shared/schemas/shots.schema.json` |
| `build/<slug>/final/build-report.json` | 构建报告（生成物） | `shared/schemas/build-report.schema.json` |
| Blender 任务 v2 | 场景任务 | `shared/schemas/blender-scene-task.schema.json` |
| 代码/终端会话 | 执行、录制、证据 | `shared/schemas/session.schema.json`、`evidence.schema.json` |
| 模型任务记录 | 任务状态与预算 | `shared/schemas/model-task.schema.json` |
| 内容审查报告 | ContentQA 输出 | `ContentQA/schemas/content-review.schema.json` |
| 规范化运行时 V1（V1-B/C/F 已实现；V1-D 证据适配器、V1-E 兼容层已实现；Remotion/Session 原生切换未完成） | `LessonSpec / ShotSpec / NarrationSpec / TimelineSpec / EvidenceManifestV1 / RenderManifest` | `shared/schemas/*-v1.schema.json` |

Schema 由 Pydantic 模型导出：旧契约用 `course-control schemas --output shared/schemas`，V1 用 `course-control schemas-v1 --output shared/schemas`。提交前必须与模型一致（有测试锁定）。V1 是 `lesson.yaml` / `storyboard.yaml` 之上的规范化运行时层，不替换作者文件。

`shots.json` 的 `annotations[]` 是二维标注的正式通道：`storyboard.yaml` 的可选 `annotations` 由 `collect` 按页面预算与 `cue_seconds` 解析成绝对时间；Remotion 只渲染该字段，不读取课程内容。标注分 `text` 与 `legend` 两类，`legend` 的色标 `stops` 由 `collect` 从 `shared/colormaps.json` 解析后写入，Blender 科学着色读同一份定义。

### 4.2 模型任务记录（`schema_version: 1`）

路径：`runtime/tasks/<task_id>.json`；ModelingStudio 另在 `workspace/jobs/<job>/tasks/<stage>.json` 留副本。

```json
{
  "schema_version": 1,
  "task_id": "modeling-sample-001-plan",
  "task_type": "modeling.plan",
  "assigned_model": "Qwen3-30B-A3B-Instruct-2507",
  "input_artifacts": ["visual_analysis.json"],
  "output_artifacts": ["model_plan.json"],
  "context_budget": {"limit_tokens": 32768, "estimated_input_tokens": 3316, "reserved_output_tokens": 3000},
  "timeout_s": 900,
  "retry_policy": {"max_attempts": 2, "backoff_s": 2},
  "status": "completed",
  "error": null,
  "started_at": "2026-11-03T12:03:37+00:00",
  "finished_at": "2026-11-03T12:13:33+00:00"
}
```

状态：`pending` / `running` / `completed` / `failed` / `blocked` / `needs_review` / `skipped`。

### 4.3 审查报告（`schema_version: 1`）

路径：`build/<slug>/review/review.json`。

字段：`lesson`、`generated_at`、`model`、`status`、`tasks[]`、`findings[]`、`errors[]`。模型任务记录新增 `provider`（`local` / `remote` / `claude_code`），任何后端都不得写成另一个后端。
单条意见：`id`、`slide`、`claim`、`verdict`（`supported` / `unsupported` / `disputed` / `needs_human_review` / `not_checked`）、`evidence`、`source_refs`。

### 4.4 状态词表

| 语境 | 词表 | 判定者 |
| --- | --- | --- |
| 课程构建阶段/检查 | `pass` / `fail` / `skipped` / `not_run` / `not_applicable` | CourseControl |
| 模型任务 | `pending` / `running` / `completed` / `failed` / `blocked` / `needs_review` / `skipped` | `ai_runtime` |
| 审查 run | `completed` / `blocked` / `failed` | ContentQA |
| 单条审查意见 | `supported` / `unsupported` / `disputed` / `needs_human_review` / `not_checked` | ContentQA + 人工 |

映射仅用于阅读，不用于互相写入：`completed ≈ pass`，`failed ≈ fail`，`skipped = skipped`，`blocked` 与 `pending` 在构建语境下对应 `not_run`。

质量层的五个 `*_VERIFIED` 名称与代码状态的对应见 [五态映射表.md](五态映射表.md)。

### 4.5 项目与运行契约（2026-11-13，增量）

- `ProjectSpec`（`delivery/project.py`，`shared/schemas/project-spec.schema.json`）：一本书或一个主题的项目定义。课程模式下 `lesson.yaml` 仍是该课的内容权威；没有 `project.yaml` 时由 `lesson.yaml` 合成，并标记 `synthesized: true`。
- `ArtifactRegistry`（`platform/artifacts.py`）：`<内容根>/runtime/artifacts/<project>/registry.json`，按 sha256 登记 build 内产物，可由目录重建；不替代交付 manifest。
- `RunRecord`（`platform/run_record.py`）：`<内容根>/runtime/runs/<run-id>/run.json`，八阶段历史内联，原子写。
- 以上三个契约当前不被构建流水线读取。CLI：`project-validate`、`project-show`、`artifact-index`、`run-start`、`run-status`。
- 知识侧：`KnowledgeStudio/knowledge_ir.py`（概念、先修、claim、证据、冲突）与 `CurriculumPlan`（覆盖、先修顺序、集数窗口）；Schema 为 `shared/schemas/knowledge-ir.schema.json` 与 `curriculum.schema.json`。这些契约不改变现有页级证据模型。
- 质量侧：`quality/defect.py`（统一缺陷，`build/<slug>/quality/defects.json`）、`quality/repair.py`（归因→策略→重跑范围）、`quality/regression.py`（fixed / still_open / introduced）。CLI：`quality-diagnose`、`quality-repair-plan`、`quality-regression`、`quality-certificate`。证书写入 `build/<slug>/quality/certificate.json`，verdict 由缺陷、质量门与报告哈希共同决定。修复执行器尚未接入。

---

## 5. AI 运行时（`shared/ai_runtime`）

纯标准库实现，不依赖 pydantic/httpx，供各工程通过 path 依赖使用。

### 5.1 跨进程锁

- 位置：`runtime/locks/llama-8080.lock`（可用参数覆盖）。
- 获取：`os.open(O_CREAT | O_EXCL)`；内容为 `pid`、`host`、`created_at`、`task_id`。
- 等待：轮询 + 超时；超时抛 `LockTimeout`。
- 陈旧回收：持有者 PID 不存在（Windows 用 `OpenProcess`），或超过 `stale_after_s`，则原子删除后重试。
- 释放：仅当锁内容中的 PID 与 task_id 与当前持有者匹配时才删除，避免误删他人锁。

### 5.2 服务生命周期

`ModelService` 上下文管理器：

1. 获取锁。
2. `/health` 健康且 `/v1/models` 含目标别名 → 复用（`mode="reused"`）。
3. 端口被占用但别名不符 → 等待至多 `startup_timeout_s`，仍不符 → `ServerBusy`（blocked）。
4. 端口空闲 → 用配置参数启动 `llama-server`。
5. 健康且别名匹配后 yielded。
6. `finally`：只停止本进程启动的实例；等待端口释放。

### 5.3 上下文预算

```python
budget = ContextBudget(limit=32768, reserved_output=2048)
budget.check(messages, images=[...])   # 超限抛 ContextOverflow，附拆分建议
```

估算规则：CJK 字符 1 token；其他字符 4 字符 1 token；图片 = `base + ceil(width*height/750)`，并计入 `--image-min-tokens` 下限。

分档：`basic=16384`、`complex=32768`、`hard=65536`。64K 不是默认值。

---

### 5.4 AI 后端：Claude Code 默认，本地/远程回退

- 入口仍是 `route_model(server, model, lock, log_path, remote=...)`：先按 §5.2 使用本地 8080。
- 仅当 `RemoteConfig` 显式启用、API key 环境变量存在、且本地失败原因在 `fallback_on` 中（`busy` / `start_error` / `lock_timeout` / `missing_executable`）时，才切换到远程 OpenAI 兼容端点。`provider` 可为 `deepseek`、`openai-compatible` 或其他兼容实现。
- 远程调用不持有本地 8080 锁；本地锁在切换前已释放。远程路由返回 `provider="remote"`、实际模型名与 `trust_env`，调用方必须写入任务记录与阶段元数据。
- 视觉阶段只有在 `supports_vision=true` 且配置 `vision_model` 时才回退；否则保持本地失败/`blocked`，不把图片交给文本模型。**DeepSeek 调用固定 `deepseek-flash`；`deepseek-v4-pro` 已禁用，`RemoteConfig` / `RemoteSettings` / ContentQA 配置都会拒绝。其他 OpenAI 兼容 provider 使用各自配置的模型。**
- 远程凭据只从环境变量读取；配置、日志、任务记录、异常与健康输出都不包含密钥。
- DeepSeek flash 默认把 `max_tokens` 用于 reasoning；长输出/结构化任务必须显式 `thinking=disabled`（`RemoteConfig.thinking` 或 `chat_completion(..., thinking="disabled")`），否则可能返回空 `content`。
- 旁白可通过 `lesson.yaml.narration.speed` 控制 VoxCPM2 后处理语速（0.5–2.0）；`narration.meta.json` 记录实际 speed 与页跨度。
- **课程 AI 默认后端是 Claude Code（D-042）。** 文本阶段用 `claude -p --tools=`（无工具），镜头 Agent 阶段才开放工具且只写 `build/` 暂存目录；任务记录 `provider=claude_code`。Claude Code 不可用时显式 `blocked`，只有 `claude_code_fallback: local_first` 才回退到本地/远程。ModelingStudio 的 vision 阶段仍用本地/远程视觉模型。
- 配置参考：`config/model-routing.example.yaml`（provider-agnostic，含 DeepSeek / OpenAI-compatible 示例）；本机实际 `.env` 与 `config/model-routing.yaml` 均被 `.gitignore` 忽略。通用环境变量为 `REMOTE_PROVIDER` / `REMOTE_BASE_URL` / `REMOTE_MODEL` / `REMOTE_VISION_MODEL` / `REMOTE_API_KEY_ENV`，DeepSeek 也兼容 `DEEPSEEK_*`。API key 只从系统环境变量读取（本机为 `DeepSeek-API`），不写入 `.env`、YAML、日志或任何文件；仓库只保留不含 key 的 `.env.example`。

## 6. 环境与端口

| 服务 | 端口 | 约束 |
| --- | --- | --- |
| 本地模型 llama.cpp | 8080 | 唯一实例；所有调用经 `ai_runtime` |
| 课件预览 / 截图源 | 8081 | live-server |
| Motion Canvas 编辑器 | 5173 | 制作/预览 |
| Motion Canvas 无头导出 | 4173 / 4174 | Vite + 帧接收器；仅构建时占用 |
| Remotion Studio | 3000 | 预览 |
| VoxCPM2 TTS（外部） | 50000 | 唯一实例；谁启动谁停止 |

不存在的约定：不提供 8082 备用端口。

技术栈版本：Python 3.12 / uv 0.10；Node 24；Reveal 6.0.2；Motion Canvas 3.17.2；Manim 0.22；Blender 5.2；Remotion 4.0.539；FFmpeg 8。

---

## 7. R1 增量（2026-11-07）

| 能力 | 模块 / 数据 | 说明 |
| --- | --- | --- |
| 输入摄取 | `course_control/authoring/ingest.py` | URL/Markdown/TXT → `authoring/sources/` + `sources.yaml`；stdlib，无新依赖 |
| 来源摘要 | `authoring/digest.py` | 稳定引用 `S1-3.2`、行号、sha、摘录 |
| 课程草稿 | `authoring/pipeline.py`、`CourseControl/prompts/` | brief/outline/script/content 候选；Claude Code 默认，本地/远程显式回退 |
| 人工批准门 | `authoring/pipeline.py`、`authoring/approval.json` | sha256 批准；`author-narration/subtitles-build` 验证 |
| 时长契约 | `content/duration.py`、`content/validators.py`、`content/collect.py`、`quality/verify.py` | `lesson.yaml.duration`；planned/measured 单向权威；V-26/V-27 |
| 整课旁白 | `voice/narration_course.py`、`voice/narrate.py` | 单服务、逐段缓存、48 kHz mono、页跨度回写；V-30 |
| 双语字幕 | `voice/subtitles.py` | 英上中下、SRT/ASS/VTT、逐 cue 翻译；V-31 |
| 双版本成片 | `adapters/burn.py`、`pipeline.py` | 干净母版 + ASS 烧录版；QSV → libx264；V-28 |
| TimelineSpec 合成 | `RemotionStudio/src/compositions/CourseTimeline.tsx`、`ScenePage.tsx`、`adapters/remotion.py` | `timeline.spec.json` 驱动；`compose.mode=scene` 用全屏 ScenePage 作为 base；`renderer: legacy` 回退 |
| 场景叠加层 | `course_control/overlays.py`、`RemotionStudio/src/overlays/AgingHud.tsx` | 课程声明 `compose.overlay: <kind>`；`collect` 把叠加数据写进 timeline `metadata.overlay`，由 Remotion 在底片之上绘制（HUD/图表不再烧进世界片） |
| 引擎路由 | `rendering/engine_router.py` | 数学/二维 → Manim；三维/工程 → Blender；排版/合成 → Remotion；motion graphics/SVG/Canvas/Three.js → code_video；Motion 兼容 |
| Code2Video 镜头 | `adapters/code_video.py`、`CodeVideoStudio/` | 镜头级 `SPEC.md` + `frame(t)` + `VERIFY.md`；本地 Playwright/ffmpeg；不部署 27B；Agent 用 Claude Code + DeepSeek |
| HTML 渲染/lint 备选 | `CodeVideoStudio/backends/hyperframes/` | HyperFrames POC：HTML/GSAP → MP4，`check` 提供首帧/字号/对比度检查；不替换 Remotion |
| Motion Canvas 自动导出 | `MotionStudio/scripts/render-headless.mjs` | core `Renderer` + 自定义 exporter + Vite + Playwright/Chrome + Node 帧接收器 + ffmpeg；端口 4173/4174 |

新增路径：`lessons/<slug>/authoring/`（来源、摘要、brief、outline、script、approval）；`build/<slug>/authoring/candidates/`（未批准候选）；`build/<slug>/narration/`；`build/<slug>/subtitles/`；`build/<slug>/timeline/page-plan.json`；`build/<slug>/final/burn.json`。

---

## 8. 扩展规则

1. 新引擎必须实现 `adapters/base.py` 的 `StageOutcome` 契约，并由 `lesson.yaml.engines` 声明。
2. 新数据文件必须有 Pydantic 模型 + 导出的 JSON Schema + 同步测试。
3. 新模型调用必须经 `ai_runtime.ModelService` 与 `ContextBudget`，并写任务记录。
4. 新阶段必须定义：输入、输出、失败语义、适用性规则（何时 `not_applicable`）。
5. 不新增“平行实现”；先确认现有模块能否扩展。
