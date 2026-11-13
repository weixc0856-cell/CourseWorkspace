# CourseControl


> **2026-11-13 状态**：`check.ps1` = `check ok`。V2 的动画预览、声音资产、镜头表、锁定、M1 闭环修补，以及项目/运行契约、阶段 DAG、质量缺陷闭环与知识概念层均已落地；执行台账见 `docs/v2/m0/EXECUTION_PLAN.md`。`build/` 为临时区、`deliver/` 为最终交付区。
课程生产控制层。读取 `lessons/<slug>/` 的 YAML 契约，按课程实际使用的引擎调度渲染，生成 `build/<slug>/shots.json`，调用 Remotion 合成最终视频，并写出 `build/<slug>/final/build-report.json`；`package` 把最终资产复制到 `deliver/<slug>/`。

在上游还包含三个设计/管理层：

- `director/`：已批准的 brief / outline / script / storyboard → 导演计划、引擎路由、硬闸门；
- `delivery/`：订单、授权、交付清单、状态与 `producer-rebuild` 增量；
- `layout/` + `simulation.py`：版式模板/配色 token，以及模拟数据的输入输出契约。

## 边界

- 临时产物只写 `build/<slug>/`，最终交付只写 `deliver/<slug>/`；各工程的 `.venv` / `node_modules` 只作缓存。
- 不修改课程正文、`CourseSlides/`、`MotionStudio/`、`ManimSandbox/`、`BlenderStudio/` 的源码。
- 课程文本/审查经 `shared/ai_runtime` 显式调用 Claude Code 或配置的后端；不自动发布，不自动提交 Git。
- 课程 YAML 由本层解析；Blender 只接收 JSON 任务。

## 环境

```powershell
cd CourseWorkspace\CourseControl
uv sync
```

依赖：`pydantic`、`PyYAML`、`typer`、`pillow`。Python `3.12`。

## 命令

```powershell
# 工具链与路径
uv run course-control audit --workspace ..

# 只校验契约
uv run course-control validate --lesson <slug> --workspace ..

# 导演计划 / 结构校验 / 局部重渲染
uv run course-control director-plan --lesson <slug> --workspace ..
uv run course-control director-validate --plan ../build/<slug>/director/director_plan.json
uv run course-control producer-run --lesson <slug> --workspace ..
uv run course-control producer-rebuild --lesson <slug> --workspace ..

# 旁白 / 字幕
uv run course-control narration-build --lesson <slug> --workspace ..
uv run course-control subtitles-build --lesson <slug> --workspace ..
uv run course-control subtitles-accept --lesson <slug> --workspace ..
uv run course-control burn-subs --lesson <slug> --workspace ..

# 音频策略
uv run course-control audio-plan --lesson <slug> --workspace ..

# 版式 / 模拟
uv run course-control layout-templates
uv run course-control layout-validate --template process_flow
uv run course-control simulation-run --spec ../BlenderStudio/scenes/primer-poc/simulation.spec.json --out ../build/primer-poc/simulation.json

# 完整构建（导演 handoff 可选）
uv run course-control build --lesson lesson-smoke `
  --lesson-dir CourseControl/tests/fixtures --workspace ..

# 跳过上游渲染 / 跳过合成
uv run course-control build --lesson lesson-smoke `
  --lesson-dir CourseControl/tests/fixtures --skip-render --workspace ..

# 仅校验已有产物
uv run course-control verify --lesson lesson-smoke `
  --lesson-dir CourseControl/tests/fixtures --workspace ..

# 导出 JSON Schema
uv run course-control schemas --output ../shared/schemas

# Blender 场景任务 IR v2：只校验
uv run course-control scene-validate `
  --task ../BlenderStudio/tasks/scene-system/demo-scene.json --workspace ..

# Blender 场景任务 IR v2：校验 + 执行 + 验收 + manifest
uv run course-control scene-run `
  --task ../BlenderStudio/tasks/scene-system/demo-scene.json --workspace ..

