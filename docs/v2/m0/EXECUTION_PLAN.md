# V2 全量落实执行计划

- **日期**：2026-11-13
- **依据**：[MIGRATION_PLAN_V2.md](MIGRATION_PLAN_V2.md) 的阶段划分，以及 `<内容根>/archive/docs-2026-11/v2/V2-工业化完成度评估.md` §7 的先后顺序。
- **状态标记**：`[x]` 已完成并验证；`[~]` 进行中；`[ ]` 未开始；`[!]` 等待所有者决策。
- **纪律**：每一阶段独立验收；未实跑的不写成通过；同一问题最多 3 次尝试。

---

## 0. 总览

| 阶段 | 目标 | 状态 | 验收 |
| --- | --- | --- | --- |
| M0 | 六份架构基线文件 | `[x]` | 文件可追溯到代码或缺口编号 |
| M1 | 闭环修补 F-1～F-3、F-8、F-9 | `[x]` | 单测通过；三条失败路径有测试 |
| M2 | 真实课程 P5 基线 | `[~]` | 20 分钟课走完八阶段；至少一次增量返工 |
| M3 | ProjectSpec / ArtifactRegistry / RunRecord | `[x]` | 存量课可合成，新项目用真实 spec |
| M4 | 编排 DAG 与恢复 | `[x]` | 注入失败只重跑受影响子图 |
| M5 | 质量缺陷闭环 | `[~]` | 真实缺陷可诊断、修复、复验、停机 |
| M6 | 前端 Intelligence 与 Mode B | `[~]` | 一本书产出 3 集规划；一个主题产出 1 条视频规划 |
| — | 产品边界写进 PRD | `[!]` | 需所有者确认 C-1～C-5 的改法 |

硬依赖：M2 先于 M3；M3 先于 M4；M5 依赖 M2 的真实缺陷样本；M6 依赖 M1–M5。产品边界决策不阻塞 M2，但阻塞 M6 的"无人值守"验收。

---

## 1. M0 文档基线（已完成）

- [x] `docs/v2/m0/` 六份正文 + 索引。
- [x] 外部提案与本机实况的五处偏离已记录（数据库、对象存储、工作流引擎、微服务、集数硬指标）。
- [x] 与现有权威文档的关系写清：落地时并入 PRD / ARCHITECTURE，不另立规范。

## 2. M1 闭环修补（已完成）

### 2.1 F-1 字幕 QC 成为交付门

- [x] `subtitles-build` 写完草稿立即跑 `check_srt`，写 `build/<slug>/quality/subtitles-qc.json`，FAIL 时退出码 1。
- [x] `quality-gate` 读取该报告：缺失 → `incomplete`，FAIL → 硬失败。
- [x] 测试覆盖缺失、失败、通过三条路径。

### 2.2 F-2 报告新鲜度

- [x] 构建报告按 `final/` 产物 sha256 校验。
- [x] `media-qc` 与 `subtitles-qc` 按来源文件哈希（有则用哈希，无则用时间）。
- [x] `quality-report` 与它所依赖的报告做时间比对。
- [x] 过期一律记为 `incomplete`，不采信旧结论。
- [x] 测试覆盖产物变更与字幕变更。

### 2.3 F-3 预览容差

- [x] animatic 新增 `audio_sync_acceptance` 检查，阈值 0.083 s。
- [x] 超过验收阈值但仍在预览容差内时输出 `warn`，不再静默通过。
- [x] 测试覆盖 0.5 s 漂移与 0.05 s 漂移。

### 2.4 F-8 / F-9

- [x] 新增 `docs/五态映射表.md`，`ARCHITECTURE.md` §4.4 链接。
- [x] 修正声音资产、镜头表、TRACEABILITY、`producer/` 的过时路径。
- [x] 统一 V2.0 建议稿与 P5 记录的状态说法。
- [x] `PROJECT_STATUS.md` 增加 2026-11-13 段落。

### 2.5 验证

- [x] CourseControl 单测：567 通过 / 7 跳过（2026-11-13 实跑）。
- [x] `scripts/check.ps1` 全量回归：`check ok`（2026-11-13 实跑，六套工程）。
- [x] 真实课程 `quality-gate` 实跑：`aging-evolution` 首次报 `subtitles.qc` 缺失（incomplete），补跑 `subtitles-qc` 后通过；无产物变更。

## 3. M2 真实课程基线（下一步）

### 3.1 选课

候选：内容根下已有构建产物、时长接近 20 分钟、字幕启用的课程。优先选不需重渲染即可复验的课；若必须重渲染，先估算墙钟。

### 3.2 执行顺序

1. `course-control validate --lesson <slug>`，记录全部 warning。
2. `course-control animatic --lesson <slug>`，记录 `audio_sync` 与 `audio_sync_acceptance`。
3. `course-control lock` + `lock-status`，记录有无漂移。
4. `course-control verify --lesson <slug>`，记录失败项。
5. `course-control quality-report --lesson <slug>`。
6. `course-control quality-gate --lesson <slug>`，确认 Q1–Q5 无 `incomplete` 或列出原因。
7. `course-control package --lesson <slug>` + `package-verify`。
8. 任一素材或旁白改动后，重跑受影响阶段，记录实际重跑范围。

### 3.3 产物

- 一份 `docs/v2/m0/P5-RUN-<date>.md` 记录：每阶段耗时、人工动作、失败点、重跑范围。
- 至少一条真实的缺陷样本，供 M5 使用。

### 3.4 已跑的前置证据（2026-11-13）

在 `aging-evolution`（145.367 s，12 镜头，字幕 32 条）上做了非破坏性实跑：

