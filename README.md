# CourseWorkspace 课程生产工作区

把人工撰写的课程内容转换成带动画与三维场景的成片视频，并在每一步留下可核验的证据。

- **唯一产品基线**：[docs/PRD.md](docs/PRD.md)
- **架构与契约**：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **验收与命令**：[docs/ACCEPTANCE.md](docs/ACCEPTANCE.md)
- **决策记录**：[docs/DECISIONS.md](docs/DECISIONS.md)
- **实现状态**：[docs/TRACEABILITY.md](docs/TRACEABILITY.md)
- **Claude Code 入口**：[CLAUDE.md](CLAUDE.md)

## 仓库范围（远程 vs 本地）

远程仓库（`git@github.com:weixc0856-cell/CourseWorkspace.git`）**只包含项目开发工作流**：代码、契约、Schema、夹具、脚本、文档与测试。

| 内容 | 是否进远程 | 说明 |
| --- | --- | --- |
| `CourseControl/`、`CourseSlides/`、`MotionStudio/`、`ManimSandbox/`、`BlenderStudio/`、`RemotionStudio/` | 是 | 工作流与渲染入口 |
| `ModelingStudio/`、`ContentQA/`、`shared/` | 是 | 内部能力与运行时 |
| `scripts/`、`config/*.example.yaml`、`docs/` | 是 | 入口、模板与指导 |
| `lessons/` 真实课程 | **否** | 本地内容，仓库只保留 `lessons/README.md` |
| `build/`、`runtime/`、`ModelingStudio/workspace/` | 否 | 生成物与运行态 |
| 模型权重、视频、音频、`*.blend1` | 否 | 大文件与媒体 |
| `config/tools.yaml`、`config/local-paths.yaml`、`config/content-qa.yaml`、`ModelingStudio/config/workflow.yaml` | 否 | 本机路径与凭据 |

克隆后是一个**没有课程内容**的工作流仓库：先按 [lessons/README.md](lessons/README.md) 在本地创建课程，再运行 `scripts/setup.ps1` 生成本机配置。

## 生产闭环

```text
lessons/<slug>/                        课程契约：slides.md、lecture_notes.md、lesson.yaml、storyboard.yaml
        │
        ▼
CourseControl validate                 契约与路径检查（V-01~V-09）
        │
        ├─ capture_slides    → build/<slug>/slides/           Reveal 逐页截图 + manifest
        ├─ render:*          → build/<slug>/animation|blender  动画与三维成片
        ▼
collect                                → build/<slug>/shots.json
        │
        ▼
compose（staging + Remotion）           → build/<slug>/final/course-video.mp4
        │
        ▼
verify                                 → build/<slug>/final/build-report.json（V-10~V-21）
```

人工节点是正式设计：Motion Canvas 没有 CLI 导出，作者必须在编辑器导出到 `build/<slug>/animation/<scene-stem>.mp4`；未导出时构建结论是 `incomplete`，不是通过。

## 工程分工

| 目录 | 职责 | 产物 | 是否主流程 |
| --- | --- | --- | --- |
| `lessons/` | 课程唯一入口 | 双文件内容 + 契约 | 是 |
| `CourseControl/` | 校验、调度、收集、报告 | `shots.json`、`build-report.json` | 是 |
| `CourseSlides/` | Reveal 6 外壳 | 浏览器页面 | 是 |
| `MotionStudio/` | 结构动画（人工导出） | `animation/<stem>.mp4` | 是（人工） |
| `ManimSandbox/` | 数学动画备选 | `animation/*.mp4` | 否 |
| `BlenderStudio/` | 课程渲染任务（v1）+ 场景系统（v2） | `blender/*.png|mp4|blend` | 是（可选引擎） |
| `RemotionStudio/` | 截图、staging、合成 | `final/course-video.mp4` | 是 |
| `ModelingStudio/` | 图片 → Blender 模型 | `workspace/jobs/<job>/` | 否（内部能力） |
| `ContentQA/` | 在线模型内容审查 | `build/<slug>/review/` | 否（内部能力） |
| `shared/ai_runtime/` | 跨进程锁、服务生命周期、任务记录、上下文预算 | `runtime/` | 支撑 |
| `shared/schemas/` | JSON Schema | — | 支撑 |
| `config/`、`scripts/` | 本机配置与工作区入口 | — | 支撑 |
| `docs/` | 权威文档；`docs/archive/` 为历史 | — | — |

## 快速开始

```powershell
.\scripts\setup.ps1                       # 首次：生成 config/tools.yaml、安装依赖
.\scripts\check.ps1                       # 全量回归，必须打印 check ok（干净克隆会跳过真实课程校验）

# 只校验课程契约
uv run --project CourseControl course-control validate --lesson 01-shell-for-ai-era

# 完整构建
.\scripts\build-lesson.ps1 -Lesson 01-shell-for-ai-era

# 三维场景任务（IR v2）
uv run --project CourseControl course-control scene-validate `
  --task BlenderStudio/tasks/scene-system/demo-scene.json
uv run --project CourseControl course-control scene-run `
  --task BlenderStudio/tasks/scene-system/demo-scene.json

# 本地自动建模
uv run --project ModelingStudio modeling-studio run --image tests/fixtures/sample-assembly.png

# 在线内容审查（未配置凭据时返回 blocked，退出码 3）
uv run --project ContentQA content-qa review --lesson 01-shell-for-ai-era
```

## 端口

| 服务 | 端口 | 约束 |
| --- | --- | --- |
| 本地模型（llama.cpp） | 8080 | 唯一实例；所有调用经 `shared/ai_runtime` 排队 |
| 课件预览 / 截图 | 8081 | `live-server`，截图复用现有实例 |
| Motion Canvas 编辑器 | 5173 | 人工导出 |
| Remotion Studio | 3000 | 预览 |
| CosyVoice（外部） | 50000 | 同一时刻一个模式 |

没有 8082 备用端口。

## 边界

- 课程正文归作者所有；自动化只做格式与路径处理。
- 本地模型严格串行：跨进程锁 + 单一 8080 服务；谁启动谁停止。
- 在线模型只产出候选意见；无凭据时 `blocked`，不降级冒充。
- 所有 AI 输出都要经程序校验；最终事实判断由人工与来源证据负责。
- 不在 `<AI_ROOT>` 写入、迁移或删除任何内容。

## 文档

- 内容规范：[课件制作总指导](docs/课件制作总指导.md) · [课程交付清单模板](docs/课程交付清单模板.md)
- 运行时：[本地模型与配音工作流](docs/本地模型与配音工作流.md) · [AI-Blender 本地建模工作流](docs/AI-Blender本地建模工作流.md)
- 三维契约：[Blender 场景任务 IR v2](docs/Blender场景任务IR-v2.md)
- 流程：[提交前检查清单](docs/提交前检查清单.md)
- 当前状态：[项目状态与 PRD 盘点](docs/PROJECT_STATUS.md) · [真实工作流](docs/WORKFLOW.md)
- 产品决策：[前端必要性评估](docs/FRONTEND_ASSESSMENT.md)
- 历史：[docs/archive/](docs/archive/README.md)
