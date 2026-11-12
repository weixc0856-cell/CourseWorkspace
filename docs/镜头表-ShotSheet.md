# 镜头表（Shot Sheet）

- **日期**：2026-11-12
- **状态**：可用。P3 完成第一段（[工业化生产流程 V2.0](v2/工业化生产流程V2.0-建议稿.md) WP-1：格式、校验、编译与复核）。
- **命令**：`course-control shot-sheet --lesson <slug>`

---

## 1. 它是什么

镜头表是**人对镜头设计的唯一权威**：这个镜头为什么存在、画面上发生什么、构图怎么摆、跨镜头哪些东西必须保持一致、用了哪些资产和证据。

**它不是新文件。** 镜头表就是 `storyboard.yaml` 的 `schema_version: 2`。这一点是 P0 审计定的（[基线审计 §5.1](v2/P0-基线审计.md)）：代码里已经写明"每个 compose 模式只有一个权威"（`plan_audit.py`），导演计划、节拍表、归一时间线都是视图。再加一个 `shot-sheet.yaml` 会造出第三个分镜源，于是把它做成 `storyboard` 的增量版本。

## 2. 字段

v2 在原字段之外增加八项，**全部可选**：

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| `purpose` | `explain` / `demonstrate` / `simulate` / `compare` / `narrate` / `emote` / `orient` / `summarize` | 镜头为什么存在；与导演计划共用一组词 |
| `visual_action` | 字符串 ≤600 | 画面上实际发生的变化，不是"展示这个概念" |
| `composition` | 字符串 ≤300 | 构图与机位 |
| `continuity_refs` | 字符串数组 | 引用的连续性对象 id |
| `asset_refs` | 字符串数组 | 本镜头用到的资产，相对 lesson 目录或 `assets/` |
| `evidence_refs` | 字符串数组 | 数据、来源、claim id |
| `transition` | `{in, out}` | 与构建产物同一套 `Transition` 契约 |
| `director_notes` | 字符串 ≤1200 | 给制作和剪辑的备注 |

顶层新增 `continuity` 对象表：

```yaml
continuity:
  - id: car-half-body          # ^[a-z0-9][a-z0-9_.-]{0,47}$
    label: 半车身模型（同一台车、同一材质）
    note: 第 2、3、9 页复用，比例与朝向必须一致
```

示例：

```yaml
schema_version: 2
lesson: a01-why-cars-need-aerodynamics

continuity:
  - id: car-half-body
    label: 半车身模型
  - id: wake-ribbon
    label: 尾流丝带

shots:
  - id: shot_009
    slide: 9
    engine: blender
    scene: scenes/a01-why-aerodynamics/build_half_body.py
    blend_task: tasks/a01-why-cars-need-aerodynamics/half_body.json
    cue_seconds: 0.0
    engine_profile: studio_3d
    purpose: demonstrate
    visual_action: 相机绕半车身一周，尾流丝带从车尾拖出
    composition: 车身占右下三分之二，丝带向左延伸
    continuity_refs: [car-half-body, wake-ribbon]
    asset_refs: [assets/half-body.png]
    evidence_refs: [E01-CFD-011]
    director_notes: 绕到车尾时放慢，给观众读压力分布的时间
```

镜头时长仍然由内容、声音和实际渲染共同决定，Schema 里不设上下限。

## 3. 版本与兼容

| 情况 | 行为 |
| --- | --- |
| `schema_version: 1` | 完全按原样加载、校验、构建；13 门旧课零改动 |
| `schema_version: 2` | 八项设计字段可用，`continuity` 可用 |
| v1 文件里写了设计字段 | 加载即报错：`shot sheet fields require schema_version: 2 (found on: shot_009)` |

没有做"自动升级"。升级一门课是把 `schema_version` 改成 2，再按需要补字段；不补也能跑。

## 4. 校验

新增三条规则，出现在 `course-control validate` 里：

| 规则 | 检查 | 例子 |
| --- | --- | --- |
| V-45 | `continuity_refs` 必须指向 `continuity` 里声明过的对象 | `continuity ref 'ghost-object' is not declared in continuity` |
| V-46 | `asset_refs` 必须在 lesson 目录或 `assets/` 下存在，且是相对路径 | `asset 'assets/missing.png': not found under …` |
| V-47 | `evidence_refs` 必须是无空白的 id | `evidence ref 'E01 CFD 011' is not a valid id` |

字段本身的问题（空白、重复、id 格式非法）在加载时由 Pydantic 拦住，不会走到 V 规则。

## 5. 编译与复核

```powershell
course-control shot-sheet --lesson <slug>
course-control shot-sheet --lesson <slug> --json
```

输出：

```text
build/<slug>/shot-sheet/
├── plan.json    解析后的镜头表：逐镜头资产解析与哈希、指纹、连续性命中、问题
└── review.md    给人看的复核表：镜头清单、连续性使用、问题
```

终端输出一行摘要和所有问题；有问题时退出码 1。

`plan.json` 里每个镜头带 **fingerprint**：由设计字段 + 资产字节哈希算出的 SHA-256。同一次设计重复编译指纹不变，改一个镜头只改那一个镜头的指纹——这是 P4 锁定与增量重建要用的键。

## 6. 实测（2026-11-12）

用 `build/_p2-fixture/` 下的 a01 副本（不改真实课程）：

| 场景 | 结果 |
| --- | --- |
| v2 镜头表（3 镜头、2 连续性对象） | `3 shots (3 with sheet fields) continuity: 2 assets: 3 evidence: 2`，无问题 |
| 连续性使用 | `car-half-body` → shot_002/003/009；`wake-ribbon` → shot_009 |
| 故意写坏三处 | `[V-45] ghost-object`、`[V-46] assets/missing.png`、`[V-47] E01 CFD 011` 各报一条，定位到具体镜头 |
| 指纹稳定性 | 同一镜头表编译两次，3 个指纹完全一致；改 `director_notes` 后只有 shot_009 变化 |
| 真实 a01（v1） | `3 shots (0 with sheet fields)`，无问题，构建不受影响 |
| 单元测试 | `test_shot_sheet.py` 9 例；CourseControl 全量 542 例通过 / 7 跳过 |

## 7. 还没做的

- **导演计划合并**：编译器现在产出的是"解析后的镜头表 + 复核"，不重写 `director_plan.json` / `directions/`。导演层目前从 `authoring/` 的 brief/outline/script 生成计划，两条链还没有接上。接的时候要处理 id 空间不一致（导演计划的 `shot_xxx` 与镜头表的 shot id 未必同名）。
- **证据引用只校验格式**：`evidence_refs` 是否真的存在于来源里，需要等 KnowledgeStudio 的 claim 索引接入后再做跨文件校验。
- **连续性只到 id 层**：还没有跨镜头的外观/资产一致性检查（比如同一对象两个镜头用了不同模型）。

## 8. 代码与测试

- `CourseControl/src/course_control/contracts.py` — `ShotSpec` 的八项字段、`ContinuityObject`、`Storyboard` v2 与版本守卫
- `CourseControl/src/course_control/authoring/shot_sheet.py` — 资产解析、指纹、问题定位、编译、复核报告
- `CourseControl/src/course_control/validators.py` — V-45～V-47
- `CourseControl/src/course_control/cli/authoring.py` — `shot-sheet`
- Schema：`shared/schemas/storyboard.schema.json`
- 测试：`CourseControl/tests/test_shot_sheet.py`（9 例）