| 命令 | 结果 | 说明 |
| --- | --- | --- |
| `validate` | `no issues` | |
| `subtitles-qc` | `PASS`，32 cues | 新交付门在真实课上生效 |
| `quality-gate`（首次） | `incomplete`：`subtitles.qc` 缺失 | 证明 F-1 会拦住存量课的漏检 |
| `quality-gate`（补跑后） | `verification: pass`（当时） | 报告与产物一致 |
| `verify` | V-10…V-17 全部 pass / not_applicable | 无回归 |
| `quality-report` → `quality-gate` | Q1/Q2 人审、Q5 `blocking`（发布签核未完成） | 与"程序通过、发布未批准"的既有语义一致 |
| `animatic` | `ok: False`，12 个 placeholder | 该课的 `build/` 没有幻灯片 PNG 或片段，属素材缺失；不是代码回归 |

结论：M1 的改动在真实课程上没有误伤；M2 的完整 P5 还需要一门**素材齐全的 20 分钟课**。`aging-evolution` 只作为前置 smoke，不计入 P5。

### 3.5 不做什么

- 不为了让门禁通过而修改阈值或预期。
- 不在 M2 期间写自动创作代码。

## 4. M3 契约落地（已完成）

- [x] `delivery/project.py`：ProjectSpec Pydantic 模型；`shared/schemas/project-spec.schema.json` 已导出。
- [x] `course-control project-validate`：校验 `project.yaml`；`project-show` 打印解析结果。
- [x] 合成路径：没有 `project.yaml` 的课由 `lesson.yaml` 合成，标记 `synthesized: true`，执行等级默认 `A0`。
- [x] `platform/artifacts.py`：ArtifactRegistry 读写、按 id 幂等登记、从 build 目录重建、缺失只标记不删除。
- [x] `platform/run_record.py`：`runtime/runs/<run-id>/run.json`，阶段历史内联，原子写。
- [x] CLI：`project-validate`、`project-show`、`artifact-index`、`run-start`、`run-status`。
- [x] 测试：10 条项目契约、5 条制品索引、4 条运行记录。

验收：内容根 15 门存量课全部可合成 ProjectSpec（`project-show --lesson` 实跑）；新项目样例通过 `project-validate`；`artifact-index` 在 `aging-evolution` 上索引 120 个产物；`run-start` / `run-status` 实跑通过。

**说明**：这些契约目前不被构建流水线读取，属于纯增量。M2 的真实运行数据到手后，再决定哪些字段写入实际调度。

## 5. M4 编排拓扑（已完成核心）

- [x] `STAGE_DEPS` 声明阶段 DAG，`STAGE_ORDER` 保留为拓扑默认路径。
- [x] `--resume-from` 只强制 origin 及其下游；兄弟渲染阶段不再被连带重跑。
- [x] `CheckpointStore.invalidate_from` 按 DAG 失效，不再按线性切片。
- [x] 测试：依赖顺序、兄弟隔离、失效范围。
- [ ] `RECOVERY_EXHAUSTED` 的持久化落点（依赖 M5 的修复计数，未做）。

说明：默认构建路径不变；变化只发生在显式 `--resume-from` 与失效计算。M2 的真实返工数据到手后，再校准范围。

## 6. M5 质量闭环（核心已完成）

- [x] 统一 defect schema：`quality/defect.py`，从 build-report / media-qc / subtitles-qc / quality-report 收集，id 按症状哈希稳定。
- [x] `quality/repair.py`：八类归因映射到四类策略 + stop；`attempt > 3` 直接 blocked；无法归因不猜。
- [x] `quality/regression.py`：按 defect id 差分 fixed / still_open / introduced。
- [x] CLI：`quality-diagnose`、`quality-repair-plan`、`quality-regression`。
- [x] 测试：10 条，覆盖收集、id 稳定、策略映射、尝试上限、回归差分。
- [ ] 影响面反查（需要 ArtifactRegistry 的 inputs 真正被生产者写入）。
- [ ] 修复执行器与自动重跑（目前只出计划，不改产物）。
- [x] 交付证书：`quality/certificate.py` + `quality-certificate`，verdict 由 defects + gate + quality-report 哈希决定。
- [ ] 用 M2 的完整缺陷样本重放。

## 7. M6 前端 Intelligence 与 Mode B（契约层已完成）

- [x] Knowledge IR：`KnowledgeStudio/src/knowledge_studio/knowledge_ir.py`，概念/先修/claim/证据/冲突，`knowledge-ir.schema.json`。
- [x] 课程规划校验：`curriculum.py` 契约在 `knowledge_ir` 内，覆盖、先修顺序、集数窗口；`curriculum.schema.json`。
- [x] CLI：`knowledge-ir-validate`、`curriculum-validate`、`schemas`。
- [x] 测试：11 条，覆盖重复、先修未知、环、证据充分性、冲突与解决、覆盖与顺序。
- [ ] 自动研究与概念提取（需要模型调用与真实来源，未做）。
- [ ] 主题视频 `profile: news` 的流程实现（契约已支持 `topic_video`）。
- [ ] A3 执行器：`run.json` 已有，自动诊断/修复/重试未接。
- [ ] 验收：一本书前 3 集规划；一个主题 1 条视频规划。需要真实书籍与主题，等所有者提供。

## 8. 等待决策

- [!] 产品边界 C-1～C-5：PRD §1 目标、§1.2 非目标、硬约束 1 与 4 的改写。草案见 `PRODUCT_SPEC_V2.md` §3。
- [!] 生成内容的版权与署名。
- [!] 第一批试点规模与选课。

在决策落地前，M1–M5 可以全部推进；M6 的 A3 验收不能宣称成立。
