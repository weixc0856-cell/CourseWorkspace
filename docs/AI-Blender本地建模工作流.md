# AI + Blender 本地自动化建模工作流

> 归档日期：2026-11-03
> 状态：已落地（阶段 1–5 实测通过，阶段 6 输出建议、人工确认后再重建）
> 关联：[PRD](PRD.md) · [架构](ARCHITECTURE.md) · [Blender 场景任务 IR v2](Blender场景任务IR-v2.md) · 历史技术方案（本地归档：`<内容根>/archive/legacy/AI-Blender自动化三维内容生产技术方案.md`，不入库）

## 0. 定位

在现有本地模型服务（`<AI_ROOT>`，llama.cpp，8080）之上，建立一条从单张图片到可编辑 Blender 模型的自动化链路：

```text
Qwen3-VL 图片理解
  → Qwen3 建模规划
  → Qwen3-Coder 生成 bpy 脚本
  → Blender 独立进程执行
  → 自动检查与预览渲染
  → （可选）Qwen3-VL 对照原图给出修正建议
```

不引入 TRELLIS.2、Hunyuan3D 或任何新的图生 3D 大模型；不新增推理服务，继续使用 8080 单实例契约。模型按阶段顺序启动、调用、停止，不同时运行。

## 1. 模型与上下文

本机实际可用模型（见 `<AI_ROOT>\README.md`）：

| 阶段 | 模型 | 文件 | 建议上下文 |
| --- | --- | --- | --- |
| 图片理解 | Qwen3-VL-30B-A3B | `Qwen3VL-30B-A3B-Instruct-Q4_K_M.gguf` + `mmproj-Qwen3VL-30B-A3B-Instruct-F16.gguf` | 日常 16K；复杂多图 32K；64K 不作为默认 |
| 建模规划 | Qwen3-30B-A3B | `Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf` | 32K–64K |
| 脚本生成 | Qwen3-Coder-30B-A3B | `Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf` | 32K–64K |

约束：

1. 模型卡上的理论上下文不等于本机可用上下文；以启动参数与实测为准。
2. VL 每次只提交当前任务需要的图片，不重复携带完整历史对话。
3. 图片分析结果落盘为 JSON；后续文本模型只读 JSON，不再读图。
4. 需要重新看图时，单独发起一次视觉任务。
5. VL 启动必须带 `--mmproj ... --no-mmproj-offload`，视觉塔放 CPU；否则 A750 8 GB 显存会在图片请求时崩溃。
6. 8080 同一时间只允许一个实例；谁启动谁停止，空闲时端口必须释放。

## 2. 阶段接口

| 阶段 | 输入 | 输出 |
| --- | --- | --- |
| 图片理解 | 图片 + 分析要求 | `visual_analysis.json` |
| 建模规划 | 视觉分析 JSON + 用户补充尺寸/约束 | `model_plan.json` |
| 脚本生成 | 建模计划 + Blender API 约束 | `build_model.py` |
| Blender 执行 | Python 脚本（受控） | `model.blend`、`model.glb`、`preview.png`、`scene_report.json` |
| 质量检查 | 场景报告 + 预览图 + 产物 | `validation.json` |
| 视觉反馈（可选） | 原图 + 预览图 | `revision.json`（建议，不自动重建） |

JSON 是系统间的正式接口，不是聊天记录。

### 2.1 视觉分析示例

```json
{
  "schema_version": 1,
  "object": "mechanical_assembly",
  "summary": "A vertical shaft mounted on a rectangular base with a side bracket.",
  "parts": [
    { "name": "base", "geometry": "cuboid", "confidence": 0.95, "visible": true, "appearance": "matte dark gray" },
    { "name": "shaft", "geometry": "cylinder", "confidence": 0.91, "visible": true, "appearance": "brushed silver metal" },
    { "name": "bracket", "geometry": "custom_mesh", "confidence": 0.72, "visible": true, "appearance": "painted gray metal" }
  ],
  "spatial_relations": [
    "shaft mounted vertically on base",
    "bracket connected to shaft"
  ],
  "materials": [
    { "name": "painted_steel", "color": "gray", "finish": "matte", "confidence": 0.8 }
  ],
  "unknowns": ["exact dimensions", "rear side geometry"]
}
```

