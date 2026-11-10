# 项目现状审计（Project Reality Audit）

- **审计日期**：2026-11-10
- **代码基线**：`feat/v1-pipeline-remote-fallback` / `23794ad`；工作树有 3 个已修改文件与 5 个未跟踪路径（品牌片头相关）
- **审计方式**：只读代码、配置、测试、日志、构建产物与真实视频抽帧；不修改任何生产代码、课程正文或配置
- **证据口径**：本文把"有代码""有测试""有构建通过""有人看过成片"分开写，不互相替代
- **实跑证据**：`scripts/check.ps1` exit 0（2026-11-10）；六套单测 585 个用例，579 通过、6 跳过；`check-paths.ps1` = `path check ok`

> 状态词沿用项目现有定义：
> `已设计`（只有方案）→ `已实现`（有代码）→ `已集成`（进入主链）→ `已测试`（有自动测试）→ `已验证`（有真实产物与检查）→ `已生产验证`（在真实课程中稳定使用并经过人工验收）。
> 本审计只把最后一档称为"成熟"。

> **2026-11-10 落实状态**：本报告是审计快照；其中 C-02/C-03/C-04/C-05/C-06/C-08/C-10/C-11/C-12 已在本轮实施，C-01/C-07 部分实施，C-09 未实施。当前测试为 585 个用例（579 通过 + 6 跳过）。以 `docs/stabilization/MIGRATION_PLAN.md` 为准。

---

## 0. 结论先行

1. **工程骨架是成熟的，产品交付不是。** 契约、适配器、跨进程锁、路径安全、失败落盘、报告与测试都达到可维护水平；但项目还没有交付过一门 20 分钟级课程，当前留存的最大成片是 5 分 54 秒的新闻样片。
2. **"通过"很多，"好看"很少。** 05/06 两门课的构建报告全 pass，动画评分 100/99，同时媒体 QC 记录 58/8 段冻结、06 响度低 6.8 dB、字幕在词中间断行。技术通过、指标通过和观看通过是三件事，当前前两者远强于第三者。
3. **视觉生产仍是手工活。** 每个 Manim/CodeVideo 镜头由人写代码，06 的 62 秒样片记录了每镜 1–5 次返工；没有一条任务记录证明"Agent 从 SPEC 生成镜头画面"已发生。系统自动化的是渲染与验收，不是美术与分镜。
4. **制片层和导演层没有成为生产驱动。** 05 的 storyboard 是 1 个镜头，导演计划是 3 个，节拍表是 27 个镜头条目；01 的 storyboard 是 5 个，导演计划是 12 个。`build` 默认读 storyboard，导演/制片产物只有显式 `--storyboard` 才进入构建。三层各自成立，但没有一门课把它们对齐。
5. **下一阶段最值钱的动作不是加架构，而是把已经完成 90% 的 20 分钟课程交付出来。** `01-transformer-demo` 的 12 页截图、7 个已渲染 Manim 文件（storyboard 使用其中 4 个）、1195.6 秒旁白、359 条双语字幕（已重排并接受）、Blender 镜头（已渲染）都已存在；完整构建已执行到 compose，但在 frame 3,879/35,868 停滞，未产出成片（C-30）。

---

## 1. 规模与结构

