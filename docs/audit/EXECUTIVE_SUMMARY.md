# 执行摘要（Executive Summary）

> 状态说明（2026-11-10 稍后）：本文件保留当时结论；问题状态与修复证据见 [../stabilization/MASTER_REMEDIATION.md](../stabilization/MASTER_REMEDIATION.md)。

- **审计日期**：2026-11-10
- **完整报告**：[PROJECT_REALITY_AUDIT.md](PROJECT_REALITY_AUDIT.md)、[ARCHITECTURE_CONFLICTS.md](ARCHITECTURE_CONFLICTS.md)、[AUTOMATION_CAPABILITY_MATRIX.md](AUTOMATION_CAPABILITY_MATRIX.md)、[SUPPORTED_CAPABILITIES.md](SUPPORTED_CAPABILITIES.md)、[OUTPUT_QUALITY_ASSESSMENT.md](OUTPUT_QUALITY_ASSESSMENT.md)、[NEXT_STAGE_ROADMAP.md](NEXT_STAGE_ROADMAP.md)

> **2026-11-10 落实状态**：本轮已实施 C-02（D-071）、C-03（VERIFY/RELEASE 分离）、C-04（去掉免费分）、C-05（run_id）、C-06（package）、C-07/C-08（06 字幕重排与单语声明）、C-10（Manim/Blender 媒体校验）、C-11（证据检查）、C-12（状态同步）。C-01 只做了 `plan-audit` 与 `--storyboard-source`，05/01 迁移未做；01 完整构建仍未执行。详见 `docs/stabilization/MIGRATION_PLAN.md`。

---

## 1. 项目现在究竟做到什么程度？

**工程骨架成熟，产品交付未成熟。**

- 六套单测 585 个用例（579 通过 + 6 跳过），`check.ps1` exit 0；契约、适配器、跨进程锁、路径安全、失败落盘、报告都可维护。
- 真实成片 5 支：05（4:52）、06（1:02）、nvda（5:54）、aging（2:25）、品牌交付（5:07）。最长 5:54。
- 20 分钟课程：01 的 12 页截图、7 个已渲染 Manim 文件（storyboard 使用其中 4 个）、1195.6 秒旁白、359 条字幕、Blender 镜头已完成；成片 1195.605 s / 1080p30，verdict=pass（C-30 已修复）。02 的 22 分钟成片只有文档记录，产物已不在。
- 结论：它是**可复现的课程样片工厂**，不是已经稳定的长课生产线。

## 2. 最有价值的现有能力是什么？

1. **确定性的构建与证据链**：`build-report.json` + 适配器 + 失败语义 + Schema 同步，让"哪里失败、为什么失败"可读。
2. **本地模型串行调度**：`shared/ai_runtime` 的跨进程锁、服务生命周期、任务记录、预算，是全项目质量最高的模块。
3. **镜头级 CodeVideo**：`SPEC.md` + `frame(t)` + capture + contact sheet + QC，让任意 HTML/Canvas/Three.js 镜头可复现。
4. **已经完成 90% 的 01 素材**：这是最快兑现"20 分钟课程"的资产。
5. **新闻事实底账**：nvda 的一手来源、事实/报道/判断三分，是可复制的内容方法。

## 3. 最大的三个问题是什么？

1. **20 分钟课程刚刚首次交付。** 01 已产出 1195.605 s / 1080p30 成片，build-report pass；仍需人工看片与 review/release 签核，不能直接发布。
2. **质量门禁曾给出虚假的安全感，本轮已修但画面仍未变好。** D-071 已落地；05 的分数从 100 降到 84.7（无相机 0 分、冻结 9.7/15）；nvda 的 `INCOMPLETE` 已阻断发布；`release-approve` 要求 review + release 两次签核。但 05/06 的画面仍然稀疏，门禁只能证明"检查跑了"，不能证明"讲得好"。
3. **视觉生产仍是手写。** 每个 Manim/CodeVideo 镜头由人写 150–1,600 行代码；06 的 62 秒记录了每镜 1–5 次返工；没有任务记录证明 Agent 生成过镜头画面。自动化的是渲染，不是美术。

## 4. 自动化目前能做到什么程度？

| 维度 | 等级 |
| --- | --- |
| 给定场景的渲染、TTS、合成、媒体 QC | **A3**（异常需人） |
| 已批准内容 → 成片 | **A2–A3** |
| 来源 → 成片 | **A1–A2** |
| 多课并行 / 夜间无人值守 | **A0–A1** |
| 稳定无人值守（A4） | **没有环节达到** |

- 20 分钟 TTS 约 3.2 小时（实测 9.6× 实时）；5 分钟 compose 约 6 分钟；06 的 62 秒约 1 小时机器 + 数小时人工。
- 失败恢复靠缓存重跑，没有顶层 resume/调度。
- 人工介入：每镜 1–5 次返工；每课至少 3 次批准（内容、字幕、发布）。

## 5. 当前输出质量能达到什么程度？

| 产物 | 综合（1–5） | 一句话 |
| --- | ---: | --- |
| 05 Transformer 5 min | 3.0 | 结构清楚、画面稀疏的合格讲解 |
| 06 Attention 62 s | 2.8 | 视觉一致，但关键帧太淡、概念有一处过度简化 |
| nvda GPU 新闻 | 3.0 | 内容可信，画面是 PPT |
| aging 3D | 2.9 | 技术 POC，美术未到成片 |
| 品牌 2D | 4.0 | 接近专业频道片头 |
| 品牌 3D | 1.8 | 灰盒角色，未过自己的 Gate |

- 稳定水平 3/5；偶发 4/5；5/5（3B1B 级连续图解、声音设计）达不到。
- 技术通过 ≠ 质量通过：文件完整、时间轴连续、音轨存在都能证明；"讲得对、看得下去、听起来自然"不能。

## 6. 下一阶段最值得做的五件事

1. **01 已交付，补人工看片与签核**：成片已产出；下一步是 review/release 签核与构图/声音人工验收。
2. **让质量门禁说真话**（1–2 天）：D-071 落地；`QUALITY_PASS` 拆义；`incomplete` 不可发布；去掉永远给满的分量；新增 `release-approve`。
3. **重切字幕**（2–3 天）：按标点/词边界切，修 01/05 的断词；06 补响度到 -16 LUFS；V-31 覆盖 Remotion 字幕。
4. **补齐交付包**（2–3 天）：build-report 加 sha256/run_id；`course-control package` 生成完整包；缺项即失败。
5. **做一次构图 pass**（3–5 天）：05/06 的主体放大、减少空白、把 06 的 38 s 边线做实；用"看片"验收，不加自动门禁。

**应该停止**：新增 grammar/评分层、新渲染后端、4K 整课、品牌 3D 美术探索、用 automation % 当目标。

---

## 一句话

项目已经能"可靠地做出一支 5 分钟的视频"，但还不能"交付一门 20 分钟的课"。下一阶段的胜负手不是更多架构，而是**把 01 交付出来，并让"通过"重新等于"真的通过"**。
