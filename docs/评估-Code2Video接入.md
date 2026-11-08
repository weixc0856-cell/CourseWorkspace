# 评估：SenseNova-6.8-Code2Video 接入可能性与优化方向

- **日期**：2026-11-07
- **仓库**：https://github.com/OpenSenseNova/SenseNova-6.8-Code2Video
- **许可证**：Apache 2.0（模型与仓库）
- **结论**：**值得接入，但只接入 Skill / 工作流 / 检查脚本，不部署 27B 模型，也不把它做成第五个独立动画引擎。** 先用独立 POC 验证，不打断当前 R1。

---

## 1. 核查到的事实

| 项 | 事实 | 来源 |
| --- | --- | --- |
| 模型 | 27B，基于 Qwen3.8-27B 微调，512K 上下文 | GitHub / Hugging Face |
| 权重 | BF16 约 54.7 GB，12 个分片；官方部署用 vLLM / LightLLM / SGLang，4 路张量并行 | GitHub / HF |
| 许可 | Apache 2.0 | HF |
| 核心思路 | 模型写可执行代码；每帧是 `t` 的纯函数；逐帧渲染、Contact Sheet 审看、修改、复渲染 | Skill / README |
| Skill | `skills/code-video`，固定工作流，**模型无关的文件与脚本** | Skill |
| 八类指南 | explainers、stylized looks、simulations/generative art、character motion、Three.js 3D、motion graphics、sound & narration、music sync | GitHub |
| 渲染栈 | Canvas 2D、SVG/HTML+CSS、Remotion、Manim、Three.js、WebGL/GLSL、Node canvas | SKILL.md |
| 脚本 | `capture.mjs`、`contact_sheet.sh`、`check_video.sh`、`audio_check.sh`、`sync_check.py`、`synth.py` | Skill |
| 生产轨迹 | `trajectories/all.openai.jsonl`，6 个完整 production，357 张 review 图；路径已匿名化，不能直接重放 | GitHub |
| 依赖 | Node 18+、Python 3、ffmpeg/ffprobe、Playwright+Chromium、numpy/scipy/soundfile/librosa、edge-tts、faster-whisper | requirements.txt |
| 官方定位 | 短视频/动效/讲解可视化；不做写实视频；长任务可达数小时/2000+ turns；官方承认视觉打磨与长程可靠性落后最强闭源模型 | README |

**关键判断**：Skill 本身不依赖 27B 模型或 SenseNova 专用 API；它是一套 Agent 工作流 + 脚本。官方默认用 27B 作为模型、Claude Code 作为 harness；用云端或现有本地模型替代 27B 在工程上可行，但**不是官方基准**，需要 POC 验证长上下文与工具调用质量。

---

## 2. 与 CourseWorkspace 的匹配与冲突

### 2.1 高价值、可直接吸收

1. **`SPEC.md` 先行**：分辨率、帧率、时长、帧数、固定文案、事实数值、素材、must-have。这正好补上我们 `storyboard.yaml` 对“镜头级视觉规格”的缺口。
2. **`frame(t)` 纯函数**：禁止 wall-clock timer、逐帧状态、未播种随机；与我们 `TimelineSpec` 的整数帧、可重建目标一致。
3. **Contact Sheet + `VERIFY.md`**：把“画面是否达标”变成可复查证据，而不是一句“已完成”。这可以直接接入我们的 `verify.py` / `build-report.json`。
4. **按镜头选渲染栈**：Canvas/SVG/Three.js/Remotion/Manim 的选型建议，可以补强我们的 `engine_router.py`。
5. **检查脚本**：`check_video.sh` 的黑帧/冻结帧/编码/音轨检查、`contact_sheet.sh` 的审看图，价值高、依赖低。
6. **Trajectories**：可以研究 Agent 如何拆镜头、选引擎、发现错误、返工；适合做课程动画 Agent 的参考案例。

### 2.2 不能直接照搬

