# 验收矩阵与命令

- **版本**：v1.0（2026-11-03）
- **上游**：[PRD.md](PRD.md)；结构与契约见 [ARCHITECTURE.md](ARCHITECTURE.md)
- 原则：**只记录真实执行结果**。未执行写 `NOT_RUN`，人工缺失写 `skipped`，凭据缺失写 `blocked`。

---

## 1. 一键回归

```powershell
.\scripts\check.ps1
# 期望：四套单测 + 课程契约（本地有课程时 5 个，干净克隆时 3 个夹具）+ 11 个场景契约，最后打印 check ok，exit 0
```

最近一次执行（2026-11-03）：**`check ok`，exit 0**。

| 套件 | 命令 | 用例数 | 结果 |
| --- | --- | --- | --- |
| CourseControl | `uv run --project CourseControl python -m unittest discover -s CourseControl/tests -t CourseControl` | 19 | 全部通过 |
| ModelingStudio | `uv run --project ModelingStudio python -m unittest discover -s ModelingStudio/tests -t ModelingStudio` | 28 | 全部通过 |
| ai_runtime | `uv run --project shared/ai_runtime python -m unittest discover -s shared/ai_runtime/tests -t shared/ai_runtime` | 22 | 全部通过 |
| ContentQA | `uv run --project ContentQA python -m unittest discover -s ContentQA/tests -t ContentQA` | 11 | 全部通过 |

合计 **80** 个用例。

---

## 2. 课程契约 V-01~V-21

| 编号 | 检查 | 实现 | 验证 |
| --- | --- | --- | --- |
| V-01 | slug 与目录一致 | `validators.py` | 5 个课程/夹具 validate 通过 |
| V-02 | 必需文件、recording 的 base_video | `validators.py` | 通过；历史故障注入见归档 R5 矩阵 |
| V-03 | 页数 = 讲师手册块数 | `validators.py` | 两门真实课 20/20、8/8 |
| V-04 | 四要素（时长预算/动画切入/技术核查/逐字口播） | `validators.py` | `test_missing_notes_element_fails` |
| V-05 | 素材路径 `/lessons/<slug>/assets/` 且存在 | `validators.py` | 两门真实课通过 |
| V-06 | 禁止 `Notes:`、`$...$`、`<video>`、`[ANIMATION` | `validators.py` | 两门真实课通过 |
| V-07 | 镜头 id/页码/引擎 | `validators.py` | 5 个夹具通过 |
| V-08 | 场景与 Blender 任务存在 | `validators.py` | 5 个夹具通过 |
| V-09 | Motion 场景已注册 | `validators.py` | 两门真实课通过 |
| V-10 | 镜头源文件存在且可读 | `verify.py` | `lesson-smoke` 构建通过 |
| V-11 | 实测时长与期望漂移（warning） | `collect.py` | 夹具无漂移 |
| V-12 | 分辨率与帧率一致 | `verify.py` | `lesson-smoke` 1920×1080@30 |
| V-13 | base 连续、overlay 落在父片段且不重叠 | `verify.py` | `lesson-smoke` 通过 |
| V-14 | 成片可读、时长在容差内 | `verify.py` | `lesson-smoke` 6.000s |
| V-15 | 音画时长差 ≤ 0.5s | `verify.py` | `lesson-smoke` 旁白启用并通过 |
| V-16 | 字幕文件与 cue 数 | `verify.py` | `lesson-smoke` 字幕启用并通过 |
| V-17 | 报告完整、verdict 一致 | `report.py` + `cli.py verify` | 构建报告包含 V-17 pass |
| V-18 | artifacts 均位于 `build/<slug>/` | `verify.py` | 通过 |
| V-19 | 阶段/检查适用性 | `report.py` | 通过 |
| V-20 | recording 时长与笔记累计一致 | `verify.py` | `lesson-smoke` 通过 |
| V-21 | 所有声明路径合法 | `path_problem` | 单测覆盖绝对路径/反斜杠/`..` |

失败注入证据：`tests/test_staging.py`（合成失败保留 staging、成功清理）；R5 历史故障注入见 `docs/archive/R5-验收矩阵.md`；本轮未重复构造全部故障样本（见 §6）。

---

## 3. 三维场景 IR v2

```powershell
.\scripts\check-scene-system.ps1          # 契约：5 合法 + 6 非法
.\scripts\check-scene-system.ps1 -Render  # 追加 4 次真实 Blender 渲染
```

最近一次带渲染执行：**`scene system check ok`，exit 0**。

| 任务 | 结果 |
| --- | --- |
| `demo-scene` | pass |
| `demo-geometry-nodes` | pass；2 个 NODES 修改器 |
| `demo-animation-scene` | pass；13 条 F-Curve，1280×720 MP4，3.0s |
| `demo-modify` | pass；基于 `scene.blend` 追加，11 个对象 |
| 6 个 invalid 夹具 | 全部被拒绝 |
| 契约与执行分离 | `test_validators_agree_without_generated_artifacts`：`base_blend` 尚未生成时两套校验器结论一致 |

