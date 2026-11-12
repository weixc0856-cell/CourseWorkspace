# CourseWorkspace 课程生产工作区


> **2026-11-11 状态**：V1 收敛完成；`check.ps1` exit 0，六套 647 用例（641 通过、6 跳过）。新增历史 / AI 时代基础 / 汽车空气动力学三个知识板块（本机开发，不入库）；统一英文成片与英上中下字幕；`build/` 为临时区、`deliver/` 为最终交付区。C-16 片头 DEFERRED。生产契约与验收见 [最终验收报告](docs/stabilization/FINAL_ACCEPTANCE_REPORT.md)。
把人工撰写的课程内容转换成带动画与三维场景的成片视频，并在每一步留下可核验的证据。

- **文档索引**：[docs/README.md](docs/README.md)
- **唯一产品基线**：[docs/PRD.md](docs/PRD.md)
- **架构与契约**：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **验收与命令**：[docs/ACCEPTANCE.md](docs/ACCEPTANCE.md)
- **决策记录**：[docs/DECISIONS.md](docs/DECISIONS.md)
- **需求映射**：[docs/TRACEABILITY.md](docs/TRACEABILITY.md)
- **Claude Code 入口**：[CLAUDE.md](CLAUDE.md)
- **CI**：`.github/workflows/check.yml`（Windows，运行 `scripts/check.ps1`）
- **质量基准**：[docs/知识视频质量基准.md](docs/知识视频质量基准.md)
- **资料采集**：[docs/资料采集与预处理.md](docs/资料采集与预处理.md)

## 知识板块

领域方案属于实际课程开发内容，只在本机，不入库：

- 历史：`<内容根>/projects/history/历史系列-生产方向.md`
- AI 时代基础知识：`<内容根>/projects/ai-era-fundamentals/AI时代基础知识-生产方向.md`
- 汽车空气动力学：`<内容根>/projects/automotive-aerodynamics/汽车空气动力学-生产方向.md`
- 经济学：`<内容根>/projects/economics/经济学系列-第一季生产方案.md`

具体课程方案、教材页映射、图片账本、讲稿与素材也留在本机 `runtime/`；远程仓库只保留生产系统、总纲与索引。

## 仓库范围（远程 vs 本地）

远程仓库（`git@github.com:<OWNER>/CourseWorkspace.git`）**只包含项目开发工作流**：代码、契约、Schema、夹具、脚本、文档与测试。

| 内容 | 是否进远程 | 说明 |
| --- | --- | --- |
| `CourseControl/`、`CourseSlides/`、`MotionStudio/`、`ManimSandbox/`、`BlenderStudio/`、`RemotionStudio/` | 是 | 工作流与渲染入口 |
| `ModelingStudio/`、`ContentQA/`、`CourseDemo/`、`KnowledgeStudio/`、`shared/` | 是 | 内部能力、会话录制与运行时 |
| `ScientificFigures/` | 是 | SymPy/LaTeX + Matplotlib/SciencePlots 科学图表 POC；`output/` 忽略 |
| `index.html` | 是 | 根入口：把 `/?lesson=<slug>` 重定向到 Reveal 外壳 |
| `CodeVideoStudio/` | 是 | Code2Video Skill（Apache 2.0）与镜头 POC；不含 27B 权重 |
| `scripts/`、`config/*.example.yaml`、`docs/` | 是 | 入口、模板与指导 |
| `<内容根>/lessons/` 真实课程 | **否** | 本地内容，仓库只保留 `lessons/README.md` |
| `<内容根>/build/`、`deliver/`、`runtime/`、`knowledge/`；`ModelingStudio/workspace/` | 否 | 临时构建、最终交付、运行态与本地资料；`deliver/` 不随 `build/` 清理 |
| 模型权重、视频、音频、`*.blend1` | 否 | 大文件与媒体 |
| `config/tools.yaml`、`config/local-paths.yaml`、`config/content-qa.yaml`、`ModelingStudio/config/workflow.yaml` | 否 | 本机路径与凭据 |

克隆后是一个**没有课程内容**的工作流仓库：先按 [lessons/README.md](lessons/README.md) 在本地创建课程，再运行 `scripts/setup.ps1` 生成本机配置。

课程内容不在仓库里：`lessons/`、`build/`、`deliver/`、`runtime/`、`knowledge/` 与 `engines/` 都相对**内容根**（见 `config/local-paths.yaml` 的 `content_root`，默认等于工作区；`course-control content-root` 可查询）。2026-11-12 起本机内容根在工作区外，仓库只剩程序、共用模块与夹具。下文路径除特别说明外都相对内容根。

