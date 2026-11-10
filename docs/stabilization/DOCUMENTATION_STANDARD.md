# 文档标准（DOCUMENTATION_STANDARD）

- 日期：2026-11-10
- 关联：C-22、C-27
- 状态：已实施；索引与状态标记已整理

## 1. 权威层级

| 层级 | 文档 | 规则 |
| --- | --- | --- |
| 产品基线 | `docs/PRD.md` | 需求编号与范围；其它文档不得改写需求 |
| 架构 | `docs/ARCHITECTURE.md`、`docs/stabilization/ARCHITECTURE_FINAL.md` | 模块职责与数据流 |
| 契约 | `docs/课程生产统一契约V1.md`、`docs/contracts/`、`shared/schemas/` | 字段级权威 |
| 决策 | `docs/DECISIONS.md` | 编号唯一、时间顺序；过期决定标记被取代 |
| 问题台账 | `docs/stabilization/MASTER_REMEDIATION.md` | 唯一状态来源 |
| 规范 | `docs/stabilization/*_STANDARD.md` | 当前生效标准 |
| 审计与评估 | `docs/audit/`、`docs/evaluations/` | 记录当时证据，不随代码更新 |
| 归档 | `docs/archive/` | 只读；引用缺失证据按历史处置 |

## 2. 状态标记

每份规范头部必须写：

- 日期；
- 状态（已实现 / 部分实现 / 草案 / 已废弃）；
- 关联问题编号与决策编号。

失效规范不删除，移入 `docs/archive/` 并在首行写 `> 已废弃：由 <新文档/决策> 取代（日期）`。仍然有效的旧规范必须在索引中标注"现行"。

## 3. 数字不手写

页面数、镜头数、cue 数、测试数、交付文件数由脚本产生：

```powershell
course-control stats --lesson <slug> --write
```

报告写入 `build/<slug>/quality/stats.json`。文档引用数字时写来源与日期，例如：

> 01：12 页、5 个 storyboard 镜头、54 段旁白、359 条 cue、1195.61 s（`stats`，2026-11-10）。

测试数量以 `check.ps1` 的实跑输出为准；不把上一轮的数字留在验收表里。

## 4. 证据引用

- 引用 `build/...` 路径时，路径必须存在于当前机器，或被 `docs/audit/evidence-decisions.yaml` 分类。
- 引用成片、报告、清单时写日期与哈希，不只写路径。
- 不把"文件存在"写成"已验收"。

## 5. 索引

`docs/README.md` 是入口。新增规范必须同时更新索引；`docs/stabilization/` 下的权威入口见文档末尾的清单。

## 6. 审查报告

不再为同一个问题新增多份独立审查报告。新发现写入 `MASTER_REMEDIATION.md`：

1. 分配新编号（C-31 起）或关联已有编号；
2. 写根因、影响模块、修复、验收；
3. 更新状态与证据。

审计报告只记录原始证据；状态在总台账更新。

## 7. 本轮修正的过期陈述

| 文档 | 原陈述 | 现在 |
| --- | --- | --- |
| `docs/evaluations/FRONTEND_ASSESSMENT.md` | "Motion Canvas 人工导出，没有 CLI" | 无头导出由 `render-headless.mjs` 完成（D-054） |
| 同上 | "看进度：`build/report.json`" | `build/<slug>/final/build-report.json` |
| `docs/PRD.md` §1.2 | "ASR 是明确非目标" | 保留非目标，并注明 `asr-align` 只作可选质检 |
| `docs/ARCHITECTURE.md` | MotionStudio 不自动导出 | 已改为无头导出（D-054） |
