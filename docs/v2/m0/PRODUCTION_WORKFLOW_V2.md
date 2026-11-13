# CourseWorkspace V2 生产工作流（草案）

- **日期**：2026-11-13
- **状态**：**草案，未生效**。落地后并入 `docs/WORKFLOW.md` 与 `docs/生产路线.md`。
- **关系**：`docs/v2/工业化生产流程V2.0-建议稿.md`（D-089）定义的是**执行工业化的八个阶段与工作包**；本文件定义**两种产品模式如何共用这条线**。两者不冲突，本文件是上层组织方式。

---

## 1. 共同内核：八阶段

两种模式走同一内核，差别在阶段 2 和 3 的组织策略。

| # | 阶段 | 输入 | 输出 | 现有命令/模块 | 缺口 |
| --- | --- | --- | --- | --- | --- |
| 1 | INGEST | ProjectSpec 的 sources | 归一化文本、页图、来源元数据 | `KnowledgeStudio ingest`、`authoring digest`、`course-control ingest` | web 来源与跨来源去重 |
| 2 | UNDERSTAND | 归一化材料 | Knowledge IR（概念、主张、证据、先修） | `KnowledgeStudio` 检索、`spancheck` | 概念层、主张层、冲突处理 |
| 3 | PLAN | Knowledge IR | 课程大纲 / 叙事结构 | `brief`、`outline`、`narrative-plan`、`director-plan` | 自动规划与覆盖检查 |
| 4 | AUTHOR | 计划 + Knowledge IR | 脚本、讲义、页面、claim 引用 | `script`、`content-draft` | 无人审批下的验收替代 |
| 5 | DIRECT | 脚本 | 镜头表、视觉语法、引擎路由 | `shot-sheet`、`director-plan`、`animation-score` | Shot Sheet 与导演计划合并（F-5） |
| 6 | PRODUCE | 导演计划 | 页面、动画、配音、字幕、时间线 | `build`、`animatic`、`narration-build`、`subtitles-build` | 声音真实合成验证（F-9 相关） |
| 7 | VERIFY | 全部产物 | 质量报告、缺陷、修复计划 | `verify`、`media-qc`、`subtitles-qc`、`quality-gate`、`teaching-qa` | 诊断、修复、回归闭环 |
| 8 | DELIVER | 通过验收的产物 | 交付包、证书 | `package`、`package-verify`、`release-approve` | 自动发证 |

阶段 1–5 是 V2 的主要新增面；阶段 6–8 已有实现，主要补闭环。

---

## 2. Mode A：课程生产

### 2.1 流程

```text
ProjectSpec(course)
  → INGEST      书/论文/网页入库，页码校准，来源元数据
  → UNDERSTAND  概念图、先修关系、claim/evidence 表、覆盖缺口
  → PLAN        课程大纲 → 分集列表（每集目标、覆盖的概念、时长区间）
  → 对每一集：
      AUTHOR    脚本 + 页面 + claim 引用
      DIRECT    镜头表 + 语法 + 引擎
      PRODUCE   截图/动画/三维/配音/字幕/时间线
      VERIFY    五维 + 技术检查
      DELIVER   单集交付包
  → 全课程一致性验收（跨集概念不重复、先修不断链、术语统一）
  → 课程包交付
```

### 2.2 课程级验收（新增）

单集验收之外，课程必须通过三项跨集检查：

1. **覆盖**：大纲里每个核心概念至少被一集覆盖；未覆盖的列出理由。
2. **先修**：每集引用的先修概念，必须在更早的集出现，或标为"假定已知"。
3. **一致性**：术语表、单位、色标、命名在所有集统一。现有 `projects/<系列>/` 下的通用参数文件是这一项的权威来源。

### 2.3 与现有 30 集系列的关系

汽车空气动力学系列已有人工规划的 COURSE_MAP 与通用参数文件。V2 不重做规划，先把这条人工流程里的重复环节（分集展开、逐集 brief/outline、镜头预算）自动化，产物与原流程一致。