## 生产闭环

```text
lessons/<slug>/                        课程契约：slides.md、lecture_notes.md、lesson.yaml、storyboard.yaml
        │
        ▼
CourseControl validate                 契约与路径检查（V-01~V-09）
        │
        ├─ capture_slides    → build/<slug>/slides/           Reveal 逐页截图 + manifest
        ├─ render:*          → build/<slug>/animation|blender  动画与三维成片
        ├─ render:code_video → build/<slug>/animation/<project>.mp4  Code2Video 镜头
        ▼
collect                                → build/<slug>/shots.json
        │
        ▼
compose（staging + Remotion）           → build/<slug>/final/course-video.mp4
        │
        ▼
verify                                 → build/<slug>/final/build-report.json（V-10~V-22）
        │
        ▼
package                                → deliver/<slug>/（唯一最终交付包）
```

Motion Canvas 已是自动节点：`MotionStudio/scripts/render-headless.mjs` 通过 core `Renderer`、帧接收器和 ffmpeg 直接产出 `build/<slug>/animation/<scene-stem>.mp4`；adapter 重试并 ffprobe，失败即 `fail`，不写 `skipped`。

## 内容形态与音频

- **科普视频**（单篇论文讲解、技术拆解）：允许低音量 BGM；默认 Serenity / Schubert，高潮段可短暂使用 We Never；
- **正式课程**（书章节、MIT/Stanford/高校或机构课程解读、二次录制）：不使用 BGM，旁白 + 静默为准；
- **新闻/资讯**：不使用 BGM。

详见 [内容类型与音频策略](docs/内容类型与音频策略.md)；曲目、许可与试听见 [音乐资产盘点](docs/音乐资产盘点.md)。

**语言**：所有视频英文画面与旁白；字幕英文在上、中文在下。中文只做字幕与文章版本，默认不做中文配音（D-084）。

## 工程分工

| 目录 | 职责 | 产物 | 是否主流程 |
| --- | --- | --- | --- |
| `<内容根>/lessons/` | 课程唯一入口 | 双文件内容 + 契约 | 是 |
| `CourseControl/` | 校验、调度、收集、报告；含 `director/` 与 `producer/` | `shots.json`、`build-report.json`、导演计划、制片清单、`deliver/<slug>/` 交付包 | 是 |
| `CourseSlides/` | Reveal 6 外壳 | 浏览器页面 | 是 |
| `MotionStudio/` | 结构动画（无头自动导出） | `animation/<stem>.mp4` | 是 |
| `ManimSandbox/` | 数学动画备选 | `animation/*.mp4` | 否 |
| `CodeVideoStudio/` | Code2Video Skill：动效/HTML/SVG 镜头 | `animation/<project>.mp4` + `VERIFY.md` | 是（镜头级） |
| `BlenderStudio/` | 课程渲染任务（v1）+ 场景系统（v2） | `blender/*.png|mp4|blend` | 是（可选引擎） |
| `RemotionStudio/` | 截图、staging、合成 | `build/<slug>/final/course-video.mp4`（临时）+ `deliver/<slug>/`（交付包） | 是 |
| `ModelingStudio/` | 图片 → Blender 模型 | `workspace/jobs/<job>/` | 否（内部能力） |
| `ScientificFigures/` | 科学图表 POC：SymPy/Matplotlib/SciencePlots | `ScientificFigures/output/*.svg|pdf|png`（忽略） | 否（POC/按需） |
| `index.html` | 根入口重定向到 `CourseSlides/template/` | 浏览器入口 | 支撑 |
| `ContentQA/` | 内容审查（默认 Claude Code，API 可选） | `build/<slug>/review/` | 否（内部能力） |
| `KnowledgeStudio/` | 教材拆页、目录校准、按页检索与引用 | `knowledge/` 与 Docling 资料区（本地，不入库） | 否（内部能力） |
| `CourseDemo/` | VS Code 会话驱动扩展 | `vscode-result.json` | 否（内部能力） |
| `shared/ai_runtime/` | 跨进程锁、服务生命周期、任务记录、上下文预算 | `runtime/` | 支撑 |
| `shared/scene_expr/` | 受限表达式：AST 白名单 + 解释器 | — | 支撑 |
| `shared/schemas/` | JSON Schema | — | 支撑 |
| `config/`、`scripts/` | 本机配置与工作区入口 | — | 支撑 |
| `docs/` | 权威文档；`<内容根>/archive/` 为历史 | — | — |

