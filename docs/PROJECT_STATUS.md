# 项目当前状态与 PRD 盘点

- **盘点日期**：2026-11-03
- **最近更新**：2026-11-08（旧 Manim 镜头统一、ContentQA 默认后端、文档/路径卫生）
- **代码基线**：`origin/main` = `b771408`；当前分支 `feat/v1-pipeline-remote-fallback` 本地 `37b0716` + 2026-11-08 未提交改动
- **基线核实**：2026-11-08 五套单测 420 个用例（414 通过 + 6 跳过）直接运行通过；`check-paths.ps1` = `path check ok`；整课旁白占用 `course-control.exe` 时 `check.ps1` 待补跑
- **需求基准**：[PRD.md](PRD.md)（v1.0）
- **映射索引**：[TRACEABILITY.md](TRACEABILITY.md)；工作流见 [WORKFLOW.md](WORKFLOW.md)

状态词：`COMPLETED`（实现且有真实证据）/ `PARTIAL`（有缺口）/ `NOT_IMPLEMENTED` / `BLOCKED`（外部条件限制）/ `NOT_RUN` / `DEFERRED` / `OUT_OF_SCOPE`。

---

## 0.1 2026-11-08 增量：导演层与制片层

| 能力 | 契约 / 代码 | 证据 | 状态 |
| --- | --- | --- | --- |
| FR-28 导演层 | `CourseControl/src/course_control/director/`、`docs/导演层.md` | 01-transformer-demo：12 镜头 / 5 章 / 1200 s / 12 ready；0 error / 5 warning；5 个真实渲染镜头 | COMPLETED（POC） |
| FR-33 模拟契约 | `simulation.py`、`primer-poc/`、POC 文档 | SimulationSpec + 30s POC；Three.js 900 帧 45.7 s；adapter + 导演计划 PASS | COMPLETED（POC） |
| FR-32 静帧运镜 | `motion.py`、`MotionImage.tsx`、`docs/运镜与剪辑.md` | ken_burns 元数据 + Remotion 组件；tsc 通过 | COMPLETED（POC） |
| FR-31 配色系统 | `layout/schema.py`、`ManimSandbox/common/design_system.py`、`docs/配色规范.md` | 浅色主题 + 语义色；palette-review 合辑 | COMPLETED（POC） |
| FR-30 版式系统 | `CourseControl/src/course_control/layout/`、`docs/版式系统.md` | 8 个模板、12 镜头模板分配、CrossAttention/Loss 前后对比 | COMPLETED（POC） |
| FR-29 制片层 | `CourseControl/src/course_control/producer/`、`docs/制片层.md` | 订单 + 七项交付清单：blocked，4 项缺失；增量检测实测 | COMPLETED（POC，交付未完成） |

边界：导演层不写场景代码、不渲染；制片层不读密钥、不触发渲染/TTS/发布；成片未产出，交付清单如实 blocked。

### 0.1a 2026-11-08 视觉与文档收尾

| 内容 | 文件 | 证据 |
| --- | --- | --- |
| 旧 Manim 镜头统一 | `ManimSandbox/01-transformer-demo/qkv_fanout.py`、`row_trace.py`、`head_split_merge.py`、`position_add.py` | 纸白底 + `design_system` 语义色；修复字面量颜色、标题/底注重叠、context 越界、标签对比度；末帧渲染核对 |
| 残差镜头核对 | `residual_bypass.py` | 垂直栈、旁路、括号与标签在安全区内；末帧渲染核对 |
| 导演层回归 | `test_director.py` | Golden plan 不再期望 `style.background_mismatch` |
| Ken Burns 真实核对 | `build/01-transformer-demo/slides/`、`build/01-transformer-demo/final/motion-test.mp4` | 12 页真实截图；150 帧 CourseTimeline；首末帧可见推近与 1.2% 平移 |
| 运行时版式检查 | `ManimSandbox/common/scene_checks.py` | 文本安全区/重叠检查；`STRICT_LAYOUT=1` 下 5 个旧镜头全部 clean |
| 4K60 渲染基准 | `build/01-transformer-demo/final/motion-4k60.mp4` | 3840×2160 / 60fps / 60 帧；slides capture 已按课程分辨率参数化 |
| AudioPlan | `CourseControl/src/course_control/audio_plan.py`、`audio-plan` CLI | 内容类型/许可/署名/电平闸门；6 个单测；输出 `build/<slug>/audio/audio_plan.json` |
| 章节卡 | `RemotionStudio/src/compositions/ChapterCard.tsx` | 真实 still 渲染；尚未自动插入时间线 |
| 全量 Manim 镜头 | `build/01-transformer-demo/animation/*.mp4` | 7 个镜头 1080p30 全部渲染并通过 adapter |
| Motion Canvas 无头导出 | `MotionStudio/scripts/render-headless.mjs`、`src/headless.js` | attention-flow 1920×1080/30fps/142 帧；3 次 SHA256 一致；注入第 30 帧失败不产 MP4 |
| 长序列基准（失败） | `CodeVideoStudio/shots/primer-rps` | 180 s / 5400 帧 capture 未产出可播放 MP4；30 s 基线仍有效 |
| ContentQA 默认后端 | `ContentQA/src/content_qa/config.py`、README | 默认 `claude_code`；API 测试显式固定 `backend: api` |
| 路径与文档 | 全部 README、`docs/` | `path check ok`；清除控制字符与个人路径；补全 `VOICE_REF_WAV`、junction、配色说明 |

