# 验收矩阵与命令

- **版本**：v1.6（2026-11-10）
- **上游**：[PRD.md](PRD.md)；结构与契约见 [ARCHITECTURE.md](ARCHITECTURE.md)
- 原则：**只记录真实执行结果**。未执行写 `NOT_RUN`，人工缺失写 `skipped`，凭据缺失写 `blocked`。
- 路径约定：`lessons/`、`build/`、`deliver/` 均相对**内容根**（`config/local-paths.yaml` 的 `content_root`，默认等于工作区；2026-11-12 起本机在工作区外）。

---

## 0. 2026-11-10 复核

本轮重跑六套单测，实际为 **647 个用例（641 通过 + 6 跳过）**：CourseControl 494、ModelingStudio 33、ai_runtime 50、ContentQA 25、Manim 18、KnowledgeStudio 27；`check.ps1` exit 0。新增的配置解析、检查点、resume、字幕 QC、裁决队列、vendor、镜头分类与证据分类测试都在这 494 之内。下面 §1 与 §8 的历史计数（412 / 550 / 465）保留为当时记录，不再作为当前基线；旧的加法 412+33+50+24+18+21=558 与"合计 550"也不一致，已按实跑数字更正。

## 0.1 2026-11-10 真实教材试点（Docling → KnowledgeStudio）

第一本真书：一本 352 页英文教材（标题与路径不入库），文本层完整。

| 项 | 实测 | 状态 |
| --- | --- | --- |
| Docling 转换 | 352/352 页，0 空页，0 warning，209.9 s | pass |
| Docling `validate` | 14 pass / 0 warn / 0 fail | pass |
| PDF 书签 | 18 条；章节边界以书签为准 | pass |
| KnowledgeStudio 导入 | 18 个单元；`verify` KS-01…KS-08 | pass |
| `extract-report` | pass；短页 3、超长页 11，长行多为 cosmetic | pass |
| 教材 claim | 5 条；`evidence` + `span-check` 5/5 | pass |
| 现代产业证据 | 0 条 | **未开始** |

命令与结果见 [KnowledgeStudio.md](KnowledgeStudio.md) §7.1、§12，以及 Docling `README.md` §12。`span-check` 第一次运行抓到一条"看起来对、实际不连续"的 quote（版面侧栏插进正文），修正后通过——这是结构校验，不是真伪判断。

**未完成**：现代成本/价格/能源证据尚未采集；该集未写旁白、未做幻灯片、未渲染。不要把本节的"教材入库"当成"课程已验证"。

## 0.2 无声观看原则（Silent Viewing Principle）

> 如果把旁白关掉，单看画面，它是不是仍然像一条有设计、有过程、有表达目的的视频，而不是一份会动的 PPT？

这是 CourseWorkspace 的最高层视觉验收原则，优先级高于动画数量、镜头数量、3D 使用比例和特效复杂度。任何样片与成片在人工验收前，先做一次无声播放审查。

它要求：

1. **画面独立成立**：不能只靠旁白解释画面上有什么。
2. **画面有发展过程**：视觉对象应发生变化，而不是依次出现。
3. **画面有表达目的**：每个镜头都在展示、解释、比较、揭示或强调某件事。
4. **画面有视觉设计**：构图、层次、色彩、空间、运动保持统一。
5. **画面有节奏**：有建立、发展、强调、停顿和转换，而不是全程匀速播放。

边界：无声观看不等于“所有知识必须仅凭画面完整理解”。公式、复杂理论和专业术语仍可由旁白解释；要求的是画面本身有独立的视觉叙事价值，不是把视频变成无声教学。

判定：无声播放时如果只剩文字、箭头、公式和逐页切换，即使 `check.ps1`、`media-qc`、构图检查全部通过，视觉质量仍不算达标。审查结果写入人工验收记录；未做无声审查的样片不得标为 `pass`。

## 0.3 语言与字幕（2026-11-11）

所有视频的画面文字与旁白用英文；字幕英文在上、中文在下。中文只做字幕与文章版本，默认不做中文配音。

验收时核对 `lesson.yaml` 的 `subtitles.top_language` / `bottom_language`、字幕文件与成片画面；不符合的按交付缺陷处理。规则来源：[DECISIONS.md](DECISIONS.md) D-084。

---

## 0.4 2026-11-12 动画预览（Animatic）实测

`course-control animatic --lesson <slug>`（FR-40）在三门真实课程上的结果。

| 项 | 实测 | 状态 |
| --- | --- | --- |
| `a01-why-cars-need-aerodynamics` | pages 模式，24 个片段单元，画面 1293.43 s，旁白 1292.84 s，`ok: true`；`page-024` 源片段短 0.6 s（`source_length` 警告，末帧冻结补齐） | pass |
| `01-transformer-demo` | pages 模式，12 个静态单元，1195.60 s，无旁白（`silent animatic` 警告），`ok: true` | pass |
| `ai-economics-e01` | shots 模式，43 个动画单元，1200.00 s，旁白 1050.72 s，`audio_sync` fail（差 149 s） | fail（真实问题） |
| 局部重生成 | `--shot page-005`：1 个重编、23 个复用 | pass |
| 换旁白 | `--audio narration_processed_raw.wav`：音频来源切换并重新混音 | pass |
| 单元测试 | `test_animatic.py` 11 例；CourseControl 全量 516 例通过 / 7 跳过 | pass |