模型不能从没有尺寸参照的单张照片得到真实尺寸。尺寸必须由规划阶段以假设形式补齐，并在 `assumptions` 中显式记录。

### 2.2 建模计划

```json
{
  "schema_version": 1,
  "object_name": "mechanical_assembly",
  "units": "METRIC",
  "coordinate_system": "Z_UP",
  "assumptions": [
    "base is 0.30 m wide, 0.20 m deep, 0.04 m thick",
    "shaft diameter is 0.03 m"
  ],
  "parts": [
    {
      "id": "base",
      "name": "base",
      "geometry": "cuboid",
      "size": [0.30, 0.20, 0.04],
      "location": [0.0, 0.0, 0.02],
      "rotation": [0.0, 0.0, 0.0],
      "material_id": "steel",
      "operations": [],
      "confidence": 0.9
    }
  ],
  "materials": [
    {
      "id": "steel",
      "base_color": [0.45, 0.47, 0.5, 1.0],
      "metallic": 0.6,
      "roughness": 0.45
    }
  ],
  "camera": {
    "location": [0.6, -0.6, 0.45],
    "target": [0.0, 0.0, 0.12],
    "focal_length": 50.0
  },
  "lights": [
    {
      "type": "AREA",
      "location": [0.5, -0.4, 0.8],
      "target": [0.0, 0.0, 0.1],
      "energy": 150.0,
      "size": 0.6
    }
  ],
  "build_order": ["base", "shaft", "bracket"]
}
```

### 2.3 尺寸与轴向约定

- 单位米，Z 轴向上。
- `size` 是旋转前的局部全尺寸。
- `cuboid` / `flat_plate`：`[x, y, z]`。
- `cylinder` / `cone`：沿局部 Z，`[直径, 直径, 高度]`。
- `sphere`：`[直径, 直径, 直径]`。
- `torus`：`[外径, 外径, 厚度]`。
- 规划完成后执行两步确定性归一化：圆柱/圆锥轴向纠正、整体落地到 `z=0`。

## 3. Blender 执行

使用独立进程：

```text
blender.exe --background --factory-startup --python-exit-code 1 ^
  --python blender/scripts/execute_build.py -- ^
  --script workspace/jobs/<job>/build_model.py ^
  --out-dir workspace/jobs/<job>/scene ^
  --plan workspace/jobs/<job>/model_plan.json
```

Blender 侧使用：

- `bpy.data`：对象、网格、材质。
- `bmesh`：网格结构。
- `bpy.ops`：仅用于建模与导出等必要操作。
- Geometry Nodes：后续扩展。

### 3.1 生成脚本的安全边界

Qwen3-Coder 的输出按“受控开发模式”处理，不直接 `exec`：

1. 只写入独立文件 `build_model.py`。
2. AST 静态检查：导入白名单、禁用文件/进程/网络 API、禁用 `eval/exec/compile/__import__`、禁用 `bpy.ops.wm.*` 与导入导出操作。
3. 必须定义无参数 `build()`；由包装脚本调用。
4. 文件读写、保存 `.blend`、导出 GLB、渲染预览全部由包装脚本负责，生成脚本不接触路径。
5. 独立 Blender 进程执行，设置超时。
6. 失败保留脚本、日志、场景文件（若已生成）。
7. 检查输出文件后再进入验收。

包装器以 `model_plan.json` 为最终依据：重设每个部件的尺寸、位置、旋转与父子关系（保留世界变换），并按场景包围盒自动取景。生成脚本只负责几何与材质，不决定最终摆放。

如果 Coder 连续 3 次被静态检查拒绝，回退到确定性图元构建器（只支持基本几何），并在 `job.json` 标记 `status=fallback`；从未通过检查的脚本不会执行。

## 4. 反馈闭环

1. Blender 生成初始模型与固定视角预览图。
2. 将原图与预览图一起发给 Qwen3-VL。
3. 找出明显差异，输出修正建议 JSON。
4. 人工确认后修改计划或脚本，再执行一次。

初期最多两轮自动/半自动修正，之后保留人工检查。不建议无限循环。

## 5. 工程目录