| 项 | 冲突 | 处理 |
| --- | --- | --- |
| 27B 模型部署 | A750 8GB / 64GB 内存；BF16 54.7GB，需 4 路 TP；不适合本机 | **不部署**；POC 用云端/现有模型 |
| edge-tts | 需要访问 Microsoft 在线语音 | **不用**；音频继续走 VoxCPM2 |
| faster-whisper | 引入 ASR；PRD 明确不做 ASR | **不用**；字幕继续走“已知文本 + 实测音频段” |
| 长任务 512K / 2000 turns | 当前本地 32K/64K；云模型也需分片 | 按镜头切分，单次只做一个 shot |
| Agent 执行 shell / 写代码 | 安全边界 | 独立 sandbox 目录/容器；不挂 `lessons/`、不挂凭据、不碰 8080/50000 |
| 第五个动画引擎 | 会与 Remotion/Manim/Blender 重叠 | 定位为 **Skill / code_video profile**，不是新引擎 |
| 短视频定位 | 课程是 18–22 分钟 | 只做**镜头级**动画，最终仍由我们的 TimelineSpec/Remotion 合成 |

---

## 3. 三种接入方案

| 方案 | 内容 | 成本 | 风险 | 建议 |
| --- | --- | --- | --- | --- |
| **A. Skill-only（推荐先做）** | 把 `skills/code-video`、八类指南、检查脚本引入独立 POC 目录；用现有云端/本地模型按 Skill 工作流做一个 30–60s 镜头；音频/合成仍用我们的链路 | 低 | 低；不碰主链 | **P0/P1 先做** |
| **B. `code_video` 镜头适配器** | 在 `ShotSpec.engine` 增加 `code_video`，新增 adapter 调 `capture.mjs` 产出 `build/<slug>/animation/<shot>.mp4`；引擎路由增加 motion graphics / SVG / Three.js 类型 | 中 | 中；新增依赖与安全边界 | **A 通过后做 P1/P2** |
| **C. 部署 27B 原生模型** | vLLM/LightLLM/SGLang + 54.7GB 权重 | 高 | 高；硬件不匹配、运维成本 | **本轮不做** |

**最终架构建议**：

```text
CourseControl（唯一编排与契约）
  ├─ LessonSpec / ShotSpec / TimelineSpec / BuildReport
  ├─ engine_router
  │    ├─ Manim：数学/公式/二维结构
  │    ├─ Blender：三维/工程
  │    ├─ Remotion：编排/字幕/合成
  │    ├─ Motion Canvas：既有资产
  │    └─ code_video（Code2Video Skill）：motion graphics / SVG / Canvas / Three.js 镜头
  ├─ 音频：VoxCPM2 + 我们的字幕/时间轴
  └─ 交付：干净版 + ASS 烧录版
```

Code2Video **不做调度器**；CourseControl 仍是调度与验收的唯一入口。Skill 只负责“把一个镜头写成确定性代码并产出 MP4 + 证据”。

---

## 4. POC 计划（不打断 R1）

### P0：仓库与 Skill 拆解（1–2 天）

- 复制 `skills/code-video` 到 `CodeVideoStudio/`（保留 Apache 2.0 NOTICE）。
- 精读 `SKILL.md`、八类 `crafts/`、`capture.mjs`、`contact_sheet.sh`、`check_video.sh`。
- 抽样分析 `trajectories/all.openai.jsonl`：镜头拆分、引擎选择、失败修复、上下文压缩。
- 产出 `docs/评估-Code2Video-P0.md`：能力清单、可复用脚本、与我们的契约映射、不可用部分。

### P1：单镜头 Skill 验证（2–4 天）

- 选一个 **30–60 秒** 镜头：建议“GPU/CPU 架构数据流”或“Attention 计算流程的 SVG/Canvas 版”，不要一上来做整课。
- 用现有模型（DeepSeek/Claude）按 Skill 写 `SPEC.md` → 代码 → 渲染 → Contact Sheet → 修改 → `VERIFY.md`。
- 本地渲染：Playwright + Chromium + ffmpeg，输出 1920×1080/30fps H.264 yuv420p。
- 音频不用 edge-tts；保留静音或用我们已有的 VoxCPM2 片段做对齐测试。
- 产出：`out/final.mp4`、`SPEC.md`、`VERIFY.md`、Contact Sheet、源码、复现命令。

