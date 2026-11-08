# PBR / BSDF 与科学可视化接入评估（修订稿 v2）

- **状态**：评估稿（未纳入 PRD，未产生任何代码、契约或状态变更）
- **日期**：2026-11-04
- **修订**：v2 —— 依据重新核对后的**一致性修订**；不新增能力判断，只修正初稿内部矛盾、补足依据与阶段依赖
- **评估对象**：外部提案《把 PBR / BSDF 纳入 CourseWorkspace 技术体系》——三层材质目标、AI 生成配置 + Python 执行的场景工作流、建议目录骨架、三步实施
- **判据**：`docs/PRD.md`（v1.0）、`docs/ARCHITECTURE.md`、`docs/Blender场景任务IR-v2.md`、`docs/DECISIONS.md`、`docs/PROJECT_STATUS.md`、`BlenderStudio/scripts/scene_system/`、`RemotionStudio/src/`、`shared/schemas/`
- **约束**：本文件只描述评估与计划，不授权任何实现

---

## 1. 结论

1. **提案的核心架构判断是对的，但 CourseWorkspace 已经在做同一件事。** “AI 只产出结构化配置、Python/Blender 只执行白名单字段”就是 IR v2（FR-05）本身，不是新增能力。参见 [Blender场景任务IR-v2.md §1](../Blender场景任务IR-v2.md) 的执行链路与 §11 的 AI 输出约束。**不需要技术体系重构，也不需要新建工程。**
2. **基础材质已覆盖大部分子项，缺口集中在贴图链路、折射、次表面与预设**（逐项计数见 §3.1，不再使用无依据的百分比概数）。
3. **Level 2（程序化 + 科学可视化）当前为 0**，而它恰好是数学 / 物理 / CFD / 汽车课程真正缺的部分。
4. **Level 3（各向异性金属、皮肤、织物、Toon）不建议建设**；对教学片而言，教学辅助表现（线框、剖切、X-ray、高亮）的性价比远高于高级 PBR。
5. **比材质更靠前的缺口是“教学表达基元”**：文字、曲线、正交相机。IR v2 目前只有 9 种图元 + EMPTY，无法在三维画面里标注单位、公式或部件名。该缺口已进入实施计划（P1），不再是“建议优先”的口号。
6. **Blender 与 Remotion 的职责必须写死**（§4）：三维与三维锚定标注归 Blender，二维图例、排版、字幕、合成归 Remotion。二者之间新增任何数据，都要走契约，不是“顺手加个组件”。
7. **提案建议的目录骨架（`BlenderStudio/geometry/`、`materials/`、`shaders/`…）与现有实现冲突**，且违反 [ARCHITECTURE.md §7](../ARCHITECTURE.md) 第 5 条“不新增平行实现”。应改为在 `BlenderStudio/scripts/scene_system/` 内部拆分。
8. **不承诺“所有阶段都保持 `schema_version: 2`”**。每个阶段实施前单独做兼容性评估（§7.3），再决定增量字段、枚举增补还是新版本号。

---

## 2. 依据重新核实

### 2.1 文档依据（结论点）

| 来源 | 核实到的约束 |
| --- | --- |
| PRD §1.1 / §1.2 | 目标是“内容已写好后的确定性产出”，明确不做“让 LLM 判定事实正确性”；不做云端渲染、ComfyUI 流水线 |
| PRD §3 | `BlenderStudio` 定位“核心（三维能力）”、`ModelingStudio`“内部能力”、`ManimSandbox`“可选能力” |
| PRD FR-05 | IR v2 双端校验、路径约束、验收项清单 |
| ARCHITECTURE §1.1 | 写入归属：`BlenderStudio/scenes|assets` 由人工写，产物只进 `build/<slug>/` |
| ARCHITECTURE §7 | 扩展规则：新引擎走 `StageOutcome`；新数据文件必须有 Pydantic + Schema + 同步测试；不新增平行实现 |
| DECISIONS D-007 | Blender v1/v2 并存，v2 是完整场景描述 |
| DECISIONS D-014 | 人工导出、内容占位、凭据缺失、模型不可用必须如实进入状态；不伪装自动化 |
| PROJECT_STATUS FR-05（评估时基线） | IR v2 状态 `COMPLETED`，证据为 4 次真实渲染 + 19 个 CourseControl 测试；2026-11-04 已增至 8 次渲染 + 51 个测试 |
| PROJECT_STATUS FR-06 | ModelingStudio `PARTIAL`，真实全链路本轮未重跑 |
| PROJECT_STATUS NFR-01 | 可复现为 `PARTIAL`：夹具稳定，真实课程未重复构建 |

