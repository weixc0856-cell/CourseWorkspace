# CourseWorkspace V2 架构（草案）

- **日期**：2026-11-13
- **状态**：**草案，未生效**。目标形态，用于指导迁移；落地后逐条并入 `docs/ARCHITECTURE.md` 与 `docs/架构-DDD上下文与边界.md`。
- **约束**：单机、Windows、CPU-only 文本模型、8080 唯一推理端口、文件即状态。所有设计默认这些约束不变。

---

## 1. 架构原则

1. **保留现有引擎，不改写已工作的部分。** 渲染、合成、声音、知识抽取、交付已有实现，V2 在其上增加控制面与质量闭环。
2. **模块化单体 + 进程内 Worker。** 不拆微服务。阶段之间通过文件与哈希通信，进程崩溃后可从 checkpoint 恢复。
3. **一个事实只有一个权威。** 内容权威、计划权威、状态权威、制品权威各自唯一，不新增第二套。
4. **状态可恢复。** 任何阶段可重跑，重跑范围由输入输出哈希决定，不靠人记。
5. **质量是独立域。** 生产模块不给自己打分，质量引擎不修改产物。
6. **不可验证即不交付。** 架构上必须存在"停下并报告缺口"的路径，而不是只有"继续"。

---

## 2. 六个架构域

| 域 | 职责 | 核心对象 | 现有包 |
| --- | --- | --- | --- |
| Project | 统一管理生产任务与资源 | ProjectSpec、ProductionOrder | `delivery/order.py`、`delivery/schema.py`、`delivery/state.py` |
| Intelligence | 研究、知识组织、课程规划 | Knowledge IR、CurriculumPlan | `KnowledgeStudio`、`authoring/digest.py`、`authoring/ingest.py` |
| Content | 脚本、讲义、教学材料 | Content IR | `authoring/models.py`、`authoring/pipeline.py`、`content/production.py` |
| Media | 分镜、动画、配音、合成 | Scene IR、Media Asset | `direction/`、`rendering/`、`voice/`、`animatic/`、`locks/` |
| Quality | 评估、诊断、修复规划、回归 | QualityReport、Defect、RepairPlan | `quality/`、`ContentQA` |
| Delivery | 打包、发布、版本 | Manifest、Certificate | `delivery/` |

依赖方向：Project → Intelligence → Content → Media → Delivery；Quality 可读全部产物，只写自己的报告。反向依赖一律禁止。

---

## 3. 与现有 8 个 DDD 上下文的映射

| 现有上下文 | V2 域 | 处置 |
| --- | --- | --- |
| content | Content | 扩展：接入 Content IR，保留 lesson/storyboard 契约 |
| direction | Media | 保留：导演计划、镜头表、语法路由 |
| rendering | Media | 保留：适配器边界不动 |
| voice | Media | 保留 |
| quality | Quality | 重构：在五维报告上增加诊断与修复规划 |
| delivery | Project + Delivery | 拆分职责：订单/状态归 Project，打包归 Delivery |
| platform | 横切 | 扩展：锁、checkpoint、原子写、配置解析 |
| authoring | Intelligence + Content | 扩展：候选稿链接入 ProjectSpec 与自动验收 |
| animatic（落地包） | Media | 保留 |
| locks（落地包） | Media | 保留，接入统一 ArtifactRegistry |

不新增平行的 Producer、Director、Renderer、Quality 包。新能力以子模块形式落在现有包里。

---

## 4. 部署形态

```text
一台机器
├─ course-control (CLI, 模块化单体)
│   ├─ Control plane: project / workflow / scheduler / state / recovery
│   └─ Production plane: research / curriculum / authoring / direction / audio / visual / compose
├─ 本地模型服务 8080 (llama.cpp, 与既有规则一致)
├─ TTS 50000 (VoxCPM2)
├─ 渲染工程 (MotionStudio / RemotionStudio / BlenderStudio / CodeVideoStudio)
└─ 文件系统
    ├─ <内容根>/lessons, build, deliver, runtime, knowledge, audio, projects
    └─ SQLite 索引 (knowledge/ 与 runtime/ 下)
```

没有数据库服务器，没有对象存储服务，没有消息队列。跨进程通信靠文件与 `platform/build_lock`。

---

## 5. 生产状态机

统一状态，不允许模块自造。与现有五态（`pass` / `fail` / `skipped` / `not_run` / `not_applicable`）是两层概念：五态描述**一个检查或阶段的结果**，状态机描述**一个项目的生命周期**。

```text
CREATED → INGESTING → PLANNING → PRODUCING → VALIDATING → DELIVERING → COMPLETED
                          ↑            │            │
                          │            ↓            ↓
                        REPAIRING ←───────────────┘
                          │
                          ├─ RECOVERING → VALIDATING
                          └─ RECOVERY_EXHAUSTED（停止，出缺口报告）
```

映射到现有实现：

| 状态 | 现有对应 |
| --- | --- |
| CREATED | `ProductionState.status = "new"` |
| INGESTING | `KnowledgeStudio ingest`、`authoring digest` |
| PLANNING | `brief` / `outline` / `director-plan` / `producer-order` |
| PRODUCING | `build` 的 `STAGE_ORDER` 各阶段 |
| VALIDATING | `verify`、`media-qc`、`quality-gate`、`subtitles-qc` |
| REPAIRING | 现有 `producer-rebuild`（只有重跑，没有计划） |
| DELIVERING | `package` / `package-verify` |
| COMPLETED | `release-approve` 之后 |
| RECOVERY_EXHAUSTED | 现有熔断规则的落点，尚无实现 |

`awaiting_approval` 在 A3 下不应成为常态停留点；它是 A2 的语义，保留在枚举里以兼容存量订单。

---

## 6. 编排的演进

现状：`platform/checkpoint.py` 的 `STAGE_ORDER` 是固定线性表，每个阶段用配置指纹 + 输入输出哈希判定是否复用。这个语义是对的，缺的是拓扑。

演进路径：

1. 把 `STAGE_ORDER` 换成阶段 DAG（节点 = 阶段，边 = 依赖），线性顺序只是 DAG 的一条默认路径。
2. 复用判定继续用哈希，不引入新的"完成标记"。
3. 恢复粒度从"从某阶段重跑到底"细化到"重跑失败节点的下游受影响子图"。
4. 修复策略表独立于 DAG，放在 Quality 域。

不在 V2 引入外部工作流引擎，理由见 `README.md` §3。

---

## 7. 与外部提案的偏离

| 提案 | 本机做法 | 原因 |
| --- | --- | --- |
| PostgreSQL | SQLite + JSON | 单机、无服务、易备份 |
| Object Storage | 内容寻址文件 + 索引 | 现有 sha256/manifest 已够用 |
| Temporal | CheckpointStore DAG | 语义已具备，缺拓扑 |
| 微服务 | 模块化单体 | 故障面与运维成本 |
| 独立 Worker 集群 | 进程内 Worker + 渲染子进程 | 一台机器 |
| 六个新顶层包 | 现有包内子模块 | 避免平行实现 |

---

## 8. 扩展点

新增能力只允许从以下五个扩展点进入：

1. `rendering/adapters/`：新渲染引擎。
2. `shared/grammars/`：新视觉语法。
3. `prompts/` + `authoring/`：新创作阶段。
4. `quality/`：新检查器（必须实现统一的 `checks[]` 输出）。
5. `shared/schemas/`：新契约（必须带 `schema_version` 与迁移说明）。

其他位置新增顶层模块需要决策记录。