产物：`build/blender-scene-acceptance/blender/` 与 `manifests/`。

---

## 4. 课程构建

| 课程 | 模式 | 结果 | 说明 |
| --- | --- | --- | --- |
| `lesson-smoke` | recording + Blender + 旁白 + 字幕 | **pass** | 全链路真实执行（Blender → collect → Remotion → verify） |
| `lesson-blender-only` | recording + Blender | **pass** | 同上，无旁白/字幕 |
| `01-shell-for-ai-era` | deck + Motion | **incomplete** | 截图 20/20 通过；8 段 Motion 动画未导出 → `manual_export_required`；下游 `not_run` |
| `01-transformer-demo` | deck + Motion | NOT_RUN（本轮） | 与 Shell 课同一阻塞 |
| `lesson-manual` | recording + 人工导出 | validate 通过 | 本轮未单独构建 |

**真实课程未完成的原因**：`build/01-shell-for-ai-era/animation/` 没有 8 个导出文件。这是人工节点，不是程序缺陷；系统如实返回 `incomplete`，未伪装成 pass。

---

## 5. 模型运行时与在线审查

| 项 | 命令 | 结果 |
| --- | --- | --- |
| 跨进程串行 | `test_concurrency.py`（两个子进程竞争锁） | 通过：区间不重叠 |
| 陈旧锁回收 | `test_runtime.py::test_stale_lock_is_reclaimed` | 通过 |
| 他人锁保护 | `test_runtime.py::test_foreign_lock_is_not_released` | 通过 |
| 复用/拒绝/启动失败 | `test_service.py`（mock HTTP） | 4 项通过，锁均释放 |
| 服务启动/停止/切换 | `test_lifecycle.py`（真实子进程 fake server） | 4 项通过：started、switch、reused 不杀他人、超时释放 |
| 重试绕过预算 | `test_budget.py::test_retry_cannot_bypass_budget` | 通过：每次请求前重新检查 |
| 任务失败落盘 | `test_job_state.py` | `job.json` 与任务记录均为 `failed` |
| 上下文预算 | `test_runtime.py` | 文本/CJK/图片/超限拆分 |
| 在线审查成功 | `test_content_qa.py`（mock） | 2 页 → 2 请求 → completed；报告字段完整 |
| 审查 Schema 漂移 | `test_schemas.py` | 4 份 Schema 与 Pydantic 模型一致 |
| 在线审查非法 JSON | 同上 | failed + raw 保存 |
| 多页中途失败 | 同上（flaky） | 第 1 页 findings 保留，第 2 页 failed |
| 在线请求超时 | 同上（slow） | failed，任务记录终态 |
| 只读边界 | 同上 | 课程文件字节不变；未生成 shots.json / build-report.json |
| 无凭据 | 同上 | blocked |
| 真实课程无配置 | `content-qa review --lesson 01-shell-for-ai-era` | **blocked，exit 3**；报告写入 `build/01-shell-for-ai-era/review/review.json` |

本地模型的真实作业证据（历史记录，本轮未重跑）：`ModelingStudio/workspace/jobs/sample-001` 六阶段 completed；`sample-002` 停在 generate；`fallback-test` build+validate 通过。

---

## 6. 未覆盖项（如实记录）

| 项 | 原因 | 影响 |
| --- | --- | --- |
| 真实课程成片 | Motion Canvas 8 段未导出（人工） | `01-shell-for-ai-era` 为 `incomplete` |
| 真实在线模型调用 | 未配置供应商与凭据 | ContentQA 真实课程为 `blocked` |
| 本轮重跑 ModelingStudio 全链路 | 需独占 8080 约 10–30 分钟，且会与用户其他任务冲突 | 仅有历史作业证据 |
| V-05/V-06/V-09/V-16/V-19/V-20 的失败注入 | 会破坏真实课程或已由正常路径覆盖 | 未新增故障样本 |
| 两门真实课程重复构建一致性 | 第二门未构建 | 夹具已验证文件集合稳定 |
| CosyVoice / ComfyUI | 运行时未启动/未部署 | 不在本期范围 |

---

## 7. 复现顺序建议

1. `.\scripts\check.ps1`
2. `.\scripts\check-scene-system.ps1 -Render`
3. `.\scripts\build-lesson.ps1 -Lesson lesson-smoke -LessonDir CourseControl/tests/fixtures`
4. `.\scripts\build-lesson.ps1 -Lesson 01-shell-for-ai-era`（预期 `incomplete`）
5. `uv run --project ContentQA content-qa review --lesson 01-shell-for-ai-era`（预期 `blocked`，exit 3）