### 2.2 代码证据（P1a 实施前基线，行号以当前工作树为准）

> 下表记录的是 **P1a 实施前** 的基线，用于支撑阶段判断。TEXT / CURVE / ORTHO 三项已由 P1a 改变，当前契约以 [Blender场景任务IR-v2.md](../Blender场景任务IR-v2.md) §5.1.1、§6 为准。

| 事实 | 位置 |
| --- | --- |
| 只有两种 shader | `BlenderStudio/scripts/scene_system/task_schema.py:37` `SHADERS = {"principled", "emission"}` |
| 材质树只创建 Output + Principled/Emission 两个节点，无任何贴图、坐标、Ramp、Attribute 节点 | `scene_system/materials.py:30-65` |
| Principled 参数为 base_color / metallic / roughness / alpha / ior / emission_color / emission_strength | `scene_system/materials.py:44-52` |
| 透明仅靠 alpha 混合模式，无 `Transmission Weight` | `scene_system/materials.py:21-27`、`:44-52` |
| 只有 9 种图元 | `scene_system/task_schema.py:52` `PRIMITIVE_PARAMS` |
| 对象类型只有 `MESH` / `EMPTY` | `CourseControl/src/course_control/blender_scene.py:183`；`scene_system/objects.py` |
| 无文字、无曲线：`bpy.data.curves` / FONT 在场景系统中无任何使用 | `scene_system/` 全文无匹配（仅 `animation.py` 的 F-Curve 同名干扰） |
| 相机只设 lens / sensor_width / DOF，未设 `camera.type`，即无正交投影 | `scene_system/cameras.py:23-40`；`blender_scene.py:265-282` |
| 场景报告对非 MESH 对象只记录 `type`，不做几何校验 | `BlenderStudio/scripts/verify_scene.py:148-171` |
| 材质只记录槽位名，不校验节点与参数值 | `verify_scene.py:161-163` |
| 缺失资源只检查图片与库，不检查导入网格 | `verify_scene.py:201-213` |
| 契约检查为 6 合法 + 11 非法（P1a 后） | `scripts/check-scene-system.ps1:34-54` |
| 双端一致性有测试锁定 | `CourseControl/tests/test_blender_scene.py`（9 个用例，含 `test_external_and_blender_validators_agree`） |
| 渲染实测：EEVEE 1080p/8 samples ≈ 0.2 s/帧；Cycles CPU ≈ 5.6 s/帧 | `BlenderStudio/README.md:178` |

### 2.3 Remotion 合成链核实（P1b 实施前基线）

| 事实 | 位置 |
| --- | --- |
| 合成只有四类图层：base 镜头、overlay 镜头、字幕、旁白 | `RemotionStudio/src/compositions/CourseVideo.tsx:123-146` |
| overlay 镜头必须是**媒体文件**（视频/图片），不是矢量层 | 同上 `:60-120`；`types.ts` 的 `presentation` 只有 cutaway / picture_in_picture / transparent_overlay |
| 没有任何图例、色标、任意文字标注组件 | `RemotionStudio/src/` 全文无 `legend` / `annotation` / `colorbar` |
| 字幕由 SRT 驱动，只能显示台词 | `RemotionStudio/src/subtitles/Captions.tsx` |
| 字体来自系统字体栈（P1b 后已捆绑 Noto Sans SC，见 D-017） | `shared/design-tokens/tokens.json`；`RemotionStudio/src/styles/tokens.ts` |
| staging 只复制 `shots` / `narration` / `subtitles` 引用的文件 | `RemotionStudio/scripts/stage-assets.mjs:32-34` |
| `shots.json` 的 `Shot` 为 `additionalProperties: false`，新增字段必须同步改 Pydantic 模型与 Schema | `shared/schemas/shots.schema.json` |