## 0. 2026-11-04 增量（P1–P4）

- **分支**：`feat/p1-teaching-primitives`（已推送，6 个提交）
- **范围**：三维教学基元、二维标注、字体、材质、科学着色、参数化曲面；**未改动任何课程正文**。

| 能力 | 契约 / 代码 | 证据 |
| --- | --- | --- |
| TEXT / CURVE / ORTHO | IR v2 §5.1.1、§6；`scene_system/` | 8 次真实渲染中的 `text-curve.png` |
| 二维标注 + 字体 | `storyboard.annotations` → `shots.json`；`overlays/Annotations.tsx`；Noto Sans SC（OFL） | `annotation-still.png`、`annotation-font-still.png` |
| 材质预设 / Coat / Bump | `scene_presets.py`、`assets/materials/presets/`、`scene.materials` | `materials.png` |
| 科学着色 | `scientific_colormap`、`shared/colormaps.json`、`scene.attributes` | `scientific.png` |
| 参数化曲面 | `shared/scene_expr`、`SURFACE`、`scene.surfaces` | `surface.png` |

当前计数：**9 合法 + 11 非法场景契约**，**8 次真实 Blender 渲染**，**112 个单测**（51+28+22+11）。

未做：课程内容（作者负责）、P5 真实数据导入（无数据源）、P6 AI 场景规划（待课程页输入）。

### 0.1 2026-11-06 代码会话增量

| 能力 | 代码 / 契约 | 证据 |
| --- | --- | --- |
| 会话契约 | `session.py`：SessionSpec / ExecutionResult / RecordingResult / EvidenceManifest / ValidationReport | `shared/schemas/session.schema.json`、`evidence.schema.json`；62 个 CourseControl 测试 |
| Docker 执行 | `session_runner.py`、`container_runner.py`、`course-tools:e1` | 无网络、非 root、只读根文件系统、cap-drop、资源限制 |
| 终端录制 | mintty + gdigrab `hwnd` | `build/lesson-smoke/code/shell_001/session.mp4`；V-23/V-24 |
| VS Code 会话（E2） | `CourseDemo/` 扩展、shell integration、`vscode_runner.py`、PrintWindow 录制 | `build/lesson-smoke/code/vscode_001/session.mp4`；V-23/V-24 |
| 旁白 V1 | `narrate.py`：VoxCPM2 单段合成、缓存键、meta、50000 锁、自动起停 | 真实 `smoke-001.wav`（48 kHz，1.76 s）与 `.meta.json` |
| Python 工具链（E3） | `offline_commands`、本地 HTTP 索引、`trim`、`check-python-session.ps1`、`check-python-network.ps1` | `python_001` / `python_network_001`：安装 + 离线验证；V-23/V-25 |
| Manim FFT 基线（E5） | `ManimSandbox/02-fft-baseline/fft_baseline.py` | `build/manim-fft/fft_baseline.mp4`：1920×1080 / 30fps / 7.8s |
| Rust 镜头（E4） | `rust-001` fixture、`check-rust-session.ps1` | host VS Code + Git Bash，`cargo run`；V-23/V-24 |
| Transformer 基线（E6） | `ManimSandbox/03-transformer-baseline/attention_baseline.py`、`04-transformer-explainer/`、`docs/archive/E6/E6-Transformer制作方案.md`（本地归档） | 四幕成片 33.1s（旁白 + 字幕 + manifest）；E6.1–E6.4 完成 |

当前计数：CourseControl 66 个单测；全套 127 个；场景契约仍为 9 合法 + 11 非法；8080 未被触碰。

### 0.2 2026-11-07 统一契约设计增量