### P2：适配器与契约接入（3–5 天，P1 通过后）

- `ShotSpec.engine` 增加 `code_video`；`engine_profile` 取 `canvas2d|svg|three|remotion|manim`。
- 新增 `adapters/code_video.py`：校验 `SPEC.md`/`VERIFY.md`，调用 `capture.mjs`，ffprobe + `check_video.sh`，产出 `animation/<shot>.mp4`。
- `engine_router` 增加规则：motion graphics/kinetic type/SVG/Canvas/Three.js → `code_video`；数学仍 Manim；三维工程仍 Blender。
- 在 `lesson-smoke` 夹具或临时课程接入一个 `code_video` 镜头，跑通 collect→compose→verify。
- 产出：单镜头真实 MP4 + build-report 证据。

### P3（可选）：多镜头与质量/成本评估

- 同一 30–60s 镜头分别用 DeepSeek 与更强云模型做，比较：代码质量、返工次数、成片质量、总耗时、token 成本。
- 记录：Agent turns、渲染耗时、Contact Sheet 轮次、人工评分、确定性（同 SPEC 重跑帧哈希）。
- 决定是否把 `code_video` 纳入默认路由。

---

## 5. 验收指标

| 指标 | 目标 |
| --- | --- |
| 成片规格 | 1920×1080 / 30fps / H.264 / yuv420p / faststart |
| 确定性 | 同一 SPEC 重跑，关键帧哈希/画面一致（字体与 Chromium 版本固定） |
| 证据 | `SPEC.md` + `VERIFY.md` + Contact Sheet，全部 must-have 有 pass/fail |
| 画质 | 文字 ≥28px@1080p，关键主体可辨认，无黑帧/冻结帧 |
| 耗时 | 单 30–60s 镜头的 Agent + 渲染总耗时；与 Manim/Remotion 对比 |
| 成本 | token 成本 + 渲染成本；不采用“1/100”宣传结论 |
| 安全 | 不挂 `lessons/`、不挂凭据、不碰 8080/50000；sandbox 内执行 |

---

## 6. 风险与缓解

1. **Agent 生成代码不可控**：独立目录、只读输入、无凭据、容器/受限用户；代码先审后跑。
2. **上下文不足**：按镜头切分；每个 shot 一个 SPEC；不把整课塞入。
3. **依赖膨胀**：只用 Skill 的渲染/检查脚本；不用 edge-tts、faster-whisper；Playwright 已存在于 RemotionStudio，可复用。
4. **字体/Chromium 漂移**：固定版本；中文用 Noto Sans SC；Contact Sheet 抽帧复核。
5. **与现有引擎重复**：只在 motion graphics/SVG/Canvas/Three.js 场景使用；数学/三维仍走 Manim/Blender。
6. **许可证**：Apache 2.0，保留 NOTICE；不要把模型权重放入仓库。
7. **长任务可靠性**：官方承认落后最强闭源；POC 以人工审看为最终门。

---

## 7. 明确不做

- 不部署 27B 权重，不改现有 8080 模型。
- 不让 Code2Video 直接接管整课编排或最终合成。
- 不使用它的 edge-tts / faster-whisper 音频链路。
- 不把 Skill 当成“第五个动画引擎”并列维护四套适配器。
- 不在 R1 成片验收前改动主流水线。

---

## 8. 建议的决策

1. **现在**：只做 P0/P1（独立 POC），同时把 `SPEC.md` / `VERIFY.md` / Contact Sheet 的**验收思想**吸收进我们的镜头检查，不改主链。
2. **P1 通过后**：再做 P2 `code_video` 适配器；只接一个镜头，跑通 build。
3. **P2 通过后**：用数据决定是否进入默认路由；不通过则只保留工作流与检查脚本。

