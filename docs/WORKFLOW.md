# 当前真实工作流

- **依据**：`CourseControl`、`BlenderStudio`、`RemotionStudio`、`ModelingStudio`、`ContentQA`、`shared/ai_runtime` 的实际调用关系
- **上游**：[PRD.md](PRD.md)、[ARCHITECTURE.md](ARCHITECTURE.md)
- 图例：`[自动]` 程序执行；`[人工]` 必须有人参与；`[可选]` 按课程或需要启用

```text
[人工] 编写 lessons/<slug>/{lesson.yaml, storyboard.yaml, slides.md, lecture_notes.md, assets/}
   │
   ▼
[自动] validate                         V-01~V-09，失败即中止
   │
   ├─[自动] capture_slides             deck 模式：8081 + Playwright → slides/*.png
   │
   ├─[人工] Motion Canvas 导出         → build/<slug>/animation/<scene-stem>.mp4
   │    └─[自动] render:motion_canvas  校验文件存在 + ffprobe
   │
   ├─[自动][可选] render:manim         uv run manim --media_dir build/<slug>/tmp
   │
   ├─[自动][可选] render:blender (v1)  scripts/blender-render.ps1 → build/<slug>/blender/
   │
   ▼
[自动] collect                         页面预算 + 镜头 → build/<slug>/shots.json
   │
   ▼
[自动] compose                         staging → npx remotion render → final/course-video.mp4
   │
   ▼
[自动] verify                          V-10~V-22 → final/build-report.json

[独立][自动][可选] scene-run           IR v2 → Blender → 场景验收 → manifests/
[独立][自动][人工触发] modeling-studio 本地模型 → 脚本 → Blender → validation.json
[独立][自动][可选] content-qa review    在线模型 → build/<slug>/review/
```

---

> **AI 后端（2026-11-08 起）**：brief / outline / script / content、字幕翻译、ContentQA、ModelingStudio 文本规划与 Code2Video 镜头默认使用 Claude Code；文本阶段禁用工具，镜头阶段只写 `build/` 暂存目录。配置见 `config/claude-code.yaml`；不可用时显式 `blocked`，只有 `claude_code_fallback: local_first` 才回退本地/远程。

## 1. 课程输入与目录组织 `[人工]`

| 项 | 内容 |
| --- | --- |
| 输入 | `lessons/<slug>/`：`lesson.yaml`、`storyboard.yaml`、`slides.md`、`lecture_notes.md`、可选 `outline.md`、`assets/`、`subtitles.srt` |
| 输出 | 同一目录，只读给后续阶段 |
| 模块 | 无（作者维护） |
| 模型 | 无 |
| 失败 | 契约校验会指出缺失文件、页数不符、路径不合法 |
| 证据 | `course-control validate` |

`lesson.yaml` 声明 `engines`、`compose.mode`、`outputs`、`narration`、`subtitles`、`acceptance`；`storyboard.yaml` 声明镜头、切入秒点与可选二维标注（`annotations`，含文字与色标）。

---

## 2. 校验 `[自动]`

| 项 | 内容 |
| --- | --- |
| 输入 | `lesson.yaml`、`storyboard.yaml`、`slides.md`、`lecture_notes.md`、场景文件 |
| 输出 | 问题列表；失败即中止构建 |
| 模块 | `CourseControl/validators.py`、`paths.py` |
| 检查 | V-01~V-09：slug、必需文件、页数=块数、四要素、素材路径、禁用标记、镜头合法性、场景/任务存在、Motion 注册 |
| 失败 | 写入 `build-report.json` 的 validate 阶段与 failures，下游 `not_run` |
| 证据 | `check.ps1` 的 5 个 validate |

---

## 3. 幻灯片生产 `[自动]`

| 项 | 内容 |
| --- | --- |
| 输入 | `slides.md` + `assets/`，由 Reveal 页面加载 |
| 输出 | `build/<slug>/slides/slide-###.png` + `capture-manifest.json` |
| 模块 | `adapters/slides.py`；`CourseSlides/template/index.html`；`RemotionStudio/scripts/capture-slides.mjs` |
| 服务 | `live-server` 8081（复用已有实例）；Playwright Chrome/Edge |
| 模型 | 无 |
| 失败 | 页面加载失败、页数与笔记块数不一致 → `capture_slides=fail` 或 `collect` 失败 |
| 恢复 | 修复页面/授课稿后重跑；构建开始会清理旧 staging |
| 证据 | `01-shell-for-ai-era` 20/20 |