| 文档 | 内容 | 状态 |
| --- | --- | --- |
| `docs/archive/reviews/架构审查-课程生产统一契约.md`（本地归档） | 现有课程/模块边界、重复实现、接口缺失、耦合、保留/调整建议 | 已完成审查，未改代码 |
| [课程生产统一契约V1.md](课程生产统一契约V1.md) | LessonSpec / ShotSpec / NarrationSpec / TimelineSpec / EvidenceManifest / RenderManifest；整数帧时间线；E6 manifest 兼容 | 已评审；V1-B 已实现 |
| [contracts/examples/](contracts/examples/) | Lesson / Shot / Narration / Timeline / Evidence / Render 示例 + E6 V0 迁移示例 | 示例 JSON，已做语法校验 |
| `docs/archive/E6.5/E6.5-MultiHead设计.md`（本地归档） | 两头算例、五 beat 分镜、旁白/字幕、维度清单、自动验收 | 已完成（见 §0.8） |

本轮只写文档与示例，未修改任何代码；CourseControl 66 个单测通过（2 个集成测试跳过）；E6.1–E6.4 未改动；8080 未触碰。决策记录见 [DECISIONS.md](DECISIONS.md) D-026。

### 0.3 2026-11-07 V1-B 实施增量

| 内容 | 文件 | 状态 |
| --- | --- | --- |
| 有理数帧率与整数时间换算 | `CourseControl/src/course_control/timecode.py` | 已实现；10 个测试 |
| V1 契约模型 | `CourseControl/src/course_control/contracts_v1.py` | 已实现；40 个测试 |
| V1 JSON Schema | `shared/schemas/*-v1.schema.json` | 7 份；与模型逐份比对 |
| V1 CLI | `schemas-v1`、`contract-v1-validate` | 已实现 |
| 实施报告 | `docs/archive/V1/V1-B-实施报告.md`（本地归档） | 测试与兼容性说明 |

CourseControl 现为 **116 个用例（114 通过 + 2 跳过）**；全项目合计 177 个用例（175 通过 + 2 跳过）。跳过的 2 个不计为通过。未迁移 E6 manifest，未改 E6.1–E6.4，未触碰 8080。

### 0.4 2026-11-07 V1-C E6 只读适配增量

| 内容 | 文件 | 状态 |
| --- | --- | --- |
| E6 V0 只读适配 | `CourseControl/src/course_control/legacy_e6.py` | 已实现；V0 与媒体未改 |
| `e6-adapt` CLI | `CourseControl/src/course_control/cli.py` | 已实现；失败检查 exit 1 |
| 自动检查 | ffprobe + sha256 + SRT 解析 | 本地 36 条：35 pass + 1 not_applicable |
| 适配器测试 | `CourseControl/tests/test_legacy_e6.py` | 12 个；本地集成测试执行，干净克隆显式 skip |
| 实施报告 | `docs/archive/V1/V1-C-实施报告.md`（本地归档） | 测试与兼容性说明 |

CourseControl 现为 **129 个用例（127 通过 + 2 跳过）**；全项目合计 190 个用例（188 通过 + 2 跳过）。E6 V0 `manifest.json` 仍为 `43037d39…` 未被修改；E6.1–E6.4 未改；8080 未触碰。V0 人工 `checks` 只进入 `legacy.manual_checks`，`manual_checks_trusted=false`。

### 0.5 2026-11-07 E6.5 数学验证

| 内容 | 文件 | 状态 |
| --- | --- | --- |
| 两头算例唯一数据源 | `ManimSandbox/05-multi-head/multi_head_math.py` | 纯标准库；无 numpy/Manim |
| 独立计算脚本 | `ManimSandbox/05-multi-head/verify_math.py` | exit 0；30 条检查全 pass |
| 单元测试 | `ManimSandbox/tests/test_multi_head_math.py` | 8 个用例 |
| 验证报告 | `docs/archive/E6.5/E6.5-数学验证报告.md`（本地归档） | 形状、alpha 行和、头差异、concat、W_O |

E6.5 当时全项目为 **198 个用例（196 通过 + 2 跳过）**。E6.5 数学算例已验证，可进入 `MultiHeadScene` 视觉编码；尚未生成旁白/字幕/成片。

### 0.6 2026-11-07 E6.5 视觉场景

| 内容 | 文件 | 状态 |
| --- | --- | --- |
| MultiHeadScene | `ManimSandbox/05-multi-head/multi_head.py` | 已创建并真实渲染 |
| 视觉成片 | `build/manim-multi-head/e6.5/media/videos/multi_head/1080p30/MultiHeadScene.mp4` | 1920×1080 / 30fps / 1504 帧 / 50.129s；仅视频 |
| 渲染报告 | `docs/archive/E6.5/E6.5-视觉渲染报告.md`（本地归档） | 五 beat、抽帧核对、未做旁白/字幕 |

场景从 `multi_head_math.py` 读取全部矩阵，未另写算例。E6.1–E6.4 未改；8080 未触碰。

### 0.7 2026-11-07 E6.5 旁白、字幕与成片

