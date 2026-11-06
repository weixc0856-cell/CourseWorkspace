# CourseWorkspace 架构与数据契约

- **版本**：v1.0（2026-11-03）
- **上游**：[PRD.md](PRD.md)
- 本文件描述“系统如何组成、模块如何调用、数据如何流动”。需求本身以 PRD 为准。

---

## 1. 总体结构

```text
CourseWorkspace/
├── lessons/            内容层：唯一的课程输入
├── CourseControl/      控制层：校验、调度、收集、报告（Python 3.12 + uv）
├── CourseSlides/       展示层：Reveal.js 外壳（Node）
├── MotionStudio/       动画层：Motion Canvas（Node，人工导出）
├── ManimSandbox/       动画层：Manim（Python，可选）
├── BlenderStudio/      三维层：Blender 5.2 + 场景系统 + 渲染脚本
├── RemotionStudio/     合成层：截图采集、staging、Remotion 合成（Node）
├── ModelingStudio/     三维内部能力：图片 → Blender（Python）
├── ContentQA/          审查内部能力：在线模型内容审查（Python）
├── shared/
│   ├── ai_runtime/     AI 运行时：跨进程锁、服务生命周期、任务状态、上下文预算
│   ├── scene_expr/     受限表达式：AST 白名单 + 解释器（控制层与 Blender 共用）
│   ├── schemas/        JSON Schema（由 Pydantic 导出）
│   └── design-tokens/  设计令牌
├── config/             本机配置（*.yaml 本地文件不入库）
├── scripts/            PowerShell 工作区入口
├── build/              全部生成物（不入库）
├── runtime/            锁与模型任务记录（不入库）
└── docs/               权威文档 + docs/archive/
```

### 1.1 写入归属

| 位置 | 写入方 | 内容 |
| --- | --- | --- |
| `lessons/` | 人工 | 课程正文与契约 |
| `build/<slug>/` | CourseControl 及其适配器 | 截图、动画、三维、时间线、日志、报告 |
| `RemotionStudio/public/staging/<slug>/` | Remotion staging | 合成期临时素材（成功后清理） |
| `runtime/locks/` | `shared/ai_runtime` | 跨进程锁 |
| `runtime/tasks/` | `shared/ai_runtime` | 模型任务记录 |
| `ModelingStudio/workspace/jobs/` | ModelingStudio | 建模作业 |
| `BlenderStudio/scenes/`、`assets/` | 人工 | `.blend` 与 GN 资产 |
| `<AI_ROOT>` | **任何人都不写** | 模型与运行时 |

---

## 2. 模块职责

| 模块 | 职责 | 不做什么 |
| --- | --- | --- |
| `CourseControl` | 解析契约、调度阶段、收集时间线、合成调用、报告 | 不改课程正文；不判定内容正确性 |
| `CourseSlides` | 加载指定课程为 Reveal 页面 | 不写 `build/` |
| `MotionStudio` | 动画场景源码 | 不自动导出 |
| `ManimSandbox` | 数学动画备选 | 不进入主流程 |
| `BlenderStudio` | v1 课程渲染任务、v2 场景系统、GN 资产、场景验收 | 不读取 `lesson.yaml` |
| `RemotionStudio` | 截图、staging、合成、字幕/旁白渲染 | 不做时间线推导 |
| `ModelingStudio` | 图片→分析→规划→脚本→Blender→验收 | 不写 `lessons/` 与课程 `build/` |
| `ContentQA` | 在线审查候选意见与报告 | 不改课程、不影响 verdict |
| `CourseDemo` | 驱动 VS Code 终端会话并回收退出码/输出 | 不做执行证据的唯一来源 |
| `shared/ai_runtime` | 锁、服务生命周期、任务状态、预算 | 不含业务逻辑 |

---

## 3. 调用关系

> 面向操作的完整流程（输入、输出、人工节点、失败恢复）见 [WORKFLOW.md](WORKFLOW.md)。

### 3.1 课程构建

```text
course-control build
  ├─ LessonPaths.load(lesson.yaml, storyboard.yaml)
  ├─ validate()                        # V-01..V-09
  ├─ adapters.slides.capture_slides()  # live-server 8081 + playwright
  ├─ adapters.motion_canvas.run()      # 校验人工导出
  ├─ adapters.manim.run()              # uv run manim
  ├─ adapters.blender.run()            # scripts/blender-render.ps1（v1）
  ├─ collect()                         # → shots.json
  ├─ adapters.remotion.compose()       # stage-assets.mjs + npx remotion
  └─ verify()                          # V-10..V-21 → build-report.json
```

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

