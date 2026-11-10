# 迁移计划（Migration Plan）

- 日期：2026-11-10
- 范围：Production Stabilization R0–R5
- 原则：先删错误权威，再补可靠性，再做画面；不重写所有课程，不新增平行实现
- 关联：[PRODUCTION_CONTRACT.md](PRODUCTION_CONTRACT.md)、[QUALITY_STATE_MACHINE.md](QUALITY_STATE_MACHINE.md)、[ANIMATION_QUALITY_MODEL.md](ANIMATION_QUALITY_MODEL.md)、[DELIVERY_CONTRACT.md](DELIVERY_CONTRACT.md)

---

## 0. 批次状态

| 批次 | 内容 | 状态 | 证据 |
| --- | --- | --- | --- |
| R0 | 基线与保护 | **完成** | `check.ps1` exit 0；585 用例；工作树未提交品牌改动未触碰 |
| R1 | C-01 生产契约 | **部分完成** | `plan-audit`、`--storyboard-source director`；05 的 Page 权威声明与 01/05 迁移未做 |
| R2 | C-02/C-03 质量状态机 | **完成** | D-071 落地；`VERIFY_*`；`release-approve`；nvda gate 不再放行 |
| R3 | C-04 动画评分 | **完成** | 05 100→84.7；无相机 0 分；无 media-qc freeze 0 分 |
| R4 | C-05/C-06/C-10 交付与 QC | **完成** | run_id；package/package-verify；Manim/Blender 共用 `verify_media` |
| R5 | C-07/C-08/C-11/C-12 | **部分完成** | 06 字幕重排与单语声明；V-31 覆盖 Remotion；证据检查；状态文档更新；01 字幕已重排/接受，构建中 |

## 1. R0 基线

- 记录：`docs/audit/` 七份；`docs/stabilization/` 五份。
- 实跑：六套单测 585（579 通过 + 6 跳过）；`check.ps1` exit 0。
- 保护：未提交的 `BrandIntro/`、`CodeVideoStudio/shots/brand-*`、`docs/品牌片头-3D桌面戏-设计.md` 未改动；`lesson.yaml` 只改了 06 的 `subtitles.bilingual: false`。
- 产物：`build/audit-frames/`（抽帧）、`build/audit-check.log`、`build/.audit/missing-evidence.txt`。

## 2. R1 生产契约

### 已做

- `plan-audit`：只读输出 mode/authority/计数/mismatches。
- `build --storyboard-source director`：显式读取 `build/<slug>/director/storyboard.director.yaml`；缺失即失败。
- 文档明确：deck/scene 的 Page 是权威；shots 的 Shot 是权威；导演计划/节拍表是视图。

### 未做

1. **05 的 Page 权威声明**：05 的 storyboard 是 1 个 292 秒镜头；导演计划 3 个、beats 27 个条目。需要在 `lesson.yaml` 或 `docs/PROJECT_STATUS.md` 明确"27 条是内部动作，不是可独立重渲染镜头"；或者把 `attention_5min.py` 拆成 3 个类。
2. **01 的迁移**：storyboard 5 个 vs 导演计划 12 个。01 的完整构建应先用 storyboard（默认），不要用 director，除非先验证 12 个镜头都能独立渲染。
3. **producer-rebuild**：已改为打印 `--storyboard-source director`；仍需在 05 上做一次真实局部重渲验证。

### 验收

- `plan-audit --lesson 06` = `mismatches: none`。
- `plan-audit --lesson 05` 明确列出 27/3 与 1 的差异，且不影响 build。
- 05 文档不再出现"27 个独立镜头"的表述。

## 3. R2 质量状态机

### 已做