| 内容 | 文件 | 状态 |
| --- | --- | --- |
| 5 段中文旁白 | `build/manim-multi-head/e6.5/narration/segments/e65-b*.wav` | VoxCPM2 真实合成；48 kHz mono |
| 混合旁白 | `build/manim-multi-head/e6.5/narration.wav` | 86.929 s；按 beat 起点放置 |
| SRT | `build/manim-multi-head/e6.5/subtitles.srt` | 10 条；均在 beat 内 |
| 最终成片 | `build/manim-multi-head/e6.5/final.mp4` | 1920×1080 / 30fps / 2608 帧 / 86.929s；视频+音频+字幕 |
| 自动检查 | `build/manim-multi-head/e6.5/manifest.json` | 14 条全 pass；`all_ok: true` |
| 成片报告 | `docs/archive/E6.5/E6.5-成片报告.md`（本地归档） | 旁白/字幕/mux/检查 |

全项目现为 **201 个用例（199 通过 + 2 跳过）**。TTS 50000 调用前已 ready，本次复用，未启动/停止他人服务；未触碰 8080。

### 0.8 2026-11-07 E6.5 V1 契约

| 内容 | 文件 | 状态 |
| --- | --- | --- |
| E6.5 V1 适配 | `CourseControl/src/course_control/e65.py` | 生成 NarrationSpec / TimelineSpec / ShotSpec / RenderManifest |
| CLI | `course-control e65-adapt` | 已实现；14 条成片检查全 pass |
| 生成契约 | `build/manim-multi-head/e6.5/contracts/` | `source.lesson_spec=null`；timeline/narration 非空 |
| 适配测试 | `CourseControl/tests/test_e65_contracts.py` | 2 个；本地集成测试执行 |
| 成片报告 | `docs/archive/E6.5/E6.5-成片报告.md`（本地归档） | V1 契约与复现命令 |

全项目现为 **203 个用例（201 通过 + 2 跳过）**。E6.5 未并入 `pipeline.py` / `lessons/`；未做逐字强制对齐；未改 E6.1–E6.4；未触碰 8080。

### 0.9 2026-11-07 路径卫生、远程回退与 V1-D/E

| 内容 | 文件 | 状态 |
| --- | --- | --- |
| 本机路径清理 | `e65.py`、`session_runner.py`、`vscode_runner.py`、文档与示例 | 去掉硬编码盘符；本机路径只存在于被忽略的 `config/*.yaml` / `.env` |
| 路径卫生检查 | `scripts/check_paths.py`、`scripts/check-paths.ps1` | 已接入 `check.ps1`；本轮 `path check ok` |
| AI 后端/回退 | `claude_code.py`、`remote.py`、`routing.py` | Claude Code 默认；本地/远程仅在显式允许时回退；任务记录写 `provider` |
| ModelingStudio 接入 | `config.py`、`server.py`、`llm.py`、四个阶段模块 | 真实值由本地 `.env` / `config/model-routing.yaml` 提供；视觉阶段使用 `deepseek-flash`，不降级到文本模型 |
| V1-E 兼容层 | `CourseControl/src/course_control/v1_timeline.py` | `shots.json ↔ TimelineSpec` 双向；`collect` 已写 `contracts/timeline.spec.json`；Remotion 仍读旧文件 |
| V1-D 证据适配 | `CourseControl/src/course_control/session_evidence_v1.py` | 现有 `evidence.json` → `EvidenceManifestV1`；缺失录屏不伪造 |
| 测试 | 各套新增用例 | 全项目 **328 个用例（326 通过 + 2 跳过）** |
| 远程真实冒烟 | 本地 `.env`、`DeepSeek-API` | 2026-11-07 可达；`deepseek-flash` 文本返回 `OK`，图片返回“红色”；密钥未落盘、未打印 |
| DeepSeek 模型策略 | `remote.py`、ModelingStudio `config.py`、ContentQA `config.py`、测试 | 所有 DeepSeek 调用固定 `deepseek-flash`；`deepseek-v4-pro` 在三个配置层均被拒绝 |
| 环境文件 | 本地 `.env`（忽略）、`.env.example`（跟踪） | 通用 `REMOTE_*` / DeepSeek `DEEPSEEK_*`；key 只从系统环境变量读取，不落盘；仓库只保留不含 key 的参考文件 |

V1-D/E 仍未完成的部分：Session/SessionSpec 原生写 V1、`ShotSpec` 扩展 `session/simulation/graphics`、Remotion 直接消费 `TimelineSpec`。本轮只做只读适配与兼容桥接，未改 `shots.json` 的消费方。

---

### 0.10 2026-11-07 R1 混合动画与课程生产闭环（进行中）

