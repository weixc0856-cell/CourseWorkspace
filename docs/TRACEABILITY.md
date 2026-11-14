# 需求映射索引

- **状态与证据的唯一清单**：[PROJECT_STATUS.md](PROJECT_STATUS.md)
- **需求基线**：[PRD.md](PRD.md)
- 本文件只回答“需求由哪些代码和测试承载”，不重复状态判定。

| 需求 | 主要代码 | 测试 |
| --- | --- | --- |
| FR-01 课程契约 | `CourseControl/src/course_control/content/paths.py`、`content/contracts.py`；`lessons/README.md` | `CourseControl/tests/test_contracts.py` |
| FR-02 校验 V-01~V-09 | `CourseControl/src/course_control/content/validators.py` | `test_contracts.py`、`check.ps1` |
| FR-03 截图 | `CourseControl/src/course_control/rendering/adapters/slides.py`；`CourseSlides/template/`；`RemotionStudio/scripts/capture-slides.mjs` | `check.ps1` + 真实课程截图 |
| FR-04 动画 | `adapters/motion_canvas.py`、`manim.py`、`blender.py`；引擎场景根解析 `platform/workspace_layout.py`（`engine_roots`） | `test_staging.py`、`test_vendor.py`、`lesson-manual` 夹具 |
| FR-05 IR v2 | `CourseControl/src/course_control/rendering/blender_scene.py`、`rendering/blender_runner.py`、`rendering/scene_presets.py`、`rendering/colormaps.py`；`BlenderStudio/scripts/scene_system/`、`verify_scene.py`；`shared/scene_expr/` | `CourseControl/tests/test_blender_scene.py`、`test_scene_expr.py` |
| FR-06 本地建模 | `ModelingStudio/src/modeling_studio/` | `ModelingStudio/tests/` |
| FR-07 时间线 | `CourseControl/src/course_control/content/collect.py`、`content/contracts.py`（annotations）、`platform/utils.py`；`shared/colormaps.json` | `test_contracts.py`、`test_staging.py` |
| FR-08 合成与验收 | `CourseControl/src/course_control/quality/verify.py`、`delivery/report.py`、`adapters/remotion.py`；`RemotionStudio/src/compositions/CourseVideo.tsx`、`overlays/Annotations.tsx` | `test_staging.py`、夹具构建、真实 Remotion still |
| FR-09 本地模型串行与远程回退 | `shared/ai_runtime/src/ai_runtime/locks.py`、`service.py`、`remote.py`、`routing.py`；`ModelingStudio/server.py`、`llm.py` | `test_concurrency.py`、`test_service.py`、`test_lifecycle.py`、`test_remote.py`、`ModelingStudio/tests/test_remote_routing.py`；flash-only 策略 |
| FR-10 任务状态 | `shared/ai_runtime/src/ai_runtime/tasks.py`；`ModelingStudio/src/modeling_studio/job.py` | `test_runtime.py`、`ModelingStudio/tests/test_job_state.py` |
| FR-11 上下文预算 | `shared/ai_runtime/src/ai_runtime/budget.py`；`ModelingStudio/src/modeling_studio/config.py`、`llm.py` | `test_runtime.py`、`ModelingStudio/tests/test_budget.py`、`ContentQA/tests/test_content_qa.py` |
| FR-12 内容审查 | `ContentQA/src/content_qa/` | `ContentQA/tests/test_content_qa.py`、`test_schemas.py`、`test_model_policy.py`、`test_env_overrides.py` |
| FR-13 报告 | `CourseControl/src/course_control/delivery/report.py`、`rendering/blender_runner.py`、`shared/ai_runtime/tasks.py`、`ContentQA/src/content_qa/review.py` | 各报告结构断言 |
| FR-14 一键回归 | `scripts/check.ps1`、`scripts/check-scene-system.ps1`、`scripts/check_paths.py` | 自身执行 |
| FR-15 输入摄取/摘要 | `CourseControl/src/course_control/authoring/ingest.py`、`digest.py` | `test_authoring_ingest.py` |
| FR-16 课程草稿/批准门 | `authoring/llm.py`、`pipeline.py`、`CourseControl/prompts/` | `test_authoring_gate.py`、`test_authoring_ingest.py` |
| FR-17 时长契约 | `content/duration.py`、`content/validators.py`、`content/collect.py`、`quality/verify.py` | `test_duration_contract.py`、`test_duration_validation.py`、`test_collect_timing.py` |
| FR-18 整课旁白 | `voice/narrate.py`、`voice/narration_course.py` | `test_narrate.py`、真实 VoxCPM2 样片 |
| FR-19 双语字幕/双版本 | `voice/subtitles.py`、`adapters/burn.py`、`pipeline.py`、`RemotionStudio/src/compositions/CourseTimeline.tsx` | `test_subtitles.py`、`test_burnin.py`、`test_staging.py`、真实 6 秒 TimelineSpec 合成 |
| FR-20 代码驱动镜头 | `CourseControl/src/course_control/rendering/adapters/code_video.py`、`quality/code_video_qc.py`、`rendering/engine_router.py`、`platform/vendor.py`、`platform/workspace_layout.py`（`engine_roots`）、`CodeVideoStudio/` | `test_code_video_adapter.py`、`test_code_video_qc.py`、`test_engine_router.py`、30 秒真实 Canvas 镜头 + 900/900 帧哈希一致 + QC/contact sheet |
| FR-21 技术雷达 | `docs/evaluations/技术雷达-视频生产.md`、`docs/evaluations/评估-Code2Video接入.md` | HyperFrames/VideoZero POC 记录；许可证核查 |
| FR-22 交付包/QC/归档 | `docs/课程生产交付物规范.md`、`delivery/report.py`、`quality/verify.py`、`quality/code_video_qc.py` | 交付清单、`build-report.json`、镜头 QC 证据 |
| FR-23 Claude Code 默认后端 | `shared/ai_runtime/src/ai_runtime/claude_code.py`、`CourseControl/authoring/llm.py`、`ContentQA/client.py`、`ModelingStudio/server.py`、`config/claude-code.example.yaml` | `test_claude_code.py`、`test_authoring_claude_code.py`、ContentQA/ModelingStudio 后端测试、四后端对比真实验证 |
| FR-24 Scene-first 合成 | `CourseControl/collect.py`、`RemotionStudio/src/compositions/ScenePage.tsx`、`lesson.yaml.compose.mode` | scene 模式 collect 单测；汽车空气动力学 scene 版真实构建 |
| FR-25 公式质量模块 | `CourseControl/src/course_control/rendering/formulas.py`、`RemotionStudio/src/components/Formula.tsx`、`scripts/formula-render.mjs`、`ManimSandbox/00-formula-smoke/` | `test_formulas.py`、KaTeX PNG、Remotion FormulaProbe、Manim FormulaSmoke |
| FR-26 科学图形资产 | `ScientificFigures/figures/continuity_figure.py`、`ScientificFigures/pyproject.toml` | 真实 SymPy LaTeX + Matplotlib/SciencePlots SVG/PDF/PNG |
| FR-27 动画视觉导演层 | `CourseControl/src/course_control/direction/animation_direction.py`、`ManimSandbox/03-vector-intro/direction-addition-v2.json`、`vector_addition.py`、`vector_direction.py` | `test_animation_direction.py`、81.6 秒技术竖切片、90 秒五概念切片 |
| FR-28 导演层 | `CourseControl/src/course_control/direction/`、`docs/导演层.md` | `test_director.py`、`<slug>` `director_plan.json`（12 镜头/1200 s/12 ready）、5 个真实渲染镜头 |
| FR-29 制片层 | `CourseControl/src/course_control/delivery/`、`docs/制片层.md` | `test_producer.py`、`<slug>` delivery manifest（blocked，4 项缺失）、affected 实测 |
| FR-30 版式系统 | `CourseControl/src/course_control/rendering/layout/`、`ManimSandbox/common/design_system.py`、`docs/版式系统.md` | `test_layout.py`、12 镜头模板分配、CrossAttention/Loss 前后对比 |
| FR-31 配色系统 | `CourseControl/src/course_control/rendering/layout/schema.py`、`ManimSandbox/common/design_system.py`、`docs/配色规范.md` | `test_color_system.py`、palette-review 合辑 |
| FR-32 静帧运镜 | `CourseControl/src/course_control/rendering/motion.py`、`RemotionStudio/src/components/MotionImage.tsx`、`docs/运镜与剪辑.md` | `test_motion.py`、`tsc --noEmit`、timeline metadata |
| FR-33 模拟契约 | `CourseControl/src/course_control/rendering/simulation.py`、`BlenderStudio/scenes/primer-poc/`、`docs/evaluations/评估-Primer模拟视频POC.md` | `test_simulation.py`、`test_simulation_director.py`、adapter PASS、30 秒 POC |
| FR-43 锁定与失效 | `CourseControl/src/course_control/locks/`（`picture.py`、`dialogue.py`、`dependencies.py`）、`cli/locks.py`、`cli/render.py`（`subtitles-build` 守卫） | `test_locks.py`（12 例）；a01 真实课程打锁与复查 |
| FR-44 仓库与项目分离 | `CourseControl/src/course_control/platform/separation.py`、`cli/lesson.py`（`separation`）、`workspace_layout.engine_roots` | `test_separation.py`（5 例）；2026-11-12 迁移后仅剩三处夹具 |
| FR-42 镜头表 | `content/contracts.py`（`ShotSpec` v2 字段、`ContinuityObject`、`Storyboard` 版本守卫）、`authoring/shot_sheet.py`、`content/validators.py`（V-45～V-47）、`cli/authoring.py` | `test_shot_sheet.py`（9 例）；a01 副本 v2 编译、三处错误定位、指纹稳定；13 门 v1 课程不受影响 |
| FR-41 声音资产 | `CourseControl/src/course_control/voice/audio/`（`voice_bible.py`、`lexicon.py`）、`narrate.segment_cache_key`、`voice/narration_course.py`、`cli/render.py`（`narration-assets`）；`shared/schemas/voice-bible.schema.json`、`lexicon.schema.json` | `test_audio_assets.py`（17 例）；a01 副本上 5/24 段被词典改写，旧缓存键不变 |
| FR-40 动画预览 | `CourseControl/src/course_control/animatic/`（`timeline.py`、`builder.py`、`report.py`）、`cli/animatic.py` | `test_animatic.py`（11 例）；三门真实课程 animatic |
| 音频策略（内容类型/BGM） | `CourseControl/src/course_control/voice/audio_plan.py`；`content/contracts.py`（`AudioPolicy`）；`audio-plan` CLI；`producer/delivery.py` | `test_audio_plan.py`；交付包在配置 BGM 时要求 `audio_plan.json` |
| V1-E 时间线兼容层 | `CourseControl/src/course_control/content/v1_timeline.py`；`collect` 写 `contracts/timeline.spec.json`；CLI `timeline-v1` | `CourseControl/tests/test_v1_timeline.py`；lesson-smoke 实跑 |
| V1-D Session 证据适配 | `CourseControl/src/course_control/platform/session_evidence_v1.py`；CLI `session-evidence-v1` | `CourseControl/tests/test_session_evidence_v1.py`；shell_001 实跑 |
| V1-D 剩余轨道 | `ShotSpec` 扩展 `session/simulation/graphics`；Session runner 原生写 V1 | 未开始 |
| V1 统一契约（V1-B/C/F） | `CourseControl/src/course_control/content/contracts_v1.py`、`content/timecode.py`、`content/legacy_e6.py`、`content/e65.py`；`shared/schemas/*-v1.schema.json`；`course-control schemas-v1` / `contract-v1-validate` / `e6-adapt` / `e65-adapt` | `CourseControl/tests/test_contracts_v1.py`、`test_timecode.py`、`test_legacy_e6.py`、`test_e65_contracts.py` |
| FR-34 品牌与片头片尾 | `RemotionStudio/src/brand/`、`shared/design-tokens/brand.json`、`CourseControl/src/course_control/rendering/branding.py`、`adapters/brand.py`、`quality/verify.py` V-36 | `test_branding.py`、`tsc --noEmit`、真实 3.0 s/12 s 渲染与 292.367 s 母版拼接（307.367 s，mode=copy，TS 重封装，video_timing/audio_alignment pass） |
| FR-35 教材知识库 | `KnowledgeStudio/src/knowledge_studio/`、`docs/KnowledgeStudio.md` | `KnowledgeStudio/tests/test_knowledge_studio.py`、`test_spancheck_and_map.py`、12 页冒烟教材 CLI 全链路；一本 352 页英文教材真实入库（18 单元，KS-01…KS-08 pass，span-check 5/5） |
| FR-36 多视觉语法生产契约 | `content/production.py`、`rendering/renderers.py`、`collect._collect_shots`、`content/paths.py`、`course-control production-validate` | `test_production.py`、`test_collect_shots.py`、`test_grammar.py` |
| FR-37 分层质量门禁 | `quality/quality_gates.py`、`direction/animation_score.py`（profile/metric_only）、`course-control quality-gate` | `test_quality_gates.py`、`<slug>` 实跑 |
| FR-38 逐词字幕与镜头转场 | `contracts.Subtitles.mode/position`、`collect._word_captions`、`v1_timeline` word_captions、`CourseTimeline.tsx`、`capture.mjs --chunk-seconds` | `tsc --noEmit`、分块捕获 PSNR 实测；逐词渲染未目检 |
| FR-39 参考驱动比较 | `quality/reference.py`、`<内容根>/references/`、`course-control reference-compare` | `test_reference.py`、3b1b-attention 实跑 |
| 配置解析与快照（C-24/C-29） | `platform/config_resolve.py`；`config-resolve`；build 写 `logs/config-resolution.json` | `test_config_resolve.py`；05/06/01/nvda 实跑 |
| 检查点与 resume（C-20） | `platform/checkpoint.py`、`pipeline.py`；`build --resume/--resume-from` | `test_checkpoint.py`、`test_pipeline_source.py` |
| 阶段超时（C-19） | `platform/timeouts.py`；各适配器调用 `resolve_timeout` | `test_timeouts.py`、`test_run_command.py` |
| 资产寻址与交付包（C-21） | `rendering/assets.py`、`delivery/package.py`、`voice/audio_mix.py` | `test_assets.py`、`test_package.py` |
| Blender 任务入口（C-13） | `rendering/blender_task.py`、`adapters/blender.py`；`blender-task-validate` | `test_blender_task.py` |
| legacy 时间线登记（C-14） | `content/legacy_registry.py`、`quality/verify.py` V-43 | `test_legacy_registry.py` |
| 字幕 QC（C-07/C-08） | `voice/subtitles_qc.py`、`quality/verify.py` V-44；`subtitles-qc` | `test_subtitles_qc.py`；06/05/01 实跑 |
| 审查裁决队列（C-23） | `quality/review_decisions.py`、`quality/quality.py`；`review-status`/`review-decide` | `test_review_decisions.py`、`test_quality.py` |
| 证据处置（C-11） | `scripts/check_evidence.py`、`docs/audit/evidence-decisions.yaml` | `check.ps1`；分类 90/90 |
| 镜头分类（C-09） | `direction/shot_taxonomy.py`、`shared/grammars/shot-taxonomy.yaml`；`shot-taxonomy` | `test_shot_taxonomy.py` |
| 单一 three.js（C-17） | `platform/vendor.py`；`vendor-sync`/`vendor-check` | `test_vendor.py` |
| 脚本化计数（C-27） | `quality/stats.py`；`stats` | `test_stats.py` |
| 探针隔离（C-18） | `RemotionStudio/src/probes/`、`src/index.ts` | `tsc --noEmit` |
| NFR-01~08 | 见 [ARCHITECTURE.md](ARCHITECTURE.md) 与 [ACCEPTANCE.md](ACCEPTANCE.md) | 见各套单测 |

