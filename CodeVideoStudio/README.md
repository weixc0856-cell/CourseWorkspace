# CodeVideoStudio

镜头级代码视频生产目录（R1 P2/P3）。

- **上游 Skill**：`skills/code-video/`，来自 [SenseNova-6.8-Code2Video](https://github.com/OpenSenseNova/SenseNova-6.8-Code2Video)，Apache 2.0（`LICENSE.code-video`）。
- **不包含**：27B 模型权重。Agent 使用 Claude Code + cc-switch + DeepSeek；渲染在本地 Playwright/ffmpeg。
- **Agent 配置**：默认 Claude Code（`config/claude-code.yaml`）。镜头阶段才开放 `Read/Write/Edit/Glob/Grep`，cwd 必须是 `CodeVideoStudio/shots/<shot>/` 或 `build/` 暂存目录；文本阶段用 `--tools=`。
- **不接管**：整课编排与最终合成。CourseControl 仍是唯一调度层；产物是镜头 MP4。

## 目录

```text
CodeVideoStudio/
├── skills/code-video/        # SKILL.md、8 类 crafts、capture/check/contact 脚本
├── shots/
│   └── attention-flow/       # 30s 验证镜头：SPEC.md、index.html、main.js、VERIFY.md
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
- HyperFrames POC：10s / 300 帧，`check` 0 error/0 warning，27.1s 渲染；仅作为可选 HTML/lint 后端。

## 外部项目边界

- **video-production-skill**：只吸收交付/QC/归档规范，不安装。
- **HyperFrames**：可选 HTML 渲染/lint 后端；不替换 Remotion 最终合成。
- **VideoZero**：Motion Canvas 图像序列自动导出候选（POC 在 `build/videozero-poc`，未并入主工程）。
- **27B**：不部署。
