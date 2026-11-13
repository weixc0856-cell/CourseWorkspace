# BlenderStudio


> **2026-11-13 状态**：`check.ps1` = `check ok`。V2 的动画预览、声音资产、镜头表、锁定、M1 闭环修补，以及项目/运行契约、阶段 DAG、质量缺陷闭环与知识概念层均已落地；执行台账见 `docs/v2/m0/EXECUTION_PLAN.md`。`build/` 为临时区、`deliver/` 为最终交付区。
3D 场景与渲染工程。负责 Blender 场景构建、Geometry Nodes 资产、场景级验收与渲染；课程级编排、调度与最终验收仍属于 `CourseControl/`。

## 边界

- 读取：`BlenderStudio/tasks/`、`BlenderStudio/scenes/`、`BlenderStudio/assets/`、`config/tools.yaml`。
- 课程场景在内容根 `<内容根>/engines/blender/scenes/`；`scenes/` 里只保留夹具与样板（`lesson-*`、`primer-poc`）。
- 写入：只写 `build/<lesson>/blender/` 与 `build/<lesson>/logs/`。
- 不写入 `CourseSlides/`、`MotionStudio/`、`ManimSandbox/`、`RemotionStudio/`。
- 不在 Blender 内置 Python 中安装第三方包。
- IR v2 任务文件只包含数据字段，不包含可执行代码。
- `scenes/primer-poc/` 是独立模拟 POC：用 Blender Python 消费 `SimulationData`，不属于 IR v2 任务；只用于双引擎对照。

## 任务入口（2026-11-10）

v1 课程任务与 v2 场景任务都由 `CourseControl` 的 `blender_task.load_blender_task` 读取：按 `schema_version` 分派、未知字段拒绝、输出必须在 `build/<lesson>/blender/`。校验命令：

```powershell
uv run --project CourseControl course-control blender-task-validate --task BlenderStudio/tasks/<lesson>/<task>.json
```

v2 场景仍用于 POC 与场景验证，不进入课程默认链路，除非课程显式引用。

## 环境

- Blender `5.2.3 LTS`（实际验收版本，运行日志会记录）。
- 可执行文件：`<BLENDER_EXE>`，实际路径写入本地 `config/tools.yaml`（已忽略）。`scripts/setup.ps1` 可从 `config/tools.example.yaml` 生成。
- 不使用 `blender-launcher.exe`；它是 GUI 启动器，不接受后台渲染参数。
- 默认引擎 `BLENDER_EEVEE`；`CYCLES` 与 `BLENDER_WORKBENCH` 可作为任务级显式选择。

## 模拟世界 POC

`scenes/primer-poc/world.py` 读取 `build/primer-poc/simulation.json`，生成六边形地块、按物种着色的 blob、轨道相机与 PNG 序列；Blender 5.2 当前构建没有 `file_format=FFMPEG`，POC 先出 PNG 再由 ffmpeg 编码。复现见 `scenes/primer-poc/README.md`。

## 入口

工作区级入口是 `scripts/blender-render.ps1`：

```powershell
# 5 秒冒烟视频：build/<lesson>/blender/smoke.mp4
.\scripts\blender-render.ps1 -Lesson <slug> -Smoke

# JSON 任务
.\scripts\blender-render.ps1 -Lesson <slug> -Task BlenderStudio/tasks/lesson-blender-only/overlay.json

# 显式覆盖引擎
.\scripts\blender-render.ps1 -Lesson <slug> -Task BlenderStudio/tasks/lesson-blender-only/overlay.json -Engine CYCLES
```

PowerShell 入口负责：

- 校验 Blender 可执行文件存在，并读取 `blender --version`；
- 读取 `config/tools.yaml` 的超时与默认引擎；
- 校验任务输出必须位于 `build/<lesson>/blender/`；
- 超时终止（退出码 `124`）；
- 合并 stdout/stderr 到 `build/<lesson>/logs/blender-*.log`；
- 原样透传 Blender 退出码。

Blender 内脚本：

- `scripts/render_smoke.py`：程序化方块场景，默认 5 秒、1920×1080、30 fps、EEVEE。
- `scripts/render_shot.py`：读取 JSON 任务，支持单帧 PNG 或 MP4。
- `scripts/render_common.py`：任务校验、场景搭建、渲染配置的共享实现。

## 任务 IR v2（推荐）

从 `schema_version: 2` 开始，BlenderStudio 支持结构化场景任务：集合、对象、材质、相机、灯光、Geometry Nodes、关键帧动画与渲染配置都由 JSON 驱动。完整字段与约束见 [Blender 场景任务 IR v2](../docs/Blender场景任务IR-v2.md)。

```powershell
# 只校验，不启动 Blender
uv run --project CourseControl course-control scene-validate `
  --task BlenderStudio/tasks/scene-system/demo-scene.json

