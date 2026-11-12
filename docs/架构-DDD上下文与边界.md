# 架构：DDD 上下文与模块边界

- **日期**：2026-11-12
- **状态**：已执行。CourseControl 的 72 个平铺模块按上下文重组为 8 个包，回归 561 例通过。
- **范围**：只改目录与依赖方向，不改业务行为。

---

## 1. 为什么动

改造前 `course_control/` 下有 72 个 `.py` 平铺在同一层：契约、渲染、声音、验收、制片、工具函数混在一起。后果很具体：

- 读代码时无法从目录判断"这个模块属于哪件事"；
- 依赖方向没有约束，`paths.py` 反向 import 生产计划，`pipeline.py` 与制片层互相引用；
- 新能力只能继续往根目录加文件（V2 的 animatic、audio、locks 差点也变成三个平铺模块）。

## 2. 八个上下文

按"这件事对谁负责"划分，不按技术分层。每个上下文有自己的语言和数据；跨上下文的调用只走对方的公开入口。

| 上下文 | 负责 | 入口 | 不做什么 |
| --- | --- | --- | --- |
| `content` | 课程是什么：契约、校验、路径、时长、shots 契约、时间线 | `LessonPaths`、`validate()`、`ProductionPlan` | 不渲染、不合成、不判断质量 |
| `direction` | 这门课该拍成什么样：章节、镜头、节拍、叙事、镜头表编译 | `direction.build()`、`shot_sheet` | 不写场景代码、不调用引擎 |
| `rendering` | 一个镜头怎么变成像素：适配器、引擎路由、Blender、Manim、版式、公式、主题 | `adapters.*`、`renderers` | 不改课程内容、不判定合格 |
| `voice` | 这门课说什么：旁白合成、声音资产、字幕、混音 | `narrate`、`subtitles`、`audio_plan` | 不写画面、不签核 |
| `quality` | 怎么知道做对了：校验、验收、媒体 QC、质量报告、对标 | `verify()`、`quality`、`quality_gates` | 不改产物、不自动放行 |
| `delivery` | 怎么变成可交付的包：订单、授权、交付清单、增量重建 | `delivery.orchestrator` | 不渲染、不读密钥、不自动发布 |
| `platform` | 所有上下文共用的底座：路径解析、文件原子写、锁、检查点、媒体探测、配置 | `workspace_layout`、`utils`、`media` | 不含业务规则 |
| `authoring` | 从资料到批准的讲稿：摄取、摘要、brief、outline、script | `authoring.pipeline` | 不改课程正文（候选人审后落地） |

另有三个**能力包**，不强行归入上面七个：

| 包 | 定位 |
| --- | --- |
| `animatic` | 预览：把时间线变成 480p 可看片段（`docs/动画预览-Animatic.md`） |
| `locks` | 版本快照：Picture / Dialogue Lock 与失效映射（`docs/锁定与失效.md`） |
| `cli` | 命令层：只做参数解析与输出，业务在上下文里 |

`pipeline.py` 留在包根，是**组合根**：它把 content → rendering → quality 串成一次构建，不承载领域规则。

## 3. 聚合与不变量

上下文内部按聚合组织；每个聚合只有一个入口负责维持不变量。

| 聚合 | 上下文 | 不变量 |
| --- | --- | --- |
| `Lesson` / `Storyboard` | content | 一模式一权威；v2 字段只在 `schema_version: 2` 下可用；镜头 id 唯一 |
| `ProductionPlan` | content | shots 是唯一计时权威；sequence 不带自己的时钟 |
| `DirectorPlan` | direction | 是视图，不是第二权威；镜头必须可路由到引擎 |
| `ShotSheet`（storyboard v2 编译结果） | direction | 引用必须能解析成资产/连续性对象；指纹由设计字段与资产字节算出 |
| `VoiceBible` / `Lexicon` | voice | 身份是文档哈希；参考音频必须与其声明哈希一致 |
| `Narration` | voice | 缓存键 = 文本 + 声线哈希 + 本段命中的词条 + 参数 |
| `Animatic` | animatic | 帧网格由绝对时间算出，段内取整不累积误差 |
| `PictureLock` / `DialogueLock` | locks | 锁是快照不是禁令；漂移必须映射到下游 |
| `QualityReport` | quality | 状态由检查结果推导，不由人写；`RELEASE_APPROVED` 需两次人工签核 |
| `DeliveryManifest` | delivery | 每个文件带 SHA-256；缺项即失败 |

## 4. 依赖方向

```text
cli ──────────────┐
                  ▼
        content ─ direction ─ rendering
           ▲          ▲           │
           │          │           ▼
        quality ◄─────┴────── voice
           │
        delivery ── pipeline（组合根）
           │
        platform（所有上下文都可依赖）
```

规则（约定，不是工具强制）：

1. `platform` 不 import 任何业务上下文。
2. `content` 只依赖 `platform`；契约不反向依赖渲染。
3. `rendering` 可以读 `content`，不能 import `direction` 的计划对象——它只接受适配器输入。
4. `quality` 观察其他上下文，不被它们 import（除了组合根）。
5. 包 `__init__.py` 不 eager import 整个上下文：`delivery/__init__.py` 就是空壳，避免 orchestrator → pipeline 的循环。

## 5. 改造结果

| 原位置 | 现位置 | 数量 |
| --- | --- | --- |
| 根目录契约类模块 | `content/` | 12 |
| 根目录 + `director/` | `direction/` | 9 + 8 |
| 根目录 + `adapters/`、`layout/` | `rendering/` | 17 + 11 + 5 |
| 根目录 + `audio/` | `voice/` | 9 + 3 |
| 根目录验收类模块 | `quality/` | 8 |
| 根目录 + `producer/` | `delivery/` | 2 + 6 |
| 根目录工具类模块 | `platform/` | 13 |

导入风格：跨上下文一律绝对导入（`from course_control.content.paths import LessonPaths`），上下文内部保持相对导入。这样移动文件时不会因为层级变化而重算点号。

## 6. 验证

- `python -m unittest discover -s CourseControl/tests`：**561 例通过 / 7 跳过**。
- `course-control validate --lesson a01-why-cars-need-aerodynamics`：通过（1 条既有 warning）。
- 改造中没有改任何业务逻辑；唯一的语义调整是把 `production.py`（shots 模式契约）从 `direction` 移到 `content`——它本来就是课程契约，这一步同时解掉了 `paths → production` 与包初始化的循环。

## 7. 没做的

- **没有强制依赖方向**。当前靠约定与代码评审；要机器检查需要引入 import-linter 之类的工具，属于单独的决策。
- **没有拆 application 层**。组合根仍是单个 `pipeline.py`；如果后续出现第二种构建形态，再抽用例层。
- **CLI 未按上下文拆分命令组**。`cli/` 仍是按命令族分文件，与上下文一一对应得并不严格。

## 8. 回归入口

```powershell
.\scripts\check.ps1
cd CourseControl; uv run python -m unittest discover -s tests -t .
```
