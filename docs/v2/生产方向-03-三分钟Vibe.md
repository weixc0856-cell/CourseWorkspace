# 生产方向 03：3 分钟 Vibe / 知识动画

- **日期**：2026-11-14
- **定位**：2–4 分钟的微型知识作品；音乐驱动、视觉驱动、程序化画面为主。不是课程切片，也不是新闻片。
- **当前实例**：`fengshui-wind-water`（2:32，1080×1920，无旁白，英文大字 + 中文字幕，CC BY 音乐）；`compound-interest`（2:32，竖屏 3D）；`xhs-plasma-etch`（2:32，竖屏）；`diesel-4-stroke-diagram`（108 s）；`whale-maid`。
- **共同点**：一条片子只讲一个点；画面承担主要表达；音乐与节拍决定节奏；交付质量是唯一门禁。

---

## 1. 这条线要解决什么

三分钟不意味着内容简单，也不意味着画面可以简陋。它要求：

- 一个足够具体的问题；
- 一个能记住的核心结论；
- 一次完整的机制解释；
- 一个真实案例或空间；
- 一条明确的认知边界；
- 一套有空间、有构图、有运动的视觉语言。

它不应该像“讲解稿配动态插图”，也不应该靠转场、粒子、光效和 BGM 把平庸画面变热闹。

素材引用不设准入：新闻画面、档案、书图、论文图、截图都可以用；只保留“不伪造、不错配来源、不改原声语义”三条红线。音乐作为背景使用时，许可与署名按 D-097 记录，属于交付/法律检查，不是“能不能引用”的内容准入。

## 2. 产品单位与格式

| 项 | 默认 | 说明 |
| --- | --- | --- |
| 时长 | 2:00–4:00 | 由内容决定；不设秒数门禁 |
| 画幅 | 竖屏 1080×1920（社交）或横屏 1920×1080（YouTube） | 项目级声明，不全局强制 |
| 帧率 | 30 fps | 与现有 Remotion / Blender 输出一致 |
| 旁白 | 有旁白为默认；无旁白是显式变体 | 风水频道目前是“无旁白”，属于已登记例外 |
| 字幕 | 英文在上、中文在下 | 与 D-084 一致；引文例外见风水频道规则 |
| 音乐 | PD / CC0 / CC BY；CC BY 必须署名 | 许可与电平是交付/法律检查，不是风格门禁 |
| 声音 | 旁白 / 音乐 / 音效 / 环境声四层 | 由 `sound_design.json` 记录 |

`fengshui-wind-water` 目前是“无旁白 + 英文大字 + 中文字幕”。评审建议的“旁白讲解 + 三层声音”与这个系列规则冲突；要么改系列规则（所有者决定），要么保持无旁白，用画面和字幕承担解释。本文不替所有者改系列规则。

## 3. 一个点，不是三个点

评审建议“2–3 个结论”。本项目已有的偏好是“一条片子只讲一个点”。两者可以合并为：

- **一个核心点**：观众看完能复述的一句话。
- **2–3 个支撑结论**：同一个点的不同侧面，不是三个并列主题。
- **一个机制**：至少一个完整的因果/空间解释。
- **一个案例**：真实地理、建筑、器物或数据。
- **一条边界**：哪些能解释，哪些不能。

如果第二句出现的是另一个主题，砍掉或另开一集。

## 4. 结构

默认五幕，对应 `narrative-validate` 的六段骨架（3 分钟属于长视频，不走 30–90 秒 Shorts 规则）：

| 幕 | 任务 | 画面 |
| --- | --- | --- |
| 1 建立 | 一个空间/物件/问题，先让观众进入 | 远景建立，空间关系 |
| 2 追问 | 提出一个具体问题，给出已知的一半 | 中景推进，关键细节 |
| 3 机制 | 用动画解释因果/空间/结构 | 三维剖视、流场、关系图 |
| 4 边界 | 哪些成立、哪些不能由此推出 | 对照、回退、标注 |
| 5 收束 | 回到开头，给一句可带走的话 | 回到建立镜头，留白 |