# 校验 + 执行 + 输出检查 + 场景验收 + manifest
uv run --project CourseControl course-control scene-run `
  --task BlenderStudio/tasks/scene-system/demo-scene.json
```

执行链：

```text
course-control scene-run
  → Pydantic 校验
  → scripts/blender-render.ps1（超时、日志、路径约束）
  → Blender 5.2 --background
  → render_shot.py → scene_system.executor
  → verify_scene.py（场景报告）
  → build/<lesson>/blender/manifests/<task_id>.json
```

执行器模块（`scripts/scene_system/`）：

| 模块 | 职责 |
| --- | --- |
| `task_schema.py` | v2 任务校验，无第三方依赖 |
| `scene.py` | 场景重置、固定集合、单位、时间轴、保存/打开 |
| `geometry.py` | `bmesh` 数据级图元、`TEXT`、`CURVE`、参数化曲面、点属性写入 |
| `objects.py` | 对象（MESH/EMPTY/TEXT/CURVE）、变换、材质槽、父子关系 |
| `materials.py` | Principled / Emission / 科学着色节点模板、Coat、程序化 Bump |
| `cameras.py` | 相机、look-at、景深 |
| `lighting.py` | Area / Point / Sun / Spot |
| `geometry_nodes.py` | 资产注册表、接口检查、修改器参数 |
| `animation.py` | 关键帧、插值、F-Curve |
| `rendering.py` | 引擎、分辨率、采样、色彩管理、输出 |
| `executor.py` | 串联以上模块，保存 `.blend` 并渲染 |

场景验收报告由 `scripts/verify_scene.py` 生成：对象/集合/网格统计、文字内容、曲线点数与倒角、材质、相机（含投影方式与 `ortho_scale`）、灯光、修改器、动画 F-Curve、缺失外部资源。

## Geometry Nodes 资产

- 资产库：`assets/geometry_nodes/gn_library.blend`
- 注册表：`assets/geometry_nodes/registry.json`
- 构建脚本：`assets/geometry_nodes/build_assets.py`

当前资产：`gn.displace_noise`、`gn.scatter_cubes`。资产修改后必须重建 `.blend` 并更新注册表版本；执行时会按 Interface 名称检查输入，缺失或类型不匹配会直接失败。

## 材质预设

- 目录：`assets/materials/presets/*.json`
- 预设：`studio_floor`、`aluminum_brushed`、`matte_plastic`、`coated_paint`、`rubber_matte`、`transparent_sheet`、`emissive_white`
- 任务中写 `{ "id": "mat.x", "preset": "aluminum_brushed" }`；控制层展开后再校验与执行，manifest 记录展开来源。
- 预设只描述 `shader` 与 `params`，不包含对象或渲染设置。

## 科学着色

- 色标定义：`shared/colormaps.json`（`viridis`、`coolwarm`、`grayscale`），Blender 与 Remotion 共用。
- 材质：`shader: "scientific_colormap"`，`source_attribute` / `min_value` / `max_value` / `units` / `colormap` 全部必填，无自动范围。
- 对象：`attributes[]` 声明点属性，字段为 `axis` / `distance` / `noise` 的声明式描述。
- 验收：`scene.materials` 回读着色参数，`scene.attributes` 核对属性存在；场景报告按首/中/末顶点复算并比对。

## 受限表达式

- 实现：`shared/scene_expr`（纯标准库，无 `eval`/`exec`）。
- 用途：`SURFACE` 的 `z = f(x, y)`，以及 `attributes[].field.kind = "expression"`。
- 变量只有 `x` / `y` / `z`；函数白名单见 IR 文档 §5.1.2。
- 控制层与 Blender 内置校验器共用同一解释器，保证双端结论一致。

```powershell
& "<BLENDER_EXE>" --background --factory-startup --python-exit-code 1 `
  --python BlenderStudio/assets/geometry_nodes/build_assets.py