`ai-economics-e01` 的失败不是工具噪声：`production.yaml` 排了 1200 s，旁白只有 1050.72 s，尾段 149 s 无声；同一门课在 `validate` 里另有 `[V-26] duration 1200.0s exceeds maximum 950.0s`。两项都待课程侧处理。

预览固定 480p，不写 `deliver/`，不作为交付判定；`ok: false` 时命令退出码为 1。

## 0.5 2026-11-12 声音资产（Voice Bible / Lexicon）实测

FR-41。用 `build/_p2-fixture/` 下的 a01 副本验证，未改真实课程。

| 项 | 实测 | 状态 |
| --- | --- | --- |
| 资产解析 | bible `wayne-en-v1` sha256 `917d43186a81…`；词典 `automotive-aerodynamics` sha256 `99ce7e544242…`，5 条 | pass |
| 参考音频相对路径 | `../../lessons/…/my_voice_en_ref_short.wav` 解析到内容根实体；声明哈希与文件一致，`problems` 为空 | pass |
| 词典改写 | 24 段中 5 段被改写（`Reynolds→Renolds` ×2、`CFD`、`SUV`、`BMW`、`Mercedes-Benz`） | pass |
| 旧缓存键 | `test_legacy_payload_is_unchanged` 重建旧 payload 比对，未声明资产的课键值不变 | pass |
| 单元测试 | `test_audio_assets.py` 17 例；CourseControl 全量 533 例通过 / 7 跳过 | pass |
| 真实 VoxCPM2 合成 | **NOT_RUN**（本轮未启动 50000 TTS 服务） | NOT_RUN |

因此"改词典后音频重新合成、换 bible 后音色一致"只验证到缓存键与文本改写这一层，没有真听。

## 0.6 2026-11-12 镜头表（Shot Sheet）实测

FR-42。用 `build/_p2-fixture/` 与 `build/_p3-broken/` 下的 a01 副本验证，未改真实课程。

| 项 | 实测 | 状态 |
| --- | --- | --- |
| v2 表编译 | 3 镜头全部带设计字段；`continuity: 2`、`assets: 3`、`evidence: 2`；无问题 | pass |
| 连续性追踪 | `car-half-body` → shot_002/003/009；`wake-ribbon` → shot_009；未使用的对象列入 `unused_continuity` | pass |
| 引用定位 | 故意写坏三处，分别报 `[V-45] ghost-object`、`[V-46] assets/missing.png`、`[V-47] E01 CFD 011`，均带镜头 id | pass |
| 设计指纹 | 同一表编译两次指纹一致；改 `director_notes` 后只有 shot_009 的指纹变化 | pass |
| 旧课程 | a01 真实 v1 表：`0 with sheet fields`、无问题、`validate` 与构建路径不变 | pass |
| 单元测试 | `test_shot_sheet.py` 9 例；CourseControl 全量 542 例通过 / 7 跳过 | pass |

导演计划合并、证据跨文件校验未实现，见 `docs/镜头表-ShotSheet.md` §7。

## 0.7 2026-11-12 锁定与分离实测

| 项 | 实测 | 状态 |
| --- | --- | --- |
| 打锁（a01） | `picture.lock.json` + `dialogue.lock.json` 写出；画面 24 个单元全部有文件 | pass |
| 锁内警告 | 镜头表 v1（无设计指纹）、旁白 meta schema 2（早于声音资产）——真实状态，未掩盖 | warn |
| 字幕对应 | 全部 cue 落在旁白段落内，`subtitles_mapped` pass | pass |
| 复查 | `lock-status` 两个锁均 `no drift` | pass |
| 分离检查 | `course-control separation`：`no lesson-shaped files in the workspace`（白名单为空；两份 Blender 课程任务、两个 Motion Canvas 场景目录、参考库与 golden 均已移出） | pass |
| 单元测试 | `test_locks.py` 12 例、`test_separation.py` 5 例；CourseControl 全量 559 例通过 / 7 跳过 | pass |
| Motion Canvas 渲染验证 | 迁移后两个课程场景均出片：`gui-vs-cli-paths` 367 帧 / 12.2 s、`attention-flow` 142 帧，`result pass`，H.264 可解码。根因是场景相对 import 的 `styles/` 未在内容根布局中提供（已加 junction）＋ headless Chrome 需 `--disable-gpu` | pass |

## 1. 一键回归

```powershell
.\scripts\check.ps1
# 期望：六套单测（含 KnowledgeStudio）+ Remotion 类型检查 + 课程契约（本地有课程时 6 个，干净克隆时 4 个夹具）+ 20 个场景契约，最后打印 check ok，exit 0
```

最近一次执行（2026-11-10）：**`check ok`，exit 0**。

