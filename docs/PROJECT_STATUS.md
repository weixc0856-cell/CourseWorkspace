# 项目当前状态与 PRD 盘点

- **盘点日期**：2026-11-03
- **最近更新**：2026-11-07（E6.5 成片，见 §0.7）
- **代码基线**：本地 `main` = `8e45a68`；`origin/main` = `027e64d`
- **需求基准**：[PRD.md](PRD.md)（v1.0）
- **映射索引**：[TRACEABILITY.md](TRACEABILITY.md)；工作流见 [WORKFLOW.md](WORKFLOW.md)

状态词：`COMPLETED`（实现且有真实证据）/ `PARTIAL`（有缺口）/ `NOT_IMPLEMENTED` / `BLOCKED`（外部条件限制）/ `NOT_RUN` / `DEFERRED` / `OUT_OF_SCOPE`。

---

## 0. 2026-11-04 增量（P1–P4）

- **分支**：`feat/p1-teaching-primitives`（已推送，6 个提交）
- **范围**：三维教学基元、二维标注、字体、材质、科学着色、参数化曲面；**未改动任何课程正文**。

| 能力 | 契约 / 代码 | 证据 |
| --- | --- | --- |
| TEXT / CURVE / ORTHO | IR v2 §5.1.1、§6；`scene_system/` | 8 次真实渲染中的 `text-curve.png` |
| 二维标注 + 字体 | `storyboard.annotations` → `shots.json`；`overlays/Annotations.tsx`；Noto Sans SC（OFL） | `annotation-still.png`、`annotation-font-still.png` |
| 材质预设 / Coat / Bump | `scene_presets.py`、`assets/materials/presets/`、`scene.materials` | `materials.png` |
| 科学着色 | `scientific_colormap`、`shared/colormaps.json`、`scene.attributes` | `scientific.png` |
| 参数化曲面 | `shared/scene_expr`、`SURFACE`、`scene.surfaces` | `surface.png` |

当前计数：**9 合法 + 11 非法场景契约**，**8 次真实 Blender 渲染**，**112 个单测**（51+28+22+11）。

未做：课程内容（作者负责）、P5 真实数据导入（无数据源）、P6 AI 场景规划（待课程页输入）。

### 0.1 2026-11-06 代码会话增量

| 能力 | 代码 / 契约 | 证据 |
| --- | --- | --- |
| 会话契约 | `session.py`：SessionSpec / ExecutionResult / RecordingResult / EvidenceManifest / ValidationReport | `shared/schemas/session.schema.json`、`evidence.schema.json`；62 个 CourseControl 测试 |
| Docker 执行 | `session_runner.py`、`container_runner.py`、`course-tools:e1` | 无网络、非 root、只读根文件系统、cap-drop、资源限制 |
| 终端录制 | mintty + gdigrab `hwnd` | `build/lesson-smoke/code/shell_001/session.mp4`；V-23/V-24 |
| VS Code 会话（E2） | `CourseDemo/` 扩展、shell integration、`vscode_runner.py`、PrintWindow 录制 | `build/lesson-smoke/code/vscode_001/session.mp4`；V-23/V-24 |
| 旁白 V1 | `narrate.py`：VoxCPM2 单段合成、缓存键、meta、50000 锁、自动起停 | 真实 `smoke-001.wav`（48 kHz，1.76 s）与 `.meta.json` |
| Python 工具链（E3） | `offline_commands`、本地 HTTP 索引、`trim`、`check-python-session.ps1`、`check-python-network.ps1` | `python_001` / `python_network_001`：安装 + 离线验证；V-23/V-25 |
| Manim FFT 基线（E5） | `ManimSandbox/02-fft-baseline/fft_baseline.py` | `build/manim-fft/fft_baseline.mp4`：1920×1080 / 30fps / 7.8s |
| Rust 镜头（E4） | `rust-001` fixture、`check-rust-session.ps1` | host VS Code + Git Bash，`cargo run`；V-23/V-24 |
| Transformer 基线（E6） | `ManimSandbox/03-transformer-baseline/attention_baseline.py`、`04-transformer-explainer/`、`docs/E6-Transformer制作方案.md` | 四幕成片 33.1s（旁白 + 字幕 + manifest）；E6.1–E6.4 完成 |

当前计数：CourseControl 66 个单测；全套 127 个；场景契约仍为 9 合法 + 11 非法；8080 未被触碰。

### 0.2 2026-11-07 统一契约设计增量

| 文档 | 内容 | 状态 |
| --- | --- | --- |
| [架构审查-课程生产统一契约.md](架构审查-课程生产统一契约.md) | 现有课程/模块边界、重复实现、接口缺失、耦合、保留/调整建议 | 已完成审查，未改代码 |
| [课程生产统一契约V1.md](课程生产统一契约V1.md) | LessonSpec / ShotSpec / NarrationSpec / TimelineSpec / EvidenceManifest / RenderManifest；整数帧时间线；E6 manifest 兼容 | 已评审；V1-B 已实现 |
| [contracts/examples/](contracts/examples/) | Lesson / Shot / Narration / Timeline / Evidence / Render 示例 + E6 V0 迁移示例 | 示例 JSON，已做语法校验 |
| [E6.5-MultiHead设计.md](E6.5-MultiHead设计.md) | 两头算例、五 beat 分镜、旁白/字幕草案、维度清单、自动验收 | 设计稿，待评审 |

本轮只写文档与示例，未修改任何代码；CourseControl 66 个单测通过（2 个集成测试跳过）；E6.1–E6.4 未改动；8080 未触碰。决策记录见 [DECISIONS.md](DECISIONS.md) D-026。

### 0.3 2026-11-07 V1-B 实施增量

