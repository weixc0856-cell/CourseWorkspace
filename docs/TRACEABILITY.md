# 需求映射索引

- **状态与证据的唯一清单**：[PROJECT_STATUS.md](PROJECT_STATUS.md)
- **需求基线**：[PRD.md](PRD.md)
- 本文件只回答“需求由哪些代码和测试承载”，不重复状态判定。

| 需求 | 主要代码 | 测试 |
| --- | --- | --- |
| FR-01 课程契约 | `CourseControl/src/course_control/paths.py`、`contracts.py`；`lessons/README.md` | `CourseControl/tests/test_contracts.py` |
| FR-02 校验 V-01~V-09 | `CourseControl/src/course_control/validators.py` | `test_contracts.py`、`check.ps1` |
| FR-03 截图 | `CourseControl/src/course_control/adapters/slides.py`；`CourseSlides/template/`；`RemotionStudio/scripts/capture-slides.mjs` | `check.ps1` + 真实课程截图 |
| FR-04 动画 | `adapters/motion_canvas.py`、`manim.py`、`blender.py` | `test_staging.py`、`lesson-manual` 夹具 |
| FR-05 IR v2 | `CourseControl/src/course_control/blender_scene.py`、`blender_runner.py`、`scene_presets.py`、`colormaps.py`；`BlenderStudio/scripts/scene_system/`、`verify_scene.py`；`shared/scene_expr/` | `CourseControl/tests/test_blender_scene.py`、`test_scene_expr.py` |
| FR-06 本地建模 | `ModelingStudio/src/modeling_studio/` | `ModelingStudio/tests/` |
| FR-07 时间线 | `CourseControl/src/course_control/collect.py`、`contracts.py`（annotations）、`utils.py`；`shared/colormaps.json` | `test_contracts.py`、`test_staging.py` |
| FR-08 合成与验收 | `CourseControl/src/course_control/verify.py`、`report.py`、`adapters/remotion.py`；`RemotionStudio/src/compositions/CourseVideo.tsx`、`overlays/Annotations.tsx` | `test_staging.py`、夹具构建、真实 Remotion still |
| FR-09 本地模型串行与远程回退 | `shared/ai_runtime/src/ai_runtime/locks.py`、`service.py`、`remote.py`、`routing.py`；`ModelingStudio/server.py`、`llm.py` | `test_concurrency.py`、`test_service.py`、`test_lifecycle.py`、`test_remote.py`、`ModelingStudio/tests/test_remote_routing.py`；flash-only 策略 |
| FR-10 任务状态 | `shared/ai_runtime/src/ai_runtime/tasks.py`；`ModelingStudio/src/modeling_studio/job.py` | `test_runtime.py`、`ModelingStudio/tests/test_job_state.py` |
| FR-11 上下文预算 | `shared/ai_runtime/src/ai_runtime/budget.py`；`ModelingStudio/src/modeling_studio/config.py`、`llm.py` | `test_runtime.py`、`ModelingStudio/tests/test_budget.py`、`ContentQA/tests/test_content_qa.py` |
| FR-12 在线审查 | `ContentQA/src/content_qa/` | `ContentQA/tests/test_content_qa.py`、`test_schemas.py`、`test_model_policy.py`、`test_env_overrides.py` |
| FR-13 报告 | `CourseControl/src/course_control/report.py`、`blender_runner.py`、`shared/ai_runtime/tasks.py`、`ContentQA/src/content_qa/review.py` | 各报告结构断言 |
| FR-14 一键回归 | `scripts/check.ps1`、`scripts/check-scene-system.ps1`、`scripts/check_paths.py` | 自身执行 |
| FR-15 输入摄取/摘要 | `CourseControl/src/course_control/authoring/ingest.py`、`digest.py` | `test_authoring_ingest.py` |
| FR-16 课程草稿/批准门 | `authoring/llm.py`、`pipeline.py`、`CourseControl/prompts/` | `test_authoring_gate.py`、`test_authoring_ingest.py` |
| FR-17 时长契约 | `duration.py`、`validators.py`、`collect.py`、`verify.py` | `test_duration_contract.py`、`test_duration_validation.py`、`test_collect_timing.py` |
| FR-18 整课旁白 | `narrate.py`、`narration_course.py` | `test_narrate.py`、真实 VoxCPM2 样片 |
| FR-19 双语字幕/双版本 | `subtitles.py`、`adapters/burn.py`、`pipeline.py`、`RemotionStudio/src/compositions/CourseTimeline.tsx` | `test_subtitles.py`、`test_burnin.py`、`test_staging.py`、真实 6 秒 TimelineSpec 合成 |
| FR-20 代码驱动镜头 | `CourseControl/src/course_control/adapters/code_video.py`、`code_video_qc.py`、`engine_router.py`、`CodeVideoStudio/` | `test_code_video_adapter.py`、`test_code_video_qc.py`、`test_engine_router.py`、30 秒真实 Canvas 镜头 + 900/900 帧哈希一致 + QC/contact sheet |
| FR-21 技术雷达 | `docs/技术雷达-视频生产.md`、`docs/评估-Code2Video接入.md` | HyperFrames/VideoZero POC 记录；许可证核查 |
| FR-22 交付包/QC/归档 | `docs/课程生产交付物规范.md`、`report.py`、`verify.py`、`code_video_qc.py` | 交付清单、`build-report.json`、镜头 QC 证据 |
| FR-23 Claude Code 默认后端 | `shared/ai_runtime/src/ai_runtime/claude_code.py`、`CourseControl/authoring/llm.py`、`ContentQA/client.py`、`ModelingStudio/server.py`、`config/claude-code.example.yaml` | `test_claude_code.py`、`test_authoring_claude_code.py`、ContentQA/ModelingStudio 后端测试、四后端对比真实验证 |
| FR-24 Scene-first 合成 | `CourseControl/collect.py`、`RemotionStudio/src/compositions/ScenePage.tsx`、`lesson.yaml.compose.mode` | scene 模式 collect 单测；汽车空气动力学 scene 版真实构建 |
| FR-25 公式质量模块 | `CourseControl/src/course_control/formulas.py`、`RemotionStudio/src/components/Formula.tsx`、`scripts/formula-render.mjs`、`ManimSandbox/00-formula-smoke/` | `test_formulas.py`、KaTeX PNG、Remotion FormulaProbe、Manim FormulaSmoke |
| FR-26 科学图形资产 | `ScientificFigures/figures/continuity_figure.py`、`ScientificFigures/pyproject.toml` | 真实 SymPy LaTeX + Matplotlib/SciencePlots SVG/PDF/PNG |
| FR-27 动画视觉导演层 | `CourseControl/src/course_control/animation_direction.py`、`ManimSandbox/03-vector-intro/direction-addition-v2.json`、`vector_addition.py`、`vector_direction.py` | `test_animation_direction.py`、81.6 秒技术竖切片、90 秒五概念切片 |
| FR-28 导演层 | `CourseControl/src/course_control/director/`、`docs/导演层.md` | `test_director.py`、01-transformer-demo `director_plan.json`（12 镜头/1200 s/12 ready）、5 个真实渲染镜头 |
| FR-29 制片层 | `CourseControl/src/course_control/producer/`、`docs/制片层.md` | `test_producer.py`、01-transformer-demo delivery manifest（blocked，4 项缺失）、affected 实测 |
| FR-30 版式系统 | `CourseControl/src/course_control/layout/`、`ManimSandbox/common/design_system.py`、`docs/版式系统.md` | `test_layout.py`、12 镜头模板分配、CrossAttention/Loss 前后对比 |
| FR-31 配色系统 | `CourseControl/src/course_control/layout/schema.py`、`ManimSandbox/common/design_system.py`、`docs/配色规范.md` | `test_color_system.py`、palette-review 合辑 |
| FR-32 静帧运镜 | `CourseControl/src/course_control/motion.py`、`RemotionStudio/src/components/MotionImage.tsx`、`docs/运镜与剪辑.md` | `test_motion.py`、`tsc --noEmit`、timeline metadata |
| V1-E 时间线兼容层 | `CourseControl/src/course_control/v1_timeline.py`；`collect` 写 `contracts/timeline.spec.json`；CLI `timeline-v1` | `CourseControl/tests/test_v1_timeline.py`；lesson-smoke 实跑 |
| V1-D Session 证据适配 | `CourseControl/src/course_control/session_evidence_v1.py`；CLI `session-evidence-v1` | `CourseControl/tests/test_session_evidence_v1.py`；shell_001 实跑 |
| V1-D 剩余轨道 | `ShotSpec` 扩展 `session/simulation/graphics`；Session runner 原生写 V1 | 未开始 |
| V1 统一契约（V1-B/C/F） | `CourseControl/src/course_control/contracts_v1.py`、`timecode.py`、`legacy_e6.py`、`e65.py`；`shared/schemas/*-v1.schema.json`；`course-control schemas-v1` / `contract-v1-validate` / `e6-adapt` / `e65-adapt` | `CourseControl/tests/test_contracts_v1.py`、`test_timecode.py`、`test_legacy_e6.py`、`test_e65_contracts.py` |
| NFR-01~08 | 见 [ARCHITECTURE.md](ARCHITECTURE.md) 与 [ACCEPTANCE.md](ACCEPTANCE.md) | 见各套单测 |

## 人工依赖

| 项 | 代码位置 | 说明 |
| --- | --- | --- |
| Motion Canvas 导出 | `adapters/motion_canvas.py` 只校验 | 编辑器导出是正式节点 |
| 在线模型凭据 | `ContentQA/src/content_qa/config.py` | 环境变量 / 本机忽略配置 |
| 课程内容 | `lessons/` | 作者维护，不入库 |
