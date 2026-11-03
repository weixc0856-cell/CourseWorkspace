# ContentQA 实施评估（R0 只读审计）

- **文档版本**：v0.1（R0 交付物）
- **日期**：2026-11-01
- **基线**：`main` 分支，HEAD `adef52fec03309add7ed3ae241446f7b9103eca7`，工作区干净
- **性质**：只读审计与设计方案。**本次未修改任何代码、配置、依赖、课程内容或现有生产资产**；唯一新增文件是本文。
- **证据等级**（沿用 PRD）：`VERIFIED` 实际读取或执行；`STATIC` 仅源码/文档确认；`NOT_RUN` 具备条件未执行；`NOT_FOUND` 已扫描范围内不存在；`UNKNOWN` 需人工或后续阶段确认。

---

## 0. 结论摘要

1. **现有工程可以直接复用**：契约建模方式（pydantic + `extra="forbid"` + JSON Schema 导出）、路径合法性规则、ffprobe 封装、`shots.json` 时间线、`build-report.json` 报告结构、夹具 + `unittest` 测试方法、CosyVoice HTTP 契约。ContentQA 以**只读消费方**接入这些成果。
2. **硬约束已确证**：`LessonConfig` 使用 `extra="forbid"`，在 `lesson.yaml` 里新增任何字段都会让 `course-control validate` 直接失败。ContentQA 的配置与元数据**不能写进 `lesson.yaml`**，必须另建文件。
3. **最关键的缺口不是模型，而是证据**：两门课都没有来源清单（`sources.yaml` 从未创建），Transformer 课仅有两处文本提及“Vaswani et al., 2017”。没有可定位的原始资料，模型审查只能产出“无证据”意见，无法形成事实核验。
4. **本地运行时是单实例**：`8080` 的 llama.cpp 服务一次只加载一个模型，`50000` 的 CosyVoice 同一时刻只跑一个模式。所谓“模型 A 生成、模型 B 审查”在工程上只能靠**人工换模型**实现；ContentQA 不启动、不切换、不重启任何服务。
5. **ASR 不存在**：`<AI_ROOT>\models\` 只有 LLM 与 FLUX 权重，没有 whisper 类模型；仓库内也没有语音识别依赖。文本到音频的反向验证在 R3 只能先做**确定性部分**（哈希、时长、字幕文本对齐），ASR 需要人工决定是否另装运行时。
6. **推荐架构**：独立 `ContentQA/` uv 项目，包名 `content_qa`，CLI `content-qa`；只读 `lessons/`、`build/`、`shared/schemas/`，只写自己的报告目录与 `build/<slug>/narration/`；**状态由程序判定，模型只能提出候选**。
7. **状态词独立**：ContentQA 的 run 状态是 `pass / fail / needs_review / not_run / not_applicable`，与 CourseControl 的 `pass / fail / skipped / not_run / not_applicable` 是两套契约，不合并、不映射、不互相写入。
8. **R1 可立即开始**：只做契约、配置、路径规则、状态聚合、CLI 骨架与离线测试，不调用任何模型，不改 CourseControl。

---

## 1. 审计范围与执行事实

### 1.1 仓库状态（`VERIFIED`）

```text
HEAD    adef52fec03309add7ed3ae241446f7b9103eca7
branch  main
status  干净（无未提交改动）
结构    lessons/ CourseControl/ CourseSlides/ MotionStudio/ ManimSandbox/
        BlenderStudio/ RemotionStudio/ shared/ config/ scripts/ docs/ build/
