# 项目当前状态与 PRD 盘点

- **盘点日期**：2026-11-03
- **代码基线**：本地 `main` = `8e45a68`；`origin/main` = `027e64d`
- **需求基准**：[PRD.md](PRD.md)（v1.0）
- **映射索引**：[TRACEABILITY.md](TRACEABILITY.md)；工作流见 [WORKFLOW.md](WORKFLOW.md)

状态词：`COMPLETED`（实现且有真实证据）/ `PARTIAL`（有缺口）/ `NOT_IMPLEMENTED` / `BLOCKED`（外部条件限制）/ `NOT_RUN` / `DEFERRED` / `OUT_OF_SCOPE`。

---

## 1. 基线核实

| 项 | 事实 |
| --- | --- |
| 本地分支 | `main`（跟踪 `origin/main`，落后 1 个提交） |
| 本地 HEAD | `8e45a68 chore: 移除误跟踪的 __pycache__ 字节码` |
| 远程 HEAD | `027e64d Create django.yml`（GitHub 网页提交，新增 `.github/workflows/django.yml`） |
| `d53ebd1` | 干净的初始工作流快照（无父提交）；是当前代码的基线 |
| 当前运行代码 | `d53ebd1` + `33c68ad`（IR v2 base_blend 校验修复）+ `8e45a68`（移除误跟踪字节码） |
| `converge/v1` | `dd1d7f2`，完整收敛历史（含早期课程内容），**仅本地** |
| `archive/full-history-2026-11-03` | `adef52f`，改造前 main，**仅本地** |
| 远程内容 | 267 个文件；`lessons/` 仅 `README.md`；无 `build/`、`runtime/`、`.venv`、`node_modules` |
| 本地/远程差异 | 远程新增 `django.yml`，本地未同步；本地无未推送提交 |

**说明**：此前报告中的 `d53ebd1` 与 `8e45a68` 没有记错——前者是干净快照，后者是在其上的第二个修复提交。当前实际代码包含两者。

**仓库元数据**：Description 与 9 个 Topics 已通过 `gh repo edit` 写入并回读确认。

**待处理（未擅自修改）**：`origin/main` 的 `.github/workflows/django.yml` 是 GitHub 的通用 Django CI 模板，与本项目无关（无 `requirements.txt` / `manage.py`），每次推送都会运行并失败。建议在 GitHub 上删除该工作流，再决定是否用本项目自己的 CI。

---

## 2. 功能需求（FR）

| 编号 | 需求 | 当前实现 | 验证证据 | 状态 | 后续 |
| --- | --- | --- | --- | --- | --- |
| FR-01 | 课程内容契约 | `lessons/` + `paths.py` / `contracts.py` | 5 个课程/夹具 validate 通过（本地） | COMPLETED | — |
| FR-02 | V-01~V-09 校验 | `validators.py` | `check.ps1`；V-04 失败单测 | COMPLETED | — |
| FR-03 | 预览与截图 | `adapters/slides.py` + `capture-slides.mjs` | 真实课程 20/20（`build/01-shell-for-ai-era/slides`） | COMPLETED | — |
| FR-04 | 动画渲染 | Motion 人工导出；Manim / Blender v1 适配器 | `lesson-manual` 夹具；真实课程 `manual_export_required` | PARTIAL | 8 段 Motion 导出未完成 |
| FR-05 | IR v2 场景任务 | `blender_scene.py`、`blender_runner.py`、`scene_system/` | `check-scene-system.ps1 -Render` 4 次真实渲染；19 个 CourseControl 测试 | COMPLETED | — |
| FR-06 | 本地自动建模 | `ModelingStudio/` | 28 个测试；历史作业 `sample-001` 六阶段 completed | PARTIAL | 真实全链路本轮未重跑（需独占 8080） |
| FR-07 | 时间线收集 | `collect.py` | `lesson-smoke` shots.json 通过 verify | COMPLETED | — |
| FR-08 | 合成与成片验收 | `verify.py`、`report.py`、`adapters/remotion.py` | `lesson-smoke`、`lesson-blender-only` verdict pass | COMPLETED | — |
| FR-09 | 本地模型严格串行 | `shared/ai_runtime` | 22 个 ai_runtime 测试（含双进程、服务生命周期） | COMPLETED | — |
| FR-10 | 任务状态与恢复 | `tasks.py`、`job.py`、`--resume` | 失败落盘、断点续跑测试 | COMPLETED | — |
| FR-11 | 上下文预算 | `budget.py` + 各阶段预算 | 预算/超限/重试绕过测试 | COMPLETED | — |
| FR-12 | 在线内容审查 | `ContentQA/` | 11 个 mock 测试；真实课程 `blocked` exit 3 | PARTIAL | 真实供应商与凭据未配置 |
| FR-13 | 报告与可追溯 | 构建报告、manifest、任务记录、审查报告 | 各报告结构测试 | COMPLETED | — |
| FR-14 | 一键回归 | `scripts/check.ps1` | `check ok`，exit 0 | COMPLETED | — |