### 3.4 在线审查

```text
content-qa review
  ├─ 读取 lessons/<slug>/slides.md、lecture_notes.md、sources.yaml（可选）
  ├─ 按页拆分 + 预算
  ├─ 在线模型（OpenAI 兼容）逐任务调用
  ├─ 结构校验（Pydantic）
  └─ build/<slug>/review/review.json + review.md
```

ContentQA 不读取也不写 `shots.json` / `build-report.json`。

---

## 4. 数据契约

### 4.1 课程契约（`schema_version: 1`）

| 文件 | 契约 | Schema |
| --- | --- | --- |
| `lessons/<slug>/lesson.yaml` | 课程配置 | `shared/schemas/lesson.schema.json` |
| `lessons/<slug>/storyboard.yaml` | 镜头表 | `shared/schemas/storyboard.schema.json` |
| `build/<slug>/shots.json` | 时间线（生成物） | `shared/schemas/shots.schema.json` |
| `build/<slug>/final/build-report.json` | 构建报告（生成物） | `shared/schemas/build-report.schema.json` |
| Blender 任务 v2 | 场景任务 | `shared/schemas/blender-scene-task.schema.json` |
| 代码/终端会话 | 执行、录制、证据 | `shared/schemas/session.schema.json`、`evidence.schema.json` |
| 模型任务记录 | 任务状态与预算 | `shared/schemas/model-task.schema.json` |
| 内容审查报告 | 在线审查输出 | `ContentQA/schemas/content-review.schema.json` |

Schema 由 Pydantic 模型导出：`course-control schemas --output shared/schemas`。提交前必须与模型一致（有测试锁定）。

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

字段：`lesson`、`generated_at`、`model`、`status`、`tasks[]`、`findings[]`、`errors[]`。
单条意见：`id`、`slide`、`claim`、`verdict`（`supported` / `unsupported` / `disputed` / `needs_human_review` / `not_checked`）、`evidence`、`source_refs`。

### 4.4 状态词表

| 语境 | 词表 | 判定者 |
| --- | --- | --- |
| 课程构建阶段/检查 | `pass` / `fail` / `skipped` / `not_run` / `not_applicable` | CourseControl |
| 模型任务 | `pending` / `running` / `completed` / `failed` / `blocked` / `needs_review` / `skipped` | `ai_runtime` |
| 审查 run | `completed` / `blocked` / `failed` | ContentQA |
| 单条审查意见 | `supported` / `unsupported` / `disputed` / `needs_human_review` / `not_checked` | ContentQA + 人工 |

映射仅用于阅读，不用于互相写入：`completed ≈ pass`，`failed ≈ fail`，`skipped = skipped`，`blocked` 与 `pending` 在构建语境下对应 `not_run`。

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

## 6. 环境与端口

| 服务 | 端口 | 约束 |
| --- | --- | --- |
| 本地模型 llama.cpp | 8080 | 唯一实例；所有调用经 `ai_runtime` |
| 课件预览 / 截图源 | 8081 | live-server |
| Motion Canvas 编辑器 | 5173 | 人工导出 |
| Remotion Studio | 3000 | 预览 |
| VoxCPM2 TTS（外部） | 50000 | 唯一实例；谁启动谁停止 |

不存在的约定：不提供 8082 备用端口。

技术栈版本：Python 3.12 / uv 0.10；Node 24；Reveal 6.0.2；Motion Canvas 3.17.2；Manim 0.22；Blender 5.2；Remotion 4.0.539；FFmpeg 8。

---

## 7. 扩展规则

1. 新引擎必须实现 `adapters/base.py` 的 `StageOutcome` 契约，并由 `lesson.yaml.engines` 声明。
2. 新数据文件必须有 Pydantic 模型 + 导出的 JSON Schema + 同步测试。
3. 新模型调用必须经 `ai_runtime.ModelService` 与 `ContextBudget`，并写任务记录。
4. 新阶段必须定义：输入、输出、失败语义、适用性规则（何时 `not_applicable`）。
5. 不新增“平行实现”；先确认现有模块能否扩展。