- `quality.py`：`BUILD_PASS`、`VERIFY_PASS`、`VERIFY_WARN`、`VERIFY_INCOMPLETE`、`VERIFY_FAIL`、`QUALITY_VERIFIED`、`REVIEW_APPROVED`、`RELEASE_APPROVED`。
- `quality_gates.py`：`incomplete_checks`；`decide` 的 `releasable` 不放过 incomplete；`grammar_warnings` 单独报告。
- `release-approve --stage review|release`：写入带哈希的签核记录；release 需要 review 先批准。
- `quality-report` 输出所有状态。
- 05 的 `QUALITY_PASS=True` 仍保留，但语义是"没有 INCOMPLETE"；`QUALITY_VERIFIED=False`。

### 未做

- 05/01 的人工 review/release 签核（需要人）。
- `producer state` 与 `quality states` 的合并；目前两套状态并存，producer 只报告交付清单。

### 验收

- nvda：`quality-gate` = `verification: incomplete`，`releasable: no`。
- 05：`quality-gate` = `verification: pass`，但有 4 个 WARN；`RELEASE_APPROVED=false`。
- `release-approve --stage release` 未批准 review 时 exit 2。

## 4. R3 动画评分

### 已做

- `beats.py` 的 `validate_sheet_report`：结构错误 vs 创作 warning。
- `CameraMove.motive` 不再 schema 失败；`BeatShot.beats` 允许 1 个动作。
- `animation_score`：无相机 0 分；freeze 对所有 grammar 计分；无 media-qc 时 freeze 0；creative warnings 不归零 gates。
- 05 84.7，06 99.0；05 的 freeze 9.7/15。

### 未做

- 05 的构图与画面运动提升（这是 R5/质量阶段，不是评分）。
- 冻结阈值的重标定；当前 9 段/分钟来自自家样片，不是普适标准。

### 验收

- 60 秒静止 + 满 beats 的样例分数不接近 100。
- 无相机样例 `camera=0`。
- 长寿命不足只 warning，`gates=15`。

## 5. R4 交付与 QC

### 已做

- `Artifact.sha256`、`BuildReport.run_id`；`report.py` 计算哈希。
- `package` / `package-verify`：必需/可选、`not_applicable`、哈希、manifest、checklist。
- `verify_media`：Manim/Blender 统一检查分辨率/帧率/时长；Motion 原有；CodeVideo 原有。
- Blender 增加输出缓存与 MP4 收尾等待：Windows 上 Blender 父进程可能先退出、子进程仍在写 `moov`；脚本现在等文件大小稳定，缓存用 ffprobe 验证，坏文件会自动重渲。
- `run_command` 改为临时文件重定向 + `Popen.wait`：Blender/Remotion 的子进程会继承管道，旧的 `subprocess.run(capture_output=True)` 会在父进程退出后继续等待，导致构建挂起。超时或 Ctrl-C 时用 `taskkill /T` 杀进程树。
- 新增 `BuildLock`（`runtime/locks/build-<slug>.lock`）：同一门课只允许一个 build，避免两个 build 同时改写 `public/staging/<slug>/` 导致 Remotion 读到半套素材。
- ContentQA `run_id` 加入 task_id 与 review.json；旧记录不被覆盖。

### 未做

- 05/06 已重新构建，`build-report.run_id` 与 artifact `sha256` 已写入；旧报告仍可能没有，package 会用 `-package` 兜底。
- Blender 的 PNG 输出只检查文件存在，不检查尺寸；v1 课程镜头目前没有 PNG 输出。
- `package` 还没有把 `build-report` 里的 artifact 哈希与包内哈希交叉核对；两者都从同一文件计算，暂可接受。

### 验收

- 05/06 `package` 成功，`package-verify` 通过；01 失败且列出缺项。
- 篡改包内文件，`package-verify` 报 hash mismatch。
- 连续两次 ContentQA，`runtime/tasks/` 保留两套 task_id。

## 6. R5 字幕、证据、状态

### 已做