### 非功能需求（NFR）

| 编号 | 需求 | 状态 | 说明 |
| --- | --- | --- | --- |
| NFR-01 | 可复现 | PARTIAL | 夹具重复构建文件集合稳定（历史证据）；真实课程因缺导出未重复构建 |
| NFR-02 | 失败可见 | COMPLETED | 状态与 failures 一致 |
| NFR-03 | 隔离 | COMPLETED | 本机配置与产物均忽略 |
| NFR-04 | 路径安全 | COMPLETED | 绝对路径/反斜杠/`..` 被拒 |
| NFR-05 | 资源串行 | COMPLETED | 跨进程锁 + 单实例服务 |
| NFR-06 | 可中断 | COMPLETED | 锁释放、陈旧锁回收 |
| NFR-07 | 最小依赖 | COMPLETED | ai_runtime 零第三方依赖 |
| NFR-08 | 文档一致 | COMPLETED | 本轮再次核对计数、链接与 Schema |

### 验收条件（PRD §9）

| # | 条件 | 状态 | 证据 |
| --- | --- | --- | --- |
| 1 | `check.ps1` 打印 `check ok` | COMPLETED | 本地与干净工作树各一次 exit 0 |
| 2 | 单测真实通过且数量一致 | COMPLETED | 80 个用例（19+28+22+11） |
| 3 | 5 课程 + 11 场景契约 | COMPLETED | `check.ps1` |
| 4 | `lesson-smoke` 全链路 pass | COMPLETED | 真实 Blender + Remotion |
| 5 | 真实课程如实 `incomplete` | COMPLETED | `manual_export_required` |
| 6 | 本地模型串行有真实证据 | COMPLETED | 双进程竞争测试 |
| 7 | 在线审查 mock + 无凭据 blocked | COMPLETED | ContentQA 测试 + 真实课程 exit 3 |
| 8 | 预算测试通过并记录 | COMPLETED | 每次请求前检查并写任务记录 |
| 9 | 失败/阻塞/取消可读回 | COMPLETED | 任务记录终态 |
| 10 | 文档一致、无 P0 | COMPLETED | 本轮盘点 |

### OPEN 项

| 编号 | 事项 | 状态 | 说明 |
| --- | --- | --- | --- |
| OPEN-01 | Motion Canvas headless 导出 | DEFERRED | 人工节点是正式设计 |
| OPEN-02 | 真实课程内容补全 | BLOCKED | 4 页占位、3 页中文、8 段动画导出，责任在作者 |
| OPEN-03 | 在线模型供应商与凭据 | BLOCKED | 未配置；`blocked` 语义已实现 |
| OPEN-04 | Manim 接入课程 | DEFERRED | 无课程使用，不强行接入 |
| OPEN-05 | 完整 ContentQA（ASR/TTS/公式/语料） | OUT_OF_SCOPE | 本期只交付审查内核 |
| OPEN-06 | 多课程并行构建 | OUT_OF_SCOPE | 单机单用户，无需求 |

### 计数