**不是秒数模板。** 2 分钟的片子可以三幕；4 分钟的片子可以给机制两段。

## 5. 视觉：四个空间层，三种动画语言

### 5.1 四个空间层

每一个主镜头至少考虑：

1. **前景**：树枝、岩石、屋檐、近处水面，提供空间参照。
2. **中景**：村落、建筑、河道、器物，是叙事对象。
3. **远景**：山脉、天空、云雾，建立尺度。
4. **运动层**：云雾、流水、树木、光线、空气流动，让场景不是壁纸。

落到 `authoring/visual-design.yaml` 的 `composition.depth_layers`：

```yaml
composition:
  focal_object: valley_village
  focal_point: [0.42, 0.55]
  depth_layers:
    - {id: fg, role: foreground, contrast: quiet, content: "near pine branch"}
    - {id: mg, role: subject, contrast: balanced, content: "village and river bend"}
    - {id: bg, role: background, contrast: quiet, content: "ridge line and cloud"}
    - {id: motion, role: atmosphere, contrast: quiet, content: "wind and water drift"}
```

景深模糊只是摄影机表现，不是空间感本身。远景和地形关系需要看清时，保持足够清晰范围。

### 5.2 三种动画语言

| 语言 | 用来讲什么 | 引擎 | 不通过的样子 |
| --- | --- | --- | --- |
| 自然现象动画 | 风、水、地形、光照、粒子 | Blender / Remotion | 漂亮流线被当成真实计算结果 |
| 空间结构动画 | 山体剖开、高程、河道与聚落 | Blender / 程序化几何 | 只换视角，不改变理解 |
| 概念关系动画 | 古人观察 ↔ 地形条件 ↔ 现代解释 | SVG / HTML / GSAP / Manim | 关系图只是装饰，没有变量变化 |

每个动画必须有知识任务：连接对象、展示变量、表现过程、把抽象概念落到现实。没有解释作用的运动删掉。

### 5.3 镜头运动

同一空间内用推、移、俯视、局部特写完成叙事，不靠转场。运动必须有动机：

- 远景建立 → 中景推进 → 俯视分析 → 细节特写；
- 从写意山水过渡到三维地形，再过渡到风场/水流解释；
- 回到开头空间收束。

摄影机、焦点、运动曲线写进 `visual-design.yaml` 的 `motion`；Remotion 已消费 `motion.camera` 与焦点，Blender 场景需要场景代码读取导出的 `design.json`。

## 6. 声音

| 层 | 任务 | 落点 |
| --- | --- | --- |
| 旁白 | 知识解释，语速随论证变化 | `sound_design.json.voice[]` |
| 音乐 | 情绪与段落；关键证据处让路 | `music[]`，`duck` / `silence` |
| 音效 | 对应画面动作 | `sfx[]`，`trigger: visual_event` |
| 环境声 | 现场空间 | `ambience[]` |

无旁白片子（如风水）没有 `voice[]`，由大字与字幕承担解释；音乐与环境声更要承担节奏。预览混音会读取有资产的 cue；缺资产只告警。

## 7. 生产线步骤

```powershell
# 1. 一个点的定义
#    产物：<内容根>/projects/<系列>/episodes/<slug>/one-point.md
#    一句话核心点 + 2–3 个支撑结论 + 边界

# 2. 项目与叙事
course-control project-validate --project <内容根>/projects/<系列>/project.yaml
course-control narrative-validate --project <内容根>/projects/<系列>/project.yaml

# 3. 视觉导演（3 分钟片子必须 authored，不用 derived 草稿直接开渲）
course-control visual-design --lesson <slug>
#    在 authoring/visual-design.yaml 覆盖：depth_layers / focal_point / motion.camera / keyframes

# 4. 声音设计
course-control sound-design --lesson <slug>

# 5. 预览：先一个镜头，再一段，再全片
course-control render shot    --lesson <slug> --shot <id>      --mode preview
course-control render segment --lesson <slug> --segment <id>   --mode preview
course-control render project --lesson <slug>                  --mode preview
course-control preview-pilot  --lesson <slug>

# 6. 正式渲染与发布检查
course-control render project --lesson <slug> --mode release
course-control release-check --lesson <slug>
```