| 内容 | 文件 | 状态 |
| --- | --- | --- |
| R1-0 基线 | `docs/archive/R1/R1-基线报告.md`（本地归档） | 已完成；`check ok`；240 用例基线 |
| R1-1 引擎验证 | `ManimSandbox/00-r1-smoke/`、`RemotionStudio/src/compositions/R1Smoke.tsx`、`docs/archive/R1/R1-1-引擎验证报告.md`（本地归档） | Manim 3.8s / Blender Eevee 5s / Remotion 5s 真实出片；Motion Canvas 无 headless CLI |
| R1-2 性能基准 | `scripts/benchmark_render.py`、`docs/archive/R1/R1-性能基准报告.md`（本地归档）、`build/r1/benchmark/` | Eevee 20.92s / Cycles CPU 346.56s / Cycles oneAPI 291.78s（2s 片段）；Manim final 5.38s；Remotion 19.66s；QSV 5.34s vs libx264 2.91s |
| 时长契约 | `duration.py`、V-26/V-27 | 已实现；`lesson-authoring` 夹具 |
| 引擎路由 | `engine_router.py` | 已实现；内容决定引擎 |
| TimelineSpec 合成 | `CourseTimeline.tsx`、`stage-assets.mjs --timeline`、`adapters/remotion.py` | 已实现；`build/r1/timeline-smoke.mp4` 6.016s 真实合成 |
| 输入/草稿/批准 | `authoring/`、`CourseControl/prompts/` | 已实现；Transformer 候选已批准并提升 |
| Transformer 内容 | `lessons/01-transformer-demo/` | 12 页 / 1200s；英文口播 2964 词；5 个动画镜头 |
| 动画 | `ManimSandbox/01-transformer-demo/`、`BlenderStudio/scenes|tasks/01-transformer-demo/` | 4 个 Manim 已测试渲染；Blender shot 25s 已真实渲染 |
| 整课旁白 | `narration_course.py`、`scripts/generate_voice_ref.py` | 已实现；英文参考音已生成；01-transformer-demo 第 1 页样片 43.92 s（计划 45 s，style_applied），整课未跑 |
| 双语字幕 | `subtitles.py`、`authoring/glossary.yaml` | 已实现；计划版 357 cue 全部翻译，2 条临界警告（cue 273 时长 0.94 s、cue 317 中文 3 行）；实测旁白后严格重排 |
| 双版本成片 | `adapters/burn.py`、V-28 | 已实现；真实 5s ASS 烧录 pass |
| Code2Video | `CodeVideoStudio/`、`adapters/code_video.py`、`code_video_qc.py` | 生产化目录；30s Canvas 镜头，check_video OK，900/900 帧哈希一致；adapter 真实跑通；QC 门输出 `*.qc.json` + `*.contact.jpg`（`build/code-video-qc2/`） |
| HyperFrames POC | `CodeVideoStudio/backends/hyperframes/hf-poc/` | 10s HTML/GSAP，check 0 error/0 warning，27.1s 渲染；仅作为可选 HTML 后端 |
| VideoZero POC | `build/videozero-poc/`（临时） | agent 连接/seek/screenshot 成功；image sequence 自动导出 3007 PNG → ffmpeg 100.2s MP4；FFmpeg exporter 直接导出挂起 |
| 汽车空气动力学课 | `lessons/02-car-aerodynamics/`（本地，不入库） | 12 页 / 2,835 词 / 4 个 Manim 镜头；13 条来源；22:00 成片；clean + captioned；V-26..V-31 pass |
| Claude Code 后端 | `shared/ai_runtime/src/ai_runtime/claude_code.py`、`config/claude-code.example.yaml` | 课程文本/字幕/ContentQA/ModelingStudio 文本规划/Code2Video 默认走 Claude Code；文本阶段 `--tools=`；任务记录 `provider=claude_code`；真实 smoke 通过 |
| 动画视觉导演 | `AnimationDirection`、`direction-validate`、`ManimSandbox/03-vector-intro/` | 90 秒竖切片 1920×1080/30fps；分镜字段与视觉门 |
| 导演层 | `director/`、`director-plan`、`director-validate` | 12 镜头 / 1200 s / 0 error / 5 warning；storyboard、directions、shot_specs、review |
| 制片层 | `producer/`、`producer-order/run/status/affected` | 七项交付清单 blocked（4 项缺失）；订单、限额、指纹与增量 |
| 版式系统 | `layout/`、`layout-templates`、`layout-validate` | 8 模板、安全区/重叠/容量闸门；CrossAttention/Loss 重做 |
| 配色系统 | `DesignSystem`、`design_system.py` | 暖白/石墨/橙 + 输入蓝/处理青/输出紫/误差红；对比度测试 |
| 静帧运镜 | `motion.py`、`MotionImage.tsx`、`lesson.motion` | Ken Burns、4 种路径、边界约束；static 可关 |
| 模拟契约 | `simulation.py`、`simulation.spec.json`、`PrimerPoc.tsx` | 91-agent RPS POC；Three.js 长序列/Blender hero |
| 科学图形 POC | `ScientificFigures/` | SymPy + Matplotlib + SciencePlots；连续性方程 LaTeX + Poiseuille SVG/PDF/PNG |
| Formula Pipeline | `formulas.py`、`Formula.tsx`、`formula-render.mjs`、Manim smoke | 唯一 LaTeX 源；KaTeX HTML/PNG；四类 validation；三路冒烟 |
| 技术雷达 | `docs/evaluations/技术雷达-视频生产.md`、`docs/课程生产交付物规范.md`、`docs/evaluations/评估-DeepSeek Harness.md`、`docs/evaluations/评估-四后端对比.md` | 评分/许可证/硬门槛/交付归档规范；Claude Code/dsh 对比与受控代理决策（不接入运行时） |
| 测试 | 五套单测 | **420 个用例（414 通过 + 6 跳过）**：CourseControl 308（303+5）、ModelingStudio 33、ai_runtime 50、ContentQA 18、ManimSandbox 11（10+1） |