| 套件 | 命令 | 用例数 | 结果 |
| --- | --- | --- | --- |
| CourseControl | `uv run --project CourseControl python -m unittest discover -s CourseControl/tests -t CourseControl` | 494（489 通过 + 5 跳过） | 489 通过，5 跳过 |
| ModelingStudio | `uv run --project ModelingStudio python -m unittest discover -s ModelingStudio/tests -t ModelingStudio` | 33 | 全部通过 |
| ai_runtime | `uv run --project shared/ai_runtime python -m unittest discover -s shared/ai_runtime/tests -t shared/ai_runtime` | 50 | 全部通过 |
| ContentQA | `uv run --project ContentQA python -m unittest discover -s ContentQA/tests -t ContentQA` | 25 | 全部通过 |
| ManimSandbox | `uv run --project ManimSandbox python -m unittest discover -s ManimSandbox/tests -t ManimSandbox` | 18（17 通过 + 1 跳过） | 17 通过，1 跳过 |
| KnowledgeStudio | `uv run --project KnowledgeStudio python -m unittest discover -s KnowledgeStudio/tests -t KnowledgeStudio` | 27 | 全部通过 |

合计 **647** 个用例（641 通过 + 6 跳过）；跳过项（Docker/录制等环境依赖）不计为通过。

### 1.1 V1-B 契约命令

```powershell
uv run --project CourseControl course-control schemas-v1 --output shared/schemas
uv run --project CourseControl course-control contract-v1-validate --kind timeline-v1 --file docs/contracts/examples/timeline.spec.json
uv run --project CourseControl course-control e6-adapt --workspace . --manifest build/manim-transformer/e6/manifest.json --output build/manim-transformer/e6/render.manifest.v1.json
python ManimSandbox/05-multi-head/verify_math.py --output build/manim-multi-head/e6.5/math-report.json
uv run --project CourseControl course-control e65-adapt --workspace . --manifest build/manim-multi-head/e6.5/manifest.json
```

- `schemas-v1`：导出 7 份 V1 JSON Schema。
- `contract-v1-validate`：按 `kind` 校验单个 V1 文件；非法输入 exit 1，未知 kind exit 2。
- 时间换算边界测试见 `CourseControl/tests/test_timecode.py`；模型与示例测试见 `CourseControl/tests/test_contracts_v1.py`；E6 V0 只读适配见 `CourseControl/tests/test_legacy_e6.py`。
- V1-E：`course-control timeline-v1 --lesson <slug>` 从现有 `shots.json` 写 `build/<slug>/contracts/timeline.spec.json`；`collect` 已自动写出。
- V1-D：`course-control session-evidence-v1 --spec <session.json> --workspace .` 把现有 `evidence.json` 升级为 `EvidenceManifestV1`。

---

## 2. 课程契约 V-01~V-22

| 编号 | 检查 | 实现 | 验证 |
| --- | --- | --- | --- |
| V-01 | slug 与目录一致 | `validators.py` | 5 个课程/夹具 validate 通过 |
| V-02 | 必需文件、recording 的 base_video | `validators.py` | 通过；历史故障注入见归档 R5 矩阵 |
| V-03 | 页数 = 讲师手册块数 | `validators.py` | 两门真实课 20/20、8/8 |
| V-04 | 四要素（时长预算/动画切入/技术核查/逐字口播） | `validators.py` | `test_missing_notes_element_fails` |
| V-05 | 素材路径 `<内容根>/lessons/<slug>/assets/` 且存在 | `validators.py` | 两门真实课通过 |
| V-06 | 禁止 `Notes:`、`$...$`、`<video>`、`[ANIMATION` | `validators.py` | 两门真实课通过 |
| V-07 | 镜头 id/页码/引擎 | `validators.py` | 5 个夹具通过 |
| V-08 | 场景与 Blender 任务存在 | `validators.py` | 5 个夹具通过 |
| V-09 | Motion 场景已注册 | `validators.py` | 两门真实课通过 |
| V-10 | 镜头源文件存在且可读 | `verify.py` | `lesson-smoke` 构建通过 |
| V-11 | 实测时长与期望漂移（warning） | `collect.py` | 夹具无漂移 |
| V-12 | 分辨率与帧率一致 | `verify.py` | `lesson-smoke` 1920×1080@30 |
| V-13 | base 连续、overlay 落在父片段且不重叠 | `verify.py` | `lesson-smoke` 通过 |
| V-14 | 成片可读、时长在容差内 | `verify.py` | `lesson-smoke` 6.000s |
| V-15 | 音画时长差 ≤ 0.5s | `verify.py` | `lesson-smoke` 旁白启用并通过 |
| V-16 | 字幕文件与 cue 数 | `verify.py` | `lesson-smoke` 字幕启用并通过 |
| V-17 | 报告完整、verdict 一致 | `report.py` + `cli.py verify` | 构建报告包含 V-17 pass |
| V-18 | artifacts 均位于 `build/<slug>/` | `verify.py` | 通过 |
| V-19 | 阶段/检查适用性 | `report.py` | 通过 |
| V-20 | recording 时长与笔记累计一致 | `verify.py` | `lesson-smoke` 通过 |
| V-21 | 所有声明路径合法 | `path_problem` | 单测覆盖绝对路径/反斜杠/`..` |
| V-22 | 二维标注/图例在时间线内、内容有效、位置在 0–1 | `verify.py` | `resolve_annotations` 单测；真实 Remotion still 渲染 |
| V-36 | 品牌交付成片 = 母版 + 片头片尾（时长/分辨率/fps/音轨/哈希/音频对齐） | `verify.py` / `branding.py` | `test_branding.py`；真实 292.367 s 母版拼接 307.367 s（`mode=copy`，TS 重封装）；`video_timing` 9221/9221 帧、clustered 1；`audio_alignment=pass`（delta 0.107 s）；`_brand_check` 实测 pass |
| V-42 | 配置解析：blocking 冲突阻断构建，快照写入 `logs/config-resolution.json` | `config_resolve.py` / `pipeline.py` | `test_config_resolve.py`；05/06/01/nvda 实跑无 blocking 冲突 |
| V-43 | V1 时间线的 `legacy_*` 字段必须登记 | `legacy_registry.py` / `verify.py` | `test_legacy_registry.py`；未登记字段判 fail |
| V-44 | 字幕 QC：时间、语言、行宽、行首标点、术语/数字断裂 | `subtitles_qc.py` / `verify.py` | `test_subtitles_qc.py`；06 PASS，05/01 WARN（行首标点、英文悬空介词） |