tracked 149 个文件
```

与任务书给出的 HEAD 一致。**文档漂移提示**：`docs/R5-验收矩阵.md` 与 `docs/提交前检查清单.md` 仍写着“R4/R5 未提交、HEAD 为 R3”，实际 HEAD 已包含 `R4-R5: CourseControl 调度、自动验收与夹具` 与后续文档提交。这些文档是当时快照，代码事实以 HEAD 为准；R0 不修改它们。

### 1.2 实际读取的文件

| 范围 | 文件 | 用途 |
| --- | --- | --- |
| 总览 | `README.md` | 生产闭环、工程分工、端口、边界 |
| 正式 PRD | `docs/CourseWorkspace-R0-R5改造PRD.md` §0、§1.1–1.6、§2.1–2.7、§3.1–3.6、§5.4、§5.5、§6.1–6.5 | 纪律、现有契约、数据契约、V-01~V-21、R4/R5 范围 |
| 验收 | `docs/R5-验收矩阵.md` | 已取得的证据与未覆盖项 |
| 内容规范 | `docs/课件制作总指导.md` | 双文件契约、四要素、动画路由、旁白/字幕输入 |
| 本地 AI | `docs/本地模型与配音工作流.md` | 三层结构、模型清单、CosyVoice 模式与接口、接入现状 |
| 提交纪律 | `docs/提交前检查清单.md` | 脱敏、忽略规则、依赖与测试命令 |
| 交付清单 | `docs/交付清单-01-shell-for-ai-era.md` | 人工“内容核查”待办（P6/P11/P15/P18/P19） |
| 控制层 | `CourseControl/README.md`、`pyproject.toml`、`.gitignore` | 命令、阶段、依赖、忽略规则 |
| 控制层源码 | `contracts.py`、`paths.py`、`validators.py`、`verify.py`、`collect.py`、`utils.py`、`cli.py`、`pipeline.py`、`report.py`、`adapters/base.py` | 契约模型、路径规则、V 检查实现、报告与调度 |
| 控制层测试 | `tests/test_contracts.py`（前 60 行）、`tests/test_staging.py`（仅统计） | 测试风格（`unittest`，10 个用例） |
| 共享契约 | `shared/schemas/{lesson,storyboard,shots,build-report}.schema.json` | 检查 `additionalProperties` 与字段命名 |
| 配置 | `config/tools.example.yaml`、`config/local-paths.example.yaml`；本地 `config/tools.yaml`、`config/local-paths.yaml`（**只确认键名与存在性，未复述任何值**） | 配置模式与脱敏策略 |
| 课程（Transformer） | `lesson.yaml`、`storyboard.yaml`、`slides.md`、`lecture_notes.md`、`assets/` 文件清单 | 8 页 / 8 块 / 1 个动画镜头 / 无字幕 / 无旁白 / 无来源清单 |
| 课程（Shell） | `lesson.yaml`、`storyboard.yaml`、`outline.md`（仅第 24 行）；`slides.md`、`lecture_notes.md`（仅页数与块数统计） | 对照课程规模与镜头登记 |
| Manim | `01-transformer-demo/dot_product.py`、`test_demo.py`、`pyproject.toml`、`requirements.txt` | 现有可验证数值示例（a·b=6、投影 0.6b） |
| Motion | `src/scenes/**`、`src/project.ts`（仅文件清单） | 场景注册规模 |
| Remotion | `package.json`、`src/audio/Narration.tsx`、`src/subtitles/Captions.tsx`、`src/types.ts`、`scripts/stage-assets.mjs` | 旁白/字幕消费方式、staging 契约 |
| 入口脚本 | `scripts/{setup,check,build-lesson,prepare-fixtures}.ps1` | 工作区级入口 |
| AI 运行时 | `<AI_ROOT>` 顶层目录与 `models/` 文件名；`CosyVoice-Runtime/README.md`、`api_server.py` | CosyVoice 真实接口、可用模型 |
| 运行环境 | `node/npm/uv/python/ffmpeg/ffprobe` 版本；`netstat` 端口；`build/` 现存文件 | 实测事实 |

**未执行**（`NOT_RUN`）：任何构建、测试、渲染与模型调用。R0 只读；同时避免在当前工作区产生 `build/` 写入或 `__pycache__`。

### 1.3 运行时实测事实

| 项目 | 实测值 | 证据 |
| --- | --- | --- |
| Node / npm | `v24.14.1` / `11.11.0` | `VERIFIED` |
| Python / uv | `3.12.10` / `0.10.8` | `VERIFIED` |
| FFmpeg / ffprobe | `8.1-full_build`（在 PATH） | `VERIFIED` |
| 本地大模型 `8080` | **未监听** | `VERIFIED`（`netstat`） |
| CosyVoice `50000` | **未监听** | `VERIFIED`（`netstat`） |
| Motion Studio `5173` | 监听中 | `VERIFIED` |
| `3000` / `8081` / `8082` / `8188` | 未监听 | `VERIFIED` |
| `<AI_ROOT>\models\` | Qwen3-30B-A3B、Qwen3-Coder、Qwen3-VL（含 mmproj）、Qwen3-8B、Qwen3.5-4B、DeepSeek-R1-8B、FLUX.2 klein；**无 ASR 权重** | `VERIFIED` |
| CosyVoice 接口 | `GET /health`、`GET /speakers`、`POST /tts`（JSON）、`POST /tts/upload`（form） | `VERIFIED`（读 `api_server.py`） |
| `build/` 现存 | 仅夹具输入（3 个 `recording.mp4`、1 个 `narration.wav`、1 个 Motion 导出样本） | `VERIFIED` |

CosyVoice 真实请求体（`api_server.py` 的 `TTSRequest`）：

```text
text: str
prompt_wav: str | None
prompt_text: str | None
speaker: str | None        # 优先于 prompt_wav
speed: float = 1.0
text_frontend: bool = True
```

响应为 `audio/wav`，带 `X-Audio-Seconds`、`X-Synth-Seconds`、`X-Sample-Rate` 三个头；`/health` 返回 `status / sample_rate / speakers / modes / error`。这些字段足以支撑旁白追溯，不需要改服务端。

---

## 2. 现有工程可直接复用的能力

| 能力 | 现有实现 | ContentQA 的复用方式 |
| --- | --- | --- |
| 契约建模 | `CourseControl/src/course_control/contracts.py`：pydantic v2、`extra="forbid"`、`schema_version` | 复制**方法**而非导入：ContentQA 自建 pydantic 模型；同包依赖不跨工程 |
| JSON Schema 导出 | `course-control schemas --output shared/schemas` | ContentQA 用同样方式导出到自己的 `schemas/` |
| 路径合法性 | `paths.path_problem`：禁反斜杠、绝对路径、`.`/`..`/空段 | 在 ContentQA 重写同语义函数；用表驱动测试锁定行为一致 |
| 媒体探测 | `utils.probe_media` / `probe_audio`（ffprobe JSON） | 重写同名能力（约 40 行），支持纯音频与 A/V |
| 命令执行 | `utils.run_command`：超时、退出码、日志、`cmd.exe /c` 兼容 | 复用同一模式：参数数组、不拼 shell 字符串 |
| 时间线 | `collect.collect()` → `build/<slug>/shots.json` | **只读**，用于音画检查与字幕轴对照 |
| 报告结构 | `report.ReportBuilder` → `build-report.json`（stages/checks/artifacts/verdict） | 只读引用；ContentQA 报告另立 schema，不复用枚举 |
| 内容解析 | `utils.notes_blocks` / `page_budgets`（`### Slide N`、`时长预算`） | 重写：按页抽取“逐字口播”，供旁白分段与字幕对齐 |
| 状态纪律 | PRD §0.3：`skip ≠ pass`、`不适用 ≠ 通过` | 直接沿用为 ContentQA 判定原则 |
| 测试方法 | `unittest` + `tests/fixtures/` + 临时目录 | 同风格；模型响应用固定夹具，不依赖服务在线 |
| 夹具生成 | `scripts/prepare-fixtures.ps1`（ffmpeg lavfi） | R4 用同样办法造音频/视频样本 |
| 本地 AI 调用 | `8080` OpenAI 兼容；`50000` CosyVoice HTTP | 只用 HTTP；ContentQA 不管理进程 |
| 字幕输入 | `lessons/<slug>/subtitles.srt` → `build/<slug>/subtitles.srt` → Remotion `Captions.tsx` | 只读消费；新增时间轴检查 |
| 脱敏纪律 | 占位符 + `config/*.yaml` 忽略 + 示例文件 | ContentQA 配置照做 |

> 隔离规则要求“工程之间不互相 import”。ContentQA 不 `import course_control`，也不被 CourseControl 导入；重复的 40~80 行工具代码是有意为之，用测试锁定语义。

---

## 3. 需要新增的能力（缺口）

| 编号 | 缺口 | 现状证据 | 影响 |
| --- | --- | --- | --- |
| G-01 | 来源清单与证据语料 | `sources.yaml` / `assets.yaml` 从未创建；全仓库仅 2 处 “Vaswani et al., 2017” | 事实核验没有可比对的原文 |
| G-02 | 模型客户端 | 仓库内无任何 `8080` 调用代码 | 无法生成、无法独立审查 |
| G-03 | 审查报告契约 | 无 claim 级模型；`build-report.json` 只表达阶段/检查 | 审查意见不可机器读取 |
| G-04 | 声明（claim）身份 | 无稳定 claim_id 方案 | 多次审查无法对比、无法追踪修复 |
| G-05 | 公式与数值验证 | 无 SymPy；`ManimSandbox` 只有演示脚本 | 公式正确性无人复核 |
| G-06 | 文本哈希与规范化 | 无 | 讲稿改动无法定位受影响旁白 |
| G-07 | 旁白 manifest | `本地模型与配音工作流.md` §4.4 明确“建议，尚未实现” | 音频来源不可追溯 |
| G-08 | 逐页 TTS 适配器 | 手工合成 + 手工复制 | 改一页要整门重做；易漏更新 |
| G-09 | ASR | 无模型、无依赖 | 无法做“文本→音频→文本”闭环 |
| G-10 | 字幕时间轴校验 | `verify.py` 的 V-16 只查 `file 存在 && cues > 0`；PRD §3.6 要求“单调递增、最后结束 ≤ 成片时长” | 字幕越轴、超出片尾不会被发现 |
| G-11 | 黑帧 / 冻结帧检测 | 无 | 渲染事故只能靠人眼 |
| G-12 | 人工复核队列 | 无结构化产物 | 争议项散落在聊天与文档里 |
| G-13 | 跨模型独立性记录 | 无 | “两个模型都说对”无法被审计 |
| G-14 | 服务健康探测 | `check.ps1` 不探测 `8080/50000` | 问题推迟到调用时才暴露 |

> G-10 是**现有实现弱于 PRD**的地方。R0 只记录差异；ContentQA 在自己的检查里补齐，**不修改 CourseControl**。

---

## 4. 与 CourseControl 的接口边界

### 4.1 只读输入（ContentQA → 读）

| 输入 | 来源 | 用途 |
| --- | --- | --- |
| `lessons/<slug>/lesson.yaml` | 内容层 | 页数/引擎/旁白与字幕开关/验收容差 |
| `lessons/<slug>/storyboard.yaml` | 内容层 | 镜头与页码 |
| `lessons/<slug>/slides.md` | 内容层 | 观众视图文本、公式、图注 |
| `lessons/<slug>/lecture_notes.md` | 内容层 | 逐字口播、时长预算、技术核查 |
| `lessons/<slug>/sources.yaml`（**待建**） | 内容层 | 证据清单与定位 |
| `lessons/<slug>/subtitles.srt` | 内容层 | 字幕文本与时间轴 |
| `build/<slug>/shots.json` | 控制层产物 | 时间线、旁白/字幕登记 |
| `build/<slug>/final/build-report.json` | 控制层产物 | 成片参数与阶段状态（只读对照） |
| `build/<slug>/narration/*.wav` | 输入/ContentQA 产物 | 音频参数与哈希 |
| `build/<slug>/animation/*.mp4`、`blender/*.mp4`、`slides/*.png` | 生产层产物 | 媒体检查 |
| `shared/schemas/*.json` | 共享层 | 只读对照，不修改 |
| `config/tools.yaml` | 本机配置 | ffmpeg/ffprobe 路径（只读） |

### 4.2 不触碰项（硬约束）

| 对象 | 约束 | 证据 |
| --- | --- | --- |
| `lesson.yaml` 结构 | **禁止新增字段**。`LessonConfig` 是 `extra="forbid"`，任何未知键都会 `ContractError` | `contracts.py:20-21,69-89`；`paths.py:44-95` |
| 状态枚举 | 禁止扩展/复用 `Status`（pass/fail/skipped/not_run/not_applicable） | `contracts.py:12-17` |
| `validate` / `verify` 判定路径 | 禁止任何模型调用进入 | `validators.py`、`verify.py` 无网络调用；`pipeline.py` 只调适配器 |
| `build-report.json` | 禁止由 ContentQA 写入 | `report.ReportBuilder.write` 是唯一写者 |
| CourseControl 依赖 | 禁止修改 `CourseControl/pyproject.toml` / `uv.lock` | 任务约束；隔离规则 |
| 课程正文 | 禁止改写 `slides.md`、`lecture_notes.md` | PRD §0.1；用户所有 |
| 本地模型 / CosyVoice | 禁止启动、停止、换模型、改启动脚本 | PRD §0.4；任务约束 |
| `build/` 其他子目录 | 禁止写入；仅 `narration/` 例外，见 §4.4 | PRD §2.3 写入归属矩阵 |

### 4.3 状态词：两套枚举，刻意不同

| 层 | 枚举 | 谁判定 |
| --- | --- | --- |
| CourseControl 阶段/检查 | `pass` / `fail` / `skipped` / `not_run` / `not_applicable`；verdict `pass` / `fail` / `incomplete` | 控制层程序 |
| ContentQA run | `pass` / `fail` / `needs_review` / `not_run` / `not_applicable` | 聚合程序（见 §6.3） |
| ContentQA 单条意见 | `verified` / `disputed` / `unsupported` / `needs_human_review` / `not_checked` | 程序 + 人工 |

不做映射表。ContentQA 的 `needs_review` **不等于** CourseControl 的 `incomplete`，也**不能**被写成 `incomplete` 或 `pass`。

### 4.4 写入边界

| 写入位置 | 内容 | 前提 |
| --- | --- | --- |
| `ContentQA/reports/<slug>/<run-id>/` | 审查报告、输入清单、日志 | 默认；不入库 |
| `ContentQA/drafts/<slug>/<run-id>/` | 模型生成的**草稿** | 只给人工采纳；永不直接写 `lessons/` |
| `build/<slug>/narration/segments/*.wav` | 逐页/逐段旁白 | 仅 `content-qa narrate` |
| `build/<slug>/narration/<master>.wav` | 合成母带 | 默认不覆盖；`--force` 才能替换 |
| `build/<slug>/narration/narration.manifest.json` | 旁白追溯清单 | 与母带同批写入 |
| `config/content-qa.yaml` | 本机配置 | 已忽略；只提交 `content-qa.example.yaml` |

理由：`build/<slug>/narration/` 本来就是旁白的**输入目录**（`collect.py:141-152` 与 `RemotionStudio/scripts/stage-assets.mjs` 只读 `narration.source` 指向的那一个文件），手工合成的 WAV 也放这里。ContentQA 生成旁白落在同一位置，不新造契约；多出来的 `segments/` 与 manifest 不会被控制层扫描：

- `collect` 只读 `paths.narration_path(narration.source)`；
- staging 只复制 `shots.json` 声明的文件；
- `artifacts[]` 只收集阶段 outputs 与 `final/`。

> 报告放在 `ContentQA/reports/` 而不是 `build/<slug>/`，是因为 `build/` 会在构建与提交前清理；审查报告需要跨构建保留，而且可能包含原文摘录，不适合入库。

### 4.5 旁白接入的现有硬限制

`lesson.yaml` 的 `narration` 只有 `enabled` 与 `source` 两个字段，`source` 相对 `build/<slug>/narration/`，且一次构建只消费**一个 WAV**。因此：

- ContentQA 可以按页生成，但必须再合成一条母带，才能进入现有构建；
- 无法在 `lesson.yaml` 里登记“第 3 页用第 3 段音频”；
- ContentQA **不自己改 `lesson.yaml`**：`narrate` 结束后打印需要人工写入的 YAML 片段。

---

## 5. 推荐的最小实现架构

### 5.1 目录与模块取舍

```text
ContentQA/
  pyproject.toml                 # uv 项目，Python 3.12，独立 .venv
  uv.lock
  README.md
  .gitignore                     # .venv/ __pycache__/ reports/ drafts/
  src/content_qa/
    contracts.py                 # R1  claim / check / report / manifest 模型
    paths.py                     # R1  路径规则（独立实现）
    config.py                    # R1  配置与环境变量
    hashing.py                   # R1  规范化与 SHA-256
    aggregate.py                 # R1  状态聚合（唯一判定入口）
    report.py                    # R1  读写与导出 schema
    cli.py                       # R1  子命令骨架
    evidence.py                  # R2  来源清单、定位、引用支持判定
    model_client.py              # R2  OpenAI 兼容客户端（urllib）
    review.py                    # R2  审查编排与 JSON 校验
    generation.py                # R2  可选：草稿生成（只写 drafts/）
    formula_check.py             # R2  SymPy / 数值检查
    align.py                     # R3  文本、字幕、旁白对齐
    narration.py                 # R3  CosyVoice 调用与 manifest
    asr.py                       # R3  可选后端接口（默认无实现）
    media_check.py               # R4  ffprobe / ffmpeg 检查
  schemas/
    content-manifest.schema.json
    review-report.schema.json
    narration-manifest.schema.json
  tests/
  fixtures/
```

与建议结构的差异（有意的简化）：

| 建议项 | 决定 | 理由 |
| --- | --- | --- |
| `text_alignment.py` | 合并进 `align.py` | 旁白、字幕、讲稿用的是同一套规范化与差异算法 |
| `review.py` 与 `report.py` 分开 | 保留 | 编排与序列化解耦，测试更容易注入 |
| `narration.py` 单独 | 保留 | 唯一写 `build/` 的模块，边界要显眼 |
| 额外 `aggregate.py` | 新增 | 状态判定必须集中，不能让模型输出决定 |
| 额外 `hashing.py` | 新增 | 讲稿、字幕、音频、输入快照共用 |
| 不建 `orchestrator/`、`agent/`、`vectorstore/` | 不建 | 顺序 CLI 足够；禁止引入编排框架与向量库 |

### 5.2 审查流水线（对应任务书 §四 的 8 步）

```text
lessons/<slug>/ ──┐
                  ├─► [1] 输入快照 + 哈希 ──► content-manifest.json
sources.yaml ─────┘                │
                                   ▼
                       [2]（可选）模型 A 生成草稿 ──► drafts/<run>/
                                   │
                                   ▼
                       [3] 模型 B 独立读原文 + 产物（不含 A 的推理）
                                   │
                                   ▼
                       [4] 结构化报告（严格 JSON）
                                   │
                                   ▼
                       [5] 程序校验：schema、必填、证据定位可解析
                                   │
                                   ▼
                       [6] 确定性检查：SymPy / 数值 / 哈希 / 字幕 / 媒体
                                   │
                                   ▼
                       [7] 聚合：claim 状态 + run 状态（程序判定）
                                   │
                                   ▼
                       [8] 人工队列：needs_human_review 清单
```

### 5.3 模型与程序的职责分工

| 动作 | 模型 | 程序 | 人工 |
| --- | --- | --- | --- |
| 提取论断、提出检查项 | 是 | 校验格式与 ID | 采纳/删除检查项 |
| 判定“有/无证据支持” | 是（只能提候选） | 定位与引文包含关系 | 争议裁决 |
| 公式与数值正确性 | 否 | SymPy / 数值 | 无法形式化的推导 |
| 文本哈希、时长、字幕轴 | 否 | 是 | 阈值口径 |
| 最终 `verified` | 否 | 确定性通过才可标 | 人工签署可标 |
| run 状态 | 否 | 是 | — |

### 5.4 配置

`config/content-qa.example.yaml`（入库）+ `config/content-qa.yaml`（本机、忽略）：

```yaml
schema_version: 1
model:
  base_url: "http://127.0.0.1:8080/v1"
  api_key: null                 # 本地服务通常不校验；需要时填 "sk-local"
  reviewer_model: "default"     # 用 /v1/models 的返回名，不写死
  generator_model: null         # null = 不生成草稿
  timeout_seconds: 120
  max_tokens: 2048
  temperature: 0
  retries: 1
tts:
  base_url: "http://127.0.0.1:50000"
  mode: zero_shot               # zero_shot | sft
  speaker: null
  prompt_wav: null
  prompt_text: null
  speed: 1.0
  text_frontend: true
  timeout_seconds: 300
  retries: 2
  target_sample_rate: 48000
checks:
  media:
    required_sample_rate: 48000
    audio_video_delta_s: 0.5
    black_min_duration_s: 0.5
    freeze_min_duration_s: 1.0
  text:
    ignore_line_patterns: ["^（.*）$"]   # 导播提示，不进 TTS
    require_numbers: true
    require_terms: true
```

环境变量覆盖：`CONTENT_QA_CONFIG`、`CONTENT_QA_MODEL_BASE_URL`、`CONTENT_QA_TTS_BASE_URL`、`CONTENT_QA_MODEL`。配置里不写本机绝对路径；需要 ffmpeg 路径时读 `config/tools.yaml`。

---

## 6. 审查契约设计

### 6.1 单条意见（claim record）

字段名与任务书一致，末尾三项为补充：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `claim_id` | string | 稳定 ID：`c_` + `sha256(section_id + "\n" + normalized_text)[:12]`；正文不变则 ID 不变 |
| `section_id` | string | `slide-001` …；子页 `slide-003b` |
| `source_id` | string\|null | `sources.yaml` 的 id；无来源为 `null` |
| `source_locator` | string\|null | 定位串，见 §6.4；无来源为 `null` |
| `claim_text` | string | 被审查的原文断言（规范化前，保留原样） |
| `evidence_quote` | string\|null | 来源中的原文片段；必须能在定位范围内逐字命中 |
| `issue_type` | enum | `factual_mismatch` / `missing_citation` / `citation_mismatch` / `overreach` / `formula_error` / `numeric_error` / `terminology` / `tts_text_mismatch` / `subtitle_omission` / `subtitle_timing` / `media_anomaly` / `other` |
| `severity` | enum | `blocker` / `major` / `minor` / `info` |
| `review_status` | enum | 见 §6.2 |
| `explanation` | string | 为什么判成这样；不得只写“模型认为” |
| `reviewer_model` | string | 实际返回的模型名；程序校验非空 |
| `confidence` | number 0–1 | **模型自评，仅供排序**；不参与任何判定 |
| `deterministic_checks` | object[] | `{id, status, expected, actual, detail}` |
| `human_signoff` | object\|null | `{reviewer, at, decision, note}`；人工批准 `verified` 的唯一途径 |

### 6.2 单条状态

| 状态 | 判定者 | 含义 | 能否自动产生 |
| --- | --- | --- | --- |
| `verified` | 程序 + 证据 | 确定性检查通过，且有可解析的来源与命中引文 | 仅当检查通过；否则必须人工签署 |
| `disputed` | 程序 | 确定性检查失败，或引文与断言明显冲突且定位可解析 | 是 |
| `unsupported` | 程序 | `source_id` 缺失，或定位不可解析，或引文未命中 | 是 |
| `needs_human_review` | 程序 | 模型无法判定、输出不合法、双方冲突、置信度不作为依据 | 是 |
| `not_checked` | 程序 | 没有适用的检查器 | 是 |

硬规则：

1. **模型不能直接产出 `verified`**。模型返回的 `verified` 一律降级为 `needs_human_review`。
2. 模型返回的 `disputed` / `unsupported` 只有在定位可解析、引文可核对时才被采纳；否则降级。
3. `confidence` 不参与任何比较与判定。
4. 两个模型意见一致 → 仍然 `needs_human_review`，不自动 `verified`。
5. `discrepancies=[]` → 不产生 `pass`。

### 6.3 run 状态（程序唯一判定）

```text
fail            任一确定性检查失败，或存在被证据确认的 disputed（severity >= major）
needs_review    存在 needs_human_review / unsupported / not_checked；
                或所有意见都是模型提出、无确定性支撑
pass            所有 claim 为 verified（确定性或人工签署），
                无未决项，且所有执行过的检查通过
not_run         没有执行任何检查（例如服务不可用且未配置离线检查）
not_applicable  请求的检查域在当前课程配置下完全不适用（例如未启用旁白时的声学检查）
```

补充记录：

| 字段 | 值 | 说明 |
| --- | --- | --- |
| `reviewer_independence` | `separate_model` / `same_model` / `none` | 由实际模型名与生成模型名比较得出 |
| `evidence_mode` | `source_text` / `quote_only` / `none` | B 是否读到原文正文 |
| `max_auto_status` | `needs_review` | 只要 `evidence_mode != source_text` 或独立性不足，run 不得为 `pass` |

### 6.4 证据定位

`sources.yaml`（建议，待人工确认）：

```yaml
schema_version: 1
lesson: 01-transformer-demo
sources:
  - id: vaswani-2017
    kind: paper
    title: "Attention Is All You Need"
    citation: "Vaswani et al., 2017"
    text_path: sources/vaswani-2017.txt     # 相对 lessons/<slug>/
    text_sha256: "<64 hex>"
    locator_scheme: page                    # page | lines
```

定位串（`source_locator`）：

| 形式 | 解析 |
| --- | --- |
| `page:4` | 文本文件中 `<!-- page: 4 -->` 到下一个页标记之间的内容 |
| `lines:120-138` | 文件的第 120–138 行 |
| `page:4§3.2.1` | 页范围内再按标题锚点收窄（可选，R2 可延后） |

校验规则（确定性）：

1. `text_sha256` 与文件实际哈希一致，否则整份来源作废并记 `source_stale`。
2. 定位可解析，否则 `unsupported`。
3. 规范化（换行/空白折叠）后，`evidence_quote` 必须是定位范围的子串，否则 `unsupported`。
4. 报告里记录定位的字符偏移与来源快照哈希，便于复核。

**不自动下载任何资料**。`sources.yaml` 只能指向本地文件；无网络抓取代码路径。

---

## 7. 四类交叉验证的实现方案

### A. 原始资料与事实核验（R2）

| 项 | 方案 |
| --- | --- |
| 输入 | `slides.md`、`lecture_notes.md`、`sources.yaml`、来源文本 |
| 确定性部分 | 每次断言必须有 `source_id`；定位可解析；引文逐字命中；数字/术语必须出现在引文或断言中 |
| 模型部分 | 模型 B 读**来源正文 + 产物文本**，输出 issue 候选；不含模型 A 的推理过程 |
| 失败语义 | 缺来源 → `unsupported`；定位失效 → `unsupported`；引文不支持 → `disputed` |
| 人工 | 所有 `disputed` 与 `needs_human_review` 进入队列；论文外推结论一律人工 |
| 首个对象 | `01-transformer-demo`（8 页，1 个动画，数字少，适合做基线） |

现成靶子（来自课文本身，`VERIFIED`）：

| 断言 | 定位 | 可验证性 |
| --- | --- | --- |
| 循环需 O(n) 串行步；注意力路径 O(1)；复杂度 O(n²) | Slide 2 / Slide 7 | 定性 + 术语；需人工确认口径 |
| `8 heads × 64 dims = 512` | Slide 4 | 算术可验证；“base 模型”限定需引文 |
| `Attention = softmax(QKᵀ/√d_k)V` | Slide 3 | 公式可形式化 |
| `PE(pos,2i)=sin(pos/10000^{2i/d_model})` | Slide 5 | 公式可形式化 |
| 原始模型堆叠 6 层 | Slide 6 | 需论文引文 |
| 点积方差 ≈ d_k（单位方差独立假设） | Slide 3 notes | 可用 SymPy/数值验证 |

### B. 公式与数值验证（R2）

| 项 | 方案 |
| --- | --- |
| 工具 | SymPy（符号）、Python 数值（蒙特卡洛，固定随机种子）、`unittest` |
| 检查项来源 | 模型只**提议**检查项，写成 `proposed_checks[]`，状态 `needs_human_review`；人工批准后固化为课内检查文件 |
| 执行 | 程序运行检查；结果写 `deterministic_checks[]` |
| 不做的 | 不解析任意 LaTeX；不把模型对公式的解释当证明 |
| 现有示例 | `ManimSandbox/01-transformer-demo/dot_product.py`：a=(1,3)、b=(3,1)、a·b=6、投影 0.6b —— 可直接写成数值断言 |

检查项存放（待 R1 定稿）：`lessons/<slug>/qa/checks.py` 或 `ContentQA/fixtures/checks/<slug>.yaml`。二者都**不由模型直接执行**；执行前需人工 review 代码。

### C. 逐字稿、旁白与字幕验证（R3）

| 项 | 方案 |
| --- | --- |
| 讲稿哈希 | `lecture_notes.md` 整体 SHA-256 + 每页“逐字口播”块 SHA-256 |
| 规范化 | NFKC、去首尾空白、折叠空白、排除导播提示（`（等待动画切入）` 之类）；算法版本写入 manifest |
| TTS 输入哈希 | 实际发送给 CosyVoice 的字符串哈希（规范化后） |
| 音频 | WAV SHA-256、采样率、声道、时长、生成时间、模型与音色参数 |
| 反向转写 | 可选 ASR；无后端时该检查 `not_checked`，明确写入报告 |
| 对齐 | 原稿 vs ASR/字幕文本的规范化差异；数字、单位、英文术语强制核对；相似度仅作参考 |
| 阈值 | **不使用统一的 1% 编辑距离**；按语言/课程/术语表配置，默认只对数字与术语做硬性判定 |
| 失败语义 | 数字缺失/错位 → `major`；术语异常 → `minor`；无法识别 → `needs_human_review` |

ASR 现状与选项（需人工决策）：

| 选项 | 代价 | 备注 |
| --- | --- | --- |
| 不装 ASR | R3 只做哈希/时长/字幕文本对齐 | 无法发现“读错但时长对”的问题 |
| whisper.cpp | 需要额外二进制与模型权重 | 权重须放在工作区外，且不得自动下载 |
| faster-whisper | 在 `ContentQA/.venv` 安装 + 下载模型 | 增加依赖与磁盘；模型缓存位置需指定 |

### D. 音画与媒体验证（R4）

| 检查 | 方法 | 失败级别 |
| --- | --- | --- |
| 音频流存在、采样率/声道 | `ffprobe` | fail |
| 音视频时长差 | `ffprobe`（与 V-15 同口径） | fail |
| 成片 vs 时间线时长 | `shots.json.timeline.total_duration_s` | fail |
| 字幕 cue 单调、重叠、越界 | 解析 SRT + 成片时长 | fail |
| 字幕覆盖与旁白时间轴 | 与 manifest 的段落起止对照 | needs_review |
| 黑帧 | `ffmpeg blackdetect` | major |
| 冻结帧 | `ffmpeg freezedetect` | major |
| 关键帧/首帧 | 抽帧均值亮度（可选） | info |
| 分镜一致性 | 视觉模型对照 storyboard 描述 | **仅提示**，永不作为判定 |

---

## 8. 旁白生成工具（`content-qa narrate`）

### 8.1 命令

```powershell
uv run --project ContentQA content-qa narrate --lesson 01-transformer-demo `
  --mode zero_shot --segment page --out narration.wav [--force] [--dry-run]

# 只记录已有手工 WAV 的哈希与参数，不调用 TTS
uv run --project ContentQA content-qa narrate --lesson 01-transformer-demo `
  --import build/01-transformer-demo/narration/narration.wav
```

| 参数 | 说明 |
| --- | --- |
| `--mode` | `zero_shot` / `sft`，与 CosyVoice 两种启动脚本对应 |
| `--speaker` | SFT 音色；`/speakers` 的返回值 |
| `--segment` | `page`（默认）/ `paragraph` |
| `--out` | 母带文件名，默认 `narration.wav`，相对 `build/<slug>/narration/` |
| `--force` | 允许覆盖已存在母带；默认拒绝 |
| `--dry-run` | 只列文本、哈希与请求体，不发请求 |
| `--import` | 为手工 WAV 补 manifest |
| `--timeout` / `--retries` | 覆盖配置 |

### 8.2 行为

1. 解析 `lecture_notes.md` 的 `### Slide N` 块，取 `#### 逐字口播` 段落；按配置排除导播提示行。
2. 逐页调用 `POST /tts`（JSON 体，字段见 §1.3），保存 `segments/slide-NNN.wav`。
3. 每段记录：`source_notes_sha256`、`segment_text_sha256`、`tts_text_sha256`、`audio_sha256`、`sample_rate`、`channels`、`duration_s`、`generated_at`、`tts_model`、`mode`、`speaker|prompt_wav`、`speed`、`text_frontend`、`X-Synth-Seconds`。
4. 失败重试：5xx/超时重试 `retries` 次；4xx 不重试；最终失败保留已完成段与失败原因。
5. 全段成功后用 ffmpeg 合成母带：单声道、48 kHz、`pcm_s16le`。合并不改变现有构建契约。
6. 写 `narration.manifest.json`（同目录），并在报告中记录其哈希。
7. 不修改 `lesson.yaml`；打印：

```yaml
narration:
  enabled: true
  source: narration.wav
```

### 8.3 安全与回退

- 母带已存在且 manifest 的文本哈希不一致 → 拒绝覆盖，提示改用 `--out narration.v2.wav`。
- 服务不可用 → 退出码 5，明确写“8080/50000 未监听或加载中”，**不尝试启动服务**。
- 保留手工流程：手工合成的 WAV 仍可直接放入 `build/<slug>/narration/`；`--import` 只是补记录。
- 逐页时长与 `时长预算` 的偏差单独报告（确定性检查），不因音频长短自动改课程时间线。

---

## 9. 需要新增的文件

图例：是 = 入库；否 = 不入库（忽略）；人工 = 由人工编写，ContentQA 不代写。

| 阶段 | 路径 | 类型 | 入库 |
| --- | --- | --- | --- |
| R0 | `docs/ContentQA_实施评估.md` | 本文 | 是 |
| R1 | `ContentQA/pyproject.toml`、`uv.lock` | uv 项目 | 是 |
| R1 | `ContentQA/.gitignore` | 忽略 `.venv/`、`__pycache__/`、`reports/`、`drafts/` | 是 |
| R1 | `ContentQA/README.md` | 用法与边界 | 是 |
| R1 | `ContentQA/src/content_qa/{__init__,contracts,paths,config,hashing,aggregate,report,cli}.py` | 契约与骨架 | 是 |
| R1 | `ContentQA/schemas/{content-manifest,review-report}.schema.json` | 由模型导出 | 是 |
| R1 | `ContentQA/tests/{test_contracts,test_paths,test_aggregate,test_cli}.py` | 离线单测 | 是 |
| R1 | `ContentQA/fixtures/review-report-{valid,invalid}.json` | 夹具 | 是 |
| R1 | `config/content-qa.example.yaml` | 配置模板 | 是 |
| R1 | `.gitignore` 追加 `config/content-qa.yaml` | 根忽略规则 | 是 |
| R1 | `docs/ContentQA-契约-v1.md` | 契约说明 | 是 |
| R2 | `ContentQA/src/content_qa/{evidence,model_client,review,generation,formula_check}.py` | 事实与公式 | 是 |
| R2 | `ContentQA/tests/{test_evidence,test_model_client,test_review,test_formula}.py` | 单测（含假 HTTP 服务） | 是 |
| R2 | `ContentQA/fixtures/canned/*.json` | 固定模型响应 | 是 |
| R2 | `lessons/<slug>/sources.yaml` + `lessons/<slug>/sources/*.txt` | 证据语料 | 人工（待确认） |
| R3 | `ContentQA/src/content_qa/{align,narration,asr}.py` | 旁白与对齐 | 是 |
| R3 | `ContentQA/schemas/narration-manifest.schema.json` | 旁白清单 | 是 |
| R3 | `ContentQA/tests/{test_alignment,test_narration,test_asr}.py` | 单测（mock HTTP） | 是 |
| R3 | `build/<slug>/narration/{segments/*.wav,narration.manifest.json}` | 运行产物 | 否 |
| R4 | `ContentQA/src/content_qa/media_check.py` | 媒体检查 | 是 |
| R4 | `ContentQA/tests/{test_media,test_integration}.py` | 单测 + 可选集成 | 是 |
| R4 | `ContentQA/fixtures/media/*` | 短样本（脚本生成） | 是 |
| 运行期 | `ContentQA/reports/<slug>/<run-id>/` | 报告 | 否 |
| 运行期 | `ContentQA/drafts/<slug>/<run-id>/` | 草稿 | 否 |

不新增：`shared/schemas/` 中的 ContentQA schema（无第二消费方前不升级为共享契约）、任何 `build/<slug>/qa/` 目录、任何 Agent/向量库目录。

---

## 10. 依赖与运行环境

| 项 | 方案 | 位置 |
| --- | --- | --- |
| Python | `>=3.12,<3.13`，与 CourseControl 一致 | `ContentQA/.venv` |
| 包管理 | uv（`uv sync` / `uv add` / `uv run`） | 本机已有 `0.10.8` |
| 运行时依赖 | `pydantic>=2.9,<3`、`PyYAML>=6,<7` | `ContentQA/.venv` |
| R2 依赖 | `sympy`（版本在 R2 锁定时确定） | `ContentQA/.venv` |
| 可选 | `pypdf`（纯 Python，若决定支持 PDF 原文） | 待确认 |
| 不装 | OpenAI SDK、requests、pytest、LangChain/LangGraph、向量库 | — |
| HTTP | 标准库 `urllib.request`（JSON + 二进制） | — |
| 测试 | 标准库 `unittest`，与 CourseControl 同风格 | — |
| 媒体 | 系统 `ffmpeg`/`ffprobe` 8.1，或 `config/tools.yaml` 的路径 | 只读调用 |
| 模型 | `http://127.0.0.1:8080/v1`，模型名运行时从 `/v1/models` 读 | 不管理进程 |
| TTS | `http://127.0.0.1:50000` | 不管理进程 |
| ASR | 无 | 待人工决定 |

约束：

- 不改 `CourseControl/pyproject.toml`、`uv.lock`、`.venv`。
- 不用系统 Python 安装依赖；不全局 `pip install`。
- `<AI_ROOT>` 只读；不写入、不迁移、不下载模型。
- ContentQA 的锁文件独立，升级不影响构建层。

---

## 11. 测试与验收设计

### 11.1 分层

| 层 | 内容 | 是否联网 |
| --- | --- | --- |
| L0 单元 | 契约、路径、哈希、状态聚合、SRT 解析、JSON 校验 | 否 |
| L1 模拟服务 | 本地 `ThreadingHTTPServer` 返回固定 JSON；断言重试、超时、非法 JSON、5xx | 仅回环 |
| L2 媒体 | 用 `ffmpeg lavfi` 生成短样本，跑媒体检查 | 否 |
| L3 集成（可选） | 真实 `8080` / `50000`；`CONTENT_QA_INTEGRATION=1` 才运行 | 是 |

### 11.2 任务书 15 个场景 → 用例

| # | 场景 | 构造 | 期望 |
| --- | --- | --- | --- |
| 1 | 正常讲稿审查 | 夹具课程 + 全部来源命中 | run `pass`（或 `needs_review`，取决于是否有模型意见） |
| 2 | 错误论断注入 | 改一句与来源冲突 | `disputed`，run `fail` |
| 3 | 缺失引用注入 | 删除 `source_id` | `unsupported`，run `needs_review` |
| 4 | 公式错误注入 | 把 `√d_k` 改成 `d_k` | `formula_error`，确定性失败 |
| 5 | 讲稿修改后哈希变化 | 改一个字符 | 页哈希变，manifest 标记受影响段 |
| 6 | TTS 音频损坏 | 截断 WAV / 0 字节 | `media_anomaly`，run `fail` |
| 7 | 旁白与讲稿不一致 | ASR 文本与原文差异（或字幕文本差异） | `tts_text_mismatch` |
| 8 | 字幕漏字 | 删除 cue 中一个数字 | `subtitle_omission` |
| 9 | 字幕时间轴异常 | cue 逆序 / 结束超过成片 | `subtitle_timing`，fail |
| 10 | 音频时长异常 | 6 秒视频 + 10 秒音频 | fail（与 V-15 口径一致） |
| 11 | 模型服务不可用 | 连接被拒 | run `not_run`，退出码 5，不无限重试 |
| 12 | CosyVoice 不可用 | 连接被拒 | `narrate` 退出码 5，不写母带 |
| 13 | 模型输出非法 JSON | 返回 `{...` 截断 | 1 次修复重试后 `needs_human_review` |
| 14 | 两个模型意见冲突 | 两个固定响应相反 | `needs_human_review`，run 不得 `pass` |
| 15 | 缺少原始证据 | 无 `sources.yaml` | `unsupported` / `not_checked`，run `needs_review` |

补充用例：

| # | 场景 | 期望 |
| --- | --- | --- |
| 16 | 在 `lesson.yaml` 写未知字段 | ContentQA 拒绝并提示“不得修改 lesson.yaml” |
| 17 | `source_locator` 越界 | `unsupported`，不抛异常 |
| 18 | 引文只差全角/半角 | 规范化后命中；记录原始差异 |
| 19 | 母带已存在 | 默认拒绝覆盖，退出码 4 |
| 20 | 路径含 `..` / 反斜杠 | 拒绝，与 CourseControl 规则一致 |

### 11.3 验收原则

- 每个失败用例必须断言**具体的状态词与退出码**，不能只断言“非零”。
- 测试不修改 `lessons/`、`build/`、`shared/`；全部在临时目录与 `ContentQA/fixtures/` 内。
- 模型相关单测不得依赖服务在线；真实调用只在 L3。
- 每次改 ContentQA 后额外跑 `uv run --project CourseControl python -m unittest discover -s CourseControl/tests`，证明未影响控制层。

---

## 12. 风险与需要人工确认的事项

### 12.1 风险

| 编号 | 风险 | 等级 | 依据 | 处理 |
| --- | --- | --- | --- | --- |
| R-01 | 在 `lesson.yaml` 加 QA 字段会让 validate 直接失败 | 高 | `extra="forbid"`（`contracts.py:20`） | QA 配置独立成文件；报告与 manifest 不进课程契约 |
| R-02 | “模型 A/B”实际共享一个 llama.cpp 实例 | 高 | `8080` 未运行；启动脚本单模型 | 记录 `reviewer_independence`；非独立时 run 上限 `needs_review` |
| R-03 | 没有来源清单，事实核验无法启动 | 高 | 全仓库无 `sources.yaml` | R2 前置：人工提供来源与摘录 |
| R-04 | 无 ASR，文本→音频闭环缺一半 | 中 | `<AI_ROOT>` 无 ASR 权重 | R3 先做确定性部分；ASR 单独决策 |
| R-05 | 模型输出不合法 JSON | 中 | 本地模型 16K/32K 档 | 严格 schema + 1 次修复 + 降级 `needs_human_review` |
| R-06 | 两个模型一致被误当正确 | 中 | 任务书 §四 | 状态规则禁止模型产出 `verified` |
| R-07 | 报告含论文原句，入库有版权与体积问题 | 中 | 报告需引文 | `ContentQA/reports/` 忽略；只提交 schema 与夹具 |
| R-08 | 覆写旁白母带 | 中 | 现有手工流程无保护 | manifest 哈希哨兵 + `--force` |
| R-09 | ContentQA 写 `build/` 越界 | 中 | PRD 写入归属矩阵 | 只写 `narration/`；其余只读 |
| R-10 | Windows 控制台编码 | 低 | CourseControl 已做 `reconfigure` | 同法处理 |
| R-11 | ffmpeg 不在 PATH | 低 | 当前在 PATH，但机器可变 | 读 `config/tools.yaml`，失败即报错 |
| R-12 | 阈值被“调松通过” | 中 | 任务书 §九 | 阈值进配置并有测试锁定；变更需记录 |
| R-13 | 依赖膨胀 | 低 | 仅 pydantic/PyYAML/SymPy | 不做 SDK、不引框架 |
| R-14 | 文档与代码漂移（R5 矩阵状态过期） | 低 | §1.1 | 阶段文档更新时同步 |

### 12.2 需要人工确认（进入 R1/R2 前）

| 编号 | 事项 | 建议默认 |
| --- | --- | --- |
| D-01 | `sources.yaml` 由谁维护、放在 `lessons/<slug>/` 是否可接受 | 人工维护；ContentQA 只读 |
| D-02 | 论文正文如何入仓：提交短摘录，还是只在本机保留全文并以哈希登记 | 提交短摘录 + 本机全文路径留在 `config/content-qa.yaml` |
| D-03 | 模型 A/B 是否接受“人工换模型”作为独立性手段 | 接受；报告记录独立性等级 |
| D-04 | 是否安装 ASR（选型与位置） | 暂不安装；R3 保留接口 |
| D-05 | 是否允许 `pypdf` 解析 PDF | 暂不允许；先用手工文本摘录 |
| D-06 | 报告存放位置 `ContentQA/reports/` 是否可接受 | 接受；不入库 |
| D-07 | 旁白母带命名与覆盖策略 | 默认 `narration.wav`，不覆盖 |
| D-08 | 视觉模型是否允许参与（仅提示） | 默认关闭 |
| D-09 | 术语表与阈值维护方式（按课程 YAML 还是独立文件） | R3 再定 |
| D-10 | ContentQA 是否需要在 `check.ps1` 里加只读健康探测 | 建议 R4 加；不阻塞构建 |

---

## 13. R1 具体实施计划

**目标**：把“契约、状态、报告、配置、CLI 骨架、离线测试”落地，不调用模型、不写 `build/`、不改 CourseControl。

### 13.1 任务

| 编号 | 任务 | 产物 | 验收 |
| --- | --- | --- | --- |
| T1.1 | 初始化 `ContentQA`（uv，`content_qa`，Python 3.12，依赖 pydantic + PyYAML） | `pyproject.toml`、`uv.lock`、`.venv` | `uv sync --locked` 通过 |
| T1.2 | `contracts.py`：`EvidenceSource`、`ClaimRecord`、`DeterministicCheck`、`ReviewReport`、`ContentManifest`、`NarrationManifest`（模型先定义，R3 导出） | 模型 + `schemas/` | `content-qa schema --check` 通过 |
| T1.3 | `paths.py`：与 CourseControl 同语义的 `path_problem` | 函数 + 测试 | 20 条表驱动用例通过 |
| T1.4 | `hashing.py`：NFKC 规范化、逐字口播抽取、文件/文本 SHA-256、算法版本号 | 函数 + 测试 | 修改一个字符即产生不同哈希 |
| T1.5 | `aggregate.py`：claim 状态与 run 状态计算（§6.3）；模型输入只能落在允许的枚举 | 函数 + 测试 | 覆盖 15 个场景中与状态相关的 8 个 |
| T1.6 | `config.py`：读 `config/content-qa.yaml`、环境变量覆盖、缺配置时的明确错误 | 函数 + 测试 | 无配置时不静默使用假默认值 |
| T1.7 | `report.py`：读写、按 schema 校验、run 目录命名、相对路径约束 | 函数 + 测试 | 非法报告被拒绝并给出字段位置 |
| T1.8 | `cli.py`：`schema`、`check-inputs`、`report validate`、`narrate --dry-run`（占位）、`review --dry-run`（占位） | CLI | 未实现命令以退出码 4 + 明确说明结束 |
| T1.9 | `config/content-qa.example.yaml` + 根 `.gitignore` 追加 `config/content-qa.yaml` | 配置模板 | `git check-ignore` 命中 |
| T1.10 | 文档：`docs/ContentQA-契约-v1.md`；`README.md` 工程分工表加一行 `ContentQA/`；目录树更新 | 文档 | 链接有效，占位符一致 |
| T1.11 | 回归：跑 CourseControl 单测与 `check.ps1` | 证据 | 10 个用例仍通过，`check ok` |

### 13.2 出口验收

- [ ] `cd ContentQA; uv sync --locked` 成功，`.venv` 只含声明依赖。
- [ ] `uv run content-qa schema --check` 成功，schema 与模型一致。
- [ ] `uv run python -m unittest discover -s tests` 全绿，且**无网络访问**。
- [ ] `uv run --project ../CourseControl python -m unittest discover -s ../CourseControl/tests` 仍 10 个用例通过。
- [ ] `.\scripts\check.ps1` 输出 `check ok`。
- [ ] 未创建 `build/` 写入、未调用 `8080`/`50000`、未修改 `lessons/`。
- [ ] 报告与草稿目录已被忽略；`git status` 只显示预期文件。
- [ ] 本文 §12.2 的 D-01、D-02、D-06、D-07 已得到答复（其余可延后）。

### 13.3 R1 明确不做

- 不做模型调用、不做 TTS、不做媒体检查、不做证据语料导入。
- 不改 CourseControl 任何文件（包括 README、PRD、R5 矩阵）。
- 不创建 `lessons/<slug>/sources.yaml`（人工事项）。
- 不提交 Git（需另行确认）。

### 13.4 后续阶段预览

| 阶段 | 范围 | 前置 |
| --- | --- | --- |
| R2 | 证据、模型客户端、审查编排、公式/数值检查、报告 | D-01/D-02 答复；`sources.yaml` 就绪 |
| R3 | 规范化、逐页 TTS、manifest、字幕/文本对齐、ASR 接口 | D-03/D-04 答复；CosyVoice 可启动 |
| R4 | 音画与媒体检查、集成测试 | R2/R3 通过；短样本 |

---

## 14. 声明

- 本次审计只读：未改动代码、配置、依赖、课程正文、构建产物与 `<AI_ROOT>`；未启动或停止任何服务；未提交 Git。
- 唯一新增文件为本文 `docs/ContentQA_实施评估.md`。
- 本文所有结论均来自 §1.2 列出的实际读取；未读取的夹具内容、Shell 课程正文细节与 `project.ts` 正文未作断言。
- 等待人工确认 §12.2 的事项与 §13 的 R1 计划后再进入下一阶段。
