# Blender 场景任务 IR v2

> 适用版本：Blender 5.2.3 LTS / CourseControl 0.1.0
> 契约实现：`CourseControl/src/course_control/blender_scene.py`（外部 Pydantic）与 `BlenderStudio/scripts/scene_system/task_schema.py`（Blender 内置 Python，无第三方依赖）
> JSON Schema：[shared/schemas/blender-scene-task.schema.json](../shared/schemas/blender-scene-task.schema.json)

任务 IR v2 是 AI / 编排层与 Blender 执行层之间的唯一结构化接口。AI 只产出 JSON，Blender 只执行白名单字段；不执行任意 Python 代码。

## 1. 执行链路

```text
task.json
   │
   ├─ course-control scene-validate    Pydantic 校验（外部）
   │
   ├─ course-control scene-run         校验 + PowerShell 包装 + Blender 执行 + 验收 + manifest
   │
   └─ scripts/blender-render.ps1       底层入口（超时、日志、输出路径约束）
          │
          ▼
      Blender 5.2 --background --python render_shot.py
          │
          ├─ scene_system.task_schema     二次校验（Blender 内置 Python）
          ├─ scene_system.scene           场景、集合、单位、时间轴、保存
          ├─ scene_system.objects         数据级几何 + 变换 + 父子关系
          ├─ scene_system.materials       Shader Nodes 模板
          ├─ scene_system.cameras         相机、朝向、景深
          ├─ scene_system.lighting        灯光
          ├─ scene_system.geometry_nodes  资产注册表 + 修改器参数
          ├─ scene_system.animation       关键帧与插值
          └─ scene_system.rendering       渲染配置与输出
```

`render_shot.py` 根据 `schema_version` 分派：`1` 走旧的单场景脚本，`2` 走 `scene_system` 执行器。旧任务不受影响。

## 2. 顶层字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `schema_version` | 是 | 固定 `2` |
| `task_id` | 是 | `^[A-Za-z][A-Za-z0-9_.-]{0,63}$`，用于日志与 manifest 命名 |
| `lesson` | 是 | 课程 slug，同时决定输出根目录 `build/<lesson>/blender/` |
| `operation` | 否 | 固定 `build_scene`，默认值即此 |
| `scene` | 否 | 场景名、单位、帧率、帧范围、随机种子 |
| `collections` | 否 | 额外集合路径；标准集合总会创建 |
| `world` | 否 | 世界背景颜色与强度 |
| `materials` | 否 | 材质模板列表 |
| `objects` | 否 | Mesh / Empty 列表 |
| `cameras` | 否 | 相机列表；无 `base_blend` 时至少一台，且最多一台 `active` |
| `lights` | 否 | 灯光列表 |
| `animations` | 否 | 关键帧动画列表 |
| `base_blend` | 否 | 以已有 `.blend` 为起点追加内容；必须在工作区内，扩展名为 `.blend`。契约校验只检查路径；文件是否已生成由执行阶段检查 |
| `render` | 是 | 渲染与输出配置 |

标准集合固定为：

```text
ENVIRONMENT/{Background,Ground,Lighting}
ASSETS/{Geometry,Imported,Procedural}
ANIMATION/{Objects,Cameras,Effects}
MATERIALS
OUTPUT
```

对象的 `collection` 必须以 `ENVIRONMENT`、`ASSETS`、`ANIMATION`、`MATERIALS`、`OUTPUT` 之一开头；不允许 AI 自造根集合。

## 3. scene / world

```json
"scene": {
  "name": "Scene_Demo",
  "units": "METRIC",
  "unit_scale": 1.0,
  "fps": 30,
  "frame_start": 1,
  "frame_end": 90,
  "seed": 7
},
"world": {
  "background_color": [0.035, 0.04, 0.05, 1.0],
  "strength": 0.6
}
```

- `units`：`METRIC` / `IMPERIAL` / `NONE`。
- `seed` 会写入 `random.seed()`，并记录到场景自定义属性与 manifest。依赖随机数的资产必须使用它。
- 内部时间单位统一为帧；秒与帧的换算只发生在入口层。

## 4. materials

材质分两种 shader，`shader` 必填，参数白名单外一律拒绝。

```json
{
  "id": "mat.cube",
  "shader": "principled",
  "params": {
    "base_color": [0.85, 0.32, 0.08, 1.0],
    "metallic": 0.1,
    "roughness": 0.35,
    "alpha": 1.0,
    "ior": 1.45,
    "emission_color": [0.0, 0.0, 0.0, 1.0],
    "emission_strength": 0.0
  }
}
```