| 模块 | 手写代码量（约） | 入口 | 实际角色 |
| --- | ---: | --- | --- |
| `CourseControl/` | 23,220 行 src + 6,227 行测试 | `course-control` | 唯一调度、校验、收集、合成、验收层 |
| `RemotionStudio/` | 3,463 行 TS/TSX | `npx remotion` | 最终合成、字幕、品牌、叠加层 |
| `MotionStudio/` | 2,353 行 TS/JS | `render-headless.mjs` | Motion Canvas 场景与无头导出 |
| `ManimSandbox/` | 场景脚本（未逐文件统计） | `uv run manim` | 数学/机制动画，05/06/01/02 的实际主力 |
| `CodeVideoStudio/` | 自写 shot/skill 约 3,700 行 | `capture.mjs` | 镜头级 HTML/Canvas/Three.js 视频；5 份 vendored three.js 各 53,044 行 |
| `BlenderStudio/` | 场景系统 + 渲染脚本 | `blender-render.ps1` | IR v2 场景、v1 课程任务、GN/材质资产 |
| `ModelingStudio/` | 3,789 行 | `modeling-studio` | 图片→Blender 的内部能力 |
| `ContentQA/` | 1,926 行 | `content-qa` | 内容审查候选意见、claim 交叉审查 |
| `KnowledgeStudio/` | 2,635 行 | `knowledge-studio` | 教材拆页、检索、引用 |
| `ReviewRunner/` | 2,869 行 | `review-runner` | 独立代码审核（只读） |
| `shared/` | 2,888 行 | — | AI 运行时、Schema、表达式、设计令牌 |
| `docs/` | 10,679 行 Markdown | — | 契约、规范、评估、状态 |
| `scripts/` | 570 行 | `check.ps1` 等 | 工作区入口 |

这个规模说明项目已经越过"原型"阶段：它有一致错误处理惯例、Pydantic 契约、Schema 同步测试和跨进程资源管理。它的问题不是代码质量，而是**生产目标没有收敛**。

---

## 2. 核心生产链：真实发生了什么

以 05 为例，实际命令序列不是一条自动流水线，而是：

```text
人工/Claude Code 写 script + notes + slides + outline
  → author-accept（sha256 人工批准）
  → narration-build（VoxCPM2，12 段；首次合成按 10× 实测推算约 49 min，05 的 meta 记录的是缓存命中，未记录首次墙钟）
  → subtitles-build（实测音频切 cue）→ subtitles-accept
  → director-plan（3 镜头）
  → producer-run（订单、交付清单、状态）
  → build（validate → manim → collect → compose → burn → verify）
  → media-qc / audio-mix / quality-report / animation-score / quality-gate
  → 人工看片（未签核）
```

`build` 本身是确定的、可重复的；它前面的创作、批准、TTS、字幕与 QC 是分离的命令，由人按顺序执行。没有任何一个命令从来源跑到成片，也没有调度器在失败后继续。

05 的构建报告显示：validate 0.1 s，Manim 缓存命中 90 s，collect 0.1 s，compose 371.5 s，烧录 18.8 s，verify 0.1 s。渲染并不慢；慢的是镜头设计与返工。

---

## 3. 模块逐个核对

### 3.1 `CourseControl`

- **负责**：课程契约、V-01~V-36 校验、阶段调度、时间线、合成调用、报告、导演/制片/质量/字幕/旁白/会话等子命令。
- **实现**：`pipeline.py` 的 `run_build` 是主链；适配器统一返回 `StageOutcome`；失败即 `fail` 并把下游标 `not_run`。
- **接入**：是，所有真实课程与夹具都经它。
- **证据**：05/06/nvda/aging 的 `build-report.json` 均为 `verdict=pass`；`lesson-smoke`/`lesson-blender-only`/`lesson-manual` 历史 pass。
- **测试**：434 个用例（5 跳过），覆盖契约、时间线、失败注入、锁、预算、字幕、品牌、导演、制片、语法、参考比较。
- **主要缺口**：
  1. 没有顶层 resume/重试；`build` 在第一个失败阶段停止，恢复靠各适配器的缓存。
  2. 导演计划与 `build` 默认输入不是同一份 storyboard（见 §5、`ARCHITECTURE_CONFLICTS.md` C-01）。
  3. 质量门禁存在"可报告但不可证伪"的分量（§5.3）。
- **判断**：**已生产验证**（作为构建控制层），但**未生产验证**（作为端到端制片系统）。

### 3.2 `RemotionStudio`

