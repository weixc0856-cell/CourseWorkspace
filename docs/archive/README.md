# 归档文档

这里的文件**不再作为任何开发依据**，只保留历史决策与证据。当前基线见 [../PRD.md](../PRD.md)。

| 文件 | 原用途 | 归档原因 | 仍然有效的部分 |
| --- | --- | --- | --- |
| `CourseWorkspace-R0-R5改造PRD.md` | R0–R5 改造规格 | R1–R5 已全部落地；文件中“未执行”“R4/R5 未提交”等状态已过期 | 状态语义 `skip ≠ pass`、路径规则、V-01~V-21 已迁入 [../PRD.md](../PRD.md) 与 [../ACCEPTANCE.md](../ACCEPTANCE.md) |
| `R5-验收矩阵.md` | R5 阶段的验收证据快照 | 测试数量、HEAD、提交状态均已过期 | 故障注入场景与结论已提炼到 [../ACCEPTANCE.md](../ACCEPTANCE.md) |
| `ContentQA_实施评估.md` | 完整 ContentQA 设计稿 | 本期只交付审查内核；TTS/ASR/公式验证/证据语料未实现 | 审查状态词、只读边界、凭据策略已实现于 `ContentQA/`，见 [../PRD.md](../PRD.md) FR-12 |
| `AI-Blender落地路线图.md` | P0–P9 实施状态 | 状态快照与当前实现不一致 | 已实现能力见 [../TRACEABILITY.md](../TRACEABILITY.md) |
| `AI-Blender自动化三维内容生产技术方案.md` | 通用技术提案 | 包含大量未实现设想，不能作为需求基线 | 已实现的 IR v2 契约见 [../Blender场景任务IR-v2.md](../Blender场景任务IR-v2.md) |

原则：归档文件不修改、不续写；新决策写进 [../DECISIONS.md](../DECISIONS.md)。