| shader | 参数 | 范围 / 默认 |
| --- | --- | --- |
| `principled` | `base_color` | RGBA，`[0,1]`，默认 `[0.8,0.8,0.8,1]` |
| | `metallic` / `roughness` / `alpha` | `[0,1]`，默认 `0 / 0.5 / 1` |
| | `ior` | `[1,3]`，默认 `1.45` |
| | `emission_color` / `emission_strength` | RGBA / `[0,1e5]`，默认全黑 / `0` |
| `emission` | `color` | RGBA，默认白 |
| | `strength` | `[0,1e5]`，默认 `1` |

`alpha < 1` 时自动切换到混合渲染模式。节点输入按名称查找，不按索引硬编码。

## 5. objects

```json
{
  "id": "prop.cube",
  "type": "MESH",
  "primitive": "CUBE",
  "params": { "size": 1.6 },
  "transform": {
    "location": [-1.2, 0, 0.8],
    "rotation": [0, 0, 25],
    "scale": [1, 1, 1]
  },
  "material": "mat.cube",
  "collection": "ASSETS/Geometry",
  "smooth": false,
  "parent": null,
  "geometry_nodes": [
    { "asset": "gn.displace_noise", "params": { "Strength": 0.1 } }
  ]
}
```

- `type`：`MESH` / `EMPTY` / `TEXT` / `CURVE`。相机与灯光走独立数组，不放进 `objects`。
- `primitive`、`params`、`geometry_nodes`、`smooth` 只适用于 `MESH`；`text` / `curve` 只适用于对应类型（见 §5.1.1）。
- `material` 适用于 `MESH` / `TEXT` / `CURVE`，不适用于 `EMPTY`。
- `rotation` 单位为**度**，内部转换为弧度；`scale` 必须全部大于 0。
- `transform` 是世界空间变换。设置 `parent` 时保留世界变换（通过 `matrix_parent_inverse`）。
- 对象名使用 `id`；与 `base_blend` 中已有对象重名会直接失败，避免静默改名。
- 对象数据通过 `bmesh` 数据级 API 创建，不依赖 `bpy.ops` 上下文。

### 5.1 图元与参数

| primitive | 参数（默认值） |
| --- | --- |
| `CUBE` | `size`（2.0） |
| `PLANE` | `size`（2.0） |
| `GRID` | `size`（2.0）、`x_segments`（10）、`y_segments`（10） |
| `UV_SPHERE` | `radius`（1.0）、`u_segments`（32）、`v_segments`（16） |
| `ICO_SPHERE` | `radius`（1.0）、`subdivisions`（2，范围 1–6） |
| `CYLINDER` | `radius`（1.0）、`depth`（2.0）、`vertices`（32） |
| `CONE` | `radius1`（1.0）、`radius2`（0.0）、`depth`（2.0）、`vertices`（32） |
| `TORUS` | `major_radius`（1.0）、`minor_radius`（0.25）、`major_segments`（48）、`minor_segments`（12） |
| `CIRCLE` | `radius`（1.0）、`vertices`（32）、`fill`（true） |

所有分段数上限 512；场景对象上限 1000，场景条目总数上限 2000。

### 5.1.1 TEXT 与 CURVE

`TEXT` 使用 `text` 对象；`CURVE` 使用 `curve` 对象。两者互斥，且不能与 `primitive` / `params` / `geometry_nodes` / `smooth` 同时出现。

```json
{
  "id": "label.formula",
  "type": "TEXT",
  "text": {
    "body": "sin(x) = 0.5",
    "size": 0.34,
    "align_x": "LEFT",
    "align_y": "CENTER"
  },
  "transform": { "location": [0, 0, 1.5], "rotation": [90, 0, 0] },
  "material": "mat.label"
}
```

```json
{
  "id": "path.parabola",
  "type": "CURVE",
  "curve": {
    "points": [[-2.4, 0, 0.35], [0, 0, 1.0], [2.4, 0, 0.35]],
    "bevel_depth": 0.03
  },
  "material": "mat.curve"
}
```

`text` 字段：

| 字段 | 默认 | 范围 |
| --- | --- | --- |
| `body` | 必填 | 1–512 字符；不能全为空白 |
| `size` | 0.5 | 0.001–1000 |
| `align_x` | `LEFT` | `LEFT` / `CENTER` / `RIGHT` |
| `align_y` | `BOTTOM` | `TOP` / `CENTER` / `BOTTOM` |
| `extrude` | 0.0 | 0–100 |
| `bevel_depth` | 0.0 | 0–100 |
| `space_line` | 1.0 | 0.1–10 |