**关键结论（P1b 前）**：Remotion 是合格的二维合成器，但当时没有通用的二维标注层。P1b 实测的改动点是 5 处：`shots.json` Schema、`CourseControl` Pydantic、`collect`、Remotion types + 组件、`verify`；标注不含外部文件，因此 **`stage-assets` 未改动**。这是 P3 色标的**前置成本**，初稿曾漏算。

### 2.4 与初稿的差异

- 初稿称“Level 1 约完成 60%”：改为逐项计数（§3.1），并说明计数口径。
- 初稿把“压力色图”放进材质基准场景：与科学着色阶段冲突，已移出（§7 P2b）。
- 初稿只说“科学着色需要 shader”：实际需要属性写入 + 字段来源 + 色标，三缺一不可（§5.2）。
- 初稿的 Blender/Remotion 边界散落在两段里：独立成章（§4），并补上 Remotion 现状与跨层成本。
- 初稿把 transmission 列为基础材质必做：改为条件项（§7 P2、Q1）。
- 初稿“缺元数据时拒绝执行**或** needs_human_review”：二选一，定为**校验期拒绝**（§5.2）。
- 初稿“所有切片保持 `schema_version: 2`”：改为逐阶段兼容性门（§7.3）。
- 初稿“教学基元优先”没有落地：进入 P1（§7），并区分 Blender 三维锚定与 Remotion 二维标注。

---

## 3. 能力对照（按提案条目逐项计数）

计数口径：把提案原文列举的**子能力**逐条计数；“已实现”指当前 IR v2 能通过配置表达且能渲染；“部分”不单独计分，归入未实现并在备注说明。

### 3.1 Level 1：基础材质自动化（14 项）

| # | 子项 | 状态 | 证据 / 备注 |
| --- | --- | --- | --- |
| 1 | Principled BSDF 节点创建 | 已实现 | `materials.py:44` |
| 2 | Base Color | 已实现 | `materials.py:46` |
| 3 | Metallic | 已实现 | `materials.py:47` |
| 4 | Roughness | 已实现 | `materials.py:48` |
| 5 | Normal Map | 未实现 | 无 Image Texture / Normal Map 节点 |
| 6 | Bump | 未实现 | 无 Bump / Noise 节点 |
| 7 | Emission | 已实现 | `materials.py:51-52`、`:58-61` |
| 8 | 透明 | 已实现 | alpha 混合，`materials.py:21-27` |
| 9 | 玻璃（折射） | 未实现 | 无 `Transmission Weight` |
| 10 | 简单次表面散射 | 未实现 | 无 `Subsurface Weight` |
| 11 | 材质命名 | 已实现 | `id` → `bpy.data.materials` |
| 12 | 材质复用 | 已实现 | 对象按 `material` 引用同一数据块 |
| 13 | 参数配置 | 已实现 | IR `params` 白名单 |
| 14 | 预设 / 参数库 | 未实现 | 无 `assets/materials/` 一类的预设层 |

**计分：9 / 14 子项已实现。** 说明：这是**子项数**，不是工作量覆盖率。未实现的 5 项（Normal Map、Bump、折射、次表面、预设）恰是难度更高的部分，因此按工作量折算的覆盖率低于 9/14。初稿的“约 60%”不再使用。

### 3.2 Level 2：程序化与科学可视化（7 项）

| # | 子项 | 状态 |
| --- | --- | --- |
| 1 | Noise / Voronoi / Wave 程序化纹理 | 未实现 |
| 2 | Geometry / Object / Texture Coordinate | 未实现 |
| 3 | Mix / Color Ramp / Map Range | 未实现 |
| 4 | Shader Attribute / Named Attribute | 未实现 |
| 5 | Volume Shader | 未实现 |
| 6 | 科学数据颜色映射 | 未实现 |
| 7 | 线框 / 等值面 / 流线辅助表现 | 未实现 |

**计分：0 / 7。**

### 3.3 Level 3：高级材质（4 项）

| # | 子项 | 状态 |
| --- | --- | --- |
| 1 | 各向异性金属 | 未实现 |
| 2 | 复杂玻璃与折射 | 未实现（依赖 Level 1 的 transmission） |
| 3 | 皮肤 / 织物 | 未实现 |
| 4 | Toon / 非真实感渲染 | 未实现 |