- **负责**：截图采集、staging、最终合成、字幕、品牌片头片尾、HUD/标注叠加。
- **实现**：`CourseTimeline` 消费 `TimelineSpec`；`CourseVideo` 保留 legacy `shots.json`；`ScenePage` 做 scene 模式；品牌组件独立。
- **接入**：是，所有成片都经 Remotion。
- **证据**：05 292.4 s、06 62.2 s、nvda 354.3 s、aging 145.4 s 均由它输出；`tsc --noEmit` 在 `check.ps1` 中通过。
- **测试**：类型检查 + Python 侧 staging/时间线测试；没有 Remotion 组件级视觉回归。
- **主要缺口**：
  1. `CourseTimeline` 仍读 `metadata.legacy_*`，V1 原生消费未完成。
  2. 转场组件已实现；06 的 7 个镜头里只有 `attn-flow` 的 out 是 `dissolve`，其余硬切；没有真实课程使用 fade/wipe，`match_cut` 在实现里回退硬切。
  3. 字幕在 Remotion 模式下只按 cue 渲染，没有双语/行宽/CPS 校验（V-31 只对 burn-in 生效）。
- **判断**：**已生产验证**（合成层），但**已验证范围窄**（deck/scene/shots 三种模式各只有少量样本）。

### 3.3 `MotionStudio`

- **负责**：Motion Canvas 场景与无头导出。
- **实现**：`render-headless.mjs` 启动 Vite、core Renderer、帧接收器、ffmpeg；适配器最多 2 次重试并校验分辨率/帧率/时长。
- **接入**：是（01、01-shell、夹具）。
- **证据**：`attention-flow` 3 次哈希一致；`lesson-manual` 真实导出 pass；注入第 30 帧失败不产 MP4。
- **测试**：`test_motion_canvas_headless.py` 等。
- **主要缺口**：真实课程本轮未重跑；Motion 场景只有少量，且 `01-shell-for-ai-era` 的 8 段导出仍未重跑。
- **判断**：**已验证**（能力），**未生产验证**（真实课程整课）。

### 3.4 `ManimSandbox`

- **负责**：数学/机制动画。
- **实现**：每门课一个或多个 `.py` 场景；`design_system.py`、`palettes.py`、`scene_checks.py` 提供版式/配色/运行时检查。
- **接入**：是，05/06/01/02 的主力引擎。
- **证据**：05 单场景 292.4 s / 102 个 play；06 `attention_geometry` 15 s；01 有 7 个已渲染 Manim 文件（storyboard 使用 4 个）1080p30；02 有 4 个 Manim 镜头。
- **测试**：18 个用例（1 跳过）；布局检查在 `STRICT_LAYOUT=1` 下可失败。
- **主要缺口**：
  1. 没有组件库；05 的 1,622 行单文件是当前最大资产，也是最大耦合点。
  2. 适配器只 `probe_media` 后复制，不做逐镜头 QC；分辨率/帧率靠后面 V-12 兜底，冻结/黑帧不查。
  3. 场景内的 27 个镜头条目（每个含 2–3 个动作）不是独立可重渲染单元（见 C-01）。
- **判断**：**已生产验证**（05/06 的真实成片），但**不可增量生产**。

### 3.5 `BlenderStudio`

- **负责**：v1 课程渲染任务、v2 IR 场景系统、GN 资产、场景验收。
- **实现**：Pydantic + Blender 内置双端校验；`scene-run` 输出 manifest；`check-scene-system.ps1` 9 合法 + 11 非法。
- **接入**：v1 进了 `build`（01 的 `stack_explode`）；v2 没有进入任何真实课程。
- **证据**：ACCEPTANCE 记录 8 次真实渲染；但 `build/blender-scene-acceptance/` 已不存在；01 的 `build/01-transformer-demo/blender/stack_explode.mp4` 已在本轮渲染。
- **测试**：`test_blender_scene.py`、`test_scene_expr.py` 等。
- **主要缺口**：真实课程使用为零（v2）；v1 的 01 镜头已在本轮渲染；旧验收证据未留存。
- **判断**：**已验证**（契约与渲染），**未生产验证**（课程）。

