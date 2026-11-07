# V1-C 实施报告：E6 V0 manifest 只读适配与自动检查

- **状态**：已实现；等待评审后续轨道接入
- **日期**：2026-11-07
- **范围**：只读 E6 V0 manifest 与现有媒体，生成 V1 `RenderManifest`；不修改 V0、不重渲染、不迁移 E6.1–E6.4
- **基线**：`71cb58c`；未触碰 8080

> 本报告记录 V1-C 当时的 190 个用例。E6.5 数学验证新增 8 个测试后，全项目当前为 198 个用例（196 通过 + 2 跳过），见 [E6.5-数学验证报告.md](E6.5-数学验证报告.md)。

---

## 1. 新增/修改

| 文件 | 内容 |
| --- | --- |
| `CourseControl/src/course_control/legacy_e6.py` | V0 模型、ffprobe 探测、SRT 解析、哈希校验、V1 RenderManifest 生成 |
| `CourseControl/src/course_control/contracts_v1.py` | `RenderManifest.source` 允许 legacy 迁移时为 `null`，但必须提供 `legacy.v0_manifest` |
| `CourseControl/src/course_control/cli.py` | 新增 `e6-adapt` |
| `CourseControl/tests/test_legacy_e6.py` | 12 个适配器测试（含本地 E6 集成测试） |
| `CourseControl/tests/test_contracts_v1.py` | 新增 legacy source 约束测试 |

旧的 `build/manim-transformer/e6/manifest.json`、四幕视频、旁白、SRT 均未被修改。

---

## 2. 使用方法

```powershell
uv run --project CourseControl course-control e6-adapt `
  --workspace . `
  --manifest build/manim-transformer/e6/manifest.json `
  --output build/manim-transformer/e6/render.manifest.v1.json
```

- 输出是新的 V1 文件，不覆盖 V0。
- 自动检查有 `fail` 时命令 exit 1，但 manifest 仍会写出，便于诊断。
- 文件缺失、ffprobe 失败、V0 结构非法时 exit 2，并打印具体原因。

本地执行结果：

```text
wrote build\manim-transformer\e6\render.manifest.v1.json
36 checks: 35 pass, 1 not_applicable
```

`not_applicable` 是 `manual_checks_not_trusted`，不是通过。

---

## 3. 适配规则

| V0 字段 | V1 结果 |
| --- | --- |
| `lesson` | `lesson_id` |
| `fps: 30` | `fps: {fps_num: 30, fps_den: 1}` |
| `resolution` | `output.width/height` |
| `shots[].duration_s` | 整数毫秒（Decimal 半入）→ 累计帧边界 |
| `shots[].file` + `sha256` | `RenderShot.asset`，实际重新哈希 |
| `narration.file` | `RenderNarration.asset`；混合 WAV |
| `narration.segments[]` | `RenderNarration.segment[]`；`start_frame` 由镜头起点推断 |
| `subtitles.file` | `RenderSubtitles.asset`；SRT 逐条解析 |
| `video.file` | `RenderManifest.video` |
| V0 `checks` | `legacy.manual_checks`；`manual_checks_trusted=false` |

E6 V0 没有 `lesson.yaml`、`storyboard.yaml` 和逐段旁白 WAV，因此：

- **不生成** `LessonSpec`；
- **不生成** `NarrationSpec`；
- **不生成** `TimelineSpec`；
- `RenderManifest.source = null`，以 `legacy.v0_manifest` 保留来源；
- 不伪造作者文件或逐段音频。

---

## 4. 自动检查

| 检查组 | 内容 |
| --- | --- |
| `v0_manifest` | V0 文件哈希与大小 |
| `shot_asset:*` | 四幕视频是否存在、sha256 是否匹配 |
| `shot_duration:*` | ffprobe 实际时长 vs V0 秒数（1 帧容差） |
| `shot_resolution:*` | 1920×1080 |
| `shot_fps:*` | 30/1 |
| `narration_asset` | 混合旁白 WAV 哈希 |
| `narration_audio_format` | 48 kHz / mono |
| `narration_duration` / `narration_mixed_extent` | 33.1 s 与时间线一致 |
| `narration_fit:*` | 每段旁白时长不超过对应镜头 |
| `subtitles_asset` | SRT 哈希 |
| `subtitle_cues` | 4 条字幕非空、按序、落在镜头内 |
| `final_asset` | 成片哈希 |
| `final_duration` / `final_timeline_extent` | 33.1 s 与 993 帧一致 |
| `final_resolution` / `final_fps` / `final_audio_format` | 成片规格 |
| `final_streams` | 视频 + 音频 + 字幕三条流 |
| `manual_checks_not_trusted` | `not_applicable`，明确 V0 人工检查未计为 pass |

本地 E6 产物：**35 pass + 1 not_applicable**。这不是“全部自动验收通过”，因为：

- 旁白只有混合 WAV，无法验证逐段音频与字幕的真实同步；
- 字幕时间仍是作者提供的 SRT，不是从音频强制对齐生成；
- `source=null` 表示这是 legacy 适配，不是完整规范化课程。

---

## 5. 测试报告

| 套件 | 结果 |
| --- | --- |
| CourseControl | **129 个用例（127 通过 + 2 跳过）** |
| ModelingStudio | 28 通过 |
| shared/ai_runtime | 22 通过 |
| ContentQA | 11 通过 |
| 合计 | **190 个用例（188 通过 + 2 跳过）** |

新增 13 个测试：

- `test_legacy_e6.py`：12 个；
- `test_contracts_v1.py` 的 legacy source 约束：1 个。

E6 集成测试在本地 E6 产物存在时执行；干净克隆缺少 `build/manim-transformer/e6/` 时该用例显式 `skip`，**不计为通过**。

跳过的 2 个仍是 Docker/录制集成测试，不计为通过。

---

## 6. 兼容性

- V0 `manifest.json` 未修改；集成测试在适配前后比较其 sha256，结果一致。
- E6.1–E6.4 四幕视频、旁白、SRT、成片未修改。
- 旧 `EvidenceManifest` / `SessionSpec` / `BuildReport` 未修改。
- V1 `RenderManifest` 仅增加 legacy 迁移路径：`source=null` 时必须有 `legacy.v0_manifest`，否则校验失败。
- 旧示例 `render.manifest.json` 仍使用正常 `source`；`e6.render.manifest.v1.json` 使用 `source=null`。

---

## 7. 未做 / 下一步

未做：

- 未生成 `LessonSpec` / `NarrationSpec` / `TimelineSpec`；
- 未重渲染 E6；
- 未把 E6 接入 `pipeline.py`；
- 未实现 E6.5 `MultiHeadScene`；
- 未运行 E6.5 独立数学验证脚本；
- 未触碰 8080。

建议下一步评审：

1. 接受 E6 legacy `source=null` 作为只读迁移的临时形态。
2. 接受混合旁白无法验证逐段同步，不把 35 条 pass 解释为完整课程验收。
3. 是否进入 V1-D（Session 证据接入）或先做 E6.5 独立数学验证脚本。