**暂缓**：具体课件内容、整课 TTS、实测字幕与最终成片（按用户要求先做仓库/接入优化）。**已完成**：Code2Video P2（含 QC 门）、HyperFrames POC、VideoZero POC、技术雷达与交付物规范、DeepSeek Harness CLI 对比、四后端镜头生成对比、Claude Code 全量默认后端接入、汽车空气动力学课（制作中）。

---

## 1. 基线核实

- 核实日期：2026-11-07；工作树干净；`check.ps1` 实跑 `check ok`。
- E6.5 的 3 个提交已合并进 `main`；无关的 `django.yml` 已删除并推送。

| 项 | 事实 |
| --- | --- |
| 当前分支 | `feat/v1-pipeline-remote-fallback` |
| 功能提交 | `d95d887 feat: 路径卫生、远程模型回退与 V1-D/E 兼容层`；本文件为随后的基线同步提交 |
| `origin/main` | `577501e chore: 移除与本项目无关的 Django CI 模板` |
| 本地 `main` | `577501e`，与 `origin/main` 同步 |
| 远程状态 | feature 分支已推送至 `d97d0af`；尚未合并 `main` |
| `d53ebd1` | 干净的初始工作流快照（无父提交）；仍是最早基线 |
| `converge/v1` | `dd1d7f2`，完整收敛历史（含早期课程内容），**仅本地** |
| `archive/full-history-2026-11-03` | `adef52f`，改造前 main，**仅本地** |
| 远程内容 | `origin/main` 375 个文件；`lessons/` 仅 `README.md`；无 `build/`、`runtime/`、`.venv`、`node_modules` |
| 本地 HEAD 内容 | 387 个文件；相对 `origin/main` 新增 12 个（远程回退、V1-D/E、路径检查与配置示例） |

**说明**：`d53ebd1` 是干净快照；当前代码已经过 E0–E6.5、V1-B/C/D/E 与远程回退增量。

**仓库元数据**：Description 与 9 个 Topics 已通过 `gh repo edit` 写入并回读确认。

**待处理（未擅自修改）**：

1. 当前 feature 分支已推送、尚未合并到 `main`；需要 PR 或直接合并。
2. V1-D 的 Session runner 原生写 V1、`ShotSpec` 扩展 `session/graphics` 未做；`simulation` 已加入。
3. Remotion adapter 已按 `compose.renderer=timeline` 选择 `CourseTimeline`；真实课程尚未跑完整构建。
4. 真实课程仍缺 8 段 Motion 导出；`01-transformer-demo` 未构建。

---

## 2. 功能需求（FR）