# 只导出场景任务 Schema
uv run course-control scene-schema
```

工作区级入口：

```powershell
.\scripts\build-lesson.ps1 -Lesson lesson-smoke -LessonDir CourseControl/tests/fixtures
```

## 阶段

| 阶段 | 何时执行 | 输出 |
| --- | --- | --- |
| `validate` | 总是 | 契约校验结果 |
| `capture_slides` | `compose.mode=deck` 且未跳过合成 | `build/<slug>/slides/*.png` + manifest |
| `render:motion_canvas` | `engines` 含 `motion_canvas` | `build/<slug>/animation/<scene>.mp4`（无头 Renderer 自动导出） |
| `render:manim` | `engines` 含 `manim` | `build/<slug>/animation/<scene>.mp4` |
| `render:blender` | `engines` 含 `blender` | 由 Blender 任务 JSON 指定的 `build/<slug>/blender/*.mp4` |
| `render:code_video` | `engines` 含 `code_video` | `build/<slug>/animation/<project>.mp4`；`inputs.simulation_spec` 会先生成 `simulation.json` |
| `collect` | 上游通过 | `build/<slug>/shots.json` |
| `compose` | 上游通过且未跳过 | staging + Remotion → `final/course-video.mp4` |
| `verify` | 合成通过 | `checks[]` |

不适用的阶段写 `not_applicable`；人工/CLI 跳过写 `skipped` / `not_run`；Motion Canvas 自动导出失败写 `fail`，重试 2 次，不写 `skipped`。只有全部必需阶段为 `pass` 才是 `verdict=pass`。

## 设计/制片层

- 导演计划：`director-plan`，输出 `director_plan.json`、`storyboard.director.yaml`、`directions/`、`shot_specs/`、`director_review.md`；
- 制片：`producer-order` / `producer-run` / `producer-status` / `producer-rebuild`，输出订单、状态和七项交付清单；
- 动画适配器：Motion Canvas 无头导出、Manim、Blender、CodeVideo 统一 `StageOutcome`，见 [动画渲染适配器](../docs/动画渲染适配器.md)；
- 版式与配色：8 个模板、安全区/重叠/容量/字幕带校验；
- 音频：`audio-plan` 按内容类型校验 BGM（正式课程/新闻禁用；许可/署名/电平硬闸门）；
- 模拟：`SimulationSpec` → `SimulationData`，Blender/Three.js 共用；
- `build --storyboard` / `--shots` 可显式加载导演 handoff 并局部重渲染。

## 阶段状态

`pass` / `fail` / `skipped` / `not_run` / `not_applicable`，与 PRD 一致。

- 引擎不在 `engines` 中 → `not_applicable`
- 任一阶段失败 → `fail`，下游写 `not_run`
- 合成失败时保留 `build/<slug>/tmp/remotion-staging/<slug>/` 与日志；Remotion 渲染器所需的 `public/staging/<slug>/` 是临时镜像，成功后清理

## Blender 场景任务（IR v2）

除课程级构建外，本层提供 Blender 场景任务的独立入口：

| 命令 | 作用 |
| --- | --- |
| `scene-validate` | 用 Pydantic 校验 `schema_version: 2` 任务，不启动 Blender |
| `scene-schema` | 导出 `shared/schemas/blender-scene-task.schema.json` |
| `scene-run` | 校验 → `scripts/blender-render.ps1` → 输出检查 → 场景验收 → manifest |

`scene-run` 的检查包括：退出码、PNG 分辨率/大小/黑帧、MP4 编码/分辨率/时长、场景问题列表、活动相机、对象数量、GN 修改器数量、F-Curve 数量。任一 `fail` 则整体 `fail`。

产物：

```text
build/<lesson>/blender/manifests/<task_id>.json        # 执行 + 验收清单
build/<lesson>/blender/manifests/<task_id>-scene.json  # 场景报告
build/<lesson>/logs/scene-run-<task_id>.log            # 包装器输出
build/<lesson>/logs/verify-<task_id>.log               # Blender 场景验收日志
```

manifest 记录任务哈希、随机种子、Blender 版本、宿主 Python/平台、渲染参数、退出码、耗时与全部检查。完整契约见 [Blender 场景任务 IR v2](../docs/Blender场景任务IR-v2.md)。

## Motion Canvas 自动导出

Motion Canvas 3.17.2 没有官方 CLI，但 core `Renderer` 可编程调用。`MotionStudio/scripts/render-headless.mjs` 启动 Vite、用 Playwright/Chrome 加载无头页、通过自定义 exporter 把每帧 PNG 发送到 Node 帧接收器，再由 ffmpeg 编码。输出命名：

```text
build/<slug>/animation/<scene-stem>.mp4
```

例如 `<内容根>/engines/motion_canvas/scenes/<lesson>/<scene>.tsx` → `build/<slug>/animation/<scene>.mp4`。

导出后重新运行 `build`，`render:motion_canvas` 会从 `skipped` 变为 `pass`。详见 [DECISIONS.md](../docs/DECISIONS.md) D-004。

## 夹具

- `tests/fixtures/lesson-smoke/`：`recording` 模式、纯 Blender 插片、字幕开启。
- `tests/fixtures/lesson-blender-only/`：纯 Blender，验证 Motion / Manim 为 `not_applicable`。
- `tests/fixtures/lesson-manual/`：Motion Canvas 自动导出接入。

夹具需要的底稿、旁白和 Motion 导出样本由脚本生成：

```powershell
.\scripts\prepare-fixtures.ps1
```

## 旁白与字幕

- 旁白是可选输入：`build/<slug>/narration/<source>`，在 `lesson.yaml` 用 `narration.enabled` / `narration.source` 打开。
- 合成时 `collect` 探测音频时长，Remotion 混音，`verify` 用 V-15 检查音画差。
- 字幕是可选输入：`lessons/<slug>/subtitles.srt`，由 `subtitles.enabled` 打开；`collect` 复制到 `build/<slug>/subtitles.srt`。
- 配音走本地 VoxCPM2（50000，唯一实例，谁启动谁停止）；合成与运行时接入见 [本地模型与配音工作流](../docs/本地模型与配音工作流.md)。
- 本层不做 ASR / 词级对齐；字幕由实测旁白时间轴生成，人工 `subtitles-accept` 后才进入正式字幕。

## 报告与日志

- 报告：`build/<slug>/final/build-report.json`
- 阶段日志：`build/<slug>/logs/*.log`
- 截图 manifest：`build/<slug>/slides/capture-manifest.json`
- 合成时间线：`build/<slug>/shots.json`

报告包含 `stages[]`、`checks[]`、`artifacts[]`、`toolchain`、`verdict` 与 `failures[]`。

## 交付分区（D-085）

- `build/<slug>/` 是临时区：渲染、预览、缓存、日志与 `producer/` 制片清单；可删除重建。
- `deliver/<slug>/` 是最终交付区：`final/master.mp4`、字幕、报告、证据、`manifest.json`、`delivery-checklist.md`；不要删。
- `producer-run` 的清单在 `build/<slug>/producer/`，不是最终交付。

## V1 收敛命令（2026-11-10）

```powershell
# 配置解析：来源、冲突、指纹；build 也会自动写 logs/config-resolution.json
course-control config-resolve --lesson <slug>

# 顶层恢复：只复用输入/配置/输出哈希都一致的阶段
course-control build --lesson <slug> --resume
course-control build --lesson <slug> --resume-from compose

# 统计与字幕 QC
course-control stats --lesson <slug> --write
course-control subtitles-qc --lesson <slug>

# 审查裁决与交付包
course-control review-status --lesson <slug>
course-control review-decide --lesson <slug> --id <finding> --decision fixed --by <name>
course-control package --lesson <slug>
course-control package-verify --package deliver/<slug>

# Blender 任务入口 / three.js / 镜头分类
course-control blender-task-validate --task BlenderStudio/tasks/<lesson>/<task>.json
course-control vendor-check
course-control shot-taxonomy
```

细节见 `docs/stabilization/CONFIGURATION_STANDARD.md`、`TASK_EXECUTION_STANDARD.md`、`QUALITY_STANDARD.md`。

## 质量闭环（P0）

```powershell
uv run --project CourseControl course-control narrative-validate --lesson <slug>
uv run --project CourseControl course-control audio-plan --lesson <slug>
uv run --project CourseControl course-control audio-mix --lesson <slug>
uv run --project CourseControl course-control media-qc --lesson <slug>
uv run --project CourseControl course-control quality-report --lesson <slug>
uv run --project CourseControl course-control teaching-qa --lesson <slug>
uv run --project CourseControl --extra asr course-control asr-align --lesson <slug>
```

- `narrative-validate`：校验 `authoring/narrative-plan.json` 的六段骨架与时长，写 `quality/narrative.json`。
- `audio-mix`：消费 `audio_plan.json`，从 `config/local-paths.yaml` 的 `bgm_root` 找本地曲目；
  sidechain ducking + `loudnorm I=-16:TP=-1.5`，输出 `final/course-video-mixed.mp4`。缺曲目或许可未知即 blocked。
- `media-qc`：全片解码、分辨率/帧率/帧数、EBU R128 响度、静音、黑帧、冻结帧、字幕结构；
  写 `quality/media-qc.json`。
- `quality-report`：五维独立状态（Q1–Q5）与 `BUILD_PASS / QUALITY_PASS / RELEASE_APPROVED`；
  输出 `quality/quality-report.{json,md,html}`。叙事结构通过只把 Q2 记 WARN，不等于教学有效。
- `teaching-qa`：教学目标覆盖、页面 claim、例子/反例、认知负荷、收尾检查；
  `learner_evidence` 永远为 `missing`，报告状态为 WARN，不声称教学有效。
- `asr-align`：faster-whisper `small.en` 转写旁白，按 cue 窗口比对英文文本；
  缺 ASR 时 Media QC 的 `media.speech_match` 为 INCOMPLETE。首次需
  `uv sync --project CourseControl --extra asr`，模型缓存到 `runtime/asr/models/`。
- 发布批准必须有人工 `quality/release-approval.json`，系统不代签。

### 项目、运行与质量（2026-11-13，增量）

```powershell
# 项目契约（没有 project.yaml 的课由 lesson.yaml 合成，标记 synthesized）
uv run course-control project-validate --project ..\projects\<id>\project.yaml --workspace ..
uv run course-control project-show --lesson <slug> --workspace ..

# 制品索引与运行记录
uv run course-control artifact-index --lesson <slug> --workspace ..
uv run course-control run-start --lesson <slug> --workspace ..
uv run course-control run-status --run <run-id> --workspace ..

# 缺陷诊断、修复计划、回归与证书
uv run course-control quality-diagnose --lesson <slug> --workspace ..
uv run course-control quality-repair-plan --lesson <slug> --attempt 1 --workspace ..
uv run course-control quality-regression --lesson <slug> --before <defects.json> --workspace ..
uv run course-control quality-certificate --lesson <slug> --workspace ..
```

约定：这些契约不改 `build` 默认行为；修复计划只给范围，不自动改产物；`attempt > 3` 直接 blocked。
