# AI-Blender 落地路线图

> 起始日期：2026-11-03
> 技术基线：[AI + Blender 自动化三维内容生产技术方案](AI-Blender自动化三维内容生产技术方案.md)
> 任务契约：[Blender 场景任务 IR v2](../Blender场景任务IR-v2.md)
> 状态口径：`PASS_VERIFIED` / `PASS_STATIC` / `PARTIAL` / `NOT_RUN`。只有真实 Blender 执行并验证产物才算 `PASS_VERIFIED`。

## 1. 方案与仓库的映射

方案中的 `ai-blender-system/` 是逻辑结构，不另起一套平行工程。落地时复用现有工作区分层：

| 方案层 | 仓库位置 | 说明 |
| --- | --- | --- |
| 任务描述层 | `shared/schemas/blender-scene-task.schema.json`、`CourseControl/src/course_control/blender_scene.py` | JSON Schema + Pydantic |
| 编排控制层 | `CourseControl/` | 已有课程调度；新增 `scene-validate` / `scene-run` |
| Blender CLI | `scripts/blender-render.ps1` | 超时、日志、路径约束、退出码 |
| bpy 执行器 | `BlenderStudio/scripts/scene_system/` | scene / objects / materials / cameras / lighting / GN / animation / rendering |
| Geometry Nodes 资产 | `BlenderStudio/assets/geometry_nodes/` | `gn_library.blend` + `registry.json` + 构建脚本 |
| 渲染与输出 | `build/<lesson>/blender/` | PNG / MP4 / `.blend` |
| 质量验证 | `BlenderStudio/scripts/verify_scene.py`、`CourseControl/src/course_control/blender_runner.py` | 场景报告 + 图像/视频检查 + manifest |
| 任务记录 | `build/<lesson>/blender/manifests/`、`build/<lesson>/logs/` | 哈希、版本、种子、退出码、耗时 |
| 课程级合成 | `RemotionStudio/`、`CourseControl` | 沿用既有 R5 管道 |
| AI 层 | `ModelingStudio/` | Qwen3-VL 视觉分析、Qwen3 规划、Qwen3-Coder 脚本；独立建模工作流，不参与课程闭环 |

现有课程生产闭环（`lessons/` → `build/` → Remotion）不变。三维任务系统是 `BlenderStudio` 的能力扩展，也可以脱离课程单独使用。

## 2. 阶段状态

| 阶段 | 建设内容 | 状态 | 证据 |
| --- | --- | --- | --- |
| P0 | Blender CLI + bpy | `PASS_VERIFIED` | R2 既有冒烟；v2 任务经 `blender-render.ps1` 执行，退出码与日志正确 |
| P1 | 场景管理和数据接口 | `PASS_VERIFIED` | `demo-scene.json` 创建 6 对象 / 10 场景项，保存并重载；`demo-modify.json` 基于 `scene.blend` 追加对象 |
| P2 | Geometry Nodes 资产系统 | `PASS_VERIFIED` | 2 个可复用节点组；接口检查；参数写入；求值后圆环 131,768 顶点；`scene-run` 报告 2 个 NODES 修改器 |
| P3 | 材质、灯光、相机 | `PASS_VERIFIED` | Principled / Emission 材质、3 灯、1 相机、AgX；渲染图人工检查通过 |
| P4 | 动画时间轴 | `PASS_VERIFIED` | 90 帧 MP4、13 条 F-Curve、首末帧画面差异明显；灯光能量与相机位移动画均生效 |
| P5 | AI 任务接口 | `PARTIAL` | Schema + Pydantic + 双端校验一致已验证；`ModelingStudio` 已用本地模型跑通视觉分析/规划/脚本三阶段；场景 IR v2 的 LLM 直接生成仍未接入 |
| P6 | 资源和外部数据 | `NOT_RUN` | 尚未实现模型导入与资产清理 |
| P7 | 渲染与媒体合成 | `PARTIAL` | Blender PNG / MP4 已验证；PNG 序列 + FFmpeg 独立合成未实现；课程级 Remotion 合成沿用 R5 |
| P8 | 质量验证 | `PASS_VERIFIED` | 场景报告、PNG 黑帧检查、MP4 时长/分辨率检查、manifest 写入均实际运行；运行期失败会写 `status=fail` manifest 并保留 `TASK_ERROR` |
| P9 | 服务化扩展 | `PARTIAL` | 单任务 CLI runner 可用；无队列、并发控制、GUI RPC |

## 3. 已实现能力

### 3.1 任务契约

- `schema_version: 2`，字段白名单，未知字段拒绝。
- 外部 Pydantic 与 Blender 内置 Python 两套校验；测试覆盖两者对全部夹具的一致结论。
- JSON Schema 由 Pydantic 导出，测试保证与模型同步。
- 路径约束：输出与 `.blend` 必须位于 `build/<lesson>/blender/`；拒绝绝对路径、反斜杠、`..`。

### 3.2 场景生产

- 固定集合层级：`ENVIRONMENT` / `ASSETS` / `ANIMATION` / `MATERIALS` / `OUTPUT`。
- 数据级建模：`bmesh` 创建 9 类图元，不依赖 `bpy.ops` 上下文。
- 世界变换、父子关系（保留世界变换）、单位、帧率、帧范围。
- `base_blend` 追加模式：打开已有场景、创建新对象、另存新文件，不覆盖原文件。

