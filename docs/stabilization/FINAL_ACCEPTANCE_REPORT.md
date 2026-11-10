# 最终验收报告（FINAL_ACCEPTANCE_REPORT）

- 日期：2026-11-10
- 范围：V1 全量修复与生产体系收敛（R0–R6）
- 结论：工程与端到端生产通过技术验收；**发布批准仍由所有者决定**，视觉与内容未代签。

## 1. 结果摘要

| 项目 | 结果 |
| --- | --- |
| 全量回归 | `scripts/check.ps1` = `check ok`，exit 0 |
| 单测 | 六套 636 个用例：630 通过、6 跳过（CourseControl 489 / ModelingStudio 33 / ai_runtime 50 / ContentQA 25 / Manim 18 / KnowledgeStudio 21） |
| Remotion 类型检查 | `tsc --noEmit` exit 0 |
| 端到端生产 | 06-attention-sample 在隔离 build root 完整构建：`verdict=pass`、62.167 s、11 个阶段、V-10..V-44 无 fail |
| 故障恢复 | 真实失败 → `--resume` → 复用阶段 → 通过；见 §3 |
| 配置权威 | 05/06/01/nvda 实跑 `config-resolve`，无 blocking 冲突；01 的 4.39 s 目标偏差有书面解释 |
| 字幕 QC | 06 PASS；05/01 WARN（行首标点、英文悬空介词），无结构错误 |
| 证据分类 | 引用 182、缺失 90、已分类 90、未分类 0 |
| 资产 | 06 交付包 `external_assets` 打包成功，`package-verify` = package ok |
| vendor | `vendor-check` = vendor ok；three.js 5 份副本降为 1 份 |
| 镜头能力 | 8/8 类型有 SPEC + VERIFY 样片；`shot-taxonomy` exit 0 |
| 问题台账 | C-01～C-30 全部有裁决；新增 C-31/C-32 已修复并验证 |

## 2. 全量回归

```text
scripts/check.ps1
  fixtures / toolchain / path hygiene / evidence paths / vendor / taxonomy / blender task
  unit tests: CourseControl, ModelingStudio, ai_runtime, ContentQA, ManimSandbox, KnowledgeStudio
  remotion typecheck
  lesson validate + director plan + scene contracts + session contracts
  → check ok (exit 0)
```

- CourseControl 489 用例包含本轮新增：配置解析、检查点、resume、超时、字幕 QC、审查裁决、资产寻址、Blender 任务、legacy 登记、vendor、stats、镜头分类、render props 路径。
- 未通过的用例：无。跳过 6 个，均为 Docker/录制等环境依赖，不计为通过。

## 3. 故障注入与恢复

真实执行序列（隔离目录 `build/_stabilization/06-attention-sample`）：

| 轮次 | 注入/故障 | 系统行为 | 结果 |
| --- | --- | --- | --- |
| 1 | `attn-*` 镜头缺 `node_modules` junction，capture 报 `ERR_MODULE_NOT_FOUND` | `render:code_video` fail；上游 `render:manim` 写入检查点；下游标记 not_run | fail，日志保留 |
| 2 | `--resume` | 复用 `render:manim`；重跑 `render:code_video`、`collect`；compose 因 `--build-root` staging 路径缺陷失败 | 暴露 C-31 |
| 3 | `--resume-from compose` | 复用 `render:manim`、`collect`；重跑 code_video（输入清单新增 vendor 哈希）与 compose；compose 成功 | 暴露 render props 路径问题 |
| 4 | `--resume` | 复用 `render:manim`、`render:code_video`、`collect`、`compose`；只运行 verify | **pass** |

证据：

- `build/<root>/runtime/last-run.json`：`resume.reused` 与 `invalid` 原因逐条记录。
- `build/<root>/final/build-report.json`：`resumed=true`、`reused_stages` 四项、`config_fingerprint`。
- 检查点文件：`runtime/checkpoints/render-manim.json`、`render-code_video.json`、`collect.json`、`compose.json`。

结论：resume 不是"标记完成即跳过"；输出、输入或配置变化都会重跑。C-31/C-32 是本轮端到端暴露并修复的真实缺陷。

## 4. 端到端生产（06）

- 命令：`course-control build --lesson 06-attention-sample --build-root build/_stabilization/06-attention-sample --resume`
- 结果：`verdict=pass`；`final/course-video.mp4` 4,852,781 bytes；时长 62.167 s。
- 阶段：config、validate、capture_slides(N/A)、motion(N/A)、manim、blender(N/A)、code_video、collect、compose、brand(N/A)、verify 全部 pass 或 N/A。
- 检查：V-42、V-43、V-44 首次进入真实构建并通过；V-14 62.167 s；V-15 音画差 0.020 s；V-27 时长策略 pass；V-31 字幕完整；V-16 14 cue。
- 构建日志：`build/_stabilization/06-build.log`、`06-build-resume.log`、`06-build-compose.log`、`06-build-compose3.log`、`06-build-final.log`。