- 使用 Blender 内置字体（Bfont），不加载外部字体文件，不引入字体资产。
- 首期承诺范围：数字、英文、数学符号。中文说明默认由 Remotion 承担（见 [评估文档 §4](评估-PBR与科学可视化接入.md)）；即便内置字体可渲染中文，也不把中文排版责任放进 Blender。
- 文本对象在 Blender 中的对象类型为 `FONT`；材质槽可用。

`curve` 字段：

| 字段 | 默认 | 范围 |
| --- | --- | --- |
| `points` | 必填 | 2–4096 个 `[x, y, z]`；分量绝对值 ≤ 1e6；不能全部重合 |
| `bevel_depth` | 0.02 | 0.0001–1000；必须大于 0，否则曲线不可见 |
| `cyclic` | false | 布尔值 |

- 曲线为 3D `POLY` 样条，执行时统一 `bevel_resolution = 3` 并封盖。
- 曲线点坐标是对象局部坐标，随后叠加 `transform`。

### 5.2 Geometry Nodes

```json
"geometry_nodes": [
  { "asset": "gn.scatter_cubes", "params": { "Density": 550, "Scale": 0.32, "Material": "mat.glow" } }
]
```

- 只能用于 `MESH`，每个对象最多 8 个修改器，按数组顺序叠加。
- `asset` 必须在 `BlenderStudio/assets/geometry_nodes/registry.json` 中登记。
- 参数按**节点组 Interface 的 Socket 名称**写入；执行时从 interface 读取 identifier，不依赖 `Socket_1` 之类的编号。
- 注册表声明参数类型与范围；未知参数、越界值、缺失必填参数都会失败。
- 类型 `material` 的参数填写材质 `id`，执行器解析为 Blender Material 数据块。

当前资产：

| asset | 输入 | 说明 |
| --- | --- | --- |
| `gn.displace_noise` | `Scale`、`Strength`、`Seed` | 4D 噪声位移 |
| `gn.scatter_cubes` | `Density`、`Scale`、`Seed`、`Material`（可选） | 面分布 + 立方体实例 + 材质 |

## 6. cameras

```json
{
  "id": "cam.main",
  "location": [7.0, -7.0, 5.0],
  "target": [0, 0, 1.0],
  "focal_length": 50.0,
  "sensor_width": 36.0,
  "projection": "PERSPECTIVE",
  "ortho_scale": 6.0,
  "active": true,
  "dof": { "enabled": true, "focus_distance": 10.0, "f_stop": 4.0 }
}
```

- `projection`：`PERSPECTIVE`（默认）/ `ORTHO`。`ORTHO` 时忽略 `focal_length`，使用 `ortho_scale`。
- `ortho_scale`：0.001–100000，默认 6.0；仅 `ORTHO` 生效。场景报告会回读实际投影方式与 `ortho_scale`。
- `rotation`（度）与 `target` 二选一，必须且只能提供一个。
- `active` 最多一个为 true；`base_blend` 模式可复用已有活动相机。
- 默认集合 `ANIMATION/Cameras`。

## 7. lights

```json
{
  "id": "light.key",
  "type": "AREA",
  "location": [4.0, -4.0, 6.0],
  "target": [0, 0, 1.0],
  "energy": 900.0,
  "size": 4.0,
  "shape": "SQUARE",
  "color": [1.0, 0.96, 0.9]
}
```

| type | 关键字段 |
| --- | --- |
| `AREA` | `energy`、`size`、`size_y`（RECTANGLE）、`shape` |
| `POINT` | `energy`、`size`（软阴影半径） |
| `SPOT` | `energy`、`spot_size`（度）、`spot_blend`、`size` |
| `SUN` | `energy`、`size`（角度制视角直径） |

- `rotation` 与 `target` 二选一。
- 默认集合 `ENVIRONMENT/Lighting`。

## 8. animations

```json
{
  "target": "prop.cube",
  "channels": [
    {
      "property": "rotation",
      "keyframes": [
        { "frame": 1, "value": [0, 0, 25], "interpolation": "LINEAR" },
        { "frame": 90, "value": [0, 360, 25], "interpolation": "LINEAR" }
      ]
    }
  ]
}
```

| property | 适用目标 | 值 |
| --- | --- | --- |
| `location` / `rotation` / `scale` | 对象、相机、灯光 | `[x,y,z]`，rotation 为度 |
| `focal_length` | 相机 | 标量 |
| `energy` | 灯光 | 标量 |

规则：