### 3.3 材质 / 相机 / 灯光

- Principled 与 Emission 模板；按节点输入名称写入，不按索引。
- 相机 look-at、焦距、传感器宽度、景深；最多一个活动相机。
- Area / Point / Spot / Sun 四类灯光；target 或欧拉角二选一。
- 世界背景颜色/强度与色彩管理。

### 3.4 Geometry Nodes

- 资产库 `gn_library.blend`（`GN_DisplaceNoise`、`GN_ScatterCubes`）。
- 注册表声明资产版本、节点组名、输入类型/范围/默认值。
- 执行时检查节点组 Interface：缺失或类型不匹配直接失败。
- Blender 5.2 修改器输入 API：`modifier.properties.inputs.<identifier>.value`。
- 实例材质通过节点组 `Material` 输入传入，避免实例回落为默认白材质。

### 3.5 动画

- 对象 / 相机 / 灯光的变换关键帧。
- 相机 `focal_length`、灯光 `energy` 的标量关键帧。
- `CONSTANT` / `LINEAR` / `BEZIER` 逐关键帧插值。
- 兼容 Blender 5.2 layered Action：F-Curve 通过 `action.layers -> strips -> channelbag -> fcurves` 读取。

### 3.6 验收与复现

- 场景报告：对象、集合、顶点/面、材质、相机、灯光、动画、缺失资源。
- 输出检查：PNG 分辨率/大小/平均亮度；MP4 编码/分辨率/时长。
- manifest：任务哈希、种子、Blender 版本、宿主环境、渲染参数、退出码、耗时、检查结果。
- 失败任务保留日志、场景文件与报告；不自动删除现场。

### 3.7 本地自动建模（独立扩展）

`ModelingStudio` 在 8080 服务上串行调用 Qwen3-VL、Qwen3、Qwen3-Coder，完成图片分析 → 规划 → 脚本 → Blender → 验收 → 视觉修正建议。它独立于课程闭环与场景 IR v2，契约与实测见 [本地自动建模工作流](../AI-Blender本地建模工作流.md)。

## 4. 已验证的入口

```powershell
# 契约校验
uv run --project CourseControl course-control scene-validate `
  --task BlenderStudio/tasks/scene-system/demo-scene.json

# 执行 + 验收
uv run --project CourseControl course-control scene-run `
  --task BlenderStudio/tasks/scene-system/demo-scene.json

# 仅底层渲染
.\scripts\blender-render.ps1 -Lesson blender-scene-acceptance `
  -Task BlenderStudio/tasks/scene-system/demo-animation-scene.json

# 单独打开 .blend 做场景验收
& "<BLENDER_EXE>" --background --factory-startup --python-exit-code 1 `
  --python BlenderStudio/scripts/verify_scene.py -- `
  --blend build/blender-scene-acceptance/blender/scene.blend --strict

# 重建 Geometry Nodes 资产库
& "<BLENDER_EXE>" --background --factory-startup --python-exit-code 1 `
  --python BlenderStudio/assets/geometry_nodes/build_assets.py

# 场景系统契约检查（不渲染）
.\scripts\check-scene-system.ps1

# 场景系统完整验收（含 4 次真实渲染）
.\scripts\check-scene-system.ps1 -Render

# 契约与双端一致性测试
cd CourseControl
uv run python -m unittest discover -s tests -v
```

## 5. 已知边界

- **不是像素级复现**：manifest 记录配置与执行环境，但不同 GPU/驱动/渲染后端可能产生不同像素。工程目标是配置可复现与执行可复现。
- **Blender 5.2 专有 API**：修改器输入、layered Action、`media_type = VIDEO` 等行为与 4.x 不同；升级 Blender 前必须跑验收集。
- **GN 资产需要 fake user**：保存 `gn_library.blend` 前调用 `use_fake_user` 与 `asset_mark`，否则无用户的节点组不会写入文件。
- **执行器只接受白名单字段**：不支持通过任务注入任意 Python。复杂脚本模式需要单独设计受控入口。
- **`base_blend` 允许追加，不允许重名覆盖**：避免静默改名；需要修改已有对象时，后续增加显式 `update` 操作。
- **课程闭环未改变**：`course-control build` 仍走原有 R0–R5 流程；v2 任务目前通过 `scene-run` 或 `blender-render.ps1` 单独执行。

## 6. 下一阶段建议

按依赖顺序：

1. **P6 资产导入**：`imports` 字段（GLB/FBX/OBJ/STL/PLY），路径白名单，尺寸/坐标/法线/材质/UV/拓扑检查；用真实 GLB 夹具验收。
2. **P7 图像序列 + FFmpeg**：`format: "png_sequence"`，帧序列落盘，外部 FFmpeg 合成音频/字幕/转场，Blender 不再直接产出最终 MP4。
3. **P5 LLM 生成层**：`ModelingStudio` 已完成图片→视觉分析→规划→脚本链路；下一步把 LLM 输出接到场景 IR v2，复用 `scene-validate` 错误回灌与最多 2–3 轮修复。
4. **P8 扩展检查**：画面构图/遮挡/光照的视觉检查；OpenEXR 支持；跨任务资产哈希。
5. **P9 服务化**：任务队列、单机并发上限、失败重试策略、GUI RPC（`bpy.app.timers` 主线程调度）。
6. **P2 资产扩容**：曲线系统、属性传递、变形、实例分布；每个资产补接口契约与验收任务。