### 3.6 `CodeVideoStudio`

- **负责**：镜头级 HTML/Canvas/Three.js 视频，`SPEC.md` + `seek(t)` + `VERIFY.md` + capture + contact sheet + QC。
- **实现**：`capture.mjs`（Playwright/ffmpeg，支持分块/GPU/JPEG）；`code_video_qc.py`（分辨率/帧率/时长/codec/pix_fmt/audio/黑帧/冻结）；适配器检查 `VERIFY.md` 无 `| fail |`。
- **接入**：是，06 的 6 个 code_video 镜头、nvda 的 3 个 cutaway、aging 的 3D plate。
- **证据**：06 62 s 成片；nvda 354 s；aging 145 s；`attn-matrix.contact.jpg` 等；180 s 分块捕获 5400 帧。
- **测试**：`test_code_video_adapter.py`、`test_code_video_qc.py`。
- **主要缺口**：
  1. 每个镜头是手写项目（`main.js` 150–660 行），没有模板/组件复用；5 份 three.js 重复 vendored。
  2. `VERIFY.md` 门禁只查字符串 `| fail |`；`attn-matrix/VERIFY.md` 只有"期望"表、没有逐条证据，仍然通过。
  3. 冻结只记 warning，不影响 pass。
- **判断**：**已生产验证**（06/nvda/aging 的镜头级生产），但**美术仍手工**。

### 3.7 `ModelingStudio`

- **负责**：图片 → 视觉分析 → 规划 → 脚本 → Blender → 验收。
- **实现**：四阶段 LLM + AST guard + 确定性回退；`job.json` 六阶段状态。
- **接入**：否，独立命令，不进入课程主链。
- **证据**：`sample-001` 六阶段 completed（2026-11-03）；`sample-002` 停在 generate；`fallback-test` build+validate pass。
- **测试**：33 个用例。
- **主要缺口**：一周前的历史作业，本轮未重跑；没有课程使用其产物。
- **判断**：**已验证**（POC），**未生产验证**。

### 3.8 `ContentQA` / `KnowledgeStudio` / `ReviewRunner`

- `ContentQA`：**已集成**为独立审查命令；05 有 23 条 findings、43 条 claim 的双模型交叉审查；但 05 的 review 由本地 Qwen + DeepSeek 完成，不是默认 Claude Code；任务记录被后一次运行覆盖（C-05）。
- `KnowledgeStudio`：**已验证**（12 页冒烟教材，KS-01..KS-08 pass），**未集成**到任何课程。
- `ReviewRunner`：**已验证**（代码审核），不参与生产 verdict；Docs/Course 审核仍 `NOT_IMPLEMENTED`。
- 三者都是"能力"，不是"生产线"。

### 3.9 `BrandIntro` 与品牌层

- `RemotionStudio/src/brand/`：**已生产验证**（真实 3 s 片头 + 12 s 片尾 + 292.4 s 母版拼接，307.4 s，`video_timing` 9221/9221，`audio_alignment` delta 0.107 s）。
- `BrandIntro/` + `CodeVideoStudio/shots/brand-intro|brand-desktop`：**已实现/已验证 POC**，未提交，未进入课程；其 README 自己写明"没有 12 秒成片、没有角色资产"，20 s opener 是"可看的 v1，不是 Gate 3 通过件"。
- 两者不是同一条生产线；3D 片头的 W 与 Remotion 的 BrandMark 在成片里不是同一种视觉处理（3D 定格帧没有橙色电流，背景是暖灰而非 `paper #FBFAF7`）。

### 3.10 共享层与支撑

