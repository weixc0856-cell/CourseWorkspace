# CourseWorkspace V2 数据契约（草案）

- **日期**：2026-11-13
- **状态**：**草案，未生效**。新契约实现后进入 `shared/schemas/`，并在 `docs/ARCHITECTURE.md` §4 登记。
- **规则**：运行时用 Pydantic（`StrictModel`，`extra="forbid"`），同时导出 JSON Schema 给 CLI、Worker 与测试共用。所有契约带 `schema_version`，旧版本至少保留一个版本周期的读取路径。

---

## 1. 契约分层

| 层 | 对象 | 现状 | 目标 |
| --- | --- | --- | --- |
| 项目 | ProjectSpec | 无 | 新增 |
| 知识 | Knowledge IR | `KnowledgeStudio/models.py` 部分具备 | 扩展 |
| 内容 | Content IR | `authoring/models.py` + `content/production.py` 两套 | 统一引用，不合并文件 |
| 场景 | Scene IR | `storyboard.schema.json` v2、`blender-scene-task`、`shots`、`timeline-v1` | 沿用 |
| 制品 | ArtifactRegistry | manifest + sha256 分散 | 统一索引 |
| 质量 | QualityReport / Defect / RepairPlan / Certificate | 五维报告 | 扩展闭环 |

---

## 2. ProjectSpec（新增）

所有生产任务的唯一入口。存于内容根 `projects/<project-id>/project.yaml`，每门课/每条视频一个。

```yaml
schema_version: 1
project:
  id: transformers-course          # ^[a-z0-9][a-z0-9-]{2,79}$
  mode: course                     # course | topic_video
  title: Understanding Transformers
  language: en                     # 与 D-084 一致：画面与旁白英文，字幕英上中下
  audience: intermediate

input:
  sources:
    - type: book                   # book | paper | report | web | notes | course_material
      uri: sources/transformers.pdf
      authority: primary           # primary | secondary | supporting
    - type: paper
      uri: sources/attention-is-all-you-need.pdf
      authority: supporting
  topic: null                      # mode=topic_video 时必填

production:
  quality_profile: premium         # premium | standard
  course:
    lesson_count: { target: 40, min: 30, max: 50 }
    lesson_seconds: { min: 600, max: 1800 }
  topic_video:
    series: auto                   # auto | single
    target_seconds: 900

media:
  resolution: 1920x1080
  frame_rate: 30
  video_format: mp4
  audio_format: wav                # 内部生产用 wav，交付可转 mp3
  subtitles: [srt, vtt]

delivery:
  include: [videos, audio, transcripts, courseware, exercises, sources, quality_report]

execution:
  autonomy: A3                     # A0 | A1 | A2 | A3，见 PRODUCT_SPEC_V2 §5
  retry_policy: adaptive
  delivery_policy: quality_gated
  limits:
    max_wall_seconds: 14400
    max_api_cost_usd: 0
    max_local_model_calls: 0
    max_disk_gb: 20
```

字段规则：

- `lesson_count` 是规划目标，允许越界但必须写 `justification`。
- `authority` 决定冲突时以谁为准，来源冲突必须显式登记，不能静默择一。
- `execution.limits` 复用 `delivery/schema.py:19-35` 的 `ResourceLimits` / `Authorizations`，不另造一套。

ProjectSpec 与现有 `ProductionOrder` 的关系：ProjectSpec 是**项目级**（一本书、一个主题），ProductionOrder 是**集级**（一集的生产授权与资源）。一档 ProjectSpec 展开为 N 个 Order。

---

## 3. Knowledge IR

现状（`KnowledgeStudio/src/knowledge_studio/models.py`）：`SourceMeta`、`PageRecord`、`UnitMeta`、`Citation`、`Excerpt`、`RetrievalResult`。能拆页、能定位、能检索。

缺口：没有概念层，没有主张层，没有证据充分性判断。

目标增量（新文件 `knowledge/concepts.json`、`knowledge/claims.json`）：

```json
{
  "schema_version": 1,
  "source_id": "transformers-3e",
  "concepts": [
    {
      "id": "concept.self-attention",
      "label": "Self-attention",
      "kind": "mechanism",
      "prerequisites": ["concept.dot-product", "concept.softmax"],
      "units": ["unit-04-02"],
      "citations": [{"source_id": "transformers-3e", "pdf_page": 312}]
    }
  ]
}
```

```json
{
  "schema_version": 1,
  "claims": [
    {
      "id": "claim.attention-scales-by-sqrt-d",
      "statement": "...",
      "type": "quantitative",
      "concept_ids": ["concept.self-attention"],
      "evidence": [
        {"source_id": "transformers-3e", "pdf_page": 315, "kind": "statement"},
        {"source_id": "attention-paper", "pdf_page": 4, "kind": "derivation"}
      ],
      "verification": "supported",
      "conflicts": []
    }
  ]
}
```

`verification` 枚举：`unsupported` / `single_source` / `supported` / `contested` / `refuted`。

规则：

- `supported` 至少两条独立证据，或一条 primary + 一条可复现推导。
- `contested` 必须记录冲突来源与采用理由，否则质量引擎按不通过处理。
- 这些判定由确定性规则与人工规则产生，LLM 只能提出候选标签，不能写 `supported`。

---

## 4. Content IR