**一句话**：Code2Video 值得引入的是“确定性代码动画的生产方法与验收证据”，不是 27B 模型，也不是第五套动画系统。

---

## 9. P0/P1 执行结果（2026-11-07）

### 9.1 环境与模型

- **未部署 27B**；使用本机 Claude Code 2.1.317 + cc-switch 代理 + DeepSeek（实测 `claude -p` 返回 OK，代理日志 `DeepSeek-V4-flash` / 200）。
- 渲染：Playwright（RemotionStudio 已有 1.64.1 + Chromium）+ SwiftShader + ffmpeg 8.1。
- 依赖：未安装 edge-tts / faster-whisper；视觉 POC 不需要 Python 音频包。

### 9.2 Skill 拆解

- Sparse clone 只取 `skills/code-video` + README；未下载 54.7GB 权重。
- 8 类 `crafts/` 指南齐全；脚本包括 `capture.mjs`、`contact_sheet.sh`、`check_video.sh`、`audio_check.sh`、`sync_check.py`、`synth.py`、`tts.py`。
- `capture.mjs` 的页面契约：`window.READY` + `window.seek(t)`；Playwright 优先，Puppeteer 兜底；ffmpeg 编码 H.264/yuv420p。
- `check_video.sh` 检查分辨率、帧率、时长、编码、像素格式、音轨、黑帧/冻结帧。

### 9.3 P1 镜头

- `CodeVideoStudio/shots/attention-flow/`：30 s / 1920×1080 / 30 fps / 900 帧 / 无音频。
- 产物：`out/final.mp4`、`out/contact.jpg`、`out/frame-20/24/29.png`、`SPEC.md`、`VERIFY.md`。
- `check_video.sh` → **OK**；冻结警告为刻意停顿。
- 两次独立渲染 **900/900 帧哈希一致**。
- 发现并修复：token 行与分数面板重叠；`label()` 覆盖 `globalAlpha` 导致 summary/context 提前出现 ghost 文本。

### 9.4 本机适配问题

1. `contact_sheet.sh` 的 `drawtext` 在本机 ffmpeg 上触发 fontconfig 段错误；已用 `CodeVideoStudio/scripts/contact_sheet.py`（Pillow）替代。
2. Git Bash 无 `python3` 命令；已加 `CodeVideoStudio/bin/python3` shim 供 skill 脚本使用。
3. Playwright 通过项目 `node_modules` junction 复用 RemotionStudio 的安装，未新装浏览器。

### 9.5 下一步

- **P2**：给 `ShotSpec` 增加 `code_video` profile 与 adapter；把 `capture.mjs` 产物落到 `build/<slug>/animation/<shot>.mp4`；在夹具或临时课程跑通 collect→compose→verify。
- **P3**：同一镜头用 DeepSeek 与更强云模型对比代码质量、返工次数、成片质量、耗时与 token 成本。

### 9.6 P2 最小接入结果

- `ShotSpec.engine` / `lesson.engines` 增加 `code_video`；`LessonPaths.engine_root("code_video")` 指向 `CodeVideoStudio`。
- 新增 `adapters/code_video.py`：读 `SPEC.md`、要求 `VERIFY.md` 无 `| fail |`，调 `capture.mjs`，产物复制到 `build/<slug>/animation/<project>.mp4`，并 `probe_media`。
- `pipeline.py` 增加 `render:code_video` 阶段；`collect` 按项目目录名找动画；`engine_router` 支持 motion_graphics/SVG/Canvas/Three.js。
- 真实跑通：`build/code-video-poc/animation/attention-flow.mp4`，1920×1080 / 30fps / 900 帧 / 30s / h264/yuv420p。
- 测试：`test_code_video_adapter.py` 3 项 + `test_engine_router.py` 新增 3 项；后续加入 QC 门后 CourseControl 为 212 用例（210 通过 + 2 skip），见 `code_video_qc.py`。
- 未接入：Code2Video 不参与最终合成；它只产出镜头 MP4，仍由 TimelineSpec/Remotion 合成。
