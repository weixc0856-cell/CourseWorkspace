# V1 全量修复总台账（MASTER_REMEDIATION）

- 日期：2026-11-10
- 范围：C-01～C-30（`docs/audit/ARCHITECTURE_CONFLICTS.md` 的完整编号）
- 状态：`OPEN → IN_PROGRESS → FIXED → VERIFIED → CLOSED`
- 规则：FIXED 只表示修改已落盘；VERIFIED 必须有测试或真实运行证据；CLOSED 需要验收人签字。
- 本文件是唯一问题台账。其他审计文档保留原始证据，不再各自维护状态。

## 0. 编号核对

仓库审计的编号与外部转述的归类表存在错位。本台账以仓库为准：

| 编号 | 真实问题 | 外部归类表曾误标为 |
| --- | --- | --- |
| C-23 | 五层审查没有统一裁决队列 | 双语内容质量 |
| C-24 | 同一生产行为有多个配置源 | 新闻内容密度 |
| C-25 | 内容层的小矛盾（标题时长、因果遮罩表述） | 人工统计未脚本化 |
| C-26 | 新闻片的幻灯片密度 | （缺号） |
| C-27 | 验收文档的算术错误 | 质量评分 |
| C-28 | 未提交的品牌工作 | 统一裁决 |
| C-29 | 06 的 `subtitle disabled` 文案 | 配置权威 |

C-15、C-26 均存在，不是缺号。统计脚本化没有独立编号，作为 C-27 的修复手段，并新增 `course-control stats`。

## 1. 基线（R0）

- Git：`feat/v1-pipeline-remote-fallback`，HEAD `047f8f4`；工作树仅 `CodeVideoStudio/shots/brand-*` 未跟踪。
- 测试基线：CourseControl 438 用例通过（5 skip）；本轮收尾结束时 CourseControl 492、六套合计 639（633 通过、6 跳过）。
- 真实产物：01（1195.605 s）、05（292 s）、06（62 s）、nvda（5:54）、aging（2:25）的 `build/` 目录存在；02 无产物。
- 配置：`config/*.yaml` 本机文件不提交；仓库保留 `.example.yaml`。
- 保护：`lessons/` 正文未改语义；只增加 `build.storyboard_source` 声明。

## 2. 总表