现状有两套表示，各自成立：

| 表示 | 位置 | 用途 |
| --- | --- | --- |
| Brief / Outline / ScriptPage / NarrationScript / ContentPage | `authoring/models.py` | 候选稿到正式内容的桥 |
| ProductionPlan / Sequence / ShotPlan | `content/production.py` | 镜头级生产计划 |

V2 的处理是**加一层稳定 id 引用**，不合并这两个文件：

- 每个 Outline 页有 `page_id`，每段脚本有 `segment_id`，每个镜头有 `shot.id`（已有规则）。
- `claims.json` 的 claim id 被脚本段引用：`ScriptSegment.claim_refs: [claim.*]`。
- 镜头引用页面：`ShotPlan.source` 指向 `page_id`。
- 一致性检查：每个 claim 至少被一个脚本段引用，否则报告"知识未使用"；每个 `claim_refs` 必须可解析，否则 V-07 类校验失败。

这样 Content IR = authoring 模型 + 引用字段，不新建第三个模型。

---

## 5. Scene IR

沿用，不合并：

- `shared/schemas/storyboard.schema.json`（v2：镜头、连续性、设计字段）
- `shared/schemas/blender-scene-task.schema.json`（IR v2）
- `shared/schemas/shots.schema.json`、`shot-v1.schema.json`、`shot-taxonomy`
- `shared/schemas/timeline-v1.schema.json`、`narration-v1.schema.json`

V2 只增加一条：所有 Scene IR 产物的路径与哈希登记进 ArtifactRegistry，取消"各模块各自记路径"的做法。

---

## 6. ArtifactRegistry（新增）

现有 `ArtifactRecord`（`delivery/schema.py:75-84`）字段：`path`、`sha256`、`bytes`、`required`、`status`。够用，但没有全局索引。

新增 `runtime/artifacts/<project-id>/registry.json`：

```json
{
  "schema_version": 1,
  "project_id": "transformers-course",
  "artifacts": [
    {
      "id": "art.build.transformers-01.final",
      "kind": "video",                    // source | knowledge | plan | script | scene | media | report | package
      "path": "build/<lesson>/final/final.mp4",
      "sha256": "...",
      "bytes": 123456789,
      "produced_by": "compose",
      "inputs": ["art.script.transformers-01", "art.voice.transformers-01"],
      "created_at": "2026-11-13T10:00:00+08:00",
      "status": "present"
    }
  ]
}
```

规则：

1. 登记是幂等的，按 `id` 覆盖；写入用原子写。
2. `produced_by` 只写阶段名，不写进程信息。
3. 索引可以由产物目录重建；索引损坏不视为数据丢失。
4. `delivery/manifest.json` 继续是交付包的权威，Registry 不是它的替代。

---

## 7. 质量契约

### 7.1 QualityReport

沿用五维（Q1 内容可信度 / Q2 教学有效性 / Q3 视听体验 / Q4 工程完整性 / Q5 最终交付），增加两项必填：

- `report_inputs`: 每个维度读取的产物路径与 sha256。用于新鲜度判断（对应 F-2）。
- `verdict`: `pass` / `fail` / `incomplete`，由程序计算，不接受手填。

### 7.2 Defect（新增）

```json
{
  "id": "DEF-0042",
  "dimension": "Q1",
  "severity": "blocking",             // blocking | major | minor | note
  "stage": "subtitles",
  "artifact_ids": ["art.build.x.subtitles"],
  "symptom": "307 cues exceed reading-speed limit",
  "root_cause_hint": "script length vs target seconds",
  "evidence": ["build/<lesson>/quality/media-qc.json#V-31"],
  "status": "open"                    // open | repairing | fixed | accepted_risk | unverifiable
}
```

`accepted_risk` 只在所有者显式决定时允许，A3 下不得自动产生。

### 7.3 RepairPlan（新增）

```json
{
  "defect_ids": ["DEF-0042"],
  "strategy": "rerun_stage",          // rerun_stage | reauthor_segment | substitute_source | re_render_shot
  "rebuild_scope": ["subtitles", "compose"],
  "expected_cost": {"wall_seconds": 300},
  "attempt": 1
}
```

`attempt > 3` 时不再生成计划，转入 `RECOVERY_EXHAUSTED`（与项目熔断规则一致）。

### 7.4 QualityCertificate（新增）

交付包内的最终凭证：

```json
{
  "schema_version": 1,
  "project_id": "...",
  "lesson_id": "...",
  "verdict": "pass",
  "dimensions": {"Q1": "pass", "...": "pass"},
  "open_defects": [],
  "report_sha256": "...",
  "generated_at": "..."
}
```

`verdict: pass` 的充要条件：五维全部 `pass`，`open_defects` 为空，`report_inputs` 全部匹配当前产物哈希。

---

## 8. 版本与兼容

1. 新契约一律 `schema_version: 1`；修改破坏性字段时升到 2，并保留 v1 读取器一个版本周期。
2. 现有 28 个 schema 不改名。新增只加文件。
3. ProjectSpec 对存量 13 门课不强制迁移：没有 `project.yaml` 时，由 `lesson.yaml` + 默认值合成一个临时 ProjectSpec，并在报告中标记 `synthesized: true`。
4. 所有新契约必须有对应的 Pydantic 模型与至少一条失败路径测试，否则不合并。