- `shared/ai_runtime`：**已生产验证**（跨进程锁、服务生命周期、任务记录、预算、远程回退；50 个用例，多进程竞争测试）。这是全项目质量最高的模块之一。
- `shared/scene_expr`：**已验证**（AST 白名单 + 解释器，双端一致）。
- `scripts/check.ps1`：**已验证**（六套单测 + 类型检查 + 路径 + 契约 + 场景；本轮 exit 0）。
- `config/*.yaml`：本机配置被忽略，凭据只从环境变量读；`.env` 无 key，`check-paths.ps1` 通过。

### 3.11 关键接口

| 接口 | 位置 | 输入 → 输出 | 稳定性 |
| --- | --- | --- | --- |
| `StageOutcome` | `CourseControl/src/course_control/adapters/base.py` | 阶段执行 → `status/outputs/warnings/errors/duration_ms` | 稳定，四引擎共用 |
| `LessonPaths` | `CourseControl/src/course_control/paths.py` | `lesson.yaml`/`storyboard.yaml` → 解析后的路径 | 稳定，路径安全在此 |
| `ModelService` | `shared/ai_runtime/src/ai_runtime/service.py` | 模型请求 → 锁/服务/HTTP | 稳定，生产验证 |
| `TaskRecord` | `shared/ai_runtime/src/ai_runtime/tasks.py` | 一次模型调用 → `runtime/tasks/<id>.json` | 稳定，但 id 不唯一（C-05） |
| `TimelineSpec` | `CourseControl/src/course_control/contracts_v1.py` | 时间线 → Remotion props | 已接入，legacy 字段仍在用 |
| `ReviewReport` | `ContentQA/schemas/content-review.schema.json` | 页面 → findings | 稳定，后端可切换 |

### 3.12 依赖与许可

| 层 | 版本/来源 | 状态 |
| --- | --- | --- |
| Python | 3.12 + uv 0.10 | 每工程独立 `.venv`，无全局安装 |
| 核心库 | pydantic 2.x、typer 0.12+、sympy 1.14、pillow 10–12 | 稳定 |
| Manim | 0.22.0（0.22.1 已发布） | 落后 1 个 patch；渲染日志提示可升级 |
| TTS | VoxCPM2（外部 50000） | 非仓库依赖，谁启动谁停止 |
| ASR | faster-whisper（`--extra asr`） | 可选；06/05 用过，nvda 未跑 |
| Node | 24 | 稳定 |
| Remotion | 4.0.539、React 18.3.1 | 锁定版本；未跟 React 19 |
| Motion Canvas | 3.17.2、Vite 4.5.14 | Vite 4 已偏旧；Motion Canvas 版本锁定 |
| Three.js | vendored r160，5 份各 53,044 行 | 上游已 0.187（项目文档记录）；升级会同时影响 5 个 shot |
| Reveal | 6.0.2 | 稳定 |
| 许可 | AGPL-3.0-or-later；Code2Video skill Apache-2.0；three.js MIT | NOTICE/THIRD_PARTY_NOTICES 已记录 |

依赖策略整体是健康的：本地安装、锁定版本、第三方准入表、负面效果否决。主要维护风险是 three.js 的 5 份副本与 Vite 4；不是安全或许可问题。

---

## 4. 真实产物台账

