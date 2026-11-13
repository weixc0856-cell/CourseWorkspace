# CourseWorkspace V2 质量标准与质量引擎（草案）

- **日期**：2026-11-13
- **状态**：**草案，未生效**。落地后并入 `docs/知识视频质量基准.md` 与 `docs/ACCEPTANCE.md`。
- **原则**：生产模块不给自己打分；质量引擎只读产物、只写报告；不通过就不交付。

---

## 1. 质量维度

两种模式共用一套基础设施，维度权重不同。

| 维度 | 课程模式 | 主题视频模式 | 现有实现 |
| --- | --- | --- | --- |
| K 知识准确 | 必须 | 必须 | Q1 内容可信度（`quality/quality.py:_q1`）、ContentQA |
| P 教学有效 | 必须 | 不适用 | Q2 教学有效性、`teaching-qa` |
| N 叙事完整 | 适用 | 必须 | 无独立维度，现由 Q2 兼任 |
| V 视听质量 | 必须 | 必须 | Q3 视听体验、`media-qc`、`animation-score` |
| T 技术完整 | 必须 | 必须 | Q4 工程完整性、`verify` |
| D 交付完整 | 必须 | 必须 | Q5 最终交付、`package-verify` |

V2 的第一个改动是**把 N 从 Q2 里拆出来**。主题视频没有"学习效果"，硬套教学指标会失真。

---

## 2. 缺陷体系

所有检查输出统一为 defect，不再直接输出"通过/不通过"。

```json
{
  "id": "DEF-0042",
  "dimension": "K",
  "severity": "blocking",
  "stage": "author",
  "artifact_ids": ["art.script.transformers-01"],
  "symptom": "claim.attention-scales-by-sqrt-d has single source",
  "root_cause_hint": "evidence_collection",
  "evidence": ["knowledge/claims.json#claim.attention-scales-by-sqrt-d"],
  "status": "open"
}
```

严重级：

| 级别 | 定义 | 交付影响 |
| --- | --- | --- |
| blocking | 事实错误、不可验证主张、交付缺项、时间线错位 | 阻断 |
| major | 表达不清、视觉层级混乱、字幕可读性差 | 阻断（可申请风险接受） |
| minor | 排版瑕疵、非关键术语不统一 | 记录，不阻断 |
| note | 优化建议 | 记录 |

`blocking` 与 `major` 的数量不设阈值。质量不按比例通过。

### 2.1 缺陷来源映射

| 来源命令 / 报告 | 产出维度 | 备注 |
| --- | --- | --- |
| `verify`（V-01～V-47） | T | 已有 |
| `media-qc` | V、T | 已有 |
| `subtitles-qc` | V | 已有，需接入交付门（F-1） |
| `teaching-qa` | P | 已有 |
| `animation-score` | V | 已有，指标不是门禁 |
| ContentQA findings | K | 候选意见，需证据升级才成为 defect |
| `claims.json` 规则检查 | K | 新增 |
| 课程级覆盖 / 先修 / 一致性 | P | 新增 |

---

## 3. 诊断

诊断要做三件事：定位、归因、确定影响面。

1. **定位**：defect 必须引用具体 artifact id 与检查项 id。
2. **归因**：给 `root_cause_hint`，枚举固定为 `source_data` / `evidence_collection` / `script_length` / `visual_grammar` / `render_engine` / `audio_timing` / `contract_violation` / `unknown`。未知归因允许存在，不能编造。
3. **影响面**：按 ArtifactRegistry 的 `inputs` 反查下游，得到候选 `rebuild_scope`。

归因规则第一版用确定性映射表，不引入模型判断。等真实缺陷样本积累到一定数量，再考虑统计归因。

---

## 4. 修复策略

| 缺陷类型 | 策略 | 重跑范围 |
| --- | --- | --- |
| 来源不足 | `substitute_source`：换来源或补充研究 | 知识 → 内容 → 受影响的集 |
| 主张与来源冲突 | `reauthor_segment`：改写该段脚本 | 脚本段 → 镜头 → 配音 → 字幕 → 合成 |
| 脚本超时 | `reauthor_segment` + 时长重算 | 同上 |
| 视觉不达标 | `re_render_shot` | 受影响镜头 |
| 音频/字幕错位 | `rerun_stage` | 配音 / 字幕 / 合成 |
| 契约违规 | 停止，交人 | 无 |
| 未知归因 | 停止 | 无 |