| 编号 | 需求 | 当前实现 | 验证证据 | 状态 | 后续 |
| --- | --- | --- | --- | --- | --- |
| FR-01 | 课程内容契约 | `lessons/` + `paths.py` / `contracts.py` | 5 个课程/夹具 validate 通过（本地） | COMPLETED | — |
| FR-02 | V-01~V-09 校验 | `validators.py` | `check.ps1`；V-04 失败单测 | COMPLETED | — |
| FR-03 | 预览与截图 | `adapters/slides.py` + `capture-slides.mjs` | 真实课程 20/20（`build/01-shell-for-ai-era/slides`） | COMPLETED | — |
| FR-04 | 动画渲染 | Motion 无头自动导出；Manim / Blender v1 适配器 | attention-flow 3 次哈希一致；注入失败不产 MP4；`lesson-manual` fixture PASS | COMPLETED（真实课程待重跑） | 重跑 01-shell 全课 |
| FR-05 | IR v2 场景任务 | `blender_scene.py`、`blender_runner.py`、`scene_system/`、`scene_presets.py`、`shared/scene_expr` | `check-scene-system.ps1 -Render` 8 次真实渲染；CourseControl 测试覆盖见 ACCEPTANCE（2026-11-04 新增 TEXT/CURVE/ORTHO、材质预设、科学着色、参数化曲面与语义验收） | COMPLETED | — |
| FR-06 | 本地自动建模 | `ModelingStudio/` | 28 个测试；历史作业 `sample-001` 六阶段 completed | PARTIAL | 真实全链路本轮未重跑（需独占 8080） |
| FR-07 | 时间线收集 | `collect.py`（含 `annotations[]`） | `lesson-smoke` shots.json 通过 verify；V-22 标注检查 | COMPLETED | — |
| FR-08 | 合成与成片验收 | `verify.py`、`report.py`、`adapters/remotion.py` | `lesson-smoke`、`lesson-blender-only` verdict pass | COMPLETED | — |
| FR-09 | 本地模型严格串行 | `shared/ai_runtime`（含 `remote.py` / `routing.py`） | 41 个 ai_runtime 测试（双进程、生命周期、远程回退、flash-only 策略、env 覆盖）；真实 DeepSeek 文本/图片冒烟 | COMPLETED | — |
| FR-10 | 任务状态与恢复 | `tasks.py`、`job.py`、`--resume` | 失败落盘、断点续跑测试 | COMPLETED | — |
| FR-11 | 上下文预算 | `budget.py` + 各阶段预算 | 预算/超限/重试绕过测试 | COMPLETED | — |
| FR-12 | 在线内容审查 | `ContentQA/` | 11 个 mock 测试；真实课程 `blocked` exit 3 | PARTIAL | 真实供应商与凭据未配置 |
| FR-13 | 报告与可追溯 | 构建报告、manifest、任务记录、审查报告 | 各报告结构测试 | COMPLETED | — |
| FR-14 | 一键回归 | `scripts/check.ps1` | `check ok`，exit 0 | COMPLETED | — |

### 非功能需求（NFR）

| 编号 | 需求 | 状态 | 说明 |
| --- | --- | --- | --- |
| NFR-01 | 可复现 | PARTIAL | 夹具重复构建文件集合稳定；Motion 自动导出 3 次 SHA256 一致；真实课程本轮未重跑 |
| NFR-02 | 失败可见 | COMPLETED | 状态与 failures 一致 |
| NFR-03 | 隔离 | COMPLETED | 本机配置与产物均忽略 |
| NFR-04 | 路径安全 | COMPLETED | 绝对路径/反斜杠/`..` 被拒 |
| NFR-05 | 资源串行 | COMPLETED | 跨进程锁 + 单实例服务 |
| NFR-06 | 可中断 | COMPLETED | 锁释放、陈旧锁回收 |
| NFR-07 | 最小依赖 | COMPLETED | ai_runtime 零第三方依赖 |
| NFR-08 | 文档一致 | COMPLETED | 本轮再次核对计数、链接与 Schema |
| NFR-09 | 路径卫生 | COMPLETED | `scripts/check-paths.ps1`；跟踪文件无本机绝对路径 |

### 验收条件（PRD §9）

| # | 条件 | 状态 | 证据 |
| --- | --- | --- | --- |
| 1 | `check.ps1` 打印 `check ok` | COMPLETED | 本地与干净工作树各一次 exit 0 |
| 2 | 单测真实通过且数量一致 | COMPLETED | 416 个用例（410 通过 + 6 跳过；308+33+50+18+11） |
| 3 | 5 课程 + 20 场景契约 | COMPLETED | `check.ps1` |
| 4 | `lesson-smoke` 全链路 pass | COMPLETED | 真实 Blender + Remotion |
| 5 | 真实课程如实报告状态 | COMPLETED | 历史 `incomplete` 保留；Motion 自动导出已用 POC/夹具验证 |
| 6 | 本地模型串行有真实证据 | COMPLETED | 双进程竞争测试 |
| 7 | 内容审查 mock + 不可用 blocked | COMPLETED | ContentQA 测试 + 真实课程 exit 3；默认 Claude Code，API 路径测试显式固定 |
| 8 | 预算测试通过并记录 | COMPLETED | 每次请求前检查并写任务记录 |
| 9 | 失败/阻塞/取消可读回 | COMPLETED | 任务记录终态 |
| 10 | 文档一致、无 P0 | COMPLETED | 本轮盘点 |

### OPEN 项