失败注入证据：`tests/test_staging.py`（合成失败保留 staging、成功清理）；R5 历史故障注入见 `<内容根>/archive/R5-验收矩阵.md`；本轮未重复构造全部故障样本（见 §6）。

---

## 3. 三维场景 IR v2

```powershell
.\scripts\check-scene-system.ps1          # 契约：9 合法 + 11 非法
.\scripts\check-scene-system.ps1 -Render  # 追加 8 次真实 Blender 渲染
```

最近一次带渲染执行：**`scene system check ok`，exit 0**。

| 任务 | 结果 |
| --- | --- |
| `demo-scene` | pass |
| `demo-geometry-nodes` | pass；2 个 NODES 修改器 |
| `demo-animation-scene` | pass；13 条 F-Curve，1280×720 MP4，3.0s |
| `demo-modify` | pass；基于 `scene.blend` 追加，11 个对象 |
| `demo-text-curve` | pass；4 个 TEXT、3 个 CURVE、1 个 ORTHO 相机专项检查通过 |
| `demo-materials` | pass；7 个材质预设展开并逐项回读一致 |
| `demo-scientific` | pass；点属性与科学着色参数回读一致 |
| `demo-surface` | pass；参数化曲面顶点数与表达式复算一致 |
| 11 个 invalid 夹具 | 全部被拒绝 |
| 契约与执行分离 | `test_validators_agree_without_generated_artifacts`：`base_blend` 尚未生成时两套校验器结论一致 |

产物：`build/blender-scene-acceptance/blender/` 与 `manifests/`。

二维标注（V-22）的渲染证据：`build/p1b-annotation-evidence/annotation-still.png`（三条标注与背景/边框样式）与 `annotation-font-still.png`（中文标注，捆绑字体 Noto Sans SC）。色标证据：`build/p3-legend-evidence/legend-still.png`（coolwarm、-400–400 Pa、真实 Remotion still）。

## 3.1 代码/终端会话（E1/V1）

```powershell
.\scripts\check-session.ps1            # 构建镜像 + 无录屏执行 + V-23
.\scripts\check-session.ps1 -Record    # 追加 mintty + gdigrab 录制 + V-24
```

| 项 | 证据 |
| --- | --- |
| 镜像 | `course-tools:e1`，`docker image inspect` 的 Id 写入 `result.json` |
| 执行 | `build/<lesson>/code/<shot>/result.json`（退出码、分离的 stdout/stderr、断言） |
| transcript | `build/<lesson>/code/<shot>/work/transcript.log`（结构化会话日志） |
| 录制 | `build/<lesson>/code/<shot>/session.mp4` + `recording.json`（ffprobe） |
| 验收 | `validation.json`：V-23 执行证据、V-24 录制证据 |
| 旁白（V1） | `course-control narrate` 输出 `build/<lesson>/narration/segments/<id>.wav` + `.meta.json`，真实 VoxCPM2 合成 |

最近一次：`session check ok`；录制 `1322×702 / 2.1s`（mintty 窗口，gdigrab `hwnd`）；V-23/V-24 pass。

### 3.1.1 VS Code 会话（E2）

```powershell
.\scripts\check-vscode-session.ps1            # 真实 VS Code + shell integration
.\scripts\check-vscode-session.ps1 -Record    # 追加 PrintWindow 录制
```

- 扩展：`CourseDemo/`（plain JS，无第三方依赖）。
- 执行：`executeCommand` + 立即 `read()` + `onDidEndTerminalShellExecution` 的 `exitCode`；`undefined` 判失败。
- 录制：gdigrab 对 Electron 窗口为黑屏，改用 **PrintWindow** 逐帧 + ffmpeg rawvideo；已抽帧确认终端命令与 `hello from vs code` 输出可见。
- 证据：`build/lesson-smoke/code/vscode_001/{result.json,vscode-result.json,validation.json,session.mp4}`；V-23/V-24 pass。

### 3.1.2 Python 工具链（E3）

```powershell
.\scripts\check-python-session.ps1
```

