# ModelingStudio


> **2026-11-11 状态**：V1 收敛完成；`check.ps1` exit 0，六套 647 用例（641 通过、6 跳过）。新增历史 / AI 时代基础 / 汽车空气动力学三个领域方案；统一英文成片与英上中下字幕；`build/` 为临时区、`deliver/` 为最终交付区。C-16 片头 DEFERRED。生产契约与验收见 [最终验收报告](../docs/stabilization/FINAL_ACCEPTANCE_REPORT.md)。
本地自动化建模工作流：单张图片 → Qwen3-VL 视觉分析 → Qwen3 建模规划 → Qwen3-Coder 生成 bpy 脚本 → Blender 执行 → 预览与验收 →（可选）VL 视觉修正建议。

不使用云端 API、不引入图生 3D 模型、不新增推理服务。模型全部走本机 `<AI_ROOT>` 的 8080 单实例 llama.cpp 服务，按阶段启动和停止。

完整方案与阶段说明见 [AI + Blender 本地自动化建模工作流](../docs/AI-Blender本地建模工作流.md)。

## 链路

```text
图片
 │
 ├─ stage 1  Qwen3-VL 16K         → visual_analysis.json
 ├─ stage 2  Qwen3 32K            → model_plan.json
 ├─ stage 3  Qwen3-Coder 32K      → build_model.py（静态检查）
 ├─ stage 4  Blender 5.2 headless → model.blend / model.glb / preview.png / scene_report.json
 ├─ stage 5  本地验收              → validation.json
 └─ stage 6  Qwen3-VL 对照原图/预览 → revision.json（建议，不自动重建）
```

## 环境

- Python 3.12，`uv` 管理依赖。
- Blender `5.2.3 LTS`。
- `<AI_ROOT>` 的 `llama-server.exe` 与三个模型：`Qwen3VL-30B-A3B-Instruct-Q4_K_M`、`Qwen3-30B-A3B-Instruct-2507`、`Qwen3-Coder-30B-A3B-Instruct-Q4_K_M`。
- 8080 同一时间只允许一个实例；`ModelingStudio` 启动的实例会在阶段结束后停止，别人启动的实例只复用、不杀。

```powershell
cd CourseWorkspace\ModelingStudio
uv sync
copy config\workflow.example.yaml config\workflow.yaml
# 编辑 config\workflow.yaml，填入本机 <AI_ROOT> 与 Blender 路径
```

`config/workflow.yaml` 已忽略，不入库。

## 命令

```powershell
# 环境与服务状态
uv run modeling-studio audit

# 全流程（新建 job）
uv run modeling-studio run --image tests/fixtures/sample-assembly.png `
  --notes "底座约 0.30 x 0.20 m，总高约 0.35 m"

# 分阶段
uv run modeling-studio analyze  --job sample-001
uv run modeling-studio plan     --job sample-001
uv run modeling-studio generate --job sample-001
uv run modeling-studio build    --job sample-001
uv run modeling-studio revise   --job sample-001

# 查看产物
uv run modeling-studio status --job sample-001

# 静态检查生成脚本
uv run modeling-studio guard --script workspace/jobs/sample-001/build_model.py

# 导出 JSON Schema
uv run modeling-studio schemas
```

`run` 可选 `--revise`，在验收通过后自动执行阶段 6。

## 产物

```text
workspace/jobs/<job>/
├── input/
│   ├── original.png|jpg     # 原图副本
│   └── input.png            # 归一化到最长边 1280 的分析图
├── visual_analysis.json
├── model_plan.json
├── build_model.py
├── scene/
│   ├── model.blend
│   ├── model.glb
│   ├── model.fbx
│   ├── preview.png
│   └── scene_report.json
├── validation.json
├── revision.json            # 可选
├── tasks/                   # 每阶段任务记录（FR-10）
├── logs/
│   ├── server-vision.log
│   ├── server-planner.log
│   ├── server-coder.log
│   ├── blender-build.log
│   └── server-revision.log
│   # 失败时另有 analyze-last-response.txt / plan-last-response.txt
└── job.json                 # 各阶段模型、usage、耗时、状态
```

## 测试夹具

`tests/fixtures/sample-assembly.png` 是一张可控的机械装配参考图，由 `tasks/reference-assembly.json` 通过现有 v2 场景系统渲染：

```powershell
cd ..
uv run --project CourseControl course-control scene-run `
  --task ModelingStudio/tasks/reference-assembly.json
copy build\modeling-fixture\blender\reference.png `
  ModelingStudio\tests\fixtures\sample-assembly.png