| 产物 | 时长/规格 | 状态 | 能证明什么 | 不能证明什么 |
| --- | --- | --- | --- | --- |
| `build/05-transformer-5min/final/course-video-mixed.mp4` | 292.37 s / 1080p30 / 8,771 帧 / -15.9 LUFS | 构建 pass，质量 Q1/Q2/Q3/Q5 WARN，未签核 | 5 分钟动画课可从 TTS 到混音全自动产出 | 视觉达到专业频道；事实全部核实 |
| `build/06-attention-sample/final/course-video.mp4` | 62.17 s / 1080p30 / 1,865 帧 / -22.8 LUFS | 构建 pass，Q1/Q2 INCOMPLETE，未签核 | 中文逐镜头 + 多语法 + 双渲染器可跑通 | 双语字幕、响度、教学有效性 |
| `build/nvda-gpu-control/final/course-video-captioned.mp4` | 354.30 s / 10,629 帧 / -16.1 LUFS | 构建 pass，media QC INCOMPLETE（ASR 未跑） | 新闻片可从一手来源到成片 | 字幕-语音一致；画面不是 PPT |
| `build/aging-evolution/final/course-video.mp4` | 145.39 s / 3D plate + HUD | 构建 pass，Q3 PASS | Three.js 长序列 + Remotion 叠加层 | 3D 美术达到参考片；内容有真实数据 |
| `build/brand-e2e/final/course-video-delivery.mp4` | 307.37 s / 3 s + 292.4 s + 12 s | 构建 pass，`video_timing`/`audio_alignment` pass | 片头片尾线性拼接不伤正片 | 品牌 3D 片头达到美术标准 |
| `build/01-transformer-demo/` | 12 页截图 + 7 个已渲染 Manim 文件 + 1195.6 s 旁白 + 359 cue 已接受 + Blender 已渲染 | **compose 停滞，未产出** | 20 分钟课的素材已基本齐备 | 整课已交付 |
| `lessons/02-car-aerodynamics/` | 12 页 / 2,835 词 / 22:00 成片（文档声明） | **无 build 产物** | 历史上曾完成过 22 分钟课 | 当前可复现；交付质量 |
| `build/lesson-smoke` / `lesson-blender-only` / `lesson-manual` | 6 s 夹具 | 历史 pass | 主链在最小输入上可跑通 | 真实内容质量 |

**结论**：当前可复现、可播放、可检查的成片共 5 支，最长 5:54。20 分钟级课程在 01 上完成了大部分素材，在 02 上只有文档记录。

---

## 5. 成熟度判定

| 能力 | 等级 | 依据 |
| --- | --- | --- |
| 课程契约与校验 | 已生产验证 | 4 门真实课 + 夹具 validate 0；V-01..V-36 |
| 构建与合成 | 已生产验证 | 5 支成片；夹具重复构建文件集合稳定 |
| 本地模型串行 | 已生产验证 | 跨进程锁、双进程测试、真实任务记录 |
| 远程回退 | 已验证 | mock + 真实 DeepSeek 文本/图片冒烟；无完整作业 |
| TTS 整课旁白 | 已生产验证 | 01 1195.6 s / 54 段；05/06/nvda 实测 |
| 双语字幕 | 已验证（有缺陷） | 05 burn-in V-31 pass；01 359 cue 已重排并接受；行宽按显示宽度校验 |
| 内容审查 | 已验证（弱） | 05 43 claim，仅 3 supported；06 未跑 |
| 教学有效性 | 已设计 | 只有结构检查；learner evidence 缺失 |
| 导演层 | 已验证（未驱动构建） | 01 12 镜头 / 05 3 镜头；默认不进入 build |
| 制片层 | 已验证（报告层） | 01/05/nvda 的 state/manifest；不执行渲染 |
| 质量门禁 | 已实施（VERIFY/RELEASE 分离） | D-071 落地；05 84.7/06 98.8；nvda incomplete 阻断；`release-approve` 两次签核 |
| Blender IR v2 | 已验证（未用于课程） | 8 次渲染记录；证据目录已不在 |
| ModelingStudio | 已验证（POC） | sample-001 六阶段；未重跑 |
| 知识库 | 已验证（未集成） | 12 页冒烟；无课程使用 |
| 品牌 3D 片头 | 已实现（POC） | 20 s opener；README 自认未过 Gate |
| 短视频 / Shorts | 已设计 | 只有契约与竖屏签名；无成片 |
| 夜间无人值守 | 未实现 | 无调度/队列/顶层恢复 |
| 多课并行 | 未实现（设计上不做） | 单机单实例 |

**总体成熟度**：**"可复现的课程样片工厂"**。
它能稳定产出 1–6 分钟、结构完整、证据齐全的课程片段；还不能稳定产出一门 20 分钟、视觉达到发布水准、经过人工签核的课程。

---