**计分：0 / 4，建议 `deferred`。** 建议不做的理由不是难度，而是收益：教学片里“看懂结构”优先于“看起来真实”。

---

## 4. 职责边界：Blender vs Remotion

这条边界在初稿里只散见于两段，容易被读成“色标放 Remotion”这种局部建议。实际它决定了后面每一个阶段的落点：

| 能力 | 归属 | 现状 | 理由 |
| --- | --- | --- | --- |
| 三维几何、材质、灯光、相机、动画、渲染 | Blender | 已实现 | 三维计算的唯一位置 |
| 与物体锚定、随相机运动的标注（坐标轴刻度、部件名） | Blender（TEXT） | 未实现 | 跟随三维透视/遮挡关系 |
| 屏幕固定位置的标题、图例、单位说明、色标 | Remotion | **未实现**（只有字幕） | 二维排版、字体、换行、对齐在 React 里成本最低 |
| 字幕 | Remotion | 已实现（SRT） | — |
| 画中画 / 切角 / 透明叠加 | Remotion | 已实现（`presentation`） | — |
| 版式与配色 | Remotion + `design-tokens` | 已实现 | 单一来源 |
| 视频编码与音画同步 | Remotion / FFmpeg | 已实现 | — |
| 二维排版系统 | **不在 Blender 内建设** | — | 与 PRD 分层和 ARCHITECTURE §7 冲突 |
| 色标（colormap 图例） | Remotion；colormap 定义放 `shared/` | 未实现 | 同一份定义同时驱动 Blender 材质与 Remotion 图例，避免两处色值漂移 |

**边界落地规则**：

1. 任何“跟随三维”的文字进 Blender；任何“贴在画面角上”的文字进 Remotion。
2. Remotion 新增标注必须以 `shots.json` 字段为载体，经 `collect` 生成、`stage-assets` 准备、`CourseVideo` 渲染、`verify` 校验；不允许在组件里硬编码课程内容。
3. colormap 定义只有一份（建议 `shared/` 下的数据文件），Blender 执行器与 Remotion 组件都读它。
4. **TEXT 首期范围**：Blender TEXT 首期只承诺数字、英文、数学符号；中文说明优先由 Remotion 渲染。P1a 首日已完成字体实测（Blender 5.2.3 LTS，内置 Bfont）：数字、英文、`± ° θ × ÷ ≤ ≥` 与中文均可渲染（证据见 P1a 报告）。即便中文字形可用，首期仍不把中文排版责任放在 Blender：换行、对齐、字体一致性与色标文本统一由 Remotion 承担。若后续要在 Blender 内正式支持中文，需单独决定是否捆绑字体（引入资产依赖）。

---

## 5. 关键缺口与依赖

### 5.1 教学表达基元（为什么排在最前）

三维教学画面的可读性依赖四类基元：**文字、曲线、坐标轴、箭头**。

| 基元 | 现状 | 结论 |
| --- | --- | --- |
| 箭头 | 可用 CYLINDER + CONE + `parent` 组合出来 | **不需要新类型**，只需文档化组合模式与夹具 |
| 坐标轴 | 同上，刻度文字依赖文字能力 | 依赖 TEXT |
| 曲线（轨迹、流线、函数线） | 只能用圆环/圆柱拼，无法表达折线 | **需要 CURVE 类型** |
| 文字（单位、公式、部件名） | 完全没有 | **需要 TEXT 类型**；中文按 §4 规则优先 Remotion |
| 正交相机 | 未实现，只有透视 + `focal_length` | **需要 `projection: ORTHO`**（数学图形常用） |

所以“教学基元优先于材质”的依据不是主观排序，而是：**没有文字与曲线，三维画面内就无法标注单位/公式，也无法画出轨迹曲线；材质只改变“看起来像什么”，不改变“能不能讲清楚”。** 这一点已落成 P1。

### 5.2 科学着色的四段链路（不能只做 shader）

初稿只写了 shader 参数，这是不完整的。端到端需要四段，缺一段就不可用：

