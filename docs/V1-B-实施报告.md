# V1-B 实施报告：模型、Schema、时间换算与单测

- **状态**：已实现，等待评审是否进入 V1-C（E6 manifest 只读适配）
- **日期**：2026-11-07
- **范围**：只增加 V1 契约模型、Schema、整数时间换算和测试；不迁移任何生产链路
- **基线**：`fdd2497`；本轮未改 E6.1–E6.4、未改旧 manifest、未触碰 8080

---

## 1. 新增文件

| 文件 | 作用 |
| --- | --- |
| `CourseControl/src/course_control/timecode.py` | 有理数帧率、帧↔毫秒、帧↔采样、SRT 时间戳；只用整数运算 |
| `CourseControl/src/course_control/contracts_v1.py` | `AssetRef`、`LessonSpec`、`ShotSpecV1`、`NarrationSpec`、`TimelineSpec`、`EvidenceManifestV1`、`RenderManifest` |
| `CourseControl/tests/test_timecode.py` | 10 个时间边界用例 |
| `CourseControl/tests/test_contracts_v1.py` | 40 个模型、非法输入、Schema 与示例用例 |
| `shared/schemas/*-v1.schema.json` | 7 份 V1 JSON Schema |
| `CourseControl/src/course_control/cli.py` | 新增 `schemas-v1`、`contract-v1-validate` 命令 |

旧的 `contracts.py`、`session.py`、`pipeline.py`、适配器均未修改。

---

## 2. 时间系统

### 2.1 有理数帧率

```json
{"fps_num": 30000, "fps_den": 1001}
```

- 不再把 30 写死为全系统帧率。
- `fps_num`、`fps_den` 必须为正整数；0、负数、浮点直接失败。
- 覆盖 24/1、25/1、30/1、30000/1001、60000/1001。

### 2.2 舍入规则

- 统一“四舍五入、.5 向上”。
- 只用整数：`(2*n + d) // (2*d)`。
- 帧边界从累计毫秒一次换算，再取差值；不允许逐段换算后累加。

### 2.3 关键边界

| fps | 1 帧 → ms | 1 秒 → 帧 | 30 帧 → ms |
| --- | --- | --- | --- |
| 24/1 | 42 | 24 | 1250 |
| 25/1 | 40 | 25 | 1200 |
| 30/1 | 33 | 30 | 1000 |
| 30000/1001 | 33 | 30 | 1001 |
| 60000/1001 | 17 | 60 | 501 |

### 2.4 音频采样对齐

- `frame_to_sample` / `sample_to_frame` 同样只用整数。
- `align_audio_segment` 返回帧边界、回映射采样与 drift。
- 48 kHz / 30 fps：1 帧 = 1600 采样，drift 0。
- 48 kHz / 30000/1001：1 帧 ≈ 1601.6 采样；示例区间 drift 为 `+2 / +48` 采样，在 1 帧容差内。
- drift 不静默修正，由调用方决定通过或失败。

### 2.5 SRT

- `frame_to_srt` 由 `frame_to_ms` 一次生成 `HH:MM:SS,mmm`。
- `srt_to_frames` 拒绝 `end <= start` 和不足 1 帧的字幕。
- `TimelineSpec.srt_text()` 直接从帧生成 SRT，便于回读校验。

---

## 3. 模型与 Schema

### 3.1 模型

- `AssetRef`：path + sha256 + bytes + kind + origin + version；外部只读素材允许绝对路径，普通素材拒绝绝对路径、反斜杠、`..`。
- `LessonSpec`：课程身份、输出、轨道、素材、旁白/字幕引用、验收阈值。
- `ShotSpecV1`：`slide / motion_canvas / manim / blender / session / simulation / graphics` 判别联合；`manim.class` 用 alias 兼容现有写法。
- `NarrationSpec`：含 `fps`；逐段校验 `duration_frames == ms_to_frame(duration_ms)`；段必须升序、不重叠。
- `TimelineSpec`：base 镜头必须从 0 开始、连续覆盖 `total_frames`；overlay 必须落在 base 内；音频/字幕不得越界或重叠；`srt_text()`。
- `EvidenceManifestV1`：沿用旧字段名，值升级为 `AssetRef`；新增 `kind / lesson_id / run_id / environment / legacy`。
- `RenderManifest`：最终成片、来源、输出、镜头、旁白、字幕、检查、工具版本；`duration_ms` 必须等于帧数换算值。
- V1 模型统一使用 `strict=True`：额外的字段、把字符串/浮点静默转成整数都会失败。