- 每个通道至少 2 个关键帧，帧号严格递增，且必须落在 `scene.frame_start..frame_end`。
- 插值：`CONSTANT` / `LINEAR` / `BEZIER`（默认）。
- 同一目标同一属性只能定义一次。
- 灯光的 `energy` 与相机的 `focal_length` 关键帧写在数据块上（Blender 5.2 layered Action），验收报告会读取对应 F-Curve。

## 9. render

```json
"render": {
  "engine": "BLENDER_EEVEE",
  "resolution": [1280, 720],
  "fps": 30,
  "samples": 32,
  "format": "png",
  "frame": 1,
  "output": "build/blender-scene-acceptance/blender/scene.png",
  "save_blend": "build/blender-scene-acceptance/blender/scene.blend",
  "view_transform": "AgX",
  "film_transparent": false
}
```

- `engine`：`BLENDER_EEVEE`（5.2 标识）、`BLENDER_EEVEE_NEXT`（别名）、`CYCLES`、`BLENDER_WORKBENCH`。
- `resolution` 每边 1–8192。
- `format`：`png`（渲染 `frame` 单帧）或 `mp4`（渲染完整帧范围）。
- `output` 与 `save_blend` 必须位于 `build/<lesson>/blender/` 内；禁止绝对路径、反斜杠与 `..`。
- `save_blend` 在渲染前写入，渲染失败也能保留现场。
- `view_transform` / `look` 直接映射到 Blender 色彩管理；未知值会失败并保留日志。

## 10. 校验、执行与产物

```powershell
# 只校验（Pydantic，不启动 Blender）
uv run --project CourseControl course-control scene-validate `
  --task BlenderStudio/tasks/scene-system/demo-scene.json

# 完整执行：校验 → Blender → 输出检查 → 场景验收 → manifest
uv run --project CourseControl course-control scene-run `
  --task BlenderStudio/tasks/scene-system/demo-scene.json

# 导出/更新 JSON Schema
uv run --project CourseControl course-control scene-schema
```

`scene-run` 写入：

```text
build/<lesson>/
├── blender/
│   ├── <output>.png | <output>.mp4
│   ├── <scene>.blend
│   └── manifests/
│       ├── <task_id>.json          # 执行 + 验收清单
│       └── <task_id>-scene.json    # 场景验收报告
└── logs/
    ├── scene-run-<task_id>.log
    ├── verify-<task_id>.log
    └── blender-<task-file>.log
```

manifest 记录：任务哈希、随机种子、Blender 版本、宿主 Python/平台、渲染参数、退出码、耗时、输出检查、场景检查。用于配置级与执行级复现；不承诺跨 GPU/驱动的逐像素一致。

验收检查：

| 检查 | 内容 |
| --- | --- |
| `execute.exit` | 包装器退出码 |
| `output.exists` / `size` / `resolution` | 输出存在、大小、分辨率 |
| `output.black_frame` | PNG 平均亮度，透明背景跳过 |
| `output.probe` / `duration` | MP4 编码、分辨率、时长为 `帧数 / fps` |
| `scene.report` | 场景问题列表为空 |
| `scene.active_camera` | 存在活动相机 |
| `scene.object_count` | 对象数量与任务一致（`base_blend` 模式为下限） |
| `scene.text_objects` | 每个声明的 `TEXT` 都存在，且 `body` 与任务一致 |
| `scene.curves` | 每个声明的 `CURVE` 都存在，且点数、`cyclic`、`bevel_depth` 与任务一致 |
| `scene.cameras` | 声明的相机存在，投影方式与 `ortho_scale` 与任务一致 |
| `scene.geometry_nodes` | GN 修改器数量 |
| `scene.animation` | F-Curve 数量 |

## 11. AI 生成约定

给 LLM 的输入应包含：

1. `shared/schemas/blender-scene-task.schema.json`；
2. 几何节点注册表 `BlenderStudio/assets/geometry_nodes/registry.json`；
3. 目标课程 slug 与输出文件名；
4. 明确的视觉需求（对象、构图、灯位、镜头运动、时长）。

输出约束：

- 只输出一个 JSON 对象，`schema_version` 固定 `2`；
- 不输出 Python、不输出 `bpy` 调用、不输出脚本路径；
- 对象、材质、相机、灯光、动画目标的 `id` 必须自洽；
- `TEXT` 只填 `text` 白名单字段，不填字体路径；中文说明默认不放进三维场景；
- 不确定的参数使用保守默认值，不编造注册表之外的 GN 资产。

校验失败时，把 `scene-validate` 的错误列表原样反馈给模型，并要求只修改对应字段。自动修复最多 2–3 轮，不做无限重试。