- 场景：`uv venv` → 本地 wheel 安装 → 导入；随后在 `network: none` 的第二容器中做离线验证。
- 证据：`build/lesson-smoke/code/python_001/{result.json,offline-result.json,validation.json}`；V-23/V-25 pass。
- 网络演示：`check-python-network.ps1` 在本机 8899 启一个只读 wheelhouse HTTP 索引，容器经 `host.docker.internal:8899` 真实下载安装；随后仍在 `network: none` 容器做离线验证。真实 PyPI 仍被本机代理/TUN 阻断，未伪装成公网演示。
- 等待剪辑：`trim` 已实现并验证；`check-python-session.ps1 -Record` 中 `sleep 2` 命令被剪到约 0.6 秒，成片时长从约 5 秒降到 3.27 秒。
- 证据：`build/lesson-smoke/code/python_network_001/{result.json,offline-result.json,validation.json}`。

### 3.1.3 Manim FFT 技术基线（E5）

```powershell
uv run --project ManimSandbox manim render -r 1920,1080 --fps 30 `
  --media_dir build/manim-fft/media ManimSandbox/02-fft-baseline/fft_baseline.py FFTBaseline
```

- 场景：`ManimSandbox/02-fft-baseline/fft_baseline.py`，两条正弦叠加与和波形。
- 证据：`build/manim-fft/fft_baseline.mp4`（1920×1080，30 fps，7.8 s）；抽帧已确认坐标轴、两条分量与和波形。
- 未完成：3Blue1Brown Transformer 完整复刻（E6 仅完成技术产品基线）。

### 3.1.5 Transformer 产品基线（E6）

```powershell
uv run --project ManimSandbox manim render -r 1920,1080 --fps 30 `
  --media_dir build/manim-transformer/media ManimSandbox/03-transformer-baseline/attention_baseline.py AttentionBaseline
```

- 场景：tokens 行、query 权重柱、注意力热图。
- 证据：`build/manim-transformer/attention_baseline.mp4`（1920×1080，30 fps，9.1 s）；抽帧已确认。
- 边界：这是技术产品基线，不等于 3Blue1Brown 的完整风格复刻；镜头编排、旁白与复杂概念拆解仍待 E6 第二阶段。

### 3.1.6 Transformer 三幕讲解（E6 第二阶段视觉）

- 文件：`ManimSandbox/04-transformer-explainer/transformer_explainer.py`
- 三个 Manim 场景：`TokensScene` / `AttentionScene` / `OutputScene`
- 合并成片：`build/manim-transformer/transformer_explainer.mp4`（1920×1080，30 fps，22.3 s）
- 成片：`build/manim-transformer/e6/transformer_attention_final.mp4`，33.1s，含 AAC 旁白与 mov_text 字幕。
- 镜头：TokensScene / QKVScene / AttentionScene / OutputScene；Q/K/V 投影、scores、softmax 权重、weighted V 合成均有画面。
- 旁白：4 段 VoxCPM2 中文旁白，逐段塞入对应镜头（6.88 / 5.60 / 5.60 / 4.32s），无溢出。
- 字幕：`build/manim-transformer/e6/subtitles.srt`，4 条 cue 与镜头对齐。
- 证据：`build/manim-transformer/e6/manifest.json`（场景/旁白/字幕/成片哈希与时长）。
- 未完成：E6.6 Transformer Block、3B1B 式逐镜节奏（E6.5 已完成，见 §3.1.7）。

### 3.1.7 E6.5 Multi-Head

```powershell
python ManimSandbox/05-multi-head/verify_math.py `
  --output build/manim-multi-head/e6.5/math-report.json
uv run --project ManimSandbox manim render -r 1920,1080 --fps 30 `
  --media_dir build/manim-multi-head/e6.5/media `
  ManimSandbox/05-multi-head/multi_head.py MultiHeadScene