```

它包含底座、四个螺栓、立柱、轴环、顶盖、球形旋钮和 L 形支架，适合验证“部件拆分 + 基本几何”的完整链路。

## 安全边界

- 生成脚本只写入文件，由 AST 静态检查后执行。
- 允许的导入：`bpy`、`bmesh`、`mathutils`、`math`、`random`。
- 禁止文件/进程/网络 API、`eval/exec/open/__import__/getattr`、dunder 属性、`bpy.ops.wm.*`、导入导出操作。
- 生成脚本只能定义 `build()`；保存 `.blend`、导出 GLB、渲染预览由 `blender/scripts/execute_build.py` 负责。
- Blender 以 `--background --factory-startup --python-exit-code 1` 独立进程执行，带超时。
- 计划是变换的最终依据：包装器按 `model_plan.json` 重设尺寸、位置、旋转与父子关系，并自动取景预览相机。
- 材质按 `part.material_id` 分配；部件未指定材质时，使用计划中的第一个材质作为默认。
- 如果 Coder 连续 3 次被静态检查拒绝，会回退到确定性图元构建器（`script_fallback.py`），并在 `job.json` 标记 `status=fallback`；不会执行未通过检查的脚本。

## 尺寸与轴向约定

- 单位米，Z 轴向上。
- `size` 是旋转前的局部全尺寸。
- `cuboid` / `flat_plate`：`[x, y, z]`。
- `cylinder` / `cone`：沿局部 Z，`[直径, 直径, 高度]`。
- `sphere`：`[直径, 直径, 直径]`。
- `torus`：`[外径, 外径, 厚度]`。
- 规划完成后会做两步确定性归一化：圆柱轴向纠正、整体落地到 `z=0`。

## 验收结果（2026-11-03）

样本 `tests/fixtures/sample-assembly.png` → job `sample-001`：

| 阶段 | 模型 | 实测 |
| --- | --- | --- |
| 分析 | Qwen3-VL 16K | 7 个部件，1917 prompt tokens / 652 completion tokens，约 1 分 48 秒（含 42 秒服务启动） |
| 规划 | Qwen3 32K CPU | 10 个部件，3316 prompt / 1948 completion tokens，约 4 分钟 |
| 编码 | Qwen3-Coder 32K CPU | 254 行，2886 prompt / 2423 completion tokens，通过静态检查 |
| 构建 | Blender 5.2 | `.blend` 121 KB、GLB 123 KB、FBX 78 KB、预览 1280×720 |
| 验收 | 本地 | 12/12 项通过（含 GLB 结构与 FBX 检查） |
| 修正 | Qwen3-VL | 2497 prompt / 381 completion tokens，5 条差异建议，`rebuild_recommended=true` |


## 并发、预算与任务状态

所有本地模型调用都经过 `shared/ai_runtime`，不再由本工程自行管理锁：

- **跨进程锁**：`runtime/locks/llama-8080.lock`（工作区根目录）。同一时刻只有一个任务能持有锁；其他进程排队等待，超时后报错。
- **服务生命周期**：健康且别名匹配则复用；8080 被其他模型占用时 `blocked`，不杀他人进程；本进程启动的实例在阶段结束后停止。
- **任务记录**：`workspace/jobs/<job>/tasks/<stage>.json`，同时写入 `runtime/tasks/`。状态为 `running` / `completed` / `failed` / `blocked`；失败会连同错误写入 `job.json`，不会静默消失。
- **断点续跑**：`modeling-studio run ... --resume` 跳过已通过且产物存在的阶段。
- **上下文预算**：分析/修正是 16K，规划/编码是 32K，硬上限 64K；每次请求前估算并写入任务记录的 `context_budget`，超限直接失败并要求拆分，不静默截断。
- **硬件**：文本模型（planner/coder）CPU-only；视觉模型使用现有 SYCL GPU 配置，与 ComfyUI 不得同时运行。

```powershell
uv run modeling-studio run --image tests/fixtures/sample-assembly.png --resume
uv run modeling-studio status --job sample-001   # 含每阶段任务状态
uv run --project ../shared/ai_runtime ai-runtime status
```

## 已知限制

- 规划阶段的尺寸是假设，不是测量；必须看 `assumptions`。
- 规划可能把 L 形结构简化成单块；阶段 6 会指出，但不会自动重建。
- 规划输出触达 `max_tokens` 时，重试会要求更短的对象（只保留必填字段、最多 8 个部件）。
- 模型偶尔会把 JSON Schema 本身当成输出；客户端检测 `$defs`/`properties` 后会带着明确纠正重试，提示词也要求返回数据实例。
- 材质颜色依赖 VL 的视觉判断；渲染光照过亮时会显得单色。
- CPU 文本模型推理较慢；完整链路约 10–15 分钟，若 JSON 校验失败会重试一次，可能更久。
- 当前不生成 UV、绑定、骨骼或动画。
- 阶段 6 只输出建议，不自动修改计划；避免无限自动修复。
