# CourseControl

课程生产控制层。读取 `lessons/<slug>/` 的 YAML 契约，按课程实际使用的引擎调度渲染，生成 `build/<slug>/shots.json`，调用 Remotion 合成最终视频，并写出 `build/<slug>/final/build-report.json`。

## 边界

- 只写 `build/<slug>/` 与各工程的 `.venv` / `node_modules` 缓存。
- 不修改课程正文、`CourseSlides/`、`MotionStudio/`、`ManimSandbox/`、`BlenderStudio/` 的源码。
- 不调用 LLM，不自动发布，不自动提交 Git。
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
uv run course-control validate --lesson 01-shell-for-ai-era --workspace ..

# 完整构建
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
| `render:motion_canvas` | `engines` 含 `motion_canvas` | `build/<slug>/animation/<scene>.mp4`（人工导出基线） |
| `render:manim` | `engines` 含 `manim` | `build/<slug>/animation/<scene>.mp4` |
| `render:blender` | `engines` 含 `blender` | 由 Blender 任务 JSON 指定的 `build/<slug>/blender/*.mp4` |
| `collect` | 上游通过 | `build/<slug>/shots.json` |
| `compose` | 上游通过且未跳过 | staging + Remotion → `final/course-video.mp4` |
| `verify` | 合成通过 | `checks[]` |

不适用的阶段写 `not_applicable`；人工导出或 CLI 跳过写 `skipped` / `not_run`；只有全部必需阶段为 `pass` 才是 `verdict=pass`。

## 阶段状态

`pass` / `fail` / `skipped` / `not_run` / `not_applicable`，与 PRD 一致。

- 引擎不在 `engines` 中 → `not_applicable`
- 人工导出缺失且 `allow_manual_animation_export=true` → `skipped`，最终 `incomplete`
- 任一阶段失败 → `fail`，下游写 `not_run`
- 合成失败时保留 `public/staging/<slug>/` 与日志，便于排查；成功后才清理

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

## 人工导出 Motion Canvas

R4 采用基线 C：Motion Canvas 3.17.2 没有 CLI 渲染入口，需在编辑器里导出。文件命名：

```text
build/<slug>/animation/<scene-stem>.mp4
```

例如 `MotionStudio/src/scenes/01-shell-for-ai-era/gui_vs_cli_paths.tsx` → `build/01-shell-for-ai-era/animation/gui_vs_cli_paths.mp4`。

导出后重新运行 `build`，`render:motion_canvas` 会从 `skipped` 变为 `pass`。详见 [决策记录](../docs/决策记录-MotionCanvas渲染.md)。

## 夹具

- `tests/fixtures/lesson-smoke/`：`recording` 模式、纯 Blender 插片、字幕开启。
- `tests/fixtures/lesson-blender-only/`：纯 Blender，验证 Motion / Manim 为 `not_applicable`。
- `tests/fixtures/lesson-manual/`：Motion Canvas 人工导出接入。

夹具需要的底稿、旁白和人工导出样本由脚本生成：

```powershell
.\scripts\prepare-fixtures.ps1
```

## 旁白与字幕

- 旁白是可选输入：`build/<slug>/narration/<source>`，在 `lesson.yaml` 用 `narration.enabled` / `narration.source` 打开。
- 合成时 `collect` 探测音频时长，Remotion 混音，`verify` 用 V-15 检查音画差。
- 字幕是可选输入：`lessons/<slug>/subtitles.srt`，由 `subtitles.enabled` 打开；`collect` 复制到 `build/<slug>/subtitles.srt`。
- 合成与配音运行时都在 `<AI_ROOT>`，接入流程见 [本地模型与配音工作流](../docs/本地模型与配音工作流.md)。
- 本层不做 TTS、不做语音识别。

## 报告与日志

- 报告：`build/<slug>/final/build-report.json`
- 阶段日志：`build/<slug>/logs/*.log`
- 截图 manifest：`build/<slug>/slides/capture-manifest.json`
- 合成时间线：`build/<slug>/shots.json`

报告包含 `stages[]`、`checks[]`、`artifacts[]`、`toolchain`、`verdict` 与 `failures[]`。