| 内容 | 文件 | 状态 |
| --- | --- | --- |
| 有理数帧率与整数时间换算 | `CourseControl/src/course_control/timecode.py` | 已实现；10 个测试 |
| V1 契约模型 | `CourseControl/src/course_control/contracts_v1.py` | 已实现；40 个测试 |
| V1 JSON Schema | `shared/schemas/*-v1.schema.json` | 7 份；与模型逐份比对 |
| V1 CLI | `schemas-v1`、`contract-v1-validate` | 已实现 |
| 实施报告 | [V1-B-实施报告.md](V1-B-实施报告.md) | 测试与兼容性说明 |

CourseControl 现为 **116 个用例（114 通过 + 2 跳过）**；全项目合计 177 个用例（175 通过 + 2 跳过）。跳过的 2 个不计为通过。未迁移 E6 manifest，未改 E6.1–E6.4，未触碰 8080。

### 0.4 2026-11-07 V1-C E6 只读适配增量

| 内容 | 文件 | 状态 |
| --- | --- | --- |
| E6 V0 只读适配 | `CourseControl/src/course_control/legacy_e6.py` | 已实现；V0 与媒体未改 |
| `e6-adapt` CLI | `CourseControl/src/course_control/cli.py` | 已实现；失败检查 exit 1 |
| 自动检查 | ffprobe + sha256 + SRT 解析 | 本地 36 条：35 pass + 1 not_applicable |
| 适配器测试 | `CourseControl/tests/test_legacy_e6.py` | 12 个；本地集成测试执行，干净克隆显式 skip |
| 实施报告 | [V1-C-实施报告.md](V1-C-实施报告.md) | 测试与兼容性说明 |

CourseControl 现为 **129 个用例（127 通过 + 2 跳过）**；全项目合计 190 个用例（188 通过 + 2 跳过）。E6 V0 `manifest.json` 仍为 `43037d39…` 未被修改；E6.1–E6.4 未改；8080 未触碰。V0 人工 `checks` 只进入 `legacy.manual_checks`，`manual_checks_trusted=false`。

### 0.5 2026-11-07 E6.5 数学验证

| 内容 | 文件 | 状态 |
| --- | --- | --- |
| 两头算例唯一数据源 | `ManimSandbox/05-multi-head/multi_head_math.py` | 纯标准库；无 numpy/Manim |
| 独立计算脚本 | `ManimSandbox/05-multi-head/verify_math.py` | exit 0；30 条检查全 pass |
| 单元测试 | `ManimSandbox/tests/test_multi_head_math.py` | 8 个用例 |
| 验证报告 | [E6.5-数学验证报告.md](E6.5-数学验证报告.md) | 形状、alpha 行和、头差异、concat、W_O |

全项目现为 **198 个用例（196 通过 + 2 跳过）**。E6.5 数学算例已验证，可进入 `MultiHeadScene` 视觉编码；尚未生成旁白/字幕/成片。

### 0.6 2026-11-07 E6.5 视觉场景

| 内容 | 文件 | 状态 |
| --- | --- | --- |
| MultiHeadScene | `ManimSandbox/05-multi-head/multi_head.py` | 已创建并真实渲染 |
| 视觉成片 | `build/manim-multi-head/e6.5/media/videos/multi_head/1080p30/MultiHeadScene.mp4` | 1920×1080 / 30fps / 1504 帧 / 50.129s；仅视频 |
| 渲染报告 | [E6.5-视觉渲染报告.md](E6.5-视觉渲染报告.md) | 五 beat、抽帧核对、未做旁白/字幕 |

场景从 `multi_head_math.py` 读取全部矩阵，未另写算例。E6.1–E6.4 未改；8080 未触碰。

### 0.7 2026-11-07 E6.5 旁白、字幕与成片

| 内容 | 文件 | 状态 |
| --- | --- | --- |
| 5 段中文旁白 | `build/manim-multi-head/e6.5/narration/segments/e65-b*.wav` | VoxCPM2 真实合成；48 kHz mono |
| 混合旁白 | `build/manim-multi-head/e6.5/narration.wav` | 86.929 s；按 beat 起点放置 |
| SRT | `build/manim-multi-head/e6.5/subtitles.srt` | 10 条；均在 beat 内 |
| 最终成片 | `build/manim-multi-head/e6.5/final.mp4` | 1920×1080 / 30fps / 2608 帧 / 86.929s；视频+音频+字幕 |
| 自动检查 | `build/manim-multi-head/e6.5/manifest.json` | 14 条全 pass；`all_ok: true` |
| 成片报告 | [E6.5-成片报告.md](E6.5-成片报告.md) | 旁白/字幕/mux/检查 |

全项目现为 **201 个用例（199 通过 + 2 跳过）**。TTS 50000 调用前已 ready，本次复用，未启动/停止他人服务；未触碰 8080。

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
| FR-05 | IR v2 场景任务 | `blender_scene.py`、`blender_runner.py`、`scene_system/`、`scene_presets.py`、`shared/scene_expr` | `check-scene-system.ps1 -Render` 8 次真实渲染；51 个 CourseControl 测试（2026-11-04 新增 TEXT/CURVE/ORTHO、材质预设、科学着色、参数化曲面与语义验收） | COMPLETED | — |
| FR-06 | 本地自动建模 | `ModelingStudio/` | 28 个测试；历史作业 `sample-001` 六阶段 completed | PARTIAL | 真实全链路本轮未重跑（需独占 8080） |
| FR-07 | 时间线收集 | `collect.py`（含 `annotations[]`） | `lesson-smoke` shots.json 通过 verify；V-22 标注检查 | COMPLETED | — |
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
| 2 | 单测真实通过且数量一致 | COMPLETED | 127 个用例（66+28+22+11） |
| 3 | 5 课程 + 20 场景契约 | COMPLETED | `check.ps1` |
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
