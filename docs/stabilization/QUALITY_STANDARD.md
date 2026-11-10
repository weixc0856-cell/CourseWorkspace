# 质量标准（QUALITY_STANDARD）

- 日期：2026-11-10
- 关联：C-03、C-04、C-07、C-08、C-10、C-23、C-27、C-29
- 主要实现：`quality.py`、`quality_gates.py`、`subtitles_qc.py`、`review_decisions.py`、`verify.py`

## 1. 四种结论，互不替代

```text
BUILD_PASS        产物生成成功
VERIFY_PASS       必需检查都执行且无 FAIL/BLOCKED/INCOMPLETE
QUALITY_VERIFIED  五个维度全 PASS（无 WARN）
RELEASE_APPROVED  人工 review + release 两次签核
```

任何一层都不能自动推导下一层。`QUALITY_PASS` 仅作为 `VERIFY_PASS` 的兼容名保留。

## 2. 五个维度

| 维度 | 来源 | PASS 条件 |
| --- | --- | --- |
| Q1 内容可信度 | `review/review.json`、`review_cross.json`、`review/decisions.json` | 每条 finding 有裁决，且没有 accepted/deferred |
| Q2 教学有效性 | `quality/teaching-qa.json` 或 `narrative.json` | 有报告；教学效果仍由人判断 |
| Q3 视听体验 | `quality/media-qc.json`、`audio/mix.json` | 媒体检查 PASS；BGM mix 存在且 PASS |
| Q4 工程完整性 | `final/build-report.json` | verdict=pass 且无 skipped 阶段 |
| Q5 最终交付 | 母版、旁白、字幕、QC、审批 | 全部存在且两次签核完成 |

## 3. WARN 分类

WARN 不再是一种模糊状态：

| `warning_class` | 含义 | 对发布的影响 |
| --- | --- | --- |
| `human_review` | 人必须阅读并判断（内容、教学、媒体冻结） | 不自动阻断；`NEEDS_HUMAN_REVIEW=true` |
| `blocking` | 缺阶段、缺审批等 | `releasable=false` |
| 无 WARN | 维度 PASS | — |

`quality-gate` 输出 `blocking_warnings`、`human_review_items`、`needs_human_review`。

## 4. 字幕链路

```text
Approved script → Approved narration → ASR/alignment → Subtitle correction
→ Timing validation → Visual subtitle QC → Final SRT
```

检查分两层：

- **V-31 完整性**：语言声明、行数、行宽、CPS、cue 数与 draft 一致。
- **V-44 质量**：时间单调/重叠、语言缺失、行宽、行首标点、英文悬空介词、术语跨 cue 断裂、数字跨行断裂、术语表一致性。

V-44 的 error 使 V-31 失败；warning 进入人工复核。禁止删除不匹配 cue 来提高覆盖率。

命令：

```powershell
course-control subtitles-qc --lesson <slug>        # 写 build/<slug>/quality/subtitles-qc.json
course-control subtitles-rewrap --lesson <slug> --write
```

2026-11-10 实测：06 PASS；05 与 01 为 WARN（行首标点、英文悬空介词），无结构错误。01 的 359 条 cue 中，V-44 未发现越界或缺失语言。

## 5. 审查裁决

`review/decisions.json` 是唯一裁决队列：

```json
{
  "schema_version": 1,
  "lesson": "05-transformer-5min",
  "decisions": {
    "contentqa:001:ab12cd34ef": {"decision": "fixed", "by": "Wayne", "at": "…", "note": "…"}
  }
}
```

- 取值：`accepted` / `rejected` / `fixed` / `deferred`。
- `rejected` 必须写理由；`--by` 必填。
- 没有裁决的 finding 一律 `needs_human_review`。
- `accepted` 与 `deferred` 视为仍开放，Q1 不会 PASS。
- 不再新增第六个审查器；现有 ContentQA、cross-review、teaching QA 的输出都汇入这一个队列。

```powershell
course-control review-status --lesson <slug>
course-control review-decide --lesson <slug> --id <finding> --decision fixed --by Wayne
```

## 6. 渲染 QC

- 共享 `verify_media` 检查分辨率、帧率、时长；Manim/Blender/Motion/CodeVideo 同一契约。
- `render:code_video` 另有 codec、pix_fmt、音轨、黑帧、冻结检查。
- 成片阶段 `media-qc`：黑帧、冻结、响度、静音、ASR 覆盖、cue 匹配。
- 黑帧为 BLOCKED；冻结与静音为 WARN（人工判断是否合理）。
- 检查输出在 `build/<slug>/quality/media-qc.json`。

## 7. 发布

```powershell
course-control quality-report --lesson <slug>
course-control quality-gate --lesson <slug>
course-control release-approve --lesson <slug> --stage review --by "<name>"
course-control release-approve --lesson <slug> --stage release --by "<name>"
```

签核记录带 `build_report_sha256`、`final_video_sha256`、`quality_report_sha256`。产物变化后哈希不匹配，读者能发现。

## 8. 不允许

- 为了让测试通过而删除有效检查或 cue。
- 把 `skipped` / `not_run` / `incomplete` 写成 pass。
- 用模型意见代替来源证据。
- 自动批准发布。程序只能证明产物符合契约，不能证明讲得对、看得下去。