1. **属性写入**：对象声明 `attributes[]`（名称、域 = POINT、字段规格），执行器把标量写到网格属性上。当前 `geometry.py` 只造图元，无属性写入。
2. **字段来源**：P3 阶段只允许**声明式字段**——`axis`（坐标分量）、`distance`（到点/平面）、`noise`（种子可复现）。**不引入表达式**；表达式留给 P4，真实数据留给 P5。
3. **颜色映射**：`scientific_colormap` shader——`source_attribute`、`min_value`、`max_value`、`units`、`colormap`。与 `principled` 语义分离：不继承任何 PBR 参数，不提供 metallic/roughness。
4. **色标**：由 Remotion 读取同一份 colormap 定义渲染，必须显示 min / max / units。

**元数据规则（统一为一条）**：

- `source_attribute`、`min_value`、`max_value`、`units`、`colormap` 任一缺失或非法 → **契约校验直接失败**（`scene-validate` 非零退出），不进入 Blender，不生成 `.blend`。
- **不提供 `auto` 范围**。P3 阶段没有“自动推导范围”这一选项；将来若要引入，必须同时满足：数据源自带范围元数据、推导结果写入报告、人工确认三项条件。
- 不使用 `needs_human_review` 表达“输入不完备”——`needs_human_review` 属于模型任务状态词表，不用于契约校验（ARCHITECTURE §4.4）。

**验收方式**：在网格上采样 N 个点，按字段规格复算标量，按 colormap 定义复算颜色，与场景中实际属性值和材质节点设置比对；不靠肉眼。

### 5.3 参数化曲面

`z = f(x, y)` 需要“表达式 → 网格”，与 §5.2 的属性通道共用写入逻辑：

- 只允许**受限 AST 求值器**：数字常量、变量 `x`/`y`/`t`、`+ - * / **`、白名单函数（sin/cos/tan/exp/log/sqrt/abs/min/max）。
- 拒绝：`import`、属性访问、下标、lambda、推导式、任何非白名单调用。
- 上限：表达式长度、AST 节点数、网格分段数、计算耗时各自设上限，超限即失败。
- 验收：与解析解在采样点上比对；越界与未知函数名必须有拒绝用例。

### 5.4 跨层契约成本

P1b（Remotion 二维标注层）不是“加个组件”：

| 动作 | 位置 |
| --- | --- |
| 新增 `annotations[]` 字段 | `shared/schemas/shots.schema.json` + `CourseControl` 的 shots Pydantic 模型 |
| 生成标注数据 | `CourseControl/src/course_control/collect.py` |
| 复制引用资源 | `RemotionStudio/scripts/stage-assets.mjs` |
| 渲染组件 | `RemotionStudio/src/compositions/CourseVideo.tsx` |
| 校验 | `CourseControl/src/course_control/verify.py`（新增 V-xx） |

`Shot` 当前是 `additionalProperties: false`，所以这是**契约变更**，不是内部实现。必须按 ARCHITECTURE §7 第 2 条走“模型 + Schema + 同步测试”。

---

## 6. 工程红线（保留并落到实现约束）

| # | 红线 | 落地方式 |
| --- | --- | --- |
| 1 | 不允许 AI 生成任意 Python / bpy 代码进入正式课程执行链 | IR v2 字段白名单；`ModelingStudio` 的 AST 守卫属于“内部建模作业”，不作为课程产物 |
| 2 | 不允许 `eval` / `exec` 执行模型生成的表达式 | P4 使用受限 AST 求值器，并包含 import / 属性访问 / 未知函数的拒绝用例 |
| 3 | 科学数据缺范围、单位等元数据时拒绝执行，不允许 AI 自动填充 | `scene-validate` 阶段失败；无默认值兜底；无 `auto` 范围 |
| 4 | 科学颜色映射与 PBR 表面材质保持不同语义 | 独立 shader kind，独立参数表，不共用 PBR 字段 |
| 5 | 不新建与 `scene_system/` 平行的实现 | 在 `scene_system/` 内拆子包（`materials/`、`geometry/`），`executor.py` 保持单入口 |
| 6 | Remotion 负责二维图例、排版与合成，不重复建设 Blender 内二维排版 | §4 的边界表；Blender 侧只做三维锚定文字 |
| 7 | 不为追求材质效果引入不必要的外部依赖 | P2 优先程序化 Bump；图片 Normal Map 延迟到有真实资产；字体捆绑单独决策 |
| 8 | 旧任务、非法任务夹具、双端校验必须纳入后续兼容性评估 | §7.3 的逐阶段兼容性门；每次改动都要跑全部合法/非法夹具（当前 6 合法 + 11 非法）与两条一致性测试 |

