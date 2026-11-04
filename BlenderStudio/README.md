# BlenderStudio

3D 场景与渲染工程。负责 Blender 场景构建、Geometry Nodes 资产、场景级验收与渲染；课程级编排、调度与最终验收仍属于 `CourseControl/`。

## 边界

- 读取：`BlenderStudio/tasks/`、`BlenderStudio/scenes/`、`BlenderStudio/assets/`、`config/tools.yaml`。
- 写入：只写 `build/<lesson>/blender/` 与 `build/<lesson>/logs/`。
- 不写入 `CourseSlides/`、`MotionStudio/`、`ManimSandbox/`、`RemotionStudio/`。
- 不在 Blender 内置 Python 中安装第三方包。
- 任务文件只包含数据字段，不包含可执行代码。

## 环境

- Blender `5.2.3 LTS`（实际验收版本，运行日志会记录）。
- 可执行文件：`<BLENDER_EXE>`，实际路径写入本地 `config/tools.yaml`（已忽略）。`scripts/setup.ps1` 可从 `config/tools.example.yaml` 生成。
- 不使用 `blender-launcher.exe`；它是 GUI 启动器，不接受后台渲染参数。
- 默认引擎 `BLENDER_EEVEE`；`CYCLES` 与 `BLENDER_WORKBENCH` 可作为任务级显式选择。

## 入口

工作区级入口是 `scripts/blender-render.ps1`：

```powershell
# 5 秒冒烟视频：build/<lesson>/blender/smoke.mp4
.\scripts\blender-render.ps1 -Lesson 01-shell-for-ai-era -Smoke

# JSON 任务
.\scripts\blender-render.ps1 -Lesson 01-shell-for-ai-era -Task BlenderStudio/tasks/01-shell-for-ai-era/still.json

# 显式覆盖引擎
.\scripts\blender-render.ps1 -Lesson 01-shell-for-ai-era -Task BlenderStudio/tasks/01-shell-for-ai-era/still.json -Engine CYCLES
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
| `geometry.py` | `bmesh` 数据级图元、`TEXT`、`CURVE` |
| `objects.py` | 对象（MESH/EMPTY/TEXT/CURVE）、变换、材质槽、父子关系 |
| `materials.py` | Principled / Emission 节点模板 |
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

```powershell
& "<BLENDER_EXE>" --background --factory-startup --python-exit-code 1 `
  --python BlenderStudio/assets/geometry_nodes/build_assets.py
```

## JSON 任务（schema_version 1，兼容保留）

```json
{
  "schema_version": 1,
  "lesson": "01-shell-for-ai-era",
  "scene": "procedural_cube",
  "engine": "BLENDER_EEVEE",
  "resolution": [1920, 1080],
  "fps": 30,
  "frames": 1,
  "samples": 16,
  "format": "png",
  "output": "build/01-shell-for-ai-era/blender/still.png",
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

`tasks/01-shell-for-ai-era/` 下的样本：

| 任务 | 预期结果 |
| --- | --- |
| `still.json` | 退出码 0，PNG 1920×1080 |
| `cycles-still.json` | 退出码 0，PNG 1920×1080（Cycles） |
| `中文 任务.json` | 退出码 0，中文 + 空格路径 |
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
