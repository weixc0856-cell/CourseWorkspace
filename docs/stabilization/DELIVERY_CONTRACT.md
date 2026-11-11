# 交付契约（Delivery Contract）

- 日期：2026-11-10
- 状态：已实现 `course-control package` / `package-verify`
- 关联审计：`docs/audit/ARCHITECTURE_CONFLICTS.md` C-06、C-10
- 关联规范：`docs/课程生产交付物规范.md`

---

## 1. 问题

交付规范要求哈希、`final/subtitles.*`、metadata、checklist 与归档，但：

- `build-report.json` 的 Artifact 只有 `path/kind/size_bytes/probe`，没有 SHA-256；
- 05/06/nvda 的 `final/` 没有 `subtitles.*`、`metadata.json`、`delivery-checklist.md`；
- 06 没有 `audio/mix.json`，母版 -22.8 LUFS，Q5 仍说"all release artifacts present"；
- 没有命令把已有产物整理成可独立验证的包。

## 2. 目标布局

`course-control package --lesson <slug>` 生成：

```text
deliver/<slug>/
├── final/
│   ├── master.mp4              # course-video-mixed.mp4 优先，否则 course-video.mp4
│   ├── captioned.mp4           # 存在则复制；否则 not_applicable
│   └── subtitles.srt|ass|vtt   # 已批准 SRT 优先；build 草稿补缺
├── build-report.json
├── narration.meta.json         # 旁白启用时必需
├── evidence/
│   └── media-qc.json
├── review/
│   ├── review.json             # 存在则复制
│   └── decisions.json          # 存在则复制；没有则 not_applicable
├── logs/*.log                  # 可选
├── metadata.json
├── manifest.json
└── delivery-checklist.md
```

说明：

- 包在 `deliver/<slug>/`；`build/<slug>/` 只作临时区。`.gitignore` 同时忽略 `build/` 与 `deliver/`。D-085 取代了本文件早期“不新建仓库根 delivery/”的规则。
- `package` 只复制，不渲染、不转码、不混音；它不改变任何源产物。
- 可选资产缺失写 `not_applicable`，不伪造空文件。

## 3. 必需与可选

| 资产 | 必需条件 | 缺失行为 |
| --- | --- | --- |
| `final/master.mp4` | 总是 | `PackageError`，exit 1 |
| `build-report.json` | 总是 | 失败 |
| `evidence/media-qc.json` | 总是 | 失败 |
| `narration.meta.json` | `narration.enabled` | 失败 |
| `final/subtitles.*` | `subtitles.enabled` | 失败 |
| `final/captioned.mp4` | 可选 | `not_applicable` |
| `review/review.json` | 可选 | `not_applicable` |
| `review/decisions.json` | 可选 | `not_applicable` |
| `logs/*.log` | 可选 | 不记录 |

母版必须能被 `probe_media` 读取；不可读即失败，不把坏文件打包。

## 4. manifest

`manifest.json`：

```json
{
  "schema_version": 1,
  "lesson": "05-transformer-5min",
  "run_id": "20261110T...-...",
  "generated_at": "...",
  "verdict": "pass",
  "files": [
    {"path": "final/master.mp4", "required": true, "status": "present", "bytes": 15773410, "sha256": "..."}
  ],
  "missing": []
}
```

- 每个实际文件都有 `bytes` 与 `sha256`。
- `run_id` 取 `build-report.run_id`；旧报告没有时生成 `...-package`，不伪造旧 run。
- `metadata.json` 记录 title、duration、resolution、fps、codec、languages、content_kind。
- `delivery-checklist.md` 由 manifest 生成，列出 required/status/sha 前 16 位。

## 5. 验证

```powershell
course-control package --lesson <slug>
course-control package-verify --package deliver/<slug>
```

`package-verify` 重新计算每个 `status=present` 文件的 SHA-256：

- 缺失 required：报错；
- 可选 `not_applicable`：跳过；
- 哈希不匹配：报错；
- 全部匹配：`package ok`。

## 6. 当前结果

| 课程 | package | 说明 |
| --- | --- | --- |
| 05 | 成功 | master、captioned、SRT、build-report、media-qc、narration meta、logs；review 缺失为 `not_applicable` |
| 06 | 成功 | master、SRT、build-report、media-qc、narration meta；captioned 为 `not_applicable` |
| 01 | 失败 | 缺 master、build-report、media-qc；这是正确行为，不是 bug |
| nvda | 可成功 | media QC 是 `INCOMPLETE`，但 package 只检查文件存在；发布仍被 `quality-gate` 拦住 |

package 成功不等于可发布：`quality-gate` 的 `incomplete` 与 `release-approve` 仍是独立门禁。

## 7. 与 producer delivery 的关系

- `producer` 的 `build/<slug>/producer/manifest.json` 是**制片清单**：判断七类资产是否齐全、订单是否批准、增量指纹。
- `package` 的 `deliver/<slug>/` 是**最终交付**：把已存在的资产复制、哈希、可独立验证。
- 两者不互相替代；短期保留。未来如果合并，以 package 的哈希与 producer 的订单状态为输入，不新增第三份清单。

## 8. 验收

1. 05/06 的 `package` exit 0，`package-verify` 输出 `package ok`。
2. 01 的 `package` exit 1，错误列出缺失的 master/build-report/media-qc。
3. 篡改包内任意文件后，`package-verify` 报 `hash mismatch`。
4. `build-report.json` 的新 artifact 带 `sha256`，新 run 带 `run_id`。