| 类别 | 数量 |
| --- | --- |
| FR 已完成 | 11 / 14 |
| FR 部分完成 | 3 / 14（FR-04、FR-06、FR-12） |
| FR 未实现 | 0 |
| FR 阻塞 | 0（阻塞发生在 PARTIAL 项的子环节） |
| NFR 完成 | 7 / 8 |
| 验收条件完成 | 10 / 10 |
| OPEN：DEFERRED / BLOCKED / OUT_OF_SCOPE | 2 / 2 / 2 |

**不需要继续投入的事项**：OPEN-05、OPEN-06；OPEN-01/04 保持暂缓，除非出现明确课程需求。

---

## 3. 发现的冲突与偏差（未修改 PRD）

| 编号 | 冲突/偏差 | 证据 | 处理建议 |
| --- | --- | --- | --- |
| C-01 | 远程 `main` 含无关的 `django.yml` CI | `origin/main = 027e64d`；工作流引用 `requirements.txt`、`manage.py` | 在 GitHub 删除；如需 CI，另写本项目工作流 |
| C-02 | 本地 `main` 落后 `origin/main` 1 个提交 | `git status -sb` 显示 `[behind 1]` | 决定删除 django.yml 后 `git fetch && git reset --hard origin/main`（需人工确认） |
| C-03 | PRD FR-10 要求“产物存在且**校验通过**才算完成”；`stage_done` 只检查状态 + 文件存在 | `ModelingStudio/src/modeling_studio/job.py::stage_done` | 当前产物为 JSON/Markdown，无独立校验器；建议在 PRD 中把措辞改为“产物存在且可由后续阶段解析”，或补校验 |
| C-04 | `ManimSandbox/requirements.txt` 与 `pyproject.toml` 重复声明依赖 | 两个文件同时存在 | 保留 `pyproject.toml`，把 `requirements.txt` 降级为可选导出，或删除 |

---

## 4. 清理记录

### 已删除（可再生成）

| 路径 | 类型 | 大小 | 依据 |
| --- | --- | --- | --- |
| 16 个 `__pycache__/` | 字节码缓存 | ~950 KB | Python 自动生成 |
| `ManimSandbox/media/` | Manim 渲染缓存 | 803 KB | 可由 `uv run manim` 重建 |
| `ModelingStudio/workspace/*-sample-002.log` | 散落日志（3 个） | ~13 KB | 作业目录内已有逐阶段日志 |
| `RemotionStudio/public/staging/`（空目录） | 合成临时目录 | 0 | 合成时自动创建 |

### 保留（不作为“无用残留”删除）

| 路径 | 大小 | 原因 |
| --- | --- | --- |
| `build/` | 30 MB | 当前验收证据（截图、渲染、报告），可再生成 |
| `ModelingStudio/workspace/jobs/` | 5 MB | 历史作业与任务记录证据 |
| `.venv/`、`node_modules/` | ~1.6 GB | 运行依赖，删除后需重装 |
| `lessons/` | 本地 | 用户课程正文 |
| `docs/archive/` | 小 | 历史决策与证据 |
| `BlenderStudio/assets/*.blend`、`scenes/*.blend` | ~300 KB | 测试与渲染夹具 |
| `config/*.yaml`（本机） | 小 | 本机路径与凭据 |

### 待确认，未删除

| 路径 | 建议 |
| --- | --- |
| `build/lesson-*` 与 `build/01-shell-for-ai-era` | 归档或重新验收前可清空；命令：`Remove-Item -Recurse -Force build` |
| `ModelingStudio/workspace/jobs/{sample-001,sample-002,fallback-test}` | 如需保留作业证据先复制到仓库外 |
| `BlenderStudio/tasks/01-shell-for-ai-era/`（v1 历史夹具） | 文档仍引用，保留；若确定不再维护可归档 |

---

## 5. 复用与重复

- `docs/TRACEABILITY.md` 已收敛为索引，状态表以本文件为准。
- 规则只在 PRD / ARCHITECTURE / ACCEPTANCE 定义一次，其余文档引用。
- 未发现新的未登记模块或配置。