| 编号 | 事项 | 状态 | 说明 |
| --- | --- | --- | --- |
| OPEN-01 | Motion Canvas headless 导出 | COMPLETED | D-054；Renderer + 帧接收器 + ffmpeg |
| OPEN-02 | 真实课程内容补全 | BLOCKED | 4 页占位、3 页中文，责任在作者；动画导出已自动 |
| OPEN-03 | 审查后端供应商与凭据 | BLOCKED | 默认 Claude Code；API 未配置时 `blocked` 语义已实现 |
| OPEN-04 | Manim 接入课程 | DEFERRED | 无课程使用，不强行接入 |
| OPEN-05 | 完整 ContentQA（ASR/TTS/公式/语料） | OUT_OF_SCOPE | 本期只交付审查内核 |
| OPEN-06 | 多课程并行构建 | OUT_OF_SCOPE | 单机单用户，无需求 |

### 计数

| 类别 | 数量 |
| --- | --- |
| FR-01..14 已完成 | 11 / 14 |
| FR-01..14 部分完成 | 3 / 14（FR-04、FR-06、FR-12） |
| FR-15..29 | 逐条跟踪见 [TRACEABILITY.md](TRACEABILITY.md)；FR-28/29 见下方增量 |
| FR 阻塞 | 0（阻塞发生在 PARTIAL 项的子环节） |
| NFR 完成 | 7 / 8 |
| 验收条件完成 | 10 / 10 |
| OPEN：DEFERRED / BLOCKED / OUT_OF_SCOPE | 2 / 2 / 2 |

**不需要继续投入的事项**：OPEN-05、OPEN-06；OPEN-01/04 保持暂缓，除非出现明确课程需求。

---

## 3. 发现的冲突与偏差（未修改 PRD）

| 编号 | 冲突/偏差 | 证据 | 处理建议 |
| --- | --- | --- | --- |
| C-01 | 远程 `main` 含无关的 `django.yml` CI | 已删除并推送（`577501e`） | **已解决**；如需 CI，另写本项目工作流 |
| C-02 | 本地 `main` 落后 `origin/main` | 已快进同步到 `577501e` | **已解决** |
| C-03 | PRD FR-10 要求“产物存在且**校验通过**才算完成”；`stage_done` 只检查状态 + 文件存在 | `ModelingStudio/src/modeling_studio/job.py::stage_done` | 当前产物为 JSON/Markdown，无独立校验器；建议在 PRD 中把措辞改为“产物存在且可由后续阶段解析”，或补校验 |
| C-04 | `ManimSandbox/requirements.txt` 与 `pyproject.toml` 重复声明依赖 | 两个文件同时存在 | 保留 `pyproject.toml`，把 `requirements.txt` 降级为可选导出，或删除 |
| C-05 | 最新 E6.5 提交只在 feature 分支 | 已合并进 `origin/main`（`b230306`） | **已解决**；当前新增工作仍需合并 |

---

## 4. 清理记录

### 已删除（可再生成）

| 路径 | 类型 | 大小 | 依据 |
| --- | --- | --- | --- |
| 16 个 `__pycache__/` | 字节码缓存 | ~950 KB | Python 自动生成 |
| `ManimSandbox/media/` | Manim 渲染缓存 | 803 KB | 可由 `uv run manim` 重建 |
| `ModelingStudio/workspace/*-sample-002.log` | 散落日志（3 个） | ~13 KB | 作业目录内已有逐阶段日志 |
| `RemotionStudio/public/staging/`（空目录） | 合成临时目录 | 0 | 合成时自动创建 |

### 保留（不作为“无用残留”删除）

| 路径 | 大小 | 原因 |
| --- | --- | --- |
| `build/` | 30 MB | 当前验收证据（截图、渲染、报告），可再生成 |
| `ModelingStudio/workspace/jobs/` | 5 MB | 历史作业与任务记录证据 |
| `.venv/`、`node_modules/` | ~1.6 GB | 运行依赖，删除后需重装 |
| `lessons/` | 本地 | 用户课程正文 |
| `docs/archive/` | 小 | 历史决策与证据 |
| `BlenderStudio/assets/*.blend`、`scenes/*.blend` | ~300 KB | 测试与渲染夹具 |
| `config/*.yaml`（本机） | 小 | 本机路径与凭据 |

### 待确认，未删除

| 路径 | 建议 |
| --- | --- |
| `build/lesson-*` 与 `build/01-shell-for-ai-era` | 归档或重新验收前可清空；命令：`Remove-Item -Recurse -Force build` |
| `ModelingStudio/workspace/jobs/{sample-001,sample-002,fallback-test}` | 如需保留作业证据先复制到仓库外 |
| `BlenderStudio/tasks/01-shell-for-ai-era/`（v1 历史夹具） | 文档仍引用，保留；若确定不再维护可归档 |

---

## 5. 复用与重复

- `docs/TRACEABILITY.md` 已收敛为索引，状态表以本文件为准。
- 规则只在 PRD / ARCHITECTURE / ACCEPTANCE 定义一次，其余文档引用。
- 未发现新的未登记模块或配置。