`compose.mode=recording` 的课程跳过截图，直接使用 `compose.base_video`。

---

## 4. 动画生产 `[人工] + [自动]`

| 项 | 内容 |
| --- | --- |
| Motion 输入 | `MotionStudio/src/scenes/<lesson>/<scene>.tsx` |
| Motion 输出 | 作者在编辑器导出到 `build/<slug>/animation/<scene-stem>.mp4` |
| 自动部分 | `adapters/motion_canvas.py` 只校验文件存在 + ffprobe；不执行导出 |
| Manim | `adapters/manim.py`：`uv run manim render --media_dir build/<slug>/tmp/manim-media`，复制到 `animation/` |
| 失败 | Motion 缺失：`skipped` + `manual_export_required`，verdict `incomplete`；导出无效：`fail` |
| 证据 | `lesson-manual` 夹具通过；真实课程如实 `incomplete` |

**这是正式的人工节点，不是待修缺陷。** 不允许用截图拼帧冒充导出。

---

## 5. Blender 三维生产

### 5.1 课程渲染任务（v1）

| 项 | 内容 |
| --- | --- |
| 输入 | `BlenderStudio/tasks/<lesson>/*.json`（schema 1）+ 可选 `.blend` |
| 输出 | `build/<lesson>/blender/*.mp4|png` |
| 模块 | `adapters/blender.py` → `scripts/blender-render.ps1` → `render_shot.py` |
| 模型 | 无 |
| 失败 | 退出码非 0、超时 124、输出缺失 → `render:blender=fail` |
| 证据 | `lesson-smoke` / `lesson-blender-only` pass |

### 5.2 场景任务 IR v2 `[独立] [自动]`

| 项 | 内容 |
| --- | --- |
| 输入 | `BlenderStudio/tasks/scene-system/*.json`（schema 2） |
| 输出 | PNG/MP4/`.blend` + `manifests/<task_id>.json` + 场景报告 |
| 模块 | `course-control scene-run` → `blender_runner.py` → `blender-render.ps1` → `scene_system/` → `verify_scene.py` |
| 校验 | Pydantic 与 Blender 内置校验器双端一致；`base_blend` 存在性属于执行前置条件 |
| 失败 | 校验、退出码、输出检查、场景报告任一失败即 `fail`，manifest 记录 |
| 证据 | `check-scene-system.ps1 -Render`：8 次真实渲染通过 |

---

## 6. 素材收集 `[自动]`

| 项 | 内容 |
| --- | --- |
| 输入 | 页面预算（`lecture_notes.md` 的“时长预算”）、`storyboard` 镜头、渲染产物、旁白、字幕 |
| 输出 | `build/<slug>/shots.json` |
| 模块 | `collect.py`、`utils.py`（ffprobe） |
| 规则 | overlay 必须落在页内且不重叠；路径相对 `build/<slug>/` |
| 失败 | 页数不符、源文件缺失、overlay 越界/重叠 → `collect=fail` |
| 模型 | 无 |

---

## 7. 视频合成 `[自动]`

| 项 | 内容 |
| --- | --- |
| 输入 | `shots.json` |
| 输出 | `build/<slug>/final/course-video.mp4` |
| 模块 | `adapters/remotion.py` → `stage-assets.mjs` → `npx remotion render` |
| 临时目录 | `RemotionStudio/public/staging/<slug>/`；成功清理，失败保留 |
| 模型 | 无 |
| 失败 | staging 或 Remotion 退出码非 0 → `compose=fail`，下游 `not_run` |
| 证据 | `lesson-smoke` / `lesson-blender-only` pass |

---

## 8. 构建验收 `[自动]`

