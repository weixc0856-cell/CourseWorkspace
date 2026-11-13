# M0 架构审计：V2 产品升级的六份基线文件

- **日期**：2026-11-13
- **来源**：外部对仓库的只读审计（2026-11-13）+ 所有者确认的升级方向 + 本机代码复核
- **地位**：**规划与审计，不是生效规范**。本目录任何结论，只有写进 `docs/PRD.md`、`docs/ARCHITECTURE.md`、`docs/TRACEABILITY.md` 并经 `docs/DECISIONS.md` 记录后，才具有约束力。这与 D-089 第 4 条一致：`docs/v2/` 只留规划与审计，不成长为第二套规范。
- **与 V2.0 的关系**：`工业化生产流程V2.0`（D-089）解决的是**生产流程工业化**，P0–P4 已落地，P5 未闭环。M0 处理的是**产品责任边界升级**（从"人工撰写内容 → 视频"到"原始输入 → 研究 → 创作 → 生产 → 验收"）。两者是叠加关系，M0 不推翻 P0–P5，也不替代 `V2-工业化完成度评估.md` 的 F-1～F-10。

---

## 1. 文件索引

| 文件 | 回答的问题 | 与现有权威文档的关系 |
| --- | --- | --- |
| [PRODUCT_SPEC_V2.md](PRODUCT_SPEC_V2.md) | 产品是什么、两种模式、质量与自动化定义 | 与 `docs/PRD.md` v1.0 有直接冲突，冲突点已逐条列出，需决策后才可改写 PRD |
| [ARCHITECTURE_V2.md](ARCHITECTURE_V2.md) | 目标架构、六个架构域、与现有 8 上下文映射 | 目标形态是 `docs/ARCHITECTURE.md` 的增量，不新建平行架构 |
| [DATA_CONTRACTS_V2.md](DATA_CONTRACTS_V2.md) | ProjectSpec、三层 IR、Artifact、Quality 契约 | 新契约进 `shared/schemas/`，旧契约保持 `schema_version` 兼容 |
| [PRODUCTION_WORKFLOW_V2.md](PRODUCTION_WORKFLOW_V2.md) | Course / Topic Video 两种模式的统一工作流 | 扩展现有 `docs/WORKFLOW.md` 与 `docs/生产路线.md` |
| [QUALITY_SPEC_V2.md](QUALITY_SPEC_V2.md) | 质量标准、缺陷体系、诊断修复回归、交付条件 | 把 `docs/知识视频质量基准.md` 的三层验收变成可执行闭环 |
| [MIGRATION_PLAN_V2.md](MIGRATION_PLAN_V2.md) | 现有模块保留 / 扩展 / 重构 / 新增 / 淘汰 | 本目录最重要的文件，逐模块给出结论 |
| [EXECUTION_PLAN.md](EXECUTION_PLAN.md) | M0–M6 的任务、验收与当前状态 | 执行台账；每阶段完成后更新 |

阅读顺序：先 MIGRATION_PLAN_V2，再回看其余五份。迁移计划决定哪些设计真的会被实现。

---

## 2. 已核实的事实基线（2026-11-13）

只列与架构判断直接相关、本轮用代码或文件核对过的事实：

| 项 | 实测 | 核对方式 |
| --- | --- | --- |
| CourseControl Python 源文件 | 217 个（不含 `.venv`） | `find CourseControl -name "*.py" -not -path "*/.venv/*"` |
| CLI 命令 | 80 个 | `grep -c "@app.command"` 系列 |
| DDD 上下文 | 8 个（content / direction / rendering / voice / quality / delivery / platform / authoring），另有 animatic、locks 两个落地包 | `docs/架构-DDD上下文与边界.md`、`src` 目录 |
| 共享 JSON Schema | 28 个 | `shared/schemas/` |
| 单测 | 605 通过 / 7 跳过（2026-11-13 实跑，CourseControl 单包） | 本轮实跑 |
| 内容根 | 仓库外内容根（`course-control content-root` 可查），`git ls-files lessons` 只剩 README | §1 同源 |
| `topic_video` / `ProjectSpec` / `artifact registry` / DAG | 全仓库零命中（排除 `.venv`、`node_modules`） | `grep -rniE ...` |
| 质量模块 | 五维报告（Q1 内容可信度 / Q2 教学有效性 / Q3 视听体验 / Q4 工程完整性 / Q5 最终交付），无诊断、修复、回归 | `quality/quality.py:297-305` |
| 编排 | 固定线性 `STAGE_ORDER` + 哈希 checkpoint，支持 `--resume` | `platform/checkpoint.py:27-38` |
| 制品登记 | manifest + sha256 分散在 `delivery/package.py`、`delivery/schema.py:75-84`、`platform/checkpoint.py` | 代码 |
| 前端候选稿 | `authoring/models.py` 已有 Brief / Outline / NarrationScript / SourceDigest / ApprovalFile | 代码 |

---

## 3. 外部提案里被本机实况改写的五处

外部的目标架构假设了云服务与分布式组件。本机是单机、CPU-only、文件即状态、8080 唯一模型端口，直接照搬会引入无法运维的依赖。以下五处按实况改写，理由写在各文件里：

| 外部提案 | 本机采用 | 理由 |
| --- | --- | --- |
| PostgreSQL | SQLite（KnowledgeStudio 已在用 FTS5）+ JSON 文件 | 单机、无服务进程、可整目录备份；多进程写入用现有 `platform/build_lock` |
| Object Storage | 内容寻址文件 + `ArtifactRegistry` 索引 | 产物本来就在 `build/`、`deliver/`；sha256 已有 |
| Temporal / 持久化 DAG | 扩展 `CheckpointStore` 为阶段 DAG，文件即状态 | 现有 checkpoint 已按输入输出哈希判定复用，语义正确 |
| 十几个微服务 | 模块化单体 + 进程内 Worker | 一台机器，拆服务只会增加故障面 |
| 课程数 30–50 作为规划目标 | 保留为目标区间，但不作硬门禁 | 与 D-089"时长、镜头数不是闸门"一致 |

---

## 4. 需要所有者决策的事项

M0 文档写完了，下面这些仍然没有定，任何一条都不能由我代填：

1. **产品边界**：是否把"无人工审批、无人值守"写进 PRD 目标，并同步修改 §1.2 非目标与硬约束 1、4。
2. **内容所有权**：自动生成课程与主题视频的版权、署名、审校责任如何界定。现有硬约束 1 是"内容归用户所有、改语义必须先问"，无人值守下需要新的表述。
3. **不可验证事实的停机线**：证据不足时停在哪一步、留什么给人看。
4. **第一批试点规模**：一门 20 分钟课，还是一本书的前 3 集。
5. **旧课程处置**：13 门存量课是否迁到 ProjectSpec，还是只对新项目生效。

---

## 5. 本目录不做的事

- 不改代码、不改课程内容、不改 PRD。
- 不把任何未实现的契约写成"已完成"。
- 不把外部审计的测试数字当成本机结果。本目录引用的测试数字只有一处，且有日期与范围。
