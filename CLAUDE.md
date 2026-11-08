# CourseWorkspace — 项目指导（Claude Code 入口）

本文件是所有开发任务的入口。**具体规则只在 `docs/` 的权威文件中定义，本文件只做索引与硬约束摘要**，不得在此复制 PRD 或架构细节。

## 1. 项目是什么

课程生产工作区：把人工撰写的课程内容（幻灯片 + 讲师手册）通过确定性流水线产出成片视频，并提供三维场景与本地 AI 建模作为**内部生产能力**。

- 主产品：`lessons/` → 校验 → 截图/动画/三维渲染 → 时间线 → Remotion 合成 → 验收。
- 三维能力（`BlenderStudio` IR v2、`ModelingStudio`）服务于课程内容，不是与课程并列的第二产品。
- 唯一产品基线：[docs/PRD.md](docs/PRD.md)
- 系统结构与数据契约：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 验收与命令：[docs/ACCEPTANCE.md](docs/ACCEPTANCE.md)
- 决策记录：[docs/DECISIONS.md](docs/DECISIONS.md)
- 当前状态与 PRD 盘点：[docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md)
- 真实工作流：[docs/WORKFLOW.md](docs/WORKFLOW.md)
- 需求—模块—测试映射：[docs/TRACEABILITY.md](docs/TRACEABILITY.md)
- 前端评估：[docs/FRONTEND_ASSESSMENT.md](docs/FRONTEND_ASSESSMENT.md)
- 统一契约 V1：[docs/课程生产统一契约V1.md](docs/课程生产统一契约V1.md)
- E6.5 成片：[docs/E6.5-成片报告.md](docs/E6.5-成片报告.md)
- 技术雷达与外部项目评估：[docs/技术雷达-视频生产.md](docs/技术雷达-视频生产.md)、[docs/评估-Code2Video接入.md](docs/评估-Code2Video接入.md)、[docs/评估-DeepSeek Harness.md](docs/评估-DeepSeek%20Harness.md)、[docs/评估-四后端对比.md](docs/评估-四后端对比.md)
- 课程复刻差距与视觉规范：[docs/课程复刻差距与稳定工作流.md](docs/课程复刻差距与稳定工作流.md)、[docs/课程视觉风格指南.md](docs/课程视觉风格指南.md)
- 公式排版与 Formula Pipeline：[docs/公式排版规范.md](docs/公式排版规范.md)
- 科学计算/绘图接入：[docs/科学图形与图表接入评估.md](docs/科学图形与图表接入评估.md)
- 动画视觉导演规范：[docs/动画视觉导演规范.md](docs/动画视觉导演规范.md)
- 导演层（章节/镜头/引擎/旁白/校验）：[docs/导演层.md](docs/导演层.md)
- 制片层（订单/授权/交付包/增量）：[docs/制片层.md](docs/制片层.md)
- 版式系统（设计 token/模板/校验）：[docs/版式系统.md](docs/版式系统.md)
- Attention 两分钟样片与 3B1B 差距：[docs/样片-注意力-3B1B差距与路线.md](docs/样片-注意力-3B1B差距与路线.md)
- 动画/音频/口播整合：[docs/评估-动画音频口播-整合.md](docs/评估-动画音频口播-整合.md)
- 交付物/QC/归档：[docs/课程生产交付物规范.md](docs/课程生产交付物规范.md)
- 代码视频镜头：[CodeVideoStudio/README.md](CodeVideoStudio/README.md)

## 2. 不可突破的硬约束