主题视频形态：

```powershell
course-control narrative-validate --project <内容根>/projects/<系列>/project.yaml
course-control render project --project <内容根>/projects/<系列>/project.yaml --shot <id>
course-control render project --project <内容根>/projects/<系列>/project.yaml --segment <id>
course-control render project --project <内容根>/projects/<系列>/project.yaml
course-control release-check --project <内容根>/projects/<系列>/project.yaml
```

## 8. 视觉压力测试：A/B/C 三版

不马上大改系统。拿风水第一期做一个 30–45 秒的同段落测试，三版共用同一脚本、同一节拍、同一音乐、同一字幕，只换视觉：

| 版本 | 主视觉 | 引擎 | 检验 |
| --- | --- | --- | --- |
| A 3D 视觉纪录片 | 空间、景深、光影、摄影机 | Blender | 空间关系与镜头组织 |
| B 东方视觉叙事 | 水墨、层次、留白、形态转换 | Remotion / 2.5D | 文化与视觉连续性 |
| C 科学可视化 | 地形、流场、结构、动态解释 | Manim / Remotion / SVG | 机制是否讲清 |

三版不是选一个“赢家”，而是确定主视觉与辅助语言的组合。测试段落建议选“山谷推进 → 风场解释”这一段，因为它同时需要空间、文化和机制。

每版交付：480p P1 预览、contact sheet、1080p 对照、渲染时间、缓存命中、人工修改点。

## 9. 验收五问

1. **静音观看**：不听旁白/不看字幕，画面本身是否有设计、有叙事？
2. **正常观看**：知识是否讲明白，动画是否帮助理解？
3. **视觉质量**：是否有真正的空间感、构图、光影和美感？
4. **视听质量**：音乐、音效、旁白/字幕是否形成整体？
5. **整体体验**：看完是否学到东西，并愿意看下一期？

这五问是人工审片，不是程序比例门禁。程序只负责交付质量：解码、响度、黑帧/冻结、字幕结构、许可、分辨率/帧率。

## 10. 与课程线、新闻线的区别

| 维度 | 3 分钟 Vibe | 10–20 分钟课程 | 新闻调查 |
| --- | --- | --- | --- |
| 核心 | 一个点 + 一次视觉体验 | 知识递进 + 完整论证 | 事件 + 证据 + 机制 + 判断 |
| 结构 | 五幕，短 | 五段，长 | 六幕，矛盾升级 |
| 画面 | 空间/视觉驱动 | 解释驱动 | 证据驱动 |
| 声音 | 音乐与氛围重 | 旁白为主 | 四层，证据让路 |
| 验收 | 五问 | 八维 | 100 分制 + 双验收 |

三条线共用 `ProjectSpec`、`render`、`release-check`、缓存、字幕、混音；不共用内容标准和视觉语法。

## 11. 当前缺口

- `fengshui-wind-water` 是 152 s 单片，没有镜头文件；P0/P1 用时间窗，不改内容结构。
- 风水目前是无旁白；评审建议的旁白驱动结构需要所有者先改系列规则。
- Blender 在这条线里还没有真实样例；A 版测试是第一次。
- `compound-interest`、`xhs-plasma-etch`、`diesel-4-stroke-diagram`、`whale-maid` 还没有 `project.yaml`；风水是第一条纳入统一入口的。
- `keyframes` / `continuity` 已传入渲染层，但引擎只逐项消费了焦点与运镜；完整关键帧对象仍待场景代码读取。

## 12. 下一步

1. 给风水第一期写 `one-point.md`，确认核心点与 2–3 个支撑结论。
2. 做 A/B/C 30–45 秒压力测试，记录时间、质量差异、返工点。
3. 用 `preview-pilot` 记录 P0/P1/P2 成本。
4. 根据测试结果决定主视觉，再谈是否把 Blender 变成这条线的默认引擎。
EOF