| ID | 根因 | 影响模块 | 必须完成的修改 | 依赖 | 验收 | 状态与证据 |
| --- | --- | --- | --- | --- | --- | --- |
| C-01 | 六种镜头/时间表示并存，导演层不驱动构建 | `pipeline`、`paths`、`producer` | 每门课声明 `build.storyboard_source`；`build` 读取声明；`plan-audit` 报权威与差异 | — | 课不再靠一次性 CLI 开关；05/01 的计数差异有文档解释 | **FIXED**：6 门课显式声明；`test_pipeline_source`；`plan-audit` |
| C-02 | D-071 已决定阈值只作诊断，代码硬失败 | `beats`、`quality_gates` | errors/warnings 分离；grammar 只收结构错误 | D-071 | 3 秒 1 动作镜头不阻断；warning 可见 | **VERIFIED**：`test_beats`、`test_quality_gates` |
| C-03 | `QUALITY_PASS`/`releasable` 可在未验证时为真 | `quality`、`quality_gates` | `VERIFY_*` 状态；incomplete 阻断；WARN 分类 | — | nvda 不可发布；WARN 分 blocking/human_review | **VERIFIED**：`test_quality`、`test_quality_gates`；`QUALITY_STANDARD.md` |
| C-04 | 动画评分有免费分 | `animation_score`、`grammars` | 无相机 0 分；freeze 全语法计分；无 media-qc 时 0 | — | 60 秒静止 + 满 beats 不接近 100 | **VERIFIED**：05 100→84.7；`test_animation_score` |
| C-05 | ContentQA 任务记录被覆盖 | `ContentQA`、`ai_runtime` | task_id 加 run_id；保留多套记录 | C-15 | 连续两次 review 保留两套 | **VERIFIED**：`review.json` run_id 测试 |
| C-06 | 交付包不符合交付规范 | `package`、`report` | `package`/`package-verify`；sha256；缺项失败 | C-15 | 删任一必需文件 exit 1 | **VERIFIED**：`test_package`；05/06 真实包 |
| C-07 | 字幕按字符比例切分，断词断句 | `subtitles`、`verify` | 标点/词边界重排；V-31 覆盖所有模式；新增 V-44 | C-08 | 05/01/06 重排；人工抽查 | **FIXED**：05 只修 3 条标点孤行，V-44 PASS（80 cue，ASR 0.992/0 mismatch）；06 PASS；01 仍 WARN（行首标点）。未重排全片、未删 cue |
| C-08 | 配置声明双语，实际单语 | `lesson.yaml`、`config_resolve` | 显式 `bilingual`；配置解析检查声明与 SRT | — | 声明与产物一致，否则 build 阻断 | **VERIFIED**：06 `bilingual: false`；`test_config_resolve` |
| C-09 | 视觉生产逐镜头手写，无能力契约 | `shot_taxonomy`、`CodeVideoStudio` | 8 类镜头契约与样片覆盖检查 | — | 每类有输入契约、禁用场景、质量检查、样片 | **FIXED**：`shared/grammars/shot-taxonomy.yaml`；`shot-taxonomy` 命令；8 类样片 SPEC+VERIFY 齐备。Agent 生成对照实验未做 |
| C-10 | 四个渲染器验收深度不一致 | `adapters` | 共用 `verify_media` | — | 坏视频在四个适配器都失败 | **VERIFIED**：`test_media_contract`、适配器测试 |
| C-11 | 文档引用已消失的证据 | `scripts/check_evidence.py` | 每个缺失路径必须匹配处置规则；未分类即失败 | — | `missing 90 / classified 90 / unclassified 0` | **VERIFIED**：`docs/audit/evidence-decisions.yaml`；`check.ps1` |
| C-12 | 项目状态落后于产物 | `PROJECT_STATUS`、`stats` | 按产物更新状态；脚本化计数 | C-27 | 状态与 `build/` 一致 | **VERIFIED**：`course-control stats`；`PROJECT_STATUS.md` 2026-11-10 段 |
| C-13 | 两代 Blender Schema 无统一入口 | `blender_task`、`adapters/blender` | 单一加载器按 `schema_version` 分派；未知字段拒绝；输出路径校验 | — | v1/v2/未知版本都有确定行为 | **VERIFIED**：`test_blender_task`；`blender-task-validate` |
| C-14 | V1 时间线靠 legacy 字段桥接 | `legacy_registry`、`v1_timeline`、`verify` | 登记每个 legacy 字段的消费者与退出目标；未登记即 V-43 失败 | C-01 | 新增字段必须登记 | **FIXED**：9 个字段登记；V-43；`test_legacy_registry` |
| C-15 | `build-report` 无 run_id/输入哈希 | `contracts`、`report` | `run_id`、artifact `sha256`、config 指纹 | — | 报告可定位到一次运行 | **VERIFIED**：`test_contracts`、真实报告 |
| C-16 | 品牌 2D/3D 视觉语言不一致 | `brand`、`BrandIntro`、3D shots | 统一 token 与 Gate；3D 未过 Gate 前不作品牌资产 | 人工 Gate | 2D/3D 同属一套体系 | **DEFERRED**（所有者决定，2026-11-10）：视觉概念与 3D 角色设计尚未成熟，暂缓片头；保留源码、角色资产与 Gate 3 证据；不以片头阻塞 V1 课程生产；后续单独重做，不在当前方案上打补丁 |
| C-17 | three.js 5 份重复 vendored | `vendor`、`CodeVideoStudio` | 单一 `vendor/three`，构建时复制；副本不提交 | — | `vendor-check` 通过 | **VERIFIED**：5 份删除；`test_vendor`；实测 copied=3/current=2 |
| C-18 | Remotion Root 混入探针 | `RemotionStudio` | 探针独立入口 `src/probes` | — | 生产入口只暴露生产 composition | **VERIFIED**：`src/Root.tsx` 仅 7 个生产 composition；`tsc` 通过 |
| C-19 | 固定 1800 s 超时 | `timeouts`、`adapters` | 按时长策略与 `config/tools.yaml` 解析；超时杀进程树 | — | 20 分钟课程 compose ≥ 3600 s | **VERIFIED**：`test_timeouts`；`run_command` 超时测试 |
| C-20 | 无顶层恢复/调度 | `checkpoint`、`pipeline` | 阶段检查点、输入/输出哈希、`--resume`/`--resume-from` | C-15、C-24 | 输出被改或输入变化时重跑 | **VERIFIED**：隔离 06 实跑——首次 code_video 因缺 Playwright 失败，`--resume` 复用 `render:manim`；修复环境后 `--resume` 复用四个阶段并通过；`test_checkpoint`、`test_pipeline_source` |
| C-21 | 音频依赖工作区外路径 | `assets`、`package`、`audio_mix` | 资产 id/哈希/来源；交付包内打包外部资产 | — | 换机可复核 | **VERIFIED**：`test_assets`、`test_package`；05/06 已重打包，06 外部声线参考已打包且 `package-verify` 通过 |
| C-22 | 文档过期点集中 | `docs/` | 修过期句；文档标准与索引 | — | 无仍然生效的旧规范冲突 | **VERIFIED**：FRONTEND/ARCHITECTURE 修正；`DOCUMENTATION_STANDARD.md` |
| C-23 | 五层审查无统一裁决队列 | `review_decisions`、`quality` | `review/decisions.json`；Q1 读取；未裁决即人工复核 | — | 每条 finding 有裁决或明确未裁决 | **VERIFIED**：`review-status`/`review-decide`；`test_review_decisions` |
| C-24 | 同一行为多配置源 | `config_resolve`、`pipeline` | 每次 build 生成不可变 `config-resolution.json`；冲突阻断 | — | 05 的四个时长值有唯一解释；指纹进入 resume | **VERIFIED**：`config-resolve` 对 05/06/01/nvda 实测；`test_config_resolve` |
| C-25 | 内容小矛盾 | `lessons/06` 正文 | 标题时长、因果遮罩表述、示意矩阵标注 | 所有者批准 | 内容与实测一致 | **VERIFIED**：标题改为 `How Attention Works in About a Minute`；s005 改为“解码器里的注意力，能看当前和之前的位置，不能看未来”；重生成 10.24 s，全片 65.533 s；V-31/V-44 PASS，ASR 0.935、0 mismatch；画面文案与 SRT 同步 |
| C-26 | 新闻片幻灯片密度 | `lessons/nvda`、版式 | 中文段落移出幻灯片，交给字幕 | 所有者批准、视觉验收 | 抽帧可读 | **VERIFIED**：删除 8 页中文段；6 条 ASR mismatch 已分类，重定时 cue 80–84、111–116；重建 354.304 s，V-44 PASS；审阅记录在 `docs/<内容根>/archive/stabilization-evidence/c26/EDITORIAL_REVIEW.md` |
| C-27 | 验收文档算术错误 | `ACCEPTANCE`、`stats` | 计数由 `stats` 生成；更新数字 | C-25 | 文档数字与产物一致 | **VERIFIED**：`stats` 命令；ACCEPTANCE 2026-11-10 段 |
| C-28 | 未提交的品牌工作 | `BrandIntro`、3D shots | 记录设计/失败/当前版本，交由所有者决定提交 | 所有者 | 下一次会话能判断哪些已决定 | **VERIFIED**：源码分两笔提交（`84d5d5c`、`e611886`）；`out/`、预览帧、`*.blend1`、渲染副本被忽略；分类见 `BrandIntro/ASSET_CLASSIFICATION.md` |
| C-29 | 06 的 `subtitle disabled` 文案 | `verify` | 只在字幕禁用时使用该文案 | — | 06 的报告不再误导 | **VERIFIED**：`test_burnin`/verify 测试；06 V-31 已执行 |
| C-30 | 20 分钟 compose 停摆 | `build_lock`、`utils`、`atomic` | 同课单 build；超时杀进程树；原子写 | — | 01 单 build 产出 1195.605 s | **VERIFIED**：01 真实产物；`test_build_lock`、`test_run_command` |