未执行：人工看片与发布签核；媒体 QC 的完整抽帧审看。技术 pass 不等于作品合格。

## 5. 配置、字幕、资产证据

### 5.1 配置

| 课程 | blocking 冲突 | 关键结论 |
| --- | --- | --- |
| 05 | 0 | target 293 / measured 292.38 / timeline 292.37 有唯一解释 |
| 06 | 0 | `bilingual: false` 与 SRT 单语一致 |
| 01 | 0 | measured 1195.61 与 target 1200 偏差 4.39 s，warning；实测权威 |
| nvda | 0 | news 无 BGM；ASR 未跑仍为 incomplete |

### 5.2 字幕

| 课程 | V-44 | 主要发现 |
| --- | --- | --- |
| 06 | PASS | 14 cue，语言、时间、行宽、术语均通过 |
| 05 | WARN | 行首标点、英文 cue 以 `it/for/to` 结尾；无结构错误 |
| 01 | WARN | 359 cue；行首标点、英文悬空介词；无越界、无缺失语言 |

未删除任何 cue 来提高覆盖率。

### 5.3 资产与交付包

- 05 包：54 个文件；`referenced_assets` 记录 BGM 与声线参考的 `asset_id`、来源、SHA-256。
- 06 包：19 个文件；外部声线参考打包到 `assets/external/719ce803-my_voice_clean_v1.wav`，`external_assets[0].sha256=745f569b4f…`；`package-verify` = package ok。
- `vendor-check`：brand-intro、brand-desktop、primer-aging、primer-hero、primer-rps 全部与 `CodeVideoStudio/vendor/three/three.module.js` 一致。

## 6. 问题裁决

- C-01～C-30：VERIFIED 22、FIXED 4、OPEN 4（C-16、C-25、C-26、C-28，均为所有者/视觉验收阻塞；详见 `MASTER_REMEDIATION.md`）。
- C-31 自定义 build root 的 staging 路径错误：已修复并实测。
- C-32 CodeVideo 镜头缺 Playwright junction：`setup.ps1` 已补建链，06 从 fail 变 pass。

## 7. 未完成与阻塞

| 项 | 原因 | 需要 |
| --- | --- | --- |
| C-16 品牌 2D/3D 统一 | 3D 美术未过 Gate 3；未改生成物 | 所有者视觉验收 |
| C-25 06 内容矛盾 | 标题、因果遮罩表述属课程正文 | 所有者批准后修改 |
| C-26 新闻片密度 | 需改版式与正文 | 所有者批准 |
| C-28 品牌工作提交 | 未跟踪目录归所有者 | 所有者决定提交/丢弃 |
| C-07 05 已批准 SRT | 保持已验收版本，仅报 WARN | 所有者决定是否重排并重新验收 |
| C-20 20 分钟长片中断注入 | 已用 06 完成真实注入；01 成本高 | 下一次 01 构建时执行 |
| 人工看片 / RELEASE_APPROVED | 程序不得代签 | 所有者 |

## 8. 复现

```powershell
# 全量回归
.\scripts\check.ps1

# 配置
uv run --project CourseControl course-control config-resolve --lesson 05-transformer-5min

# 字幕
uv run --project CourseControl course-control subtitles-qc --lesson 06-attention-sample

# 镜头能力
uv run --project CourseControl course-control shot-taxonomy --workspace .

# 证据
uv run --project CourseControl python scripts/check_evidence.py --workspace .

# 端到端（隔离目录，不覆盖正式产物）
uv run --project CourseControl course-control build --lesson 06-attention-sample `
  --build-root build/_stabilization/06-attention-sample --resume

# 交付包
uv run --project CourseControl course-control package --lesson 06-attention-sample
uv run --project CourseControl course-control package-verify --package build/06-attention-sample/package
```

## 9. Git

本轮修改未提交。工作树包含：课程契约与配置声明、15 个新模块、13 个新测试文件、11 份 stabilization 文档、vendor 重构与探针迁移。`lessons/` 只增加 `build.storyboard_source`，未改课程正文。

提交前请复核：

```powershell
git status
git diff --stat
```

`CodeVideoStudio/shots/brand-*` 仍为未跟踪的用户资产，本轮未删除、未提交。