| 项 | 内容 |
| --- | --- |
| 输入 | `shots.json`、最终视频、`lesson.yaml` |
| 输出 | `build/<slug>/final/build-report.json`（stages / checks / artifacts / verdict / failures） |
| 模块 | `verify.py`、`report.py` |
| 检查 | V-10~V-22：源文件、分辨率/帧率、时间线、成片时长、音画、字幕、报告一致性、产物边界、适用性、recording 时长、路径、二维标注 |
| verdict | `pass` / `fail` / `incomplete`；`skipped`、`not_run`、`not_applicable` 不算通过 |
| 模型 | 无 |

---

## 8.1 V1 兼容层 `[自动]`

| 项 | 内容 |
| --- | --- |
| 时间线 | `collect` 在写 `shots.json` 后，同时写 `build/<slug>/contracts/timeline.spec.json` |
| 证据 | `session-evidence-v1` 把现有 `evidence.json` 升级为 `EvidenceManifestV1` |
| 方向 | 旧文件仍是 Remotion / runner 的输入；V1 是只读规范化视图，不改变渲染行为 |
| 失败 | 素材缺失、帧率无法整数化、旁白超出时间线 → 明确失败，不静默降级 |

---

## 9. ContentQA 内容审查 `[独立] [可选]`

| 项 | 内容 |
| --- | --- |
| 输入 | `lessons/<slug>/slides.md`、`lecture_notes.md`、可选 `sources.yaml` |
| 输出 | `build/<slug>/review/review.json`、`review.md`、`raw/` |
| 模块 | `ContentQA/src/content_qa/` |
| 模型 | **在线模型**（OpenAI 兼容），凭据只读环境变量 |
| 拆分 | 按页/按段，逐任务预算（默认 16K） |
| 失败 | 无配置/无凭据 → `blocked`（exit 3）；非法 JSON/500/超时 → `failed` |
| 边界 | 只读课程；不影响构建 verdict；不降级到本地模型 |
| 证据 | mock 测试 11 项；真实课程 `blocked` |

---

## 10. 本地自动建模 `[独立] [人工触发]`

| 项 | 内容 |
| --- | --- |
| 输入 | 单张图片 + 可选尺寸说明 |
| 输出 | `workspace/jobs/<job>/`：`visual_analysis.json`、`model_plan.json`、`build_model.py`、`scene/model.blend|glb|fbx|preview.png`、`validation.json`、`tasks/` |
| 模块 | `ModelingStudio/` |
| 模型 | 本地 Qwen3-VL / Qwen3 / Qwen3-Coder，经 `shared/ai_runtime` 串行 |
| 人工 | 触发命令；审阅规划与结果 |
| 失败 | 阶段失败写入 `job.json` 与任务记录；`--resume` 跳过已完成阶段 |
| 证据 | 28 个测试；历史作业 `sample-001` |

---

## 11. AI Runtime `[贯穿]`

| 能力 | 实现 |
| --- | --- |
| 跨进程锁 | `runtime/locks/llama-8080.lock`，原子创建 + PID + 陈旧回收 |
| 服务生命周期 | 健康且别名匹配则复用；否则启动；只停止自己启动的实例 |
| 模型切换 | 阶段结束停止自有实例 → 端口释放 → 下一阶段启动新模型 |
| 远程回退 | 本地 8080 busy/启动失败/锁超时 → 按 `config/model-routing.yaml` 切远程；DeepSeek 固定 `deepseek-flash`，pro 禁用；任务记录写 `provider=remote` |
| 任务状态 | `runtime/tasks/<task_id>.json` + 作业内副本；失败/阻塞落盘 |
| 上下文预算 | 16K 默认 / 32K 复杂 / 64K 硬上限；每次请求前检查 |
| 证据 | 33 个 ai_runtime 测试（含远程回退与任务 provider） |

---

## 12. 用户入口

```powershell
# 1) 准备（首次）
.\scripts\setup.ps1

# 2) 写课程（本地，不入库）
#    lessons/<slug>/lesson.yaml、storyboard.yaml、slides.md、lecture_notes.md

# 3) 检查与构建
uv run --project CourseControl course-control validate --lesson <slug>
.\scripts\build-lesson.ps1 -Lesson <slug>

# 4) 人工导出 Motion Canvas（如课程使用）
#    编辑器导出到 build/<slug>/animation/<scene-stem>.mp4，然后重跑构建

# 5) 结果
#    build/<slug>/final/course-video.mp4
#    build/<slug>/final/build-report.json
```