python ManimSandbox/05-multi-head/assemble.py
```

- 数学：`multi_head_math.py` 为唯一数据源；30 条检查全 pass。
- 视觉：`MultiHeadScene` 五 beat，1920×1080 / 30 fps。
- 旁白：5 段 VoxCPM2 中文旁白，48 kHz mono；按 beat 起点放置。
- 字幕：`build/manim-multi-head/e6.5/subtitles.srt`，10 条，均在 beat 内。
- 成片：`build/manim-multi-head/e6.5/final.mp4`，2608 帧，86.929 s，视频+音频+字幕。
- 检查：`build/manim-multi-head/e6.5/manifest.json` 14 条全 pass。
- 测试：`ManimSandbox/tests` 11 个（8 数学 + 3 成片/SRT）。
- V1 契约：`e65-adapt` 生成 `NarrationSpec` / `TimelineSpec` / `ShotSpec` / `RenderManifest`；`source.lesson_spec=null`。
- 未完成：未并入 `pipeline.py` / `lessons/`；SRT 未做逐字强制对齐。

### 3.1.4 Rust 镜头（E4）

```powershell
.\scripts\check-rust-session.ps1
.\scripts\check-rust-session.ps1 -Record
```

- 环境：**host VS Code + Git Bash**（Rust 1.97）。Docker Hub 的 Rust 镜像拉取被本机 TLS 阻断，未伪装成容器验证。
- 场景：`cargo --version` + `cargo run --quiet`。
- 证据：`build/lesson-smoke/code/rust_001/{result.json,validation.json,session.mp4}`；V-23/V-24 pass；抽帧可见 `hello from rust`。

---

## 4. 课程构建

| 课程 | 模式 | 结果 | 说明 |
| --- | --- | --- | --- |
| `lesson-smoke` | recording + Blender + 旁白 + 字幕 | **pass** | 全链路真实执行（Blender → collect → Remotion → verify） |
| `lesson-blender-only` | recording + Blender | **pass** | 同上，无旁白/字幕 |
| `01-shell-for-ai-era` | deck + Motion | NOT_RUN（本轮） | Motion 自动导出已实现，但本轮未重跑整课 |
| `01-transformer-demo` | deck + Motion | NOT_RUN（本轮） | 同上 |
| `lesson-manual` | recording + Motion | **pass** | adapter 真实无头渲染 `gui_vs_cli_paths`，ffprobe 通过；含 1 条时长差异 warning |

Motion Canvas 已从人工节点改为自动节点；真实课程本轮没有重跑，因此不能把历史 `incomplete` 直接改写成 pass。

---

## 5. 模型运行时与内容审查

| 项 | 命令 | 结果 |
| --- | --- | --- |
| 跨进程串行 | `test_concurrency.py`（两个子进程竞争锁） | 通过：区间不重叠 |
| 陈旧锁回收 | `test_runtime.py::test_stale_lock_is_reclaimed` | 通过 |
| 他人锁保护 | `test_runtime.py::test_foreign_lock_is_not_released` | 通过 |
| 复用/拒绝/启动失败 | `test_service.py`（mock HTTP） | 4 项通过，锁均释放 |
| 服务启动/停止/切换 | `test_lifecycle.py`（真实子进程 fake server） | 4 项通过：started、switch、reused 不杀他人、超时释放 |
| 重试绕过预算 | `test_budget.py::test_retry_cannot_bypass_budget` | 通过：每次请求前重新检查 |
| 任务失败落盘 | `test_job_state.py` | `job.json` 与任务记录均为 `failed` |
| 上下文预算 | `test_runtime.py` | 文本/CJK/图片/超限拆分 |
| 内容审查成功 | `test_content_qa.py`（mock API 后端） | 2 页 → 2 请求 → completed；报告字段完整 |
| 审查 Schema 漂移 | `test_schemas.py` | 4 份 Schema 与 Pydantic 模型一致 |
| 内容审查非法 JSON | 同上 | failed + raw 保存 |
| 多页中途失败 | 同上（flaky） | 第 1 页 findings 保留，第 2 页 failed |
| 在线请求超时 | 同上（slow） | failed，任务记录终态 |
| 只读边界 | 同上 | 课程文件字节不变；未生成 shots.json / build-report.json |
| 无凭据 | 同上 | blocked |
| 远程回退（mock） | `test_remote.py` | 本地繁忙 → `provider=remote`；本地正常不切换；无远程/无 key/无 vision 模型均不伪造 |
| 远程凭据隔离 | `test_remote.py`、`test_remote_routing.py` | key 只从环境变量读取；健康输出不含 key；任务记录 `provider` 可追溯 |
| 远程真实文本冒烟 | `config/model-routing.yaml` + `DeepSeek-API` | 2026-11-07 可达；`deepseek-flash` 返回 `OK`；未打印密钥 |
| 远程真实图片冒烟 | 256×256 PNG + `deepseek-flash` | 2026-11-07 返回“红色”；`deepseek-v4-pro` 已禁用 |
| DeepSeek 模型策略 | `test_remote.py`、`test_remote_routing.py`、`test_model_policy.py` | flash 接受；pro 在 ai_runtime / ModelingStudio / ContentQA 配置层均被拒绝 |
| 环境变量优先 | `test_env.py`、`test_remote.py::EnvironmentOverrideTest`、`test_env_overrides.py` | `.env` 自动加载；shell env 优先；通用 `REMOTE_*` 与 DeepSeek `DEEPSEEK_*` 覆盖本地 YAML；env 设 pro 仍被拒绝 |
| 密钥隔离 | 系统环境变量 `DeepSeek-API` | key 不写入 `.env`/YAML/日志/跟踪文件；跟踪文件只含不含 key 的 `.env.example` |
| 路径卫生 | `scripts/check-paths.ps1` | `path check ok`；跟踪文件中无本机盘符/用户目录绝对路径 |
| 真实课程无配置 | `content-qa review --lesson 01-shell-for-ai-era` | **blocked，exit 3**；报告写入 `build/01-shell-for-ai-era/review/review.json` |

本地模型的真实作业证据（历史记录，本轮未重跑）：`ModelingStudio/workspace/jobs/sample-001` 六阶段 completed；`sample-002` 停在 generate；`fallback-test` build+validate 通过。

---

## 6. 未覆盖项（如实记录）

| 项 | 原因 | 影响 |
| --- | --- | --- |
| 真实课程成片 | 本轮未重跑；Motion 自动导出已有 POC 与夹具证据 | 真实课程仍待下次完整构建 |
| 真实审查调用 | ContentQA 默认 Claude Code；API 后端已配置 DeepSeek，但本轮未重跑真实课程审查 | 保留历史 `blocked` 证据；远程路由冒烟已单独完成 |
| 本轮重跑 ModelingStudio 全链路 | 需独占 8080 约 10–30 分钟，且会与用户其他任务冲突 | 仅有历史作业证据 |
| V-05/V-06/V-09/V-16/V-19/V-20 的失败注入 | 会破坏真实课程或已由正常路径覆盖 | 未新增故障样本 |
| 两门真实课程重复构建一致性 | 第二门未构建 | 夹具已验证文件集合稳定 |
| VoxCPM2 / ComfyUI | 运行时未启动/未部署 | 不在本期范围 |
| V1-D 原生写入 | Session runner 仍写旧 `evidence.json`；V1 由适配器生成；`ShotSpec` 已支持 `simulation`，`session/graphics` 未做 | 新 session 不会自动产出 `EvidenceManifestV1` |
| V1-E Remotion 切换 | adapter 已按 `compose.renderer=timeline` 选择 `CourseTimeline`；真实课程尚未完成全链路构建 | 需要在真实课程上验证 |
| 远程完整作业 | 只验证了单轮文本/图片；未跑完整 ModelingStudio 远程作业 | 远程回退的路由与协议已测，作业级证据待补 |

---

## 6.9 导演层与制片层（2026-11-08）

| 检查 | 命令 | 预期 |
| --- | --- | --- |
| 导演计划 | `course-control director-plan --lesson 01-transformer-demo --workspace .` | `status: ready`；12 镜头 / 5 章 / 1200 s；0 error，5 warning |
| 结构校验 | `course-control director-validate --plan build/01-transformer-demo/director/director_plan.json` | `no issues` |
| 交付清单 | `course-control producer-run --lesson 01-transformer-demo --workspace .` | exit 1；`blocked`；4 项缺失（成片、旁白、字幕、build-report） |
| 增量检测 | `course-control producer-affected --lesson 01-transformer-demo --workspace .` | 无修改时 `no affected shots` |
| 增量命令 | `course-control producer-rebuild --lesson 01-transformer-demo --workspace .` | 无修改时 `no affected shots`；有修改时打印 `--shots` 命令与 `allow_render` 授权 |
| 旁白样片 | `course-control narration-build --lesson 01-transformer-demo --workspace . --sample-pages 1` | 第 1 页 43.92 s（计划 45 s，drift -1.08 s），`style_applied=true`，服务自动停止 |

边界：这两层是设计与制片校验，不是成片验收；不设抽帧关卡（D-047），渲染与 TTS 仍需显式命令。`build --storyboard` / `--shots` 已接入，可在已有构建上手动局部重渲染。

---

## 6.10 品牌层与教材知识库（2026-11-09）

品牌层（`docs/品牌与片头片尾.md`）：

| 检查 | 命令 | 实测 |
| --- | --- | --- |
| 计划 | `course-control brand-plan --lesson <slug>` | `formal_course` → intro 3.0 s（90 帧）+ outro 12 s（360 帧），合计 15.0 s；`news` 无 intro；`short` 只允许签名 |
| 片段渲染 | `course-control brand-render --lesson <slug>` | `BrandCourseIntro` / `BrandCourseOutro` 真实渲染通过；缓存键命中时不重复渲染 |
| 拼接 | `course-control brand-render --lesson <slug> --stitch` | 292.367 s 母版 + 15.0 s → 307.367 s，`mode=copy`（MPEG-TS 重封装 + 显式 duration）；`video_timing`：9221/9221 帧、最小间距 0.012 s、clustered 1、pass；`audio_alignment`：expected 3.0 / actual 3.107 / delta 0.107 / pass |
| 类型检查 | `RemotionStudio/node_modules/.bin/tsc --noEmit` | 通过；已加入 `check.ps1` |
| 视觉审查 | 抽帧：`build/brand-review/final-intro.png`、`final-outro.png`、`final-handoff.png`、`first12-final.png`、`outro-centered.png` | 修复记录：片头空白尾帧、片尾米色色块、标题换行压字、W 基线错位、元数据堆砌、MP4 直拼导致 PTS 塌缩（前 20 s 快闪）；最终为全英文、3.0 s 硬切、CTA-only 片尾、TS 重封装线性拼接 |
| 片尾主轴 | `npx remotion still src/index.ts BrandCourseOutro build/x.png --frame=150` → `scripts/brand-centers.py <png>` | 5 个内容带 `center_x` 959.5/959.5/959.5/959.0/959.0，|Δ| ≤ 1 px；exit 0 |

教材知识库（`docs/KnowledgeStudio.md`）：

| 检查 | 命令 | 实测 |
| --- | --- | --- |
| PDF 导入 | `knowledge-studio import-source --pdf build/knowledge-smoke/pdf-smoke.pdf --source-id pdf-book --root build/knowledge-smoke/pdf-book` | 2 页，`extractor=pypdf==6.9.2` |
| 文本教材 | `knowledge-studio import-text` → `toc` → `segment` → `index` | 12 页；目录 4 条，偏移 -4；3 个单元（2-5 / 6-8 / 9-12）；索引 12 页 3 单元 |
| 英文检索 | `knowledge-studio retrieve --query "drag coefficient" --max-pages 4` | 4/12 页（33.3%），单元 U02 |
| 中文检索 | `knowledge-studio retrieve --query "风洞 实验" --max-pages 3` | 3/12 页（25.0%），单元 U02/U03 |
| 证据 | `knowledge-studio evidence --retrieval <json> --claims <json>` | 两条 claim 落盘，`verification=pending`；引用未检索页时 exit 1 |
| 完整性 | `knowledge-studio verify --root build/knowledge-smoke/demo-book` | KS-01…KS-08 全 pass，exit 0 |
| 提取质检 | `knowledge-studio extract-report --root build/knowledge-smoke/pdf-book` | 2/2 页，status pass；缺页/空页为 fatal，exit 1 |

边界：品牌音效、新闻正片来源条、缩略图、4K 品牌渲染未实现；教材 OCR、表格/公式语义、语义检索未实现，均按 `blocked` 或文档边界记录，不写成通过。

---

## 7. 复现顺序建议

1. `.\scripts\check.ps1`
2. `.\scripts\check-scene-system.ps1 -Render`
3. `.\scripts\build-lesson.ps1 -Lesson lesson-smoke -LessonDir CourseControl/tests/fixtures`
4. `.\scripts\build-lesson.ps1 -Lesson 01-shell-for-ai-era`（预期 `incomplete`）
5. `uv run --project ContentQA content-qa review --lesson 01-shell-for-ai-era`（预期 `blocked`，exit 3）

---

## 8. R1 增量检查（2026-11-07）

| 编号 | 检查 | 实现 | 适用条件 |
| --- | --- | --- | --- |
| V-26 | 时长契约一致性（计划/实测/重复权威） | `validators.py` + `collect.py` | `lesson.yaml.duration` 存在 |
| V-27 | 成片时长在窗口内 | `verify.py` | duration 存在且成片存在 |
| V-28 | 字幕版与干净版时长/流/分辨率/帧率一致 | `verify.py` + `adapters/burn.py` | `subtitles.render=burn_in` |
| V-29 | 脚本与逐字口播一致、style 语法 | `validators.py` | `authoring.script` 存在 |
| V-30 | 旁白 meta/哈希/页跨度/时间轴一致 | `verify.py` | `narration.timing=measured` |
| V-31 | 双语字幕条数/完整/行宽/CPS/间隔 | `verify.py` | `subtitles.render=burn_in` |
| V-32 | 来源引用完整性 | `validators.py` | `authoring.digest` 存在 |
| V-33 | 批准门（sha256 匹配） | `validators.py` | `authoring` 块存在 |

R1 测试计数：五套合计 **465 个用例（459 通过 + 6 跳过）**：CourseControl 346（341+5）、ModelingStudio 33、ai_runtime 50、ContentQA 18、ManimSandbox 18（17+1）。

R1 真实产物：

- 本地归档：`<内容根>/archive/R1/R1-基线报告.md`、`R1-1-引擎验证报告.md`、`R1-性能基准报告.md`、`R1-5-候选稿索引.md`（不入库）
- `build/r1/manim/.../SmokeScene.mp4`、`build/r1-smoke/blender/smoke.mp4`、`build/r1/remotion/smoke.mp4`
- `build/r1/timeline-smoke.mp4`（TimelineSpec 驱动 Remotion 的 6 秒真实片段）
- `build/01-transformer-demo/blender/stack_explode.mp4`（1920×1080 / 30 fps / 750 帧 / 25 s）
- `CodeVideoStudio/shots/attention-flow/out/final.mp4`（30s / 900 帧 / 两次渲染 900/900 帧哈希一致）
- `CodeVideoStudio/backends/hyperframes/hf-poc/out/hf-poc.mp4`（10s / 300 帧 / check 0 error 0 warning / 27.1s）
- `build/videozero-poc/output/attention-flow.mp4`（Motion Canvas image sequence → ffmpeg，1920×1080 / 30fps / 3007 帧 / 100.2s）
- `build/01-transformer-demo/narration/audition/s001-p1.wav`、`s001-p2.wav`（VoxCPM2 真实合成）

## 6.11 多视觉语法生产（2026-11-10）

| 检查 | 命令 | 期望 |
| --- | --- | --- |
| 语法注册表 | `course-control grammar-list` | 7 个 grammar，含 long_take / kinetic_edit / simulation |
| 生产契约 | `course-control production-validate --plan <yaml>` | `verdict: pass`；未知 grammar / 能力缺口 blocked |
| 镜头驱动校验 | `course-control validate --lesson <slug> --lesson-dir <dir>`（`compose.mode=shots`） | 不要求 slides/notes 页数对齐 |
| 镜头驱动构建 | `course-control build --lesson <slug> --lesson-dir <dir>` | validate/render/collect/compose/verify 全 pass |
| 分层质量 | `course-control quality-gate --lesson <slug>` | hard / grammar / metrics / human 四段；不输出 85 分线 |
| 指标工具 | `course-control animation-score --lesson <slug> --profile kinetic_edit` | `release_gate: metric_only`，退出码 0 |
| 参考对比 | `course-control reference-compare --lesson <slug> --reference 3b1b-attention` | 六维报告；三维修为 human_review |
| 分块捕获 | `capture.mjs <dir> --dur 12 --chunk-seconds 4` | 帧数一致；PSNR vs 单次捕获 > 50 dB |

本地证据（不入库）：`build/shots-demo/`（30 s shots 模式成片 + 逐词字幕抽帧）、`build/architecture-samples/`（四支语法样片 + 分块捕获对比）。