规则：

- 每次修复记录 `attempt`，同一缺陷第 3 次仍失败即 `RECOVERY_EXHAUSTED`，按项目熔断规则停手。
- 修复不得修改检查预期、不得降低阈值、不得把 fail 改成 skipped。
- `accepted_risk` 只能由所有者显式记录。

---

## 5. 回归

修复后必须复验，且复验结果要能回答"有没有引入新问题"。

1. **范围**：修复的 defect + 受影响产物上的全部检查。
2. **对比**：修复前后的 defect 集合做差。新增 defect 一律视为回归。
3. **重复**：同一 defect 重现且无变化时，不再自动重试，转人工。
4. **产物新鲜度**：所有报告必须记录输入产物哈希；哈希不匹配的报告直接判 `incomplete`，不读它的结论（对应 F-2）。

---

## 6. 证据充分性

知识维度不靠"另一个模型说对"。

| 状态 | 条件 | 可否交付 |
| --- | --- | --- |
| `supported` | ≥2 条独立证据，或 1 条 primary 证据 + 可复现推导 | 可以 |
| `single_source` | 只有 1 条证据且非 primary | 不可以 |
| `contested` | 来源冲突且未给出采用理由 | 不可以 |
| `contested_resolved` | 冲突已记录，采用理由可审 | 可以 |
| `refuted` | 证据反对该主张 | 不可以 |
| `unverifiable` | 补充研究后仍无法判断 | 不可以，输出缺口报告 |

`span-check` 只证明引用文本出现在来源页，不改变 claim 状态。这一层的边界必须写进实现注释，避免以后被误用。

---

## 7. 门禁规则

| 状态 | 含义 | 是否阻断交付 |
| --- | --- | --- |
| `pass` | 检查执行且通过 | 否 |
| `fail` | 执行且不通过 | 是 |
| `incomplete` | 未能执行或证据不全 | 是 |
| `not_run` | 未执行 | 是 |
| `skipped` | 设计上不适用 | 否，但必须写明原因 |
| `not_applicable` | 该模式下无此项 | 否 |

四条硬规则：

1. `skipped` / `not_applicable` 不能当成 `pass` 统计。
2. 报告必须带新鲜度（输入哈希 + 生成时间），过期报告不采信。
3. 预览阶段的容差不得宽于验收阶段的容差（F-3）。
4. 字幕 QC 从"可选检查"变成交付前置（F-1）。

---

## 8. 不交付条件

出现任意一条即停止，产出缺口报告，不生成交付包：

- 任一维度存在 `blocking` defect。
- 任一必要检查为 `incomplete` 或 `not_run`。
- 任一 claim 状态不在 `supported` / `contested_resolved`。
- 交付包 manifest 有 `missing` 项。
- 修复达到上限（同一缺陷 3 次）。
- 资源限制触发且没有完成全部阶段。

缺口报告必须写明：缺什么、为什么、已经尝试过什么、下一步需要谁决定。

---

## 9. 与现有代码的差异

| 现状 | 目标 | 涉及位置 |
| --- | --- | --- |
| 五维报告，无缺陷对象 | 检查输出 defect，报告由 defect 汇总 | `quality/quality.py`、`quality/media_qc.py` |
| 报告不校验新鲜度 | 报告带输入哈希，门禁校验 | `quality/quality_gates.py:35,65,117` |
| 无修复规划 | RepairPlan + 范围计算 | 新增 `quality/repair.py` |
| 无回归对比 | defect 集合差分 | 新增 `quality/regression.py` |
| `verify` 与 `media-qc` 各自输出 | 统一 defect schema | `content/validators.py`、`quality/media_qc.py` |
| 教学与叙事共用 Q2 | 拆出 N 维 | `quality/quality.py:_q2` |

---

## 10. 指标

用于判断质量引擎本身是否有效，不用于放行单集：

- 缺陷发现率：已知问题样本中被检出的比例。
- 误报率：`blocking` 被所有者驳回的比例。
- 一次修复成功率：RepairPlan 一次通过的比例。
- 回归逃逸：修复后引入且下一轮才发现的问题数。
- 停机准确率：系统停止时确实存在不可验证内容的比例。

这些指标需要真实运行数据，P5 之前没有基线。