---

## 7. 实施阶段与依赖

各阶段独立验收、独立回滚。**阶段之间的顺序不是偏好，是依赖关系**（§7.2）。

### 7.1 阶段表

| 阶段 | 内容 | 规模 | 依赖 | 验收（必须落盘或打印） |
| --- | --- | --- | --- | --- |
| **P0** 评估与决策 | 本修订稿；作者对 §9 问题的答复；是否采纳的决策记录 | S | — | 文档评审通过；无代码变更 |
| **P1** 教学表达基元 | P1a：`TEXT`、`CURVE`、相机 `ORTHO`；箭头组合模式文档化。P1b：Remotion 二维标注层（`annotations[]`，跨 5 处契约变更） | P1a M；P1b M | P0 | P1a：`scene-run` 真实渲染；场景报告含 text/curve 统计；空文本、非法曲线被拒；原有夹具仍通过（当前 6 合法 + 11 非法）。P1b：叠加层渲染一帧；shots schema 同步测试；verify 新增检查 |
| **P2** 基础材质参数、预设、语义验收 | 必做：`coat`、程序化 `bump`（无外部资产）、材质预设 JSON、材质语义回读检查。条件项：`transmission` / `subsurface`（待 Q1）、图片 Normal Map（待 Q3） | M | P0 | 逐材质回读参数与声明一致；预设展开确定（同输入同哈希，记入 manifest）；旧夹具不受影响 |
| **P2b** 材质基准场景 | 6 个表面材质（铝、哑光塑料、自发光、涂层、Bump 表面、透明薄片）+ 1 个简化车形体；**不含科学色图** | S | P2 | 1 帧真实渲染 + manifest + 每材质回读；视觉确认记为人工节点；色图演示移到 P3 夹具 |
| **P3** 科学数据着色、属性映射与 Remotion 色标 | 属性写入通道；声明式字段（axis / distance / noise）；`scientific_colormap` shader；固定范围与单位强制；Remotion 色标（复用 P1b） | L | **P1b**；不依赖 P4/P5 | 采样点复算比对（属性值 + 颜色）；缺元数据的非法夹具被拒；色标文本 = min/max/units；色标与材质读同一份 colormap 定义 |
| **P4** 参数化曲面与受限表达式 | 受限 AST 求值器；表达式生成顶点与属性；复用 P3 的属性通道 | M–L | P3（属性通道） | 与解析解采样比对；import / 属性访问 / 未知函数被拒；长度与节点数上限被拒 |
| **P5** 真实数据导入 | 仅在有真实数据源时启动；格式由数据决定 | 未估 | P3；Q2 | 文件哈希入 manifest；单位与场名来自元数据或作者声明；缺失即失败 |
| **P6** AI 场景规划 | 课程页 → IR 草案 → 人审 → 执行 | L | **实际采纳的能力**的 IR 稳定；`ai_runtime` 锁与预算。不强制依赖 P5 | 草案通过 `scene-validate`；人工确认记录入 manifest；按页切片，不整课入模 |

**实施状态（2026-11-04）**：P1a、P1b、P2、P2b、P3、P4 已实施并通过真实渲染与全量回归（P1b：`build/p1b-annotation-evidence/annotation-still.png`；P2b：`build/blender-scene-acceptance/blender/materials.png`；P3：`build/blender-scene-acceptance/blender/scientific.png`、`build/p3-legend-evidence/legend-still.png`；P4：`build/blender-scene-acceptance/blender/surface.png`）；P5 待真实数据源；P6 待课程页输入与人工审查（IR 已稳定）。

删除与调整说明：

- 初稿的“P1 材质 / P1b 基准 / P2a 科学着色 / P2b 曲面 / P3 导入 / P4 规划”编号已废止，统一到本节。
- 初稿把 transmission 列为 P1 必做：改为 **P2 条件项**，理由见 Q1——没有课程需求确认就实现折射，属于为效果而建设。
- 初稿把压力色图放进基准场景：移出到 P3，避免“基准场景依赖尚未实现的着色能力”。
- 初稿让科学着色成为一个 shader 切片：拆成“属性通道 + 字段来源 + 着色 + 色标”，因为它们互为前提。