状态计数：VERIFIED 25，FIXED 4（C-01、C-07、C-09、C-14），DEFERRED 1（C-16，所有者暂缓片头），OPEN 0。C-07 未升为 VERIFIED，因为 01 仍有行首标点 WARN。

## 3. 依赖图

```text
C-15 (run_id/hash)
  ├── C-05 (task run_id)
  ├── C-06 (package)
  └── C-20 (resume) ── C-24 (config snapshot)
C-08 (language declaration)
  └── C-07 (subtitle chain)
C-01 (production authority)
  └── C-14 (legacy bridge exit)
C-27 (scripted counts)
  └── C-12 (status truth)
C-16 (brand Gate) ── DEFERRED，不阻塞 V1
C-25 / C-26 ── 所有者内容批准
```

## 4. 未关闭项

### 4.1 C-25 / C-26（已处理）

- C-25：标题、因果遮罩、画面文案、旁白、SRT 已同步；06 重建 64.405 s，V-31/V-44 PASS，ASR 0.935、0 mismatch。原稿在 `lessons/06-attention-sample/authoring/original-2026-11-10/`。
- C-26：8 页中文重复段落已移除，NVDA 重建 354.304 s，V-44 PASS；前后帧与 15 s 片段在 `docs/<内容根>/archive/stabilization-evidence/c26/`。
- 仍待所有者：新措辞与新闻写作的编辑签核；不是工程阻塞。