## V2 增量需求（2026-11-13，PRD v2.0）

| 需求 | 主要代码 | 测试 |
| --- | --- | --- |
| FR-45 项目契约与双模式 | `delivery/project.py`、`cli/project.py`；`shared/schemas/project-spec.schema.json` | `test_project_spec.py`；15 门存量课合成实跑 |
| FR-46 制品索引与运行记录 | `platform/artifacts.py`、`platform/run_record.py`、`cli/project.py` | `test_artifacts.py`、`test_run_record.py`；真实课索引 120 个产物 |
| FR-47 阶段 DAG 与受影响范围 | `platform/checkpoint.py`（`STAGE_DEPS`）、`pipeline.py`（`--resume-from`） | `test_checkpoint.py`（依赖顺序、兄弟隔离、失效范围） |
| FR-48 质量缺陷闭环 | `quality/defect.py`、`repair.py`、`regression.py`、`certificate.py`、`cli/quality.py` | `test_defects.py`、`test_certificate.py`；真实课诊断实跑 |
| FR-49 知识概念层与课程规划 | `KnowledgeStudio/src/knowledge_studio/knowledge_ir.py`、`cli.py`；`shared/schemas/knowledge-ir.schema.json`、`curriculum.schema.json` | `KnowledgeStudio/tests/test_knowledge_ir.py`（11 例） |
| FR-50 自动化等级与停机条件 | `delivery/project.py`（`ExecutionSpec`）、`docs/v2/m0/PRODUCT_SPEC_V2.md`、`QUALITY_SPEC_V2.md`；`platform/run_record.py` | 契约与文档；A3 实跑未开始 |
| FR-51 主题视频模式（PLANNED） | `delivery/project.py`（`topic_video` 契约） | 仅契约校验；流程未实现 |
| FR-52 视觉设计层 | `CourseControl/src/course_control/design/`（schema/planner/checks/board/report）、`cli/design.py`；`authoring/visual-design.yaml` 覆盖 | `test_visual_design.py`（17 例）；`<slug>` 12 镜头关键帧看板 + beat 条实跑 |
| FR-53 声音导演层 | `CourseControl/src/course_control/sound/`（schema/planner/checks/report）、`cli/sound.py` | `test_sound_design.py`（20 例）；`<slug>` 54 段旁白 cue sheet 实跑 |
| FR-54 课程质量模型 | `docs/课程质量模型.md` | 文档标准；单集验收表待第一集实跑 |
| FR-55 Preview / Release 双模式 | `CourseControl/src/course_control/preview/`（profile/units/remotion_window/engines/runner/topic/audio/sound_mix）、`cli/preview.py` | `test_preview_modes.py`；02/06 真实 P0/P1；fengshui P0/P1/P2 |
| FR-56 统一渲染入口与发布检查 | `CourseControl/src/course_control/release/check.py`、`cli/preview.py`、`delivery/project.py`（TopicPlan） | `test_preview_modes.py`；05/aging release-check；fengshui release-check pass |

## 人工依赖

| 项 | 代码位置 | 说明 |
| --- | --- | --- |
| Motion Canvas 导出 | `MotionStudio/scripts/render-headless.mjs`、`src/headless.js`、`adapters/motion_canvas.py` | `test_motion_canvas_headless.py`；attention-flow 3 次哈希一致；注入失败 |
| 审查后端凭据 | `ContentQA/src/content_qa/config.py` | 默认 Claude Code；API 凭据只读环境变量 / 本机忽略配置 |
| 课程内容 | `lessons/` | 作者维护，不入库 |