- 06 的 `subtitles.bilingual: false`；SRT 已按标点/词边界重排（67 行），V-31 对 Remotion 字幕执行并通过。
- 01 的 357 cue 草稿已重排/拆分为 359 条并 `subtitles-accept`；Blender `stack_explode` 已渲染；20 分钟成片已产出（1195.605 s，verdict=pass）。
- `V-31` 覆盖 `render: remotion`；不再写"subtitles disabled"。
- `subtitles-rewrap` 命令；中文断行不拆常用词、不以标点开头；英文按词边界。中文行宽按显示宽度计（CJK=1，拉丁/数字=0.5，空格=0），避免 `Transformer` 这类长词把一行算成 17 个字。
- `scripts/check_evidence.py` + `check-evidence.ps1`；`check.ps1` 非阻断运行，报告 178 个引用、88 个缺失。
- `PROJECT_STATUS.md` / `ACCEPTANCE.md` 增加 2026-11-10 基线。

### 未做

1. **01 的完整构建**：**已完成**。单一 build + 清理后，01 输出 1195.605 s / 1080p30，build-report `verdict=pass`；C-30 的根因是同课并发 build 覆盖 staging，已用 `BuildLock` 修复。
2. **05 的已批准 SRT**：V-31 通过；本轮未重排，避免改动已验收的字幕。
3. **02 的证据**：22 分钟成片不在 build；只能重跑或接受"历史记录"。
4. **88 个缺失路径**：`build/.audit/missing-evidence.txt` 列出了 88 个；关键 POC 证据应归档或从文档中移除引用。

### 验收

- 06 `verify` 的 V-31 pass；`build-report` 重建后 V-31 不再是 `not_applicable`。
- 01 的 SRT 重排后 V-31 在真实构建中 pass；人工批准。
- `check_evidence` 的缺失数下降，且关键路径有归档或说明。

## 7. 兼容与回滚

- 所有新命令都是增量：`plan-audit`、`package`、`package-verify`、`release-approve`、`subtitles-rewrap`。
- `quality-report` / `quality-gate` 新增字段，不删旧字段；旧读者仍可读 `QUALITY_PASS` / `releasable`。
- `beats` 的模型放宽（motive、1 个动作）不会让旧 sheet 失效；旧 sheet 只是从 error 变 warning。
- 回滚单个批次：
  - R2：恢复 `quality.py` 的 `QUALITY_PASS` 计算与 `quality_gates.decide` 的旧 `releasable`；
  - R3：恢复 `validate_sheet` 的硬失败与 `camera=1.0`/`freeze=1.0`；
  - R4：删除 `package.py` 与 CLI 命令；
  - R5：恢复 06 的 `bilingual` 默认与 SRT 原文（Git 可回滚）。
- 不迁移课程正文；只改 06 的格式级声明与字幕行宽。

## 8. 需要所有者批准的事项

1. 05 选择"Page 权威"并保留 1 个 292 秒镜头，还是拆成 3 个可独立渲染的 Manim 类？
2. 01 先用 storyboard（5 镜头）完整构建，还是先验证导演计划的 12 镜头？
3. 05/01 的人工 review 与 release 由谁签核？签核前不写 `review-approval.json`。
4. 是否接受 05 的已批准 SRT 不重排（V-31 已 pass），只对 01 做重排？
5. 88 个缺失证据路径：归档关键 POC，还是从文档中移除引用？
6. 是否把 `producer` 的 delivery manifest 与 `package` 合并？当前建议保留两套，避免一次性大改。

## 9. 下一批次的完成定义

- 01 的 SRT 重排 + 批准 + 完整构建；`verify` 的 V-31 pass。
- 06 已重建：`build-report.run_id` 非空，V-31 pass，`package` 使用新 run。
- 05 的 `plan-audit` 差异被文档明确解释，不再出现"27 个独立镜头"。
- 至少一门课完成 `review-approve` + `release-approve`（可以是样片，不要求正式发布）。
- `check.ps1` 仍是 exit 0；新增测试全部通过。
