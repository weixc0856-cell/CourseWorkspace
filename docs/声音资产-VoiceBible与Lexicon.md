# 声音资产：Voice Bible 与 Lexicon

- **日期**：2026-11-12
- **状态**：可用。P2 完成（[工业化生产流程 V2.0](v2/工业化生产流程V2.0-建议稿.md) WP-3 的 Voice Bible / Lexicon 部分；Dialogue Lock 属 P4，未开始）。
- **命令**：`course-control narration-assets --lesson <slug>`

---

## 1. 它解决什么

旁白以前只有两件事：`config/local-paths.yaml` 里的一个参考音频路径，和一段 prompt 文本。三集课程之间靠复制路径保持一致，换声音只能改配置，改发音只能改讲稿。

现在把"谁的声音"和"这个词怎么读"拆成两份可版本化的资产：

- **Voice Bible**：一个人的声音身份——参考录音的哈希、语言、合成模式、基准语速与风格。
- **Lexicon**：一个系列的读法——缩写、品牌、人名、符号。

两者都放在内容根，不进程序仓库；课程通过 id 引用，引用关系写在 `lesson.yaml`。

## 2. 放在哪

```text
<内容根>/audio/
├── voice-bibles/
│   └── <voice-id>.yaml
└── lexicons/
    └── <series-id>.yaml
```

```powershell
course-control content-root      # 内容根位置
```

## 3. 课程怎么引用

`lesson.yaml`：

```yaml
narration:
  enabled: true
  voice_bible: wayne-en-v1
  lexicon: automotive-aerodynamics
```

两个字段都可选。不写就完全退回原来的行为：用 `config` 里的 `tts.voice_ref*`，缓存键与以前逐字节一致（见 §8）。

## 4. Voice Bible

```yaml
schema_version: 1
id: wayne-en-v1
language: en
ref_audio: ../../lessons/02-car-aerodynamics/assets/voice/my_voice_en_ref_short.wav
ref_audio_sha256: ab3e6449…d630
prompt_text: "Welcome to this lesson. Today, we will look at how the model works."
backend: voxcpm2
model: VoxCPM2
mode: reference_only
speed: 0.80
text_frontend: true
style: null
approved_samples: []
notes: 英语旁白的标准声线。
```

| 字段 | 作用 |
| --- | --- |
| `id` | slug，等于文件名 |
| `language` | `en` / `zh`；决定课程该用哪个声线 |
| `ref_audio` | 相对 bible 文件解析，也接受绝对路径 |
| `ref_audio_sha256` | 声明即校验；不一致直接报问题 |
| `prompt_text` | `prompt_reference` 模式必填 |
| `mode` / `speed` / `text_frontend` / `style` | 声线的基准参数 |
| `approved_samples` | 已批准样例（路径 + 可选哈希），一并校验 |

**身份是文档的 SHA-256，不是路径。** 移动内容根、重命名目录、复制系列都不会改变声线身份；反过来，改了参考音频或参数，哈希变化，所有引用它的课自动重合成。这是 `narration.meta.json` 里那条迁移前绝对路径给过的教训：按路径标识资产，目录一搬就失效。

### 覆盖规则

Voice Bible 拥有"谁在说"：参考音频、prompt 文本、合成模式、语言。课程拥有"怎么说"：`speed`、`text_frontend`、`style_enabled` 等交付参数。`lesson.yaml` 里**显式写了**就按课程，没写就取 bible 的基准值（用 pydantic 的 `model_fields_set` 判断，不是猜默认值）。

## 5. Lexicon

```yaml
schema_version: 1
id: automotive-aerodynamics
language: en
entries:
  - term: CFD
    say: C F D
  - term: Mercedes-Benz
    say: Mercedes Benz
  - term: Reynolds
    say: Renolds
  - term: 空气动力学
    say: 空气动力学（ke xue）
```

匹配规则：

- 拉丁字母/数字开头的词条按**整词**匹配，大小写不敏感（`CFDish` 不会被改写）。
- 中日韩或符号开头的词条按字面匹配。
- 一次扫描完成，**长词优先**，替换结果不会被再次替换（`Mercedes-Benz` 不会先拆再被 `Benz` 命中）。
- 同一条目重复且读法不同，加载时直接报错。

改写只发生在送 TTS 之前。讲稿、字幕、笔记里的原文保持不变——字幕仍然显示 `CFD`。

## 6. 缓存失效

