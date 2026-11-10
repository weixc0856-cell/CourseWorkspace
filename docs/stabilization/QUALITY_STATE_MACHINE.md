# 质量状态机（Quality State Machine）

- 日期：2026-11-10
- 状态：已实现；05/06/nvda 已按新语义重算
- 关联审计：`docs/audit/ARCHITECTURE_CONFLICTS.md` C-02、C-03
- 关联决策：D-071

---

## 1. 问题

之前有四个"通过/完成"混在一起：

- `build-report.verdict=pass`：产物生成成功。
- `quality-report.QUALITY_PASS=True`：所有维度是 PASS 或 WARN。
- `quality-gate.releasable=true`：hard 与 grammar 都通过。
- producer `state.status=delivered`：交付清单齐全且订单已批准。

它们语义不同，却都读作"可以发"。05 就是例子：`QUALITY_PASS=True`，同时 Q1/Q2/Q3/Q5 全是 WARN；nvda 的 `media-qc` 是 `INCOMPLETE`，但 `build-report.verdict=pass`。

## 2. 状态定义

| 状态 | 含义 | 能否发布 | 实现 |
| --- | --- | --- | --- |
| `BUILD_PASS` | 所有预期产物生成成功 | 否 | `quality-report` |
| `VERIFY_PASS` | 必需检查都执行，且无 FAIL/BLOCKED/INCOMPLETE；WARN 允许 | 否 | `quality-report` / `quality-gate` |
| `VERIFY_WARN` | `VERIFY_PASS` 为真且至少一个 WARN | 否 | `quality-report` |
| `VERIFY_INCOMPLETE` | 任一必需检查未执行 | 否 | `quality-report` / `quality-gate` |
| `VERIFY_FAIL` | 任一必需检查失败，或 build 失败 | 否 | 同上 |
| `QUALITY_VERIFIED` | 所有维度都是 PASS（无 WARN） | 否 | `quality-report` |
| `REVIEW_APPROVED` | `VERIFY_PASS` 且有人工 review 签核 | 尚需发布签核 | `release-approve --stage review` |
| `RELEASE_APPROVED` | review 已批准且 release 已签核 | 是 | `release-approve --stage release` |

`QUALITY_PASS` 保留为兼容名，等价于 `VERIFY_PASS`；新代码不应再把它当作"质量已验证"。

## 3. 三条硬规则

1. **WARN 不等于 FAIL，但必须展示。** `quality-report` 的 `risks` 与 `quality-gate` 的 `grammar_warnings` 都列出。
2. **SKIP 不等于 PASS。** `quality-gate` 把 `incomplete` / `not_run` / `blocked` 收进 `incomplete_failures`；`releasable` 为假。
3. **INCOMPLETE 不能通过任何默认逻辑变成可发布。** `release-approve` 在 `VERIFY_PASS=false` 时 exit 2；`package` 也要求 build-report / media-qc / narration meta。

## 4. 人工签核

```powershell
course-control release-approve --lesson <slug> --stage review --by "<name>"
course-control release-approve --lesson <slug> --stage release --by "<name>"
```

写入：

- `build/<slug>/quality/review-approval.json`
- `build/<slug>/quality/release-approval.json`

字段：`stage`、`decision`、`approved_by`、`approved_at`、`note`、`build_report_sha256`、`final_video_sha256`、`quality_report_sha256`。

- `release` 阶段要求 `REVIEW_APPROVED=true`，否则拒绝。
- `--decision rejected` 可记录驳回；`RELEASE_APPROVED` 保持 false。
- 签核记录包含当时产物的哈希，产物改动后哈希不匹配，读者能发现。

## 5. 现有结果

| 课程 | BUILD | VERIFY | INCOMPLETE | QUALITY_VERIFIED | REVIEW | RELEASE |
| --- | --- | --- | --- | --- | --- | --- |
| 05 | true | true（WARN） | false | false | false | false |
| 06 | true | false | true（Q1/Q2） | false | false | false |
| nvda | true | false | true（Q3 ASR） | false | false | false |
| aging | true | true（WARN） | false | false | false | false |

05 的 `QUALITY_PASS` 仍为 true，但这只表示"没有 INCOMPLETE"；它的 Q1/Q2/Q3/Q5 仍是 WARN，发布仍需两次人工签核。

`quality-gate` 现在读取 `quality-report.json`：Q1/Q2 的 `INCOMPLETE` 会进入 `incomplete_failures`，06 因此 `releasable=no`；WARN 维度进入 `quality_warnings`，05 仍可 `releasable=yes`（等待人工签核）。如果 `quality-report.json` 不存在，gate 记 `Q0` incomplete 并阻止发布。

## 6. 兼容性

- `quality-report.json` 新增字段，不删除旧字段；旧读者仍能读 `QUALITY_PASS`。
- `quality-gate.json` 新增 `incomplete`、`grammar_warnings`、`verification_status`；`releasable` 更严格。
- `release-approval.json` 以前没有写入命令，本轮补上；旧文件只要有 `decision=approved` 与非空 `approved_by` 仍被识别。

## 7. 验收

1. 静止画面 + 满 beats 的样例，`quality-gate` 的 `verification_status` 与实际检查一致，`releasable` 不因 WARN 而真。
2. nvda 的 `quality-gate` 输出 `verification: incomplete`、`releasable: no`。
3. `release-approve --stage release` 在没有 review 批准时 exit 2；补 review 后 exit 0，`RELEASE_APPROVED=true`。
4. `QUALITY_VERIFIED` 只有在五个维度全 PASS 时才为真；05/06/nvda 当前都是 false。