### 7.2 依赖关系

```text
P0
 ├─ P1a（Blender 文字/曲线/正交）        ── 独立
 ├─ P1b（Remotion 二维标注层）           ── 独立，但 P3 的色标必须等它
 └─ P2（材质参数/预设/语义验收）
      └─ P2b（材质基准场景）
P1b ─→ P3（科学着色 + 色标）
P3  ─→ P4（受限表达式，复用属性通道）
P3  ─→ P5（真实数据导入，且需 Q2）
已采纳阶段的 IR 稳定 ─→ P6（AI 规划；不强制依赖 P5）
```

**顺序评估**：

- 用户给定的 P1 → P2 → P2b → P3 → P4 → P5 → P6 与依赖关系**不冲突**，可以照此排期。
- 唯一需要补充的依赖是 **P1b → P3**。若 P3 之前不需要任何二维标注，可以把 P1b 并入 P3 一起做，但**成本不变**，不能当作“P3 只做一个 shader”。
- P4 在技术上可以先于 P3（表达式曲面自带属性），但那样 P3 的端到端验收仍缺“属性写入通道”，反而要重做一次，因此建议保持 P3 → P4。
- P2b 与 P3 无依赖，可以并行；但它不应包含色图（初稿矛盾）。
- P6 必须最后，因为它消费的是已采纳阶段的 IR；未采纳的能力（例如没有真实数据时的 P5）不构成前置条件。在 IR 仍在变时做规划器，等于反复返工。

### 7.3 兼容性门（取代初稿的“保持 schema_version: 2”承诺）

每个阶段实施前，先做一次兼容性评估并留证：

1. 跑 `scripts/check-scene-system.ps1`（当前 6 合法 + 11 非法）。
2. 跑 `course-control scene-schema`，对比导出的 JSON Schema 差异。
3. 跑 `test_external_and_blender_validators_agree` 与 `test_validators_agree_without_generated_artifacts`。
4. 若涉及 `shots.json`，同步跑 `test_contracts.py` 与 `test_staging.py`。

判定规则：

| 变更类型 | 版本判定 |
| --- | --- |
| 新增可选字段、带默认值 | 可能保持 v2 / shots v1，需 Schema diff 为空以外的最小增量 |
| 新增枚举值（如 `TEXT`、`CURVE`、`ORTHO`、`scientific_colormap`） | 旧任务不受影响，通常可保持 v2；必须在 IR 文档标注版本 |
| 修改既有字段语义、收紧既有校验 | **必须升版本**（v3），并提供旧任务迁移说明 |
| 新增跨层字段（`annotations[]`） | 属另一份契约（shots v1），按同样规则评估 |

**结论**：每个阶段按上述四步出结论，不预先承诺版本号。

---

## 8. 明确不做的事

1. 新建 `BlenderStudio/materials|shaders|geometry` 平行引擎（违反 ARCHITECTURE §7.5）。
2. 引入 Substance Painter / 外部材质库 / 商业贴图源。
3. Toon / 皮肤 / 织物 / 各向异性金属（Level 3）。
4. Volume Shader 与烟雾流体：EEVEE 体渲染能力有限，走 Cycles 后 CPU 约 5.6 s/帧（`BlenderStudio/README.md:178`），与课程批量产出不匹配。
5. 让模型直接生成 `bpy` 代码进课程。
6. 由 AI 决定色标范围、单位或物理结论。
7. 用 alpha 混合冒充玻璃折射。
8. 在 Blender 里建设二维排版系统。
9. 在没有真实数据源的情况下建设数据导入。

---

## 9. 待作者决定

| 编号 | 问题 | 影响 |
| --- | --- | --- |
| Q1 | 近期课程是否真的需要玻璃/折射，还是哑光、金属、自发光、透明薄片已够 | 决定 P2 的 transmission / sub surface 是否实现；不确认则标 `deferred` |
| Q2 | 手上是否有真实 CFD / 仿真数据文件？格式与规模 | 决定 P5 是否存在，以及导入格式 |
| Q3 | 是否有可用的图片 Normal Map 资产 | 决定 P2 是否引入图片贴图链路（会带来外部资产与打包规则） |
| Q5 | 数学曲面以“解析表达式”还是“离散数据点”为主 | 决定 P4 与 P5 的优先级 |
| Q6 | Blender 内是否需要中文文字 | 需要则必须决定是否捆绑字体（外部资产）；否则中文标注走 Remotion（§4） |
| Q7 | 近期优先：教学基元（P1）还是材质（P2） | 两者无依赖，可交换；同时开会拉长首个可用场景的时间 |