```

## JSON 任务（schema_version 1，兼容保留）

```json
{
  "schema_version": 1,
  "lesson": "<slug>",
  "scene": "procedural_cube",
  "engine": "BLENDER_EEVEE",
  "resolution": [1920, 1080],
  "fps": 30,
  "frames": 1,
  "samples": 16,
  "format": "png",
  "output": "build/<slug>/blender/still.png",
  "blend": null
}
```

字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `schema_version` | 是 | 固定 `1` |
| `lesson` | 是 | slug，必须与输出目录一致 |
| `scene` | 否 | `procedural_cube`；当前只用于标识 |
| `engine` | 否 | `BLENDER_EEVEE`（默认）/ `CYCLES` / `BLENDER_WORKBENCH` |
| `resolution` | 是 | `[宽, 高]`，正整数 |
| `fps` | 是 | 正整数 |
| `frames` | 是 | 正整数；PNG 必须为 `1` |
| `samples` | 否 | 默认 `8`；EEVEE 对应 `taa_render_samples`，Cycles 对应 `samples` |
| `format` | 是 | `png` 或 `mp4` |
| `output` | 是 | 必须位于 `build/<lesson>/blender/`，扩展名与格式一致 |
| `blend` | 否 | `.blend` 绝对/相对路径；为空时使用程序化场景 |

校验失败时脚本打印 `TASK_ERROR: ...` 并以非零码退出。

## 测试任务

仓库内保留的 v1 夹具只有 `tasks/lesson-smoke/overlay.json` 与 `tasks/lesson-blender-only/overlay.json`，它们是课程夹具的最小任务。真实课程的任务在内容根：`<内容根>/engines/blender/tasks/<slug>/`，由 `course-control build` 的 `render:blender` 阶段读取。
| `invalid-missing-output.json` | 退出码 4（PowerShell 预检） |
| `invalid-resolution.json` | 退出码 1（Blender 内校验，日志含 `TASK_ERROR`） |
| `invalid-outside.json` | 退出码 5（PowerShell）/ 1（Blender 直调），不生成文件 |
| `timeout-test.json` | 配合 `-TimeoutSeconds 2` 时退出码 124，日志 `TIMED_OUT: true` |

`tasks/scene-system/` 下的 v2 样本（lesson 统一为 `blender-scene-acceptance`）：

| 任务 | 覆盖能力 | 预期结果 |
| --- | --- | --- |
| `demo-scene.json` | 场景、集合、9 类图元中的 5 类、材质、相机、灯光、父子关系、保存 `.blend` | `scene-run` 全部检查 pass |
| `demo-modify.json` | `base_blend` 追加、复用已有相机 | `scene-run` pass，对象数为下限检查 |
| `demo-geometry-nodes.json` | 噪声位移、实例散布、材质输入、GN 参数 | `scene-run` pass，2 个 NODES 修改器 |
| `demo-animation.json` | 多帧 MP4、无动画 | `scene-run` pass，时长 1 秒 |
| `demo-animation-scene.json` | 变换/灯光/相机关键帧、3 秒 MP4 | `scene-run` pass，≥13 条 F-Curve |
| `demo-text-curve.json` | `TEXT`、`CURVE`、`ORTHO` 相机；4 个文字、3 条曲线 | `scene-run` pass，文字/曲线/相机专项检查通过 |
| `demo-materials.json` | 7 个材质预设、Coat、程序化 Bump、简化车形体 | `scene-run` pass，`scene.materials` 7 项全部回读一致 |
| `demo-scientific.json` | 点属性、科学着色、ORTHO 相机 | `scene-run` pass，`scene.attributes` 与 `scene.materials` 通过 |
| `demo-surface.json` | 参数化曲面、表达式属性、viridis 着色 | `scene-run` pass，`scene.surfaces` 通过 |
| `invalid-*.json` | 重复 ID、非法集合根、无相机、越界输出、非法图元、未知材质、空文字、文字带图元、曲线点数不足、曲线倒角为 0、非法投影方式 | `scene-validate` 与 Blender 均拒绝 |

## 课程 YAML 与 JSON 的关系

`lesson.yaml` / `storyboard.yaml` 是课程级作者格式，由 `CourseControl`（R4）解析。Blender 入口只接收解析后的 JSON 任务，Blender 内置 Python 不依赖 PyYAML。R2 阶段先用 JSON 任务验证渲染能力；R4 再把 storyboard 解析成同样的 JSON。

## Blender 5.2 注意事项

- 视频输出必须先设置 `image_settings.media_type = "VIDEO"`，再设置 `file_format = "FFMPEG"`；直接设 `FFMPEG` 会报 `TypeError`。
- Blender 内置 Python 3.13 没有 PyYAML，任务文件因此使用 JSON。
- `RenderSettings.engine` 的枚举列表可能只显示 `BLENDER_EEVEE`，但 `CYCLES` / `BLENDER_WORKBENCH` 赋值仍可用；不要用枚举判断能力。
- `world.use_nodes` 在 5.2 有弃用警告（计划 6.0 移除）；当前保留，不在 R2 引入兼容层。
- EEVEE 在 1080p、8 samples 下约 `0.2 秒/帧`；Cycles CPU 约 `5.6 秒/帧`，默认只用于显式选择的终版渲染。
- 5.2 的 Geometry Nodes 修改器输入不再通过 ID 属性访问，而是 `modifier.properties.inputs.<identifier>.value`；接口 identifier 从节点组 Interface 读取，不能写死 `Socket_1`。
- 5.2 的 Action 默认是 layered Action，`action.fcurves` 不存在；需通过 `action.layers → strips → channelbag(slot) → fcurves` 读取。
- 保存 GN 资产库前必须给节点组设置 `use_fake_user = True`（并 `asset_mark()`），否则无用户的节点组不会写入 `.blend`。