## 快速开始

本地预览入口：`http://localhost:8081/?lesson=<slug>`；根目录 `index.html` 会重定向到 `CourseSlides/template/`。

```powershell
.\scripts\setup.ps1                       # 首次：生成 config/tools.yaml、安装依赖
.\scripts\check.ps1                       # 全量回归，必须打印 check ok（干净克隆会跳过真实课程校验）

# 只校验课程契约
uv run --project CourseControl course-control validate --lesson 01-shell-for-ai-era
uv run --project CourseControl course-control director-plan --lesson 01-transformer-demo
uv run --project CourseControl course-control producer-run --lesson 01-transformer-demo
uv run --project CourseControl course-control producer-rebuild --lesson 01-transformer-demo
uv run --project CourseControl course-control audio-plan --lesson 01-transformer-demo
uv run --project CourseControl course-control layout-templates
uv run --project CourseControl course-control layout-validate --template process_flow
uv run --project CourseControl course-control simulation-run `
  --spec BlenderStudio/scenes/primer-poc/simulation.spec.json `
  --out build/primer-poc/simulation.json

# 配置解析 / 恢复 / 统计 / 字幕 QC / 交付包
uv run --project CourseControl course-control config-resolve --lesson 01-shell-for-ai-era
uv run --project CourseControl course-control build --lesson 01-shell-for-ai-era --resume
uv run --project CourseControl course-control stats --lesson 01-shell-for-ai-era
uv run --project CourseControl course-control subtitles-qc --lesson 01-shell-for-ai-era
uv run --project CourseControl course-control package --lesson 01-shell-for-ai-era
uv run --project CourseControl course-control package-verify --package deliver/01-shell-for-ai-era

# 完整构建
.\scripts\build-lesson.ps1 -Lesson 01-shell-for-ai-era

# 代码/终端会话（E1；需要 Docker）
.\scripts\check-session.ps1

# VS Code 会话（E2；真实窗口 + shell integration）
.\scripts\check-vscode-session.ps1

# Python 工具链（E3；venv + 离线验证）
.\scripts\check-python-session.ps1

# Python 工具链（E3；本地 HTTP 索引网络安装）
.\scripts\check-python-network.ps1

# Rust 镜头（E4；host VS Code + Git Bash）
.\scripts\check-rust-session.ps1

# Manim 基线（E5 FFT / E6 Transformer）
uv run --project ManimSandbox manim render -r 1920,1080 --fps 30 `
  --media_dir build/manim-fft/media ManimSandbox/02-fft-baseline/fft_baseline.py FFTBaseline
uv run --project ManimSandbox manim render -r 1920,1080 --fps 30 `
  --media_dir build/manim-transformer/explainer/media ManimSandbox/04-transformer-explainer/transformer_explainer.py TokensScene

# 三维场景任务（IR v2）
uv run --project CourseControl course-control scene-validate `
  --task BlenderStudio/tasks/scene-system/demo-scene.json
uv run --project CourseControl course-control scene-run `
  --task BlenderStudio/tasks/scene-system/demo-scene.json

# 本地自动建模
uv run --project ModelingStudio modeling-studio run --image tests/fixtures/sample-assembly.png

# 科学图表 POC
uv run --project ScientificFigures python ScientificFigures/figures/continuity_figure.py

# 内容审查（默认 Claude Code；不可用或 API 无凭据时 blocked，退出码 3）
uv run --project ContentQA content-qa review --lesson 01-shell-for-ai-era
```

## 端口

| 服务 | 端口 | 约束 |
| --- | --- | --- |
| 本地模型（llama.cpp） | 8080 | 唯一实例；所有调用经 `shared/ai_runtime` 排队 |
| 课件预览 / 截图 | 8081 | `live-server`，截图复用现有实例 |
| Motion Canvas 编辑器 | 5173 | 制作/预览 |
| Motion Canvas 无头导出 | 4173 / 4174 | Vite + 帧接收器；仅构建时占用 |
| Remotion Studio | 3000 | 预览 |
| VoxCPM2 TTS（外部） | 50000 | 唯一实例；谁启动谁停止 |

没有 8082 备用端口。

## AI 后端：Claude Code 默认，本地/远程回退