**合格判定**：`build-report.json` 的 `verdict=pass`，且没有 `skipped` / `not_run` / `fail`。`incomplete` 表示还差人工步骤或渲染产物。

**真实状态**：两门真实课程目前都是 `incomplete`（Motion 未导出）；夹具 `lesson-smoke`、`lesson-blender-only` 为 `pass`。

---

## 13. R1 自动课程生产（2026-11-07）

```text
[人工] URL / Markdown / TXT
  → ingest → digest（来源 + 稳定引用）
  → brief → outline → script → content-draft（候选，写 build/<slug>/authoring/candidates/）
  → [人工] author-accept（sha256 批准，写 lessons/<slug>/）
  → narration-build（本地 VoxCPM2，整课或 --sample-pages 样片）
  → subtitles-build（实测音频；--planned 可先生成计划版草稿）
  → [人工] subtitles-accept
  → build（validate → 截图/动画 → collect → TimelineSpec 合成 → ASS 烧录 → verify）
```

| 阶段 | 命令 | 产物 |
| --- | --- | --- |
| 摄取 | `course-control ingest --lesson <slug> --source <url\|md\|txt>` | `lessons/<slug>/authoring/sources/`、`sources.yaml` |
| 摘要 | `course-control digest --lesson <slug>` | `authoring/source-digest.{json,md}` |
| 草稿 | `brief` / `outline` / `script` / `content-draft` | `build/<slug>/authoring/candidates/` |
| 批准 | `author-accept --kind digest\|brief\|outline\|script\|content` | `authoring/approval.json` |
| 整课旁白 | `narration-build --mode reference_only --timing measured` | `narration/narration.wav`、`narration.meta.json` |
| 样片 | `narration-build --sample-pages 3` | `narration/sample/sample.wav`、`sample.meta.json` |
| 字幕 | `subtitles-build [--planned] [--remote]` | `subtitles/bilingual.draft.{json,srt,vtt}` |
| 字幕批准 | `subtitles-accept` | `lessons/<slug>/subtitles.srt` |
| 构建 | `build-lesson.ps1` | `final/course-video.mp4` + `final/course-video-captioned.mp4` |

**边界**：`build`/`validate`/`check.ps1` 不调用 8080/50000/网络；TTS 与翻译是显式命令。本地模型默认优先；远程只在 `config/model-routing.yaml` 显式启用且 key 存在时回退，任务记录写 `provider`。`--remote` 是显式远程开关。

---

## 14. Code2Video 镜头（POC，2026-11-07）

```powershell
# 在 CodeVideoStudio 中准备 SPEC.md / index.html / main.js 后
node CodeVideoStudio/skills/code-video/scripts/capture.mjs `
  CodeVideoStudio/shots/<shot> --fps 30 --dur 30 --size 1920x1080 --out out/final.mp4
PATH="CodeVideoStudio/bin:$PATH" sh CodeVideoStudio/skills/code-video/scripts/check_video.sh `
  CodeVideoStudio/shots/<shot>/out/final.mp4 1920 1080 30 29.5 30.5 0
```

- 镜头契约：`SPEC.md` + `window.READY` + `window.seek(t)` + `VERIFY.md`；`frame(t)` 必须可重放。
- CourseControl 接入：`adapters/code_video.py`；`ShotSpec.engine=code_video`，`scene` 指向 `SPEC.md`。
- 输出：`build/<slug>/animation/<project>.mp4`，进入现有 collect/compose/verify。
- 音频仍走 VoxCPM2；不使用 edge-tts / faster-whisper。
- 生产目录：`CodeVideoStudio/shots/attention-flow/`（30s、900 帧、900/900 帧哈希一致）。

可选后端：`CodeVideoStudio/backends/hyperframes/hf-poc/`（HTML/GSAP，10s，check 通过）；`build/videozero-poc/`（Motion Canvas agent，image sequence + ffmpeg）。