片段缓存键新增两个维度：

| 维度 | 何时出现 | 失效范围 |
| --- | --- | --- |
| `voice_bible_sha256` | 课程声明了 bible | 整个 bible 变了 → 该课全部片段重合成 |
| `lexicon_hits` | 本段实际命中的 `(term, say)` 对 | 只有命中被修改词条的片段重合成 |

**这里有意偏离了建议稿的字面要求**（"缓存键必须包含 Lexicon 版本"）。整份词典的哈希会让改一个词条使全课失效，与建议稿自己要求的"不受影响的资产继续复用"矛盾。改成记录本段的命中集，既保住了可追溯性，也让失效范围停在真正受影响的片段上。实测：给 a01 挂上 5 条词典，24 段里只有 5 段被改写。

## 7. 元数据与命令

`narration.meta.json` 升到 `schema_version: 3`：

```json
"assets": {
  "voice_bible": {"id": "wayne-en-v1", "sha256": "917d43…", "ref_audio": "…", "model": "VoxCPM2"},
  "lexicon": {"id": "automotive-aerodynamics", "sha256": "99ce7e…", "entries": 5},
  "problems": []
}
```

每个片段另记 `spoken_text_sha256` 与实际替换的 `lexicon_applied`。旧版本（2）的元数据仍可读。

```powershell
# 看这门课解析到哪个 bible / 词典，并做完整性检查
course-control narration-assets --lesson a01-why-cars-need-aerodynamics

# 打印被词典改写的段落，核对读音
course-control narration-assets --lesson <slug> --show-text

# 机器可读
course-control narration-assets --lesson <slug> --json
```

有问题（参考音频缺失、哈希不符、词典自相矛盾）时退出码为 1，问题逐条打印；声明的文件不存在则直接失败，不回退到 config——静默换声线比报错更难查。

## 8. 向后兼容

不声明 `voice_bible` / `lexicon` 的课：`voice_bible_sha256=None`、`lexicon_hits=()`，这两个字段不写进缓存键。有单测锁定这一点（`test_legacy_payload_is_unchanged` 直接重建旧 payload 比对），所以 a01 现有 48 个片段的缓存继续命中。

## 9. 实测（2026-11-12）

用试点课程的一份临时副本（不改真实课程；副本已随课程归档清理），声明 `wayne-en-v1` + `automotive-aerodynamics`：

| 项 | 结果 |
| --- | --- |
| 资产解析 | bible `wayne-en-v1` sha256 `917d43186a81…`；词典 `automotive-aerodynamics` sha256 `99ce7e544242…`，5 条 |
| 相对路径 | `../../lessons/…/my_voice_en_ref_short.wav` 正确解析到内容根下的实体 |
| 哈希校验 | 声明值与文件一致，`problems` 为空 |
| 词典改写 | 24 段中 5 段被改写：`Reynolds→Renolds`（2 段）、`CFD`、`SUV`、`BMW`、`Mercedes-Benz` |

**未执行**：真实 VoxCPM2 合成。本轮没有启动 50000 的 TTS 服务，因此"改词典后音频重新合成、音色一致"只验证到缓存的键与文本改写这一层，没有真听。要补的话，跑一次 `narration-build` 即可，但会占用本地模型服务。

## 10. 与 P4 的关系

Dialogue Lock 还没做。它要记录的是：正式旁白文本哈希、bible 版本、lexicon 版本、音频文件哈希与实测时长、以及旁白段落与字幕的对应关系。本轮的 `assets` 块已经把前三项写进 `narration.meta.json`，P4 在此基础上加锁文件与下游失效检查即可。

## 11. 代码与测试

- `CourseControl/src/course_control/audio/voice_bible.py` — 契约、加载、相对路径、哈希与校验
- `CourseControl/src/course_control/audio/lexicon.py` — 契约、单次扫描改写、命中记录
- `CourseControl/src/course_control/audio/__init__.py` — `resolve_assets()`，按课程解析两份资产
- `CourseControl/src/course_control/narrate.py` — `segment_cache_key()` 新增两个可选维度
- `CourseControl/src/course_control/narration_course.py` — 合成接入、meta v3
- `CourseControl/src/course_control/cli/render.py` — `narration-assets`
- Schema：`shared/schemas/voice-bible.schema.json`、`lexicon.schema.json`；`lesson.schema.json` 增加两个可选字段
- 测试：`CourseControl/tests/test_audio_assets.py`（17 例）