1. **内容归用户所有。** `slides.md`、`lecture_notes.md`、`outline.md`、课程 `assets/` 的正文只允许格式级调整（路径、分页、主题类名）；改语义必须先问。
2. **skip ≠ pass。** 未执行的阶段不得写成通过；人工导出缺失、凭据缺失、模型不可用都必须如实记录。
3. **本地模型严格串行。** 任何本地模型调用必须经过 `shared/ai_runtime` 的跨进程锁；同一时刻 8080 只允许一个推理任务；谁启动谁停止。
4. **AI 输出不等于已完成。** LLM 生成的结构化计划、脚本、审查意见都是候选结果，必须经程序校验；最终事实判断由人工与来源证据负责。
5. **上下文硬上限 64K。** 默认 8K–16K；复杂任务 16K–32K；禁止把整份课程/历史对话塞进一次请求。
6. **工程隔离。** 不全局安装依赖、不改系统 PATH、不写入 `<AI_ROOT>`；产物只写 `build/<slug>/` 与各工程自己的运行时目录。
7. **不伪造验收。** 不能为了通过而修改测试预期、跳过检查或补写内容。
8. **远程仓库只放工作流。** `lessons/` 真实课程、`build/`、`runtime/`、模型权重与媒体文件不入库；远程仓库必须保持可克隆、可测试、无课程内容。
9. **Claude Code 默认后端。** 课程文本生产（brief/outline/script/content）、字幕翻译、ContentQA 与 ModelingStudio 文本规划默认走 Claude Code；文本阶段必须禁用工具（`--tools=`），镜头 Agent 阶段只允许写 `build/` 暂存目录。不可用即 `blocked`；只有 `claude_code_fallback: local_first` 才可回退本地/远程，禁止静默降级。
10. **远程回退必须显式。** 8080 被占用或本地启动失败时，只有 `config/model-routing.yaml` 明确启用且 key 环境变量存在才可回退远程 OpenAI 兼容 API；任务记录必须写 `provider`，不得冒充本地；视觉阶段没有 `vision_model` 时不得回退。**所有 DeepSeek 调用固定 `deepseek-flash`，禁用 `deepseek-v4-pro`；配置层会拒绝 pro。API key 只从系统环境变量读取（本机 `DeepSeek-API`），不写入 `.env`、YAML、日志或跟踪文件；仓库只保留不含 key 的 `.env.example`。远程 provider 可为 `deepseek` / `openai-compatible` 等；通用变量为 `REMOTE_*`，DeepSeek 兼容 `DEEPSEEK_*`。**

## 3. 常用入口

```powershell
.\scripts\check.ps1                                        # 全量回归（必须打印 check ok）
uv run --project CourseControl course-control validate --lesson <slug>
.\scripts\build-lesson.ps1 -Lesson <slug>                  # 完整课程构建
uv run --project ModelingStudio modeling-studio run --image <png>
uv run --project CourseControl course-control director-plan --lesson <slug>   # 导演计划 + 校验
uv run --project CourseControl course-control producer-run --lesson <slug>     # 订单 → 计划 → 交付清单
uv run --project CourseControl course-control producer-rebuild --lesson <slug> # 受影响镜头局部重渲染
uv run --project ContentQA content-qa review --lesson <slug>
# Code2Video 镜头（可选）：ShotSpec.engine=code_video，scene 指向 CodeVideoStudio/shots/<shot>/SPEC.md
.\scripts\check-scene-system.ps1                           # IR v2 契约检查
```

## 4. 修改前的检查顺序

1. 读 `docs/PRD.md` 对应条目与 `docs/TRACEABILITY.md` 状态。
2. 读目标模块 README 与相邻代码，确认现有实现是否已满足。
3. 优先修复与收敛，不新增平行实现。
4. 改完同步：测试、`docs/TRACEABILITY.md` 状态、必要的决策记录。

## 5. 环境

- Python 3.12 + uv；Node 24 + npm；Blender 5.2；FFmpeg 8。
- 本机配置：`config/tools.yaml`、`config/local-paths.yaml`、`ModelingStudio/config/workflow.yaml`、`config/content-qa.yaml`，均不进仓库。
- 端口：8080 本地模型（唯一实例）、8081 课件预览、5173 Motion Canvas、3000 Remotion、50000 VoxCPM2 TTS。8082 不存在。
