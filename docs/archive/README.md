# 归档文档（本地，不入远程）

本目录保存**已完成项目**的历史报告、验收快照与被取代的设计稿，不再作为开发依据。

- 当前基线：[PRD.md](../PRD.md) · [ARCHITECTURE.md](../ARCHITECTURE.md) · [ACCEPTANCE.md](../ACCEPTANCE.md) · [DECISIONS.md](../DECISIONS.md)
- `.gitignore` 只保留本 README；`docs/archive/**` 下的其他文件**不进入远程仓库**。
- 归档文件不修改、不续写；新结论写进 `DECISIONS.md` 或对应现行文档。

## 目录

| 目录 | 内容 | 状态 |
| --- | --- | --- |
| `legacy/` | R0–R5 改造 PRD、R5 验收矩阵、ContentQA/AI-Blender 早期方案 | 历史 |
| `E6/` | E6 Transformer 四幕基线制作方案 | 已完成 |
| `E6.5/` | Multi-head 设计、数学验证、视觉渲染、成片报告 | 已完成 |
| `R1/` | 基线、引擎验证、性能基准、候选稿索引 | 已完成 |
| `V1/` | V1-B/V1-C 实施报告 | 已完成，结论已并入现行契约 |
| `reviews/` | 向量加法动画评审、统一契约架构审查 | 已完成 |
| `records-2026-11/` | 2026-11-12 文档收敛移出的一次性记录：审计、迁移、会话、已完成评估 | 历史 |
| `decisions/` | Motion Canvas 导出、Remotion staging 的早期决策记录 | 已提炼为 `DECISIONS.md` D-004/D-005 |

## 仍然有效的结论去向

| 归档内容 | 现行位置 |
| --- | --- |
| `skip ≠ pass`、路径规则、V-01~V-21 | [PRD.md](../PRD.md)、[ACCEPTANCE.md](../ACCEPTANCE.md) |
| E6/E6.5 成片与测试结论 | [PROJECT_STATUS.md](../PROJECT_STATUS.md) 历史增量、[TRACEABILITY.md](../TRACEABILITY.md) |
| R1 引擎验证与性能基准 | [DECISIONS.md](../DECISIONS.md) D-053、[PROJECT_STATUS.md](../PROJECT_STATUS.md) |
| V1-B/V1-C 契约 | [课程生产统一契约V1.md](../课程生产统一契约V1.md) |
| Motion Canvas 人工导出 | [DECISIONS.md](../DECISIONS.md) D-004 |
| Remotion staging | [DECISIONS.md](../DECISIONS.md) D-005 |

## 说明

- 归档文件只在本地可读；干净克隆中不存在这些路径，因此现行文档只用代码路径标注“本地归档”，不提供链接。
- 需要把某份归档重新纳入主线时，先复制回 `docs/`、更新引用，再按现行契约评审。