### 3.2 Schema

- `course-control schemas-v1 --output shared/schemas` 生成 7 份 JSON Schema。
- `test_schema_files_match_models` 逐份比较 Schema 文件与 `model_json_schema()`，防止漂移。
- 所有示例 JSON 均通过对应 Pydantic 模型校验。

### 3.3 失败诊断

- Pydantic 错误保留字段路径；CLI 输出示例：

```text
<file> does not match the contract:
  - title: Field required
  - status: Field required
  - output: Field required
```

- 时间错误抛出 `TimecodeError`，消息包含非法值或无法对齐的原因。
- 时间线错误明确区分 `overlap`、`gap`、`outside`、`exceeds`、`expected`。

---

## 4. 测试报告

| 套件 | 结果 |
| --- | --- |
| CourseControl | **116 个用例（114 通过 + 2 跳过）** |
| ModelingStudio | 28 个用例，OK |
| shared/ai_runtime | 22 个用例，OK |
| ContentQA | 11 个用例，OK |
| 合计 | **177 个用例（175 通过 + 2 跳过）** |

新增 50 个用例：

- `test_timecode.py`：10 个；
- `test_contracts_v1.py`：40 个。

跳过的 2 个是 Docker/录制集成测试，**不计入通过**；完整回归仍需在具备条件时单独执行。

运行命令：

```powershell
uv run --project CourseControl python -m unittest discover -s CourseControl/tests -t CourseControl
uv run --project CourseControl course-control schemas-v1 --output shared/schemas
uv run --project CourseControl course-control contract-v1-validate --kind timeline-v1 --file docs/contracts/examples/timeline.spec.json
```

---

## 5. 新旧接口兼容性

### 5.1 保持不变

- `lesson.yaml` / `storyboard.yaml` 仍是作者文件；V1 不替换。
- `contracts.py` 的 `LessonConfig` / `Storyboard` / `ShotsFile` 未改字段、未改默认值。
- `session.py` 的 `SessionSpec` / `EvidenceManifest` 未改；V1 是并列的新模型。
- `pipeline.py`、`collect.py`、`verify.py`、Manim/Remotion/Blender 适配器未改。
- 旧 `course-control schemas` 命令仍只导出旧 Schema；V1 用 `schemas-v1`。

### 5.2 新增而非替换

- `contracts_v1.py` 不导入旧适配器，旧适配器也不导入它。
- `EvidenceManifestV1` 与 `session.EvidenceManifest` 同时存在；后续由适配器把旧 JSON 转成 V1，不改旧文件。
- E6 现有 `build/manim-transformer/e6/manifest.json` 未读取、未改写；V1-C 才做只读适配。
- E6.1–E6.4 成片与四幕代码未动。

### 5.3 已知差异

- V1 `shot_id` / `session_id` 允许下划线，以兼容现有的 `shot_001`、`shell_001`；`lesson_id` 仍要求小写连字符 slug。
- V1 `NarrationSpec` 增加 `fps`，因为 `duration_frames` 必须由帧率校验。
- V1 `EvidenceManifestV1` 的 `execution_result` 等字段名不变，但值从字符串路径升级为 `AssetRef`；旧值由后续适配器转换。
- `RenderManifest.checks` 允许空列表，表示“未执行自动检查”，不是通过。

---

## 6. 未做 / 下一步

本轮**未做**：

- 未做 E6 manifest 只读适配；
- 未迁移任何课程或 E6 生产链路；
- 未删除旧 manifest；
- 未实现 E6.5 `MultiHeadScene`；
- 未运行 E6.5 独立数学验证脚本；
- 未修改 8080。

建议下一步（V1-C）评审前确认：

1. 接受 `shot_id` 允许下划线的兼容规则。
2. 接受 `NarrationSpec.fps` 为必填。
3. 接受 `EvidenceManifestV1` 的值类型升级，而不是内联执行结果。
4. 同意 V1-C 只读适配 E6 V0 manifest，并重新生成自动检查，不沿用人工 `checks`。
5. E6.5 编码前先提交独立数学验证脚本与结果。
