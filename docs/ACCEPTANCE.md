# 验收矩阵与命令

- **版本**：v1.4（2026-11-08）
- **上游**：[PRD.md](PRD.md)；结构与契约见 [ARCHITECTURE.md](ARCHITECTURE.md)
- 原则：**只记录真实执行结果**。未执行写 `NOT_RUN`，人工缺失写 `skipped`，凭据缺失写 `blocked`。

---

## 1. 一键回归

```powershell
.\scripts\check.ps1
# 期望：五套单测 + 课程契约（本地有课程时 6 个，干净克隆时 4 个夹具）+ 20 个场景契约，最后打印 check ok，exit 0
```

最近一次执行（2026-11-08）：**`check ok`，exit 0**。

| 套件 | 命令 | 用例数 | 结果 |
| --- | --- | --- | --- |
| CourseControl | `uv run --project CourseControl python -m unittest discover -s CourseControl/tests -t CourseControl` | 298（293 通过 + 5 跳过；含 R1 + Code2Video POC/QC + Claude Code + scene/Formula/Direction + director/producer） | 293 通过，5 跳过 |
| ModelingStudio | `uv run --project ModelingStudio python -m unittest discover -s ModelingStudio/tests -t ModelingStudio` | 33 | 全部通过 |
| ai_runtime | `uv run --project shared/ai_runtime python -m unittest discover -s shared/ai_runtime/tests -t shared/ai_runtime` | 50 | 全部通过 |
| ContentQA | `uv run --project ContentQA python -m unittest discover -s ContentQA/tests -t ContentQA` | 18 | 全部通过 |
| ManimSandbox | `uv run --project ManimSandbox python -m unittest discover -s ManimSandbox/tests -t ManimSandbox` | 11（10 通过 + 1 跳过） | 10 通过，1 跳过 |

合计 **416** 个用例（410 通过 + 6 跳过）；跳过项（Docker/录制等环境依赖）不计为通过。

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
| V-05 | 素材路径 `/lessons/<slug>/assets/` 且存在 | `validators.py` | 两门真实课通过 |
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

失败注入证据：`tests/test_staging.py`（合成失败保留 staging、成功清理）；R5 历史故障注入见 `docs/archive/R5-验收矩阵.md`；本轮未重复构造全部故障样本（见 §6）。

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
| `01-shell-for-ai-era` | deck + Motion | **incomplete** | 截图 20/20 通过；8 段 Motion 动画未导出 → `manual_export_required`；下游 `not_run` |
| `01-transformer-demo` | deck + Motion | NOT_RUN（本轮） | 与 Shell 课同一阻塞 |
| `lesson-manual` | recording + 人工导出 | validate 通过 | 本轮未单独构建 |

**真实课程未完成的原因**：`build/01-shell-for-ai-era/animation/` 没有 8 个导出文件。这是人工节点，不是程序缺陷；系统如实返回 `incomplete`，未伪装成 pass。

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
| 真实课程成片 | Motion Canvas 8 段未导出（人工） | `01-shell-for-ai-era` 为 `incomplete` |
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
| 导演计划 | `course-control director-plan --lesson 01-transformer-demo --workspace .` | `status: ready`；12 镜头 / 5 章 / 1200 s；0 error，9 warning |
| 结构校验 | `course-control director-validate --plan build/01-transformer-demo/director/director_plan.json` | `no issues` |
| 交付清单 | `course-control producer-run --lesson 01-transformer-demo --workspace .` | exit 1；`blocked`；4 项缺失（成片、旁白、字幕、build-report） |
| 增量检测 | `course-control producer-affected --lesson 01-transformer-demo --workspace .` | 无修改时 `no affected shots` |
| 增量命令 | `course-control producer-rebuild --lesson 01-transformer-demo --workspace .` | 无修改时 `no affected shots`；有修改时打印 `--shots` 命令与 `allow_render` 授权 |
| 旁白样片 | `course-control narration-build --lesson 01-transformer-demo --workspace . --sample-pages 1` | 第 1 页 43.92 s（计划 45 s，drift -1.08 s），`style_applied=true`，服务自动停止 |

边界：这两层是设计与制片校验，不是成片验收；不设抽帧关卡（D-047），渲染与 TTS 仍需显式命令。`build --storyboard` / `--shots` 已接入，可在已有构建上手动局部重渲染。

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

R1 测试计数：五套合计 **416 个用例（410 通过 + 6 跳过）**：CourseControl 304（299+5）、ModelingStudio 33、ai_runtime 50、ContentQA 18、ManimSandbox 11（10+1）。

R1 真实产物：

- `docs/R1-基线报告.md`、`docs/R1-1-引擎验证报告.md`、`docs/R1-性能基准报告.md`
- `docs/R1-5-候选稿索引.md`
- `build/r1/manim/.../SmokeScene.mp4`、`build/r1-smoke/blender/smoke.mp4`、`build/r1/remotion/smoke.mp4`
- `build/r1/timeline-smoke.mp4`（TimelineSpec 驱动 Remotion 的 6 秒真实片段）
- `build/01-transformer-demo/blender/stack_explode.mp4`（1920×1080 / 30 fps / 750 帧 / 25 s）
- `CodeVideoStudio/shots/attention-flow/out/final.mp4`（30s / 900 帧 / 两次渲染 900/900 帧哈希一致）
- `CodeVideoStudio/backends/hyperframes/hf-poc/out/hf-poc.mp4`（10s / 300 帧 / check 0 error 0 warning / 27.1s）
- `build/videozero-poc/output/attention-flow.mp4`（Motion Canvas image sequence → ffmpeg，1920×1080 / 30fps / 3007 帧 / 100.2s）
- `build/01-transformer-demo/narration/audition/s001-p1.wav`、`s001-p2.wav`（VoxCPM2 真实合成）
