# 需求—模块—测试—验收映射

- **版本**：v1.0（2026-11-03）
- 需求编号来自 [PRD.md](PRD.md)；本表是唯一的状态清单，不另建任务列表。
- 状态：`VERIFIED`（已运行验证）/ `PARTIAL`（部分验证或有人工依赖）/ `BLOCKED`（外部条件缺失）/ `NOT_RUN`。

| 需求 | 模块 / 代码 | 测试 | 验收证据 | 状态 |
| --- | --- | --- | --- | --- |
| FR-01 课程契约 | `lessons/`；`CourseControl/paths.py`、`contracts.py` | `test_contracts.py` | 5 个课程/夹具 validate 通过 | VERIFIED |
| FR-02 V-01~V-09 | `CourseControl/validators.py` | `test_contracts.py`（V-04）、validate 全量 | `check.ps1` | VERIFIED |
| FR-03 预览与截图 | `CourseSlides/`；`adapters/slides.py`；`RemotionStudio/scripts/capture-slides.mjs` | 无单测（依赖浏览器） | 真实课程 20/20；`lesson-smoke` recording 模式 `not_applicable` | VERIFIED |
| FR-04 动画渲染 | `adapters/motion_canvas.py`、`manim.py`、`blender.py` | `test_staging.py`（合成）；无 Motion 单测 | `lesson-manual` 夹具；真实课程 `manual_export_required` | PARTIAL（人工导出） |
| FR-05 IR v2 | `CourseControl/blender_scene.py`、`blender_runner.py`；`BlenderStudio/scripts/scene_system/`、`verify_scene.py` | `test_blender_scene.py`（9 例） | `check-scene-system.ps1 -Render` 4 次真实渲染 pass | VERIFIED |
| FR-06 本地建模 | `ModelingStudio/src/modeling_studio/` | `test_contracts.py`、`test_script_guard.py`、`test_validator.py`、`test_budget.py`、`test_job_state.py`、`test_server_busy.py`（28 例） | 历史作业 `sample-001` 六阶段 completed | PARTIAL（未重跑全链路） |
| FR-07 时间线 | `CourseControl/collect.py`、`utils.py` | `test_contracts.py`、`test_staging.py` | `lesson-smoke` shots.json 通过 verify | VERIFIED |
| FR-08 合成与验收 | `CourseControl/verify.py`、`report.py`、`adapters/remotion.py` | `test_staging.py`；verify 检查 | `lesson-smoke` / `lesson-blender-only` 均 pass | VERIFIED |
| FR-09 本地模型串行 | `shared/ai_runtime/locks.py`、`service.py`；`ModelingStudio/server.py` | `test_concurrency.py`、`test_service.py`、`test_lifecycle.py` | 双进程不重叠；mock 复用/拒绝/释放 | VERIFIED |
| FR-10 任务状态与恢复 | `shared/ai_runtime/tasks.py`；`ModelingStudio/job.py` | `test_runtime.py::TaskStoreTest`、`test_job_state.py` | 失败写入 `job.json` 与任务记录；`--resume` | VERIFIED |
| FR-11 上下文预算 | `shared/ai_runtime/budget.py`；各 LLM 阶段 | `test_runtime.py::TextBudgetTest`、`test_budget.py`、`test_content_qa.py` 超限 | 请求前估算；超限失败不调用模型 | VERIFIED |
| FR-12 在线审查 | `ContentQA/src/content_qa/` | `test_content_qa.py`、`test_schemas.py`（11 例，含中途失败/超时/只读） | mock 成功/非法 JSON/无凭据；真实课程 `blocked` exit 3 | PARTIAL（无真实凭据） |
| FR-13 报告与追溯 | `report.py`、`blender_runner.py`、`tasks.py`、`review.py` | 各报告结构测试 | 报告均落盘，含版本/时间/哈希或预算 | VERIFIED |
| FR-14 一键回归 | `scripts/check.ps1` | 自身执行 | `check ok`，exit 0 | VERIFIED |
| NFR-01 可复现 | `collect`/`report` | 夹具重复构建（历史） | 文件集合稳定 | PARTIAL |
| NFR-02 失败可见 | `pipeline.py`、`report.py` | `test_staging.py` | failures 与状态一致 | VERIFIED |
| NFR-03 隔离 | 各工程 `.gitignore`、`config/*` | `git check-ignore` | 本机配置不入库 | VERIFIED |
| NFR-04 路径安全 | `paths.py`、`blender_scene.py` | `test_contracts.py`、`test_blender_scene.py` | 绝对路径/反斜杠/`..` 被拒 | VERIFIED |
| NFR-05 资源串行 | `ai_runtime` | `test_concurrency.py` | 跨进程互斥 | VERIFIED |
| NFR-06 可中断 | `locks.py` 陈旧回收、`service.py` finally | `test_runtime.py`、`test_service.py` | 锁释放；陈旧锁回收 | VERIFIED |
| NFR-07 最小依赖 | 各 `pyproject.toml` | — | ai_runtime 零依赖 | VERIFIED |
| NFR-08 文档一致 | 本文件与 ACCEPTANCE | — | 文档引用的命令与数量来自实际执行 | VERIFIED |

## 人工依赖与阻塞

| 项 | 类型 | 责任 | 状态 |
| --- | --- | --- | --- |
| 8 段 Motion Canvas 动画导出 | 人工步骤 | 课程作者 | BLOCKED（真实课程 `incomplete`） |
| 课程内容补全（4 页占位、3 页中文） | 内容 | 课程作者 | BLOCKED |
| 在线模型供应商与凭据 | 配置 | 用户 | BLOCKED（ContentQA 为 `blocked`） |
| Manim 接入课程 | 可选 | 课程作者 | NOT_RUN（无课程使用） |
| CosyVoice / ComfyUI | 外部运行时 | 用户环境 | NOT_RUN（未启动/未部署） |

## 归档与不再维护

| 内容 | 处理 | 原因 |
| --- | --- | --- |
| R0–R5 改造 PRD、R5 矩阵 | `docs/archive/` | 已完成的历史规格与快照 |
| ContentQA 完整设计稿（TTS/ASR/公式/语料） | `docs/archive/` | 本期只交付审查内核 |
| AI-Blender 通用技术提案、落地路线图 | `docs/archive/` | 含未实现设想，不能作为基线 |
| Blender v1 任务 | 保留 | 课程夹具的稳定接口；见 `BlenderStudio/tasks/README.md` |
| 8082 备用端口 | 删除约定 | 代码从未实现 |