## 6. 文档、代码与产物不一致的地方

| # | 文档说法 | 实际 | 影响 |
| --- | --- | --- | --- |
| 1 | `ARCHITECTURE.md:58`：MotionStudio"不自动导出" | D-054/PRD FR-04 已改为无头自动导出 | 误导新读者 |
| 2 | `FRONTEND_ASSESSMENT.md:34,65`：Motion Canvas 无 CLI、人工导出 | 已有 `render-headless.mjs` | 评估结论的输入已过期 |
| 3 | `PRD.md:27`：ASR 是非目标 | 已有 `asr-align`（faster-whisper） | 需求边界需更新 |
| 4 | `ACCEPTANCE.md`：412 个 CourseControl 用例、合计 550 | 实跑 438、合计 585（579 通过 + 6 跳过）；且 412+33+50+24+18+21=558≠550 | 验收数字不可复算 |
| 5 | `PROJECT_STATUS.md`：01-transformer 20 分钟课"blocked" | 旁白（1195.6 s）、截图、7 个已渲染 Manim 文件已完成；缺字幕批准/Blender 镜头/最终构建 | 状态落后于产物 |
| 6 | `项目差距清单.md`：01 缺整课旁白 | 已存在 `build/01-transformer-demo/narration/narration.wav` | 路线图会重复劳动 |
| 7 | `跨学科生产能力矩阵`：只有汽车空气动力学有完整成片 | 02 的成片已不在 build；05/06/nvda/aging 有完整成片 | 能力判断的证据基线过期 |
| 8 | `课程生产交付物规范.md`：交付包含哈希、`final/subtitles.*`、metadata、checklist | `build-report.json` 的 artifacts 无 sha256；05/06/nvda 的 final 目录没有这些文件 | FR-22 验收不成立 |
| 9 | `提交前检查清单.md`：五套单测 | `check.ps1` 跑六套（含 KnowledgeStudio） | 小偏差，说明清单未随代码更新 |
| 10 | 多份文档引用 `build/blender-scene-acceptance/`、`build/p1b-annotation-evidence/`、`build/manim-multi-head/` 等 | 这些目录已不存在 | 证据不可回读 |
| 11 | `PROJECT_STATUS.md`：05 的 `animation-score` 94.7 | `build/05-transformer-5min/quality/gate.json` 重算后是 100.0 | 同一课的分数有两个版本，读者无法判断哪个有效 |

这些不是"文档写得不好"，而是**状态与证据没有单一来源**。文档在描述一个已经向前走了几步的系统。

---

## 7. 本次审计没有验证的事

以下项只能标 `待验证`，不能据此下结论：

1. **TTS 自然人声**：本环境无法听音；只能说 ASR 覆盖率（05 0.992、06 0.935）证明可懂，不能证明好听、停顿自然、情绪正确。
2. **02-car-aerodynamics 的 22 分钟成片**：文件不在 build，只有 delivery checklist 的记录；未重跑。
3. **01 的完整构建**：2026-11-10 已执行到 compose；超时已改为按课程时长推导（01 为 3600 s），字幕 burn-in 与 verify 结果以最终 report 为准。
4. **ContentQA 真实 Claude Code 后端**：05 的 review 实际由本地/远程 API 完成；没有 Claude Code 的真实课程审查记录。
5. **180 s 分块捕获在真实镜头上**：只在测试图（`build/long-capture-180`）上验证。
6. **4K/60**：只有 60 帧的 Remotion 基准，没有整课。
7. **长片稳定性**：没有连续构建多门课、或夜间无人值守的记录。

---

## 8. 审计结论

项目的工程能力已经足以支撑"可靠地做视频"；它缺的不是更多抽象，而是**把一条真实长课从头走到尾，并让质量结论与画面一致**。

如果下一阶段只能做一件事：交付 `01-transformer-demo`。
如果要再做第二件：把质量门禁里"永远不会失败"的分量去掉，让 100 分重新有意义。