**已定（2026-11-04，人工审查）**：

- **Q4 不再是开放问题**：Remotion 的二维标注内容（标题、图例、单位）正式通过 `shots.json` 的 `annotations[]` 契约传递。实施时仍须完成 Schema、Pydantic、测试的兼容性评估（§5.4、§7.3），但“是否纳入契约”本身已决定。

---

## 10. 与提案的逐条差异

| 提案主张 | 本评估 |
| --- | --- |
| PBR 不要做成独立工程，应成为三维能力的一部分 | **同意**，且现状已如此 |
| AI 生成配置而非代码 | **同意**，IR v2 已实现，直接复用 |
| 分三级建设 | **同意分级**，但顺序调整为：先教学基元 → 再基础材质 → 再科学着色 → 再表达式/导入 |
| 建议 `BlenderStudio/{geometry,materials,shaders,...}/` 骨架 | **不同意**：改为 `scene_system/` 内部拆分 |
| 第一阶段 10 种材质 + 基准场景 | **同意**，作为 P2 + P2b；色图演示移出 |
| 科学颜色映射不需要 PBR | **同意**，独立 shader kind，独立参数表 |
| 需要色标/图例 | **同意必要性**，由 Remotion 生成，colormap 定义单一来源 |
| 复杂机械/有机模型人工参与 | **同意**，与 `ModelingStudio` 现有 AST 守卫 + `needs_review` 一致 |
| 科学结论不能交给 AI | **同意**，并升格为契约级拒绝（缺范围/单位即失败） |
| Level 1 可直接覆盖日常教学需求 | **部分不同意**：缺文字与曲线时，日常教学场景连标注都做不出，优先级应前移 |

---

## 11. 修订记录：初稿矛盾与修复位置

| # | 初稿问题 | 初稿位置 | 修订后位置 |
| --- | --- | --- | --- |
| 1 | 认定教学基元高优先级，但实施计划里没有对应阶段 | §1 第 5 条、§3.4 与 §5 阶段表 | §5.1（依据）+ §7 P1（P1a/P1b） |
| 2 | 基准场景包含压力色图，但科学着色排在更后的阶段 | §3.1 基准夹具行、§5 P1b | §7 P2b（明确移除色图）+ §7 P3 夹具 |
| 3 | 科学着色只写 shader 与参数，缺属性写入与数据进入链路 | §3.2 | §5.2 四段链路 + §7 P3 范围 |
| 4 | Blender 与 Remotion 职责边界散落、未成体系 | §3.2 第 4 段、§3.3 | §4 专章 + §2.3 Remotion 现状与跨层成本 |
| 5 | transmission 未确认课程需求即列为必做 | §3.1 缺口表、§5 P1 | §7 P2 条件项 + Q1 |
| 6 | 缺元数据处理规则不一致（“拒绝执行**或** needs_human_review”） | §3.2、§4-C4 | §5.2 单一规则：校验期拒绝；不用 `needs_human_review` |
| 7 | 提前承诺所有切片保持 `schema_version: 2` | §5 开头 | §7.3 逐阶段兼容性门 |
| 8 | “Level 1 约 60%”无计算依据 | §1 第 2 条 | §3.1 逐项计数（9/14，并说明口径） |

同时修正的次要问题：

- 初稿把箭头列为“缺口”，实际可用现有图元组合，已降级为“文档化组合模式”（§5.1）。
- 初稿未说明 Remotion 没有通用标注层，导致“色标放 Remotion”看似零成本；已补 §2.3、§5.4。
- 初稿把 P3 数据导入写成“可选第三刀”，与“只做 shader 不可用”的结论不一致；已改为 P5 且以 Q2 为门槛。
- 初稿的精确工作日估算没有依据，改为 S / M / L 相对规模。