### 4.2 C-28（已处理）

`brand-desktop` / `brand-intro` 源码已分两笔提交（`84d5d5c`、`e611886`）；生成物、预览帧、Blender 备份与 three.js 副本被忽略。分类见 `BrandIntro/ASSET_CLASSIFICATION.md`。

### 4.3 C-16 品牌 3D（DEFERRED）

所有者决定暂缓：当前视觉概念与 3D 角色设计不成熟，不在本方案上继续打补丁。保留 `BrandIntro/` 设计记录、`CodeVideoStudio/shots/brand-intro` 源码、角色资产与 Gate 3 前后帧。片头不进入生产默认链路，不阻塞 V1。后续独立重新设计。

### 4.4 C-07 05 已批准字幕

9 条 WARN 已逐条核对：6 条为句子续行/固定搭配的规则误报，3 条为中文标点孤行的真实排版错误。只修这 3 个 cue，V-44 现为 PASS；未重排全片。05 已按新 SRT 重建（292.373 s，ASR 0.992、0 mismatch）。复核记录：`lessons/05-transformer-5min/authoring/subtitles-review-2026-11-10.md`。仍待所有者确认这次微调是否作为正式修订。

## 4.5 C-20 真实中断注入

检查点与 resume 有单元测试；还没有在 01 这种 20 分钟构建上做"杀进程 → resume"的实测。下一次长片构建时应执行：

```powershell
.\scripts\build-lesson.ps1 -Lesson 01-transformer-demo
# 中途 Ctrl-C，然后
uv run --project CourseControl course-control build --lesson 01-transformer-demo --resume
```

## 4.6 R6 新发现（C-31、C-32）

| ID | 根因 | 影响 | 修复 | 状态 |
| --- | --- | --- | --- | --- |
| C-31 | `stage-assets.mjs` 把 `build/<lesson>/` 写死为 staging 根；`--build-root` 指向隔离目录时，时间线资产路径被拼成 `build/_stabilization/.../build/...` | 隔离构建无法 compose；真实课程用默认根时不受影响 | 增加 `--build-root` 参数；时间线资产按 workspace 解析后再相对实际 build root 计算 | **VERIFIED**：隔离 06 构建实测 |
| C-32 | 部分 CodeVideo 镜头目录没有 `node_modules` junction；`capture.mjs` 用项目目录解析 Playwright，直接报 `ERR_MODULE_NOT_FOUND` | 06 的 4 个 `attn-*` 镜头无法捕获 | `setup.ps1` 为所有含 `index.html` 的镜头建立指向 `RemotionStudio/node_modules` 的 junction；本轮已补建 | **VERIFIED**：06 的 `render:code_video` 从 fail 变为 pass |

这两条不在原始 C-01～C-30 中，是 R6 端到端构建暴露的问题；按文档标准分配新编号，不并入旧条目。

## 5. 本轮不做

- 不新增第七种生产计划或第二个配置层。
- 不为了通过而降低 QC、删 cue、改测试预期。
- 不重写课程正文。
- 不把实验能力（3D 片头、Agent 生成镜头）纳入生产默认链路。