- **课程文本生产（brief/outline/script/content）、字幕翻译、ContentQA、ModelingStudio 文本规划与 Code2Video 镜头默认走 Claude Code。** 配置见 `config/claude-code.yaml`（示例：`config/claude-code.example.yaml`）；文本阶段禁用工具，镜头 Agent 阶段只写 `build/` 暂存目录。
- 本地 8080 仍由 `shared/ai_runtime` 持有跨进程锁，同一时刻只允许一个本地任务；它现在是显式回退/视觉阶段后端，不再是默认文本生成路径。
- 8080 被占用或本地启动失败时，可按 `config/model-routing.yaml` 回退到远程 OpenAI 兼容 API。`provider` 可为 `deepseek`、`openai-compatible` 或其他兼容实现；参考文件：`config/model-routing.example.yaml`。
- 当前本机用 DeepSeek：`deepseek-flash` 支持图像理解，视觉阶段也可回退（2026-11-07 实测）。**所有 DeepSeek 调用固定 `deepseek-flash`，`deepseek-v4-pro` 已禁用，配置层会拒绝。**
- API key 只从系统环境变量读取（本机已有 `DeepSeek-API`），**不要写进 `.env`、YAML、日志或任何文件**。
- **`.env` 是本地实际配置（git 忽略）；`.env.example` 进远程，只含占位符与配置说明。** 通用变量为 `REMOTE_PROVIDER` / `REMOTE_BASE_URL` / `REMOTE_MODEL` / `REMOTE_VISION_MODEL` / `REMOTE_API_KEY_ENV`；DeepSeek 也可用 `DEEPSEEK_*` 别名。任何文件都不得出现明文 API key。
- 任务记录新增 `provider`（`local` / `remote` / `claude_code`）与实际模型名；任何后端都不会冒充另一个后端。视觉阶段只有在配置 `vision_model` 时才回退。
- 本机路径只允许出现在被忽略的 `config/*.yaml`、`.env`、`ModelingStudio/config/workflow.yaml`；跟踪文件由 `scripts/check-paths.ps1` 检查。

```powershell
Copy-Item config/model-routing.example.yaml config/model-routing.yaml
Copy-Item config/claude-code.example.yaml config/claude-code.yaml
# 然后把 api_key_env 改成你实际使用的环境变量名
```

## License

- 本仓库代码采用 **AGPL-3.0-or-later**，全文见 [LICENSE](LICENSE)。
- **商业双许可**：如要在闭源产品或商业服务中内嵌本仓库代码、且不愿承担 AGPL 的源码公开义务，需向仓库所有者取得单独的商业授权。
- 第三方组件保留原许可：CodeVideoStudio Skill 为 Apache-2.0，Three.js 为 MIT，Noto Sans SC 为 OFL，HyperFrames 为 ISC；完整清单见 [NOTICE](NOTICE)。这些组件不会被重新标为 AGPL。
- `lessons/` 课程正文、`build/` 成片与仓库外音频/模型资产不在 AGPL 范围内，除非文件另有声明。
- 贡献前需按 [CONTRIBUTING.md](CONTRIBUTING.md) 完成 CLA；这是维持双许可的前提。

## 边界

- 课程正文归作者所有；自动化只做格式与路径处理。
- 本地模型严格串行：跨进程锁 + 单一 8080 服务；谁启动谁停止。
- 内容审查只产出候选意见；Claude Code 不可用或 API 无凭据时 `blocked`，不降级冒充。
- 所有 AI 输出都要经程序校验；最终事实判断由人工与来源证据负责。
- 不在 `<AI_ROOT>` 写入、迁移或删除任何内容。

## 文档

- 内容规范：[课件制作总指导](docs/课件制作总指导.md) · [课程交付清单模板](docs/课程交付清单模板.md)
- 运行时：[本地模型与配音工作流](docs/本地模型与配音工作流.md) · [AI-Blender 本地建模工作流](docs/AI-Blender本地建模工作流.md)
- 三维契约：[Blender 场景任务 IR v2](docs/Blender场景任务IR-v2.md)
- 流程：[提交前检查清单](docs/提交前检查清单.md)
- 当前状态：[项目状态与 PRD 盘点](docs/PROJECT_STATUS.md) · [真实工作流](docs/WORKFLOW.md)
- 导演/制片：[导演层](docs/导演层.md) · [制片层](docs/制片层.md)
- 版式/配色/运镜：[版式系统](docs/版式系统.md) · [配色规范](docs/配色规范.md) · [运镜与剪辑](docs/运镜与剪辑.md)
- 历史归档与项目材料在内容根下：`<内容根>/archive/`、`<内容根>/projects/<系列>/`（不入库）
