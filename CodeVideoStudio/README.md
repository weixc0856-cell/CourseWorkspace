# CodeVideoStudio


> **2026-11-11 状态**：V1 收敛完成；`check.ps1` exit 0，六套 647 用例（641 通过、6 跳过）。新增历史 / AI 时代基础 / 汽车空气动力学三个领域方案；统一英文成片与英上中下字幕；`build/` 为临时区、`deliver/` 为最终交付区。C-16 片头 DEFERRED。生产契约与验收见 [最终验收报告](../docs/stabilization/FINAL_ACCEPTANCE_REPORT.md)。
镜头级代码视频生产目录（R1 P2/P3）。

- **上游 Skill**：`skills/code-video/`，来自 [SenseNova-6.8-Code2Video](https://github.com/OpenSenseNova/SenseNova-6.8-Code2Video)，Apache 2.0（`LICENSE.code-video`）。该目录保留 Apache-2.0；仓库其余部分为 AGPL-3.0-or-later，见根目录 `LICENSE` / `NOTICE`。
- **不包含**：27B 模型权重。Agent 使用 Claude Code + cc-switch + DeepSeek；渲染在本地 Playwright/ffmpeg。
- **输出目录**：`out/` 只是手动镜头的本地缓存；课程构建用 `build/<slug>/tmp/code-video/`，旧的 `shots/<shot>/out/` 已归入 `build/_engine-cache/code-video/`；最终交付在 `deliver/<slug>/`。
- **Agent 配置**：默认 Claude Code（`config/claude-code.yaml`）。镜头阶段才开放 `Read/Write/Edit/Glob/Grep`，cwd 必须是 `CodeVideoStudio/shots/<shot>/` 或 `build/` 暂存目录；文本阶段用 `--tools=`。
- **不接管**：整课编排与最终合成。CourseControl 仍是唯一调度层；产物是镜头 MP4。

## three.js 与镜头副本（2026-11-10）

唯一 checked-in 副本是 `vendor/three/three.module.js`。镜头目录里的 `three.module.js` 由 `course-control vendor-sync`（或 `render:code_video`）在构建时复制，不提交。升级只改 vendor 一处，然后重捕获使用它的镜头。

```powershell
uv run --project CourseControl course-control vendor-sync
uv run --project CourseControl course-control vendor-check
```

## 目录

```text
CodeVideoStudio/
├── skills/code-video/        # SKILL.md、8 类 crafts、capture/check/contact 脚本
├── shots/
│   ├── attention-flow/       # 30s 验证镜头：SPEC.md、index.html、main.js、VERIFY.md
│   └── primer-rps/           # 30s 模拟镜头：Three.js + SimulationData，900 帧约 46 s
├── scripts/contact_sheet.py  # Windows/Pillow fallback（ffmpeg drawtext 会段错误）
├── bin/python3               # Git Bash shim（本机没有 python3 命令）
├── backends/hyperframes/
│   └── hf-poc/               # HyperFrames 10s POC（可选 HTML 后端，不替换 Remotion）
├── LICENSE.code-video
└── THIRD_PARTY_NOTICES.md
```

## 镜头契约

1. `SPEC.md`：分辨率、fps、时长、固定文案、事实、must-have。
2. 页面：`window.READY = true` + `window.seek(t)`；`t` 是唯一输入，禁止 wall-clock/未播种随机。
3. 渲染：`skills/code-video/scripts/capture.mjs`。
4. 检查：`check_video.sh` + Contact Sheet + `VERIFY.md`。
5. CourseControl：`ShotSpec.engine="code_video"`，`scene` 指向 `SPEC.md`；`adapters/code_video.py` 要求 `VERIFY.md` 无 `| fail |`。
6. `capture.json`（可选）：`{"gpu": true, "jpeg": true}` 让适配器给捕获追加 `--gpu` / `--jpeg`，未知键直接失败。默认仍是 SwiftShader + PNG（跨机器可复现）；开启 GPU 的镜头必须在 `VERIFY.md` 重新验证两次捕获一致。

## 复现 attention-flow

```powershell
cd CodeVideoStudio/shots/attention-flow
node ../../skills/code-video/scripts/capture.mjs . --fps 30 --dur 30 --size 1920x1080 --out out/final.mp4
PATH="../../bin:$PATH" sh ../../skills/code-video/scripts/check_video.sh out/final.mp4 1920 1080 30 29.5 30.5 0
uv run --project CourseControl python ../../scripts/contact_sheet.py out/final.mp4 out/contact.jpg --step 2 --cols 5 --thumb 384
```

`node_modules` 是指向 `RemotionStudio/node_modules` 的本地 junction，用于复用 Playwright；不要提交。

## 已验证

- 30s / 1920×1080 / 30fps / 900 帧；`check_video.sh` OK；两次独立渲染 900/900 帧哈希一致。
- `adapters/code_video.py` 真实跑通：`build/code-video-studio/animation/attention-flow.mp4`。
- `primer-rps`：ShotSpec `inputs.simulation_spec` → adapter 自动生成 `simulation.json` → 1920×1080/30s capture → QC PASS（`build/lesson-simulation/animation/primer-rps.mp4`）；导演层 `visual_kind: simulation` 可直接路由到该镜头。
- `primer-aging`：官方 r160 addons 后处理链（景深/泛光/调色/颗粒/暗角/FXAA）；`capture.json` 开启 GPU + JPEG 中间帧后 36 ms/帧（SwiftShader + PNG 为 777 ms/帧），同一帧与 PNG 路径成片对比 40.34 dB vs 40.56 dB，两次捕获 sha256 一致。
- HyperFrames POC：10s / 300 帧，`check` 0 error/0 warning，27.1s 渲染；仅作为可选 HTML/lint 后端。

## 外部项目边界

- **video-production-skill**：只吸收交付/QC/归档规范，不安装。
- **HyperFrames**：可选 HTML 渲染/lint 后端；不替换 Remotion 最终合成。
- **VideoZero**：Motion Canvas 图像序列自动导出候选（POC 在 `build/videozero-poc`，未并入主工程）。
- **27B**：不部署。