---

## 3. Mode B：主题视频生产

### 3.1 流程

```text
ProjectSpec(topic_video)
  → INGEST      资料入库（文章、论文、报告）
  → UNDERSTAND  研究结论、事实核查、争议点
  → PLAN        叙事结构（钩子 → 冲突 → 解释 → 证据 → 收束）
  → AUTHOR      脚本
  → DIRECT      分镜、视觉方案、引擎
  → PRODUCE     媒体生产
  → VERIFY      质量验收
  → DELIVER     视频包
```

与课程模式的区别：PLAN 阶段输出的是叙事结构而不是知识覆盖表；VERIFY 阶段看叙事完整性与信息密度，不看学习效果指标。

### 3.2 与新闻视频的关系

`docs/新闻视频生产流程.md` 已经是主题视频的一个 profile（时效性强、来源以新闻为主、通常 3–8 分钟）。V2 的实现路径是把它参数化为 Mode B 的 `profile: news`，而不是再写第三条流程。

---

## 4. 运行协议

### 4.1 一次运行 = 一个 run 目录

```text
runtime/runs/<run-id>/
├─ run.json          # 项目、模式、执行等级、资源限制、阶段历史（stages 数组）
└─ logs/
```

阶段历史写在 `run.json` 里，不再另开 `stages.json`：两个文件描述同一件事，迟早会不一致。缺陷记录在 M5 落地后写 `defects.json`。`run.json` 是恢复依据；`build/` 下的 checkpoint 继续作为阶段级复用依据，两者不互相替代。

### 4.2 幂等与恢复

- 同一 ProjectSpec + 同一输入哈希 = 同一产物集合。
- 恢复从失败节点开始，只重跑其下游受影响子图。
- 任何阶段不得依赖"上次跑过"的内存状态。

### 4.3 失败策略

| 失败类型 | 处理 |
| --- | --- |
| 可重试（网络、临时锁、渲染进程崩溃） | 退避重试，最多 3 次 |
| 可修复（质量缺陷） | 生成 RepairPlan，重跑受影响范围 |
| 不可修复（证据不足、契约冲突） | 停止，产出缺口报告 |
| 未知 | 停止，保留现场 |

任何类型都不允许"跳过并标记通过"。与硬约束 2 一致。

### 4.4 资源策略

沿用现有规则，不新增并行度：

- 本地模型 8080 串行，经 `shared/ai_runtime` 跨进程锁。
- GPU 独占：ComfyUI 与三维/图像生成不并发。
- TTS 50000 串行。
- 一次运行内，渲染与模型调用不同时抢占 CPU。

---

## 5. 人的位置

A3 下只有两个介入点：

1. **开工前**：给材料、选题、项目级标准（`project.yaml`）。
2. **成品后**：看成品，决定接受或拒收。拒收必须写理由，理由进入下一轮规划。

中间不设审批节点。这不是"减少把关"，是把把关从过程挪到验收，并由程序承担过程内的判断。

---

## 6. 与现有文档的关系

| 现有文档 | 本文件的关系 |
| --- | --- |
| `docs/WORKFLOW.md` | 本文件是它的上游组织方式；落地时合并 |
| `docs/工业化生产流程V2.0-建议稿.md` | 本文件复用其工作包与阶段定义，不重复 |
| `docs/生产路线.md` | Slide-first 等路线建议在两种模式下都适用 |
| `docs/新闻视频生产流程.md` | 成为 Mode B 的 `news` profile |
| `docs/课程生产统一契约V1.md` | 契约细节仍以该文件为准 |

---

## 7. 落地顺序

1. 先用现有命令手工跑通一次 Mode A 的 1–8 阶段（P5），记录每一步的真实耗时与人工动作。
2. 把人工动作里确定性的部分写成脚本，不确定的部分做成 `run.json` 的显式参数。
3. 再引入 ProjectSpec 与自动规划，避免在没有真实基线时设计抽象。