```text
ModelingStudio/
├── README.md
├── pyproject.toml
├── config/
│   ├── workflow.example.yaml
│   └── workflow.yaml          # 本机路径，不入库
├── schemas/                   # 由 Pydantic 导出
├── prompts/
│   ├── image_analysis.md
│   ├── modeling_plan.md
│   ├── script_generation.md
│   └── visual_revision.md
├── src/modeling_studio/
│   ├── cli.py
│   ├── config.py
│   ├── llm.py
│   ├── server.py
│   ├── image_analyzer.py
│   ├── model_planner.py
│   ├── script_generator.py
│   ├── script_guard.py
│   ├── script_fallback.py
│   ├── blender_runner.py
│   ├── validator.py
│   ├── reviser.py
│   └── job.py
├── blender/scripts/execute_build.py
├── workspace/jobs/            # 不入库
└── tests/
```

## 6. 实施顺序与验收

| 阶段 | 验证目标 | 状态 | 实测 |
| --- | --- | --- | --- |
| 1 | Qwen3-VL 单图分析 | `PASS_VERIFIED` | 7 个部件；1917 prompt / 652 completion tokens |
| 2 | Qwen3 建模规划 | `PASS_VERIFIED` | 10 个部件；3160 prompt / 2020 completion tokens |
| 3 | Qwen3-Coder 生成脚本 | `PASS_VERIFIED` | 254 行，通过 AST 静态检查 |
| 4 | Blender 自动建模 | `PASS_VERIFIED` | `.blend` 121 KB、GLB 123 KB、FBX 78 KB、预览 1280×720 |
| 5 | 自动渲染与检查 | `PASS_VERIFIED` | 12/12 项检查通过（含 GLB 结构与 FBX） |
| 6 | 反馈修正 | `PASS_VERIFIED` | 输出 5 条差异建议；不自动重建 |

第一阶段不追求复杂模型。先用一张结构明确、包含几个基本几何部件的图验证全流程，再增加曲面、复杂机械结构、材质、骨骼和动画。

## 7. 实现位置

代码与操作说明见 [ModelingStudio](../ModelingStudio/README.md)：

```text
ModelingStudio/
├── config/workflow.yaml         # 本机模型与 Blender 路径（忽略）
├── prompts/                     # 三个阶段的提示词
├── schemas/                     # visual_analysis / model_plan / validation / revision
├── src/modeling_studio/         # server、llm、job、三阶段、验收、修正
├── blender/scripts/execute_build.py
└── workspace/jobs/<job>/        # 每个任务的完整现场
```

关键工程约束在实现中固化为：

- `server.py` → `shared/ai_runtime`：跨进程锁 + 8080 单实例；只停止自己启动的实例，别人启动的只复用；被其他模型占用时 `blocked`。
- 每个阶段写任务记录（`workspace/jobs/<job>/tasks/` 与 `runtime/tasks/`），失败/阻塞落盘；`--resume` 跳过已完成阶段。
- 每次请求前做上下文预算（16K/32K，硬上限 64K），超限失败并要求拆分。
- `script_guard.py`：生成脚本的 AST 白名单检查。
- `llm.py`：识别“模型回显 JSON Schema”与 `finish_reason=length`，带着明确纠正重试；提示词要求返回数据实例而不是 schema。
- `execute_build.py`：计划是尺寸/位置/旋转/父级的最终依据；自动取景；包装器负责保存与导出。
- `model_planner.py`：圆柱轴向归一化与整体落地，消除常见的 Z 轴尺寸错误。

### 7.1 已修复的实测问题

- 2026-11-03 全链路 `run` 首次在规划阶段失败：模型把 JSON Schema 本身当成输出（`$defs`/`properties`），重试又撞到 3000 token 上限。
- 修复：提示词末尾明确要求“返回数据实例，不要返回 schema”；`llm.py` 检测 schema 回显和 `finish_reason=length`，带着明确纠正重试；规划提示词要求简洁输出。
- 修复后重跑阶段 2 成功（10 个部件，3565 prompt / 1730 completion tokens，`finish_reason=stop`）。

## 8. 非目标

- 不新增图生 3D 大模型服务。
- 不引入 MCP、LangChain、向量数据库、独立 RPC 服务或 `bpy` Python Module。
- 不追求从单张无标定照片恢复真实尺寸。
- 不把 AI 生成脚本直接作为生产环境的无约束入口。
