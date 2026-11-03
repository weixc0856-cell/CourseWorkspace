# CourseWorkspace R0→R5 改造 PRD

- **文档版本**：v1.1.4
- **编写日期**：2026-11-01
- **文档性质**：可执行改造规格（PRD + 目录迁移规则 + 测试验收规范）。本文只描述"要做什么、按什么顺序做、怎么判定完成"，不包含任何已执行的迁移动作。
- **依据**：2026-11-01 工作区架构提案；本仓库只读审计结果（§1，均为本次实际读取或执行所得）；v1.1 评审意见。
- **路径脱敏**：本机绝对路径统一写成 `<AI_ROOT>`、`<BLENDER_EXE>`、`<WORKSPACE>`、`<LOCAL_ROOT>` 等占位符；实际值见本地 `config/local-paths.yaml`（已忽略，不入库）。
- **执行者**：Claude Code / Codex 等编码代理。
- **阅读顺序**：§0 纪律 → §1 现状 → §2 目标架构 → §3 数据契约 → §4 迁移规则 → §5 阶段任务 → §6 验收。

**修订记录**：

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v1.0 | 2026-11-01 | 初版：R0 审计、目标架构、四份契约、迁移规则、阶段 PRD |
| v1.1 | 2026-11-01 | 按评审修订：Manim 产物改指 `build/`；`overlay` 拆为 `timeline_role` + `presentation`；新增幻灯片截图采集；新增 Remotion 外部文件读取 spike；去重 R0/R1 提交纪律；新增 `not_applicable` 状态与适用性规则；区分 Blender 后台可执行文件与 GUI 启动器 |
| v1.1.1 | 2026-11-01 | 契约闭合：按字段登记路径基准；`not_applicable` 进入正式状态枚举；V-10 区别人工导出与自动渲染；R-08 状态对齐；补充 overlay 父片段识别与 recording 时间轴换算（V-20） |
| v1.1.2 | 2026-11-01 | 边界确认：路径合法性与大小写规则；deck 模式允许一页多个 overlay 但只允许一条 base；V-20 明确默认容差、配置位置与 ffprobe 读取失败语义（V-21） |
| v1.1.3 | 2026-11-01 | R1 执行中发现并修正：Motion Canvas 场景路径基准应为引擎根的 `src/scenes/...`，storyboard 与示例同步 |
| v1.1.4 | 2026-11-01 | 与 R2 实现同步：Blender 任务文件改为 JSON；补充数据格式归属；默认引擎改为 `BLENDER_EEVEE` |

**证据等级**（全文沿用）：

| 等级 | 含义 |
| --- | --- |
| `VERIFIED` | 本次实际执行命令并取得输出 |
| `STATIC` | 只读源码、配置或文档确认 |
| `NOT_RUN` | 具备条件但本次未执行 |
| `NOT_FOUND` | 在已扫描范围内不存在 |
| `UNKNOWN` | 现有信息无法判断，需在指定阶段验证 |

---

## 0. 执行纪律（硬约束）

0.1 **只整合，不重写。** `slides.md`、`lecture_notes.md`、`outline.md` 的正文归用户所有。执行者只能改文件位置、路径、分页与格式，不得改写措辞、增删论点、替换数字或结论。发现必须改语义时，停下来提问并记录，不得自行补写。此规则适用于 R1–R5 全部阶段。

0.2 **阶段门禁。** R1→R2→R3→R4→R5 顺序执行。上一阶段的出口验收未全部通过，不得开始下一阶段；不得为了"让检查通过"而放宽检查本身。

0.3 **skip ≠ pass，不适用 ≠ 通过。** 构建报告、验收记录与阶段汇报必须区分 `pass` / `fail` / `skipped` / `not_run` / `not_applicable`：

- `skipped`：本应执行，但被人工步骤或配置跳过；
- `not_run`：尚未执行（只允许出现在中间状态，最终报告必须解释）；
- `not_applicable`：当前课程配置下该阶段或检查不适用（例如纯 Blender 课程没有 Motion Canvas 场景）。

任何情况下都不得把后三者写成通过。

0.4 **环境边界。** 不执行全局 `pip install`、不装全局 npm 包、不修改系统 PATH；不在 `<AI_ROOT>` 内写入、移动或删除任何文件；不启动、停止或重配本地模型 / ComfyUI / CosyVoice 服务。依赖只安装在各工程自己的目录内。

0.5 **写入边界。** 各工程只写自己的目录和 `build/<lesson>/`。适配器不得把产物写进其他工程目录（例如 Remotion 不得往 `MotionStudio/output/` 写；Blender 不得往 `ManimSandbox/media/` 写）。临时文件必须落在 `build/<lesson>/tmp/` 或系统临时目录，并在构建报告中登记。

0.6 **提交纪律。** R0 的提交由用户审查并执行，执行者只记录哈希，不得代提交（见 §1.6）。R1–R5 每个阶段一个提交，提交信息带阶段号，例如 `R1: 课程数据独立到 lessons/`；提交前必须跑完该阶段出口验收。R1 及以后不再重复执行 R0 的提交动作。

0.7 **先读后改。** 本文给出的路径、行号与字符串以编写时仓库状态为准。执行任一步骤前先读取目标文件当前内容；若与本文不一致，以实际内容为准，并在阶段报告中记录偏差。

0.8 **不新增课程内容。** 本文的示例数据取自现有两门课；执行者不得借改造之机补写占位页、补翻中文或改动画文案。

---

## 1. R0 现状审计

### 1.1 工作区快照

审计时仓库位于 `main` 分支，HEAD `cf48b1c`，工作区有未提交改动。

| 路径 | 角色 | 跟踪状态 | 证据 |
| --- | --- | --- | --- |
| `docs/` | 总指导、交付清单模板、本期清单 | 2 个已跟踪 + 2 个未跟踪 | `VERIFIED` |
| `CourseSlides/` | Reveal.js 6.0.2 外壳 + 课程 Markdown | 已跟踪 | `VERIFIED` |
| `MotionStudio/` | Motion Canvas 3.17.2 动画 | 已跟踪 | `VERIFIED` |
| `ManimSandbox/` | Manim 0.22.0 数学动画 | 已跟踪 | `VERIFIED` |
| `README.md`、`.gitignore` | 工作区说明与忽略规则 | 已跟踪 | `VERIFIED` |
| `lessons/`（根） | — | **不存在** | `VERIFIED` |
| `shared/`、`build/`、`scripts/`、`CourseControl/`、`BlenderStudio/`、`RemotionStudio/` | — | **均不存在** | `VERIFIED` |

课程内容：

| 课程 | 页数 | `lecture_notes.md` 块数 | 动画场景 | 证据 |
| --- | --- | --- | --- | --- |
| `01-transformer-demo` | 8（7 个 `---`） | 8 | `attention-flow` | `VERIFIED`（grep 计数） |
| `01-shell-for-ai-era` | 20（19 个 `---`） | 20 | 8 个 Motion Canvas 场景 | `VERIFIED`（grep 计数） |

`01-shell-for-ai-era` 的动画切口（来自 `lecture_notes.md`，`VERIFIED`）：

| 页码 | 场景名 | 切入秒点 | 清单标注时长 |
| --- | --- | --- | --- |
| Slide 2 | `gui_vs_cli_paths` | 40 | ≈12.2s |
| Slide 4 | `terminal_shell_layers` | 35 | ≈10.0s |
| Slide 6 | `argument_tokenization` | 30 | ≈11.0s |
| Slide 8 | `path_lookup_flow` | 45 | ≈11.9s |
| Slide 11 | `unix_pipeline_stream` | 40 | ≈13.3s |
| Slide 12 | `redirection_mechanics` | 35 | ≈13.0s |
| Slide 15 | `permission_shebang` | 30 | ≈12.1s |
| Slide 19 | `pipeline_case_demo` | 35 | ≈15.0s |

`01-transformer-demo` 只有 1 个切口：Slide 3，第 60 秒，场景 `attention-flow`（`VERIFIED`）。

### 1.2 运行时与依赖事实

| 项目 | 实际值 | 证据 |
| --- | --- | --- |
| Node.js | `v24.14.1` | `VERIFIED` |
| npm | `11.11.0` | `VERIFIED` |
| reveal.js（已安装） | `6.0.2` | `VERIFIED` |
| live-server（已安装） | `1.2.2` | `VERIFIED` |
| Motion Canvas core / vite / typescript | `3.17.2` / `4.5.14` / `5.9.3` | `VERIFIED` |
| `tsc --noEmit`（MotionStudio） | 退出码 0 | `VERIFIED` |
| uv | `0.10.8` | `VERIFIED` |
| Python（ManimSandbox `.venv`） | `3.12.10` | `VERIFIED` |
| Manim | `0.22.0` | `VERIFIED` |
| FFmpeg / ffprobe | `8.1-full_build` | `VERIFIED` |
| Blender | `5.2`；后台渲染用 `<BLENDER_HOME>\blender.exe`（约 113 MB）；同目录 `blender-launcher.exe`（约 335 KB）是 GUI 启动器。**均不在 PATH** | `VERIFIED` |
| Docker | 已安装（本次改造不需要） | `VERIFIED` |
| `<AI_ROOT>` | `CosyVoice-Runtime`、`models`、`start_server.bat` 等；本地模型 `127.0.0.1:8080` | `VERIFIED`（目录列举） |
| ComfyUI | 在 `<AI_ROOT>`、`<LOCAL_ROOT>\Project`、`<LOCAL_ROOT>\Tools` 两层级内未发现 | `NOT_FOUND`（扫描范围有限） |
| `CourseSlides/node_modules` | 存在，约 14 MB | `VERIFIED` |
| `MotionStudio/node_modules` | 存在，约 275 MB | `VERIFIED` |
| `ManimSandbox/.venv` | 存在 | `VERIFIED` |
| `MotionStudio/output/` | 不存在；无导出的课程视频 | `VERIFIED` |
| `ManimSandbox/media/` | 存在；有 `dot_product/480p15/DotProduct.mp4` 预览与 27 个分段文件；**0 个文件被 Git 跟踪**，全部命中 `ManimSandbox/.gitignore` 的 `media/` | `VERIFIED` |
| 工作区外参考项目 | `<REFERENCE_PROJECT>`（另一套课程生产框架，本文不并入、不依赖） | `STATIC` |

> Blender 路径说明：`blender-launcher.exe` 只负责启动 GUI，不接受后台渲染参数；所有自动化命令必须使用同目录的 `blender.exe`。`config/tools.yaml` 只记录 `blender.exe`，不记录启动器。
>
> Manim 既有 `media/`：Git 跟踪数为 0，全部命中 `ManimSandbox/.gitignore`。改造不删除、不迁移，作为历史缓存保留；新构建只写 `build/<slug>/tmp/manim-media/`。是否清理由用户决定。

### 1.3 现有契约靠什么成立

改造前，所有契约都是"隐式"的，靠多处代码与约定同时成立。迁移时必须逐条对照。

**A. 幻灯片加载契约**

- `CourseSlides/template/index.html` 用相对路径 `data-markdown="../lessons/<slug>/slides.md"` 加载 Markdown。
- 同一文件中的 JS 会把挂载点改成 `` `../lessons/${lesson}/slides.md` ``，slug 受正则 `^[a-z0-9]+(?:-[a-z0-9]+)*$` 限制，非法 slug 回退到 `01-transformer-demo`。
- `slides.md` 内的图片写**根路径** `/lessons/<slug>/assets/...`（`CourseSlides/README.md` 明确禁止写相对路径）。
- `live-server` 的工作根是 `CourseSlides/`，所以 `/lessons/...` 映射到 `CourseSlides/lessons/...`，`../node_modules/...` 映射到 `CourseSlides/node_modules/...`。

结论：**课程目录位置、Markdown 加载路径、图片根路径、HTTP 服务根**四者绑死。只搬目录不改服务根，幻灯片和图片会同时 404。

**B. 双文件契约**

- `slides.md` 与 `lecture_notes.md` 同目录平行存在；`---` 分页，`--` 垂直子页；`lecture_notes.md` 用 `Slide N`（子页记 `3b`）一一对应。
- `lecture_notes.md` 每块四要素：时长预算、动画切入、技术核查、逐字口播。
- 动画切入里的"引擎 + 场景名 + 秒点"是**目前唯一的镜头来源**，没有机器可读的镜头清单。

**C. 动画注册契约**

- Motion Studio：`src/scenes/<slug>/<scene>.tsx` + `<scene>.meta`；必须在 `src/project.ts` 的 `scenes` 数组手工注册。当前注册 9 个场景（1 个 Transformer + 8 个 Shell），**全部在同一个项目里**。
- Manim：`ManimSandbox/<slug>/<scene>.py`，类名 PascalCase，无需注册。
- 两套引擎都只产出独立视频；`slides.md` 不写 `<video>`。

**D. 端口契约**

| 服务 | 端口 |
| --- | --- |
| 本地模型 `start_server.bat` | `8080` |
| 课件预览 `npm run dev` | `8081` |
| 课件预览备用 | `8082` |
| Motion Studio 编辑器 | `5173` |

**E. 交付清单契约**

`docs/课程交付清单模板.md` 与 `docs/交付清单-01-shell-for-ai-era.md` 承载页面完成度、动画切口、验证记录与待办。改造后这些信息要能被 `lesson.yaml` / `storyboard.yaml` 机器读取，清单文档继续保留给人看。

### 1.4 现状与目标架构的差距

| 目标 | 现状 | 差距 | 主要影响 |
| --- | --- | --- | --- |
| 课程内容是唯一入口 `lessons/` | `CourseSlides/lessons/` | 内容归属展示引擎 | `template/index.html`、`package.json`、全部文档路径 |
| 统一控制层 | 无 | 无任务、无调度、无报告 | 新增 `CourseControl/` |
| 3D 生产 | 无 | Blender 装了但没有任何工程 | 新增 `BlenderStudio/` |
| 最终视频编排 | 无 | 只能人工剪辑 | 新增 `RemotionStudio/` |
| 跨工程契约 | 无 | 靠人读文档 | 新增 `shared/`、`lesson.yaml`、`storyboard.yaml`、`shots.json` |
| 统一产物目录 | `MotionStudio/output/`、`ManimSandbox/media/` 分散 | 产物不可枚举 | 新增 `build/<slug>/` |
| 一键构建 | 无 | Motion Canvas 只能手动点 RENDER | 新增 `scripts/build-lesson.ps1` |
| 自动验收 | 人工清单 | 无机器判定 | 新增 `course-control verify` |
| 幻灯片画面来源 | 无 | 没有截图或录屏采集路径 | R3 定义 `deck` / `recording` 两种编排模式 |

### 1.5 R0 风险与阻塞项

| 编号 | 风险 | 等级 | 证据 | 处理阶段 |
| --- | --- | --- | --- | --- |
| R0-01 | 课程目录与幻灯片加载、图片根路径、HTTP 服务根四者耦合，直接搬目录会让页面和图片 404 | 高 | §1.3-A | R1 |
| R0-02 | Motion Canvas 3.17.2 没有 CLI 渲染入口：`node_modules/.bin` 只有 `vite`，`@motion-canvas/vite-plugin` 只有 `lib/index.js` 无 `bin`。官方导出依赖编辑器 UI | 高 | `VERIFIED` | R4 前 spike |
| R0-03 | `src/project.ts` 是单一场景数组，9 个场景在同一项目里，无法按课单独渲染 | 中 | `STATIC` | R4 |
| R0-04 | 两门课的 slug 都以 `01` 开头（`01-transformer-demo` / `01-shell-for-ai-era`），课程编号不唯一 | 低 | `VERIFIED` | R1 记录，不改名 |
| R0-05 | Blender 5.2 已安装但不在 PATH；后台渲染引擎（EEVEE / Cycles）可用性未验证 | 中 | `VERIFIED` 路径，`UNKNOWN` 渲染 | R2 spike |
| R0-06 | 提案假设的 ComfyUI 在已扫描路径不存在 | 低 | `NOT_FOUND` | 冻结，不阻塞 |
| R0-07 | 工作区有 10 个已修改文件与 4 个未跟踪路径，迁移前必须提交 | 高 | `git status` `VERIFIED` | R0 出口 |
| R0-08 | 文档中课程路径引用分散在 6 个文件、27 处 `lessons/` 提及 | 中 | grep `VERIFIED` | R1 |
| R0-09 | Remotion 未安装；Node 24 兼容性未验证 | 中 | `VERIFIED` 未安装 | R3 |
| R0-10 | 没有音频与字幕源文件，`build/narration/` 与 `.srt` 暂无输入 | 中 | `VERIFIED` | R3/R5 按可选输入设计 |
| R0-11 | `01-shell-for-ai-era` 有 4 页结构占位、3 页中文待补，不能作为完整成片验收对象 | 中 | 交付清单 | R5 用 fixture 验收 |
| R0-12 | Manim 预览产物在 `media/`，Motion 无产物，没有统一收集机制 | 中 | `VERIFIED` | R2/R4 |
| R0-13 | 没有幻灯片画面采集路径（截图或录屏），Remotion 无法单独生成完整成片 | 高 | `VERIFIED` 无相关代码 | R3 |
| R0-14 | Manim 默认把成片写进 `ManimSandbox/media/`，与"产物只进 `build/`"冲突；现有 `media/` 全部未跟踪，可保留为历史缓存 | 中 | `VERIFIED` | R2/R4 |

### 1.6 R0 出口条件

执行者开始 R1 之前，必须确认：

- [ ] 当前 10 个修改文件与 4 个未跟踪路径已由用户确认并提交（`git status` 干净）。提交信息由用户确认，执行者不得代拟课程内容相关措辞。
- [ ] 记录提交哈希到本阶段报告。
- [ ] 确认 §1.2 的版本事实没有变化（Node、uv、Blender 路径）。
- [ ] 确认 `<AI_ROOT>` 未被改动。

---

## 2. 目标架构

### 2.1 分层

```text
内容层    lessons/<slug>/            课程唯一内容入口（Markdown、YAML、素材）
生产层    CourseSlides/             展示
          MotionStudio/             结构动画
          ManimSandbox/             数学动画
          BlenderStudio/            3D 场景
          RemotionStudio/           最终视频编排
控制层    CourseControl/            契约校验、任务调度、日志、验收报告
共享层    shared/                   跨工程 schema、设计令牌、类型
产物层    build/<slug>/             所有生成物的唯一落点
入口层    scripts/                  工作区级 PowerShell 入口
```

依赖方向：**控制层 → 生产层**（通过命令行与文件契约），生产层之间**互不引用代码**。生产层只读 `lessons/` 与 `shared/`，只写 `build/<slug>/`（Motion Canvas 编辑器自身的临时导出目录除外，见 §5.2）。

### 2.2 最终目录树

`入库` 列标注该目录/文件是否进入 git。

```text
CourseWorkspace/
├── docs/
│   ├── 课件制作总指导.md
│   ├── 课程交付清单模板.md
│   ├── 交付清单-<slug>.md
│   └── CourseWorkspace-R0-R5改造PRD.md      # 本文
├── lessons/                                  # 入库：课程唯一入口
│   └── <slug>/
│       ├── lesson.yaml                       # 元数据、画布、引擎、编排模式
│       ├── slides.md                         # 观众视图（用户所有）
│       ├── lecture_notes.md                  # 口播与导播（用户所有）
│       ├── outline.md                        # 阶段一大纲（可选）
│       ├── storyboard.yaml                   # 镜头需求（动画切口的结构化）
│       ├── sources.yaml                      # 来源与证据（可选，R3 后启用）
│       ├── assets.yaml                       # 素材来源与授权登记（可选，R3 后启用）
│       ├── subtitles.srt                     # 可选字幕输入
│       └── assets/                           # 幻灯片图片素材
├── CourseSlides/                             # 入库；node_modules 忽略
│   ├── template/index.html
│   ├── css/mckinsey-orange.css
│   ├── docs/课件生成调用指南.md
│   └── package.json
├── MotionStudio/                             # 入库；node_modules、output、dist 忽略
├── ManimSandbox/                             # 入库；.venv、media 忽略
├── BlenderStudio/                            # 入库；产物写 build/
│   ├── README.md
│   ├── tasks/<slug>/<shot>.json
│   ├── scenes/<slug>/*.blend
│   ├── scripts/render_shot.py                # 在 Blender 内执行
│   ├── scripts/render_smoke.py               # 程序化冒烟场景
│   ├── templates/
│   └── tests/
├── RemotionStudio/                           # 入库；node_modules 忽略
│   ├── package.json
│   ├── remotion.config.ts
│   ├── src/
│   │   ├── index.ts
│   │   ├── Root.tsx
│   │   ├── compositions/
│   │   ├── components/
│   │   ├── transitions/
│   │   ├── subtitles/
│   │   ├── audio/
│   │   └── styles/
│   └── public/            # staging/：放入 build 素材供 Remotion 访问，不入库
├── CourseControl/                            # 入库；.venv、__pycache__ 忽略
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── src/course_control/
│   │   ├── cli.py
│   │   ├── contracts.py
│   │   ├── adapters/
│   │   ├── validators/
│   │   ├── pipeline/
│   │   └── report.py
│   └── tests/
│       └── fixtures/
├── shared/                                   # 入库；R3 首次落盘
│   ├── schemas/                              # JSON Schema
│   ├── design-tokens/tokens.json
│   └── types/
├── config/
│   └── tools.yaml                            # 工具路径与超时（R2 落盘）
├── assets/                                   # 入库；登记过的公共素材（R3 起）
│   ├── fonts/ images/ audio/ models/
├── build/                                    # 不入库
│   └── <slug>/
│       ├── slides/        # 幻灯片画面：slide-###.png 或 recording.mp4
│       ├── animation/     # Motion Canvas / Manim 成片
│       ├── blender/       # Blender 成片
│       ├── narration/     # 旁白音频（可选输入）
│       ├── remotion/      # Remotion 中间产物
│       ├── preview/       # 低清预览
│       ├── final/         # course-video.mp4 / course-subtitles.srt / build-report.json
│       ├── logs/          # 每个阶段一个日志
│       ├── tmp/           # 临时文件；manim-media/ 存 Manim 原始渲染结果
│       └── shots.json     # 生成物：镜头清单
├── scripts/
│   ├── setup.ps1
│   ├── check.ps1
│   └── build-lesson.ps1
├── .gitignore
└── README.md
```

**空目录策略**：`shared/`、`assets/` 在首次有真实内容时再创建（均为 R3），不为了凑结构提前建空壳。`build/` 由 `course-control build` 按需创建。

### 2.3 写入归属矩阵

| 目录 | 唯一写入者 | 其他工程可读 | 说明 |
| --- | --- | --- | --- |
| `lessons/<slug>/` | 用户 / 内容生成流程 | 全部 | 改造阶段执行者只能移动与改路径 |
| `CourseSlides/` | 幻灯片工程 | 否 | 只读 `lessons/` |
| `MotionStudio/` | 动画工程 | 否 | 导出后由控制层搬运 |
| `ManimSandbox/` | 动画工程 | 否 | 同上 |
| `BlenderStudio/` | 3D 工程 | 否 | 产物直接写 `build/<slug>/blender/` |
| `RemotionStudio/` | 编排工程 | 否 | 只读 `build/<slug>/` 与 `lessons/` 字幕 |
| `CourseControl/` | 控制层 | 否 | 只调度，不生产内容 |
| `shared/` | 人工 / 控制层 | 全部 | 变更需版本化 |
| `build/<slug>/` | 控制层 + 各适配器 | 全部 | 每个阶段写自己的子目录 |
| `scripts/` | 人工 / 控制层 | — | 只做入口 |

### 2.4 环境隔离矩阵

| 工具 | 管理器 | 位置 | 本次状态 |
| --- | --- | --- | --- |
| CourseSlides | npm | `CourseSlides/node_modules` | 已装 |
| MotionStudio | npm | `MotionStudio/node_modules` | 已装 |
| RemotionStudio | npm | `RemotionStudio/node_modules` | R3 新建 |
| ManimSandbox | uv | `ManimSandbox/.venv` | 已装 |
| CourseControl | uv | `CourseControl/.venv` | R4 新建 |
| Blender | 自带 Python | `<BLENDER_HOME>` | 已装，路径写入 `config/tools.yaml` |
| ComfyUI | 独立部署 | 工作区外 | 未发现，冻结 |
| CosyVoice | 独立部署 | `<AI_ROOT>\CosyVoice-Runtime` | 保留，不迁移 |
| 本地模型 | 独立部署 | `<AI_ROOT>\start_server.bat`，`127.0.0.1:8080` | 保留，不迁移 |
| FFmpeg | 可执行文件 | 系统 PATH 中的 `8.1` | 只读调用 |

### 2.5 端口与进程

| 服务 | 端口 | 归属 | 变化 |
| --- | --- | --- | --- |
| 本地模型 | `8080` | `<AI_ROOT>` | 不变，任何工程不得占用 |
| 课件预览 | `8081` | CourseSlides | URL 入口保持 `http://localhost:8081/?lesson=<slug>`（由根 `index.html` 转发） |
| 课件预览备用 | `8082` | CourseSlides | 不变 |
| Motion Studio | `5173` | MotionStudio | 不变 |
| Remotion Studio | `3000` | RemotionStudio | 新增（R3）；若占用顺延到 `3001` |
| ComfyUI | `8188` | 外部 | 未部署，不预留实现 |

### 2.6 工程间协作 = 文件契约

```text
lessons/<slug>/slides.md              ──→ CourseSlides    → 浏览器
lessons/<slug>/lesson.yaml            ──→ CourseControl
lessons/<slug>/storyboard.yaml        ──→ CourseControl   → 各动画适配器
lessons/<slug>/subtitles.srt          ──→ CourseControl   → RemotionStudio
MotionStudio / ManimSandbox / BlenderStudio ──→ build/<slug>/{animation,blender}/*.mp4
CourseControl                         ──→ build/<slug>/shots.json
build/<slug>/{slides,animation,blender,narration} + subtitles.srt
                                      ──→ RemotionStudio  → build/<slug>/final/course-video.mp4
CourseControl                         ──→ build/<slug>/final/build-report.json
```

硬规则：

1. 下游不 import 上游源码，只读文件。
2. 所有跨工程路径相对 `build/<slug>/` 书写，不用绝对路径。
3. 每个视频产物的实际时长由 ffprobe 测量后写入 `shots.json`，不信任场景里写的估计值。

### 2.7 冻结清单（本改造不引入）

| 工具 / 做法 | 决定 | 原因 |
| --- | --- | --- |
| LangGraph / CrewAI / AutoGen | 不引入 | 单线任务调度足够 |
| Dify / n8n | 不引入 | 本地脚本即可组织 |
| Monorepo 工具（pnpm workspace、turbo、nx） | 不引入 | 三个 Node 工程保持独立，等重复维护再评估 |
| 全局 `.venv` | 禁止 | 各 Python 工程独立 |
| 把 `bpy` 装进普通 `.venv` | 禁止 | Blender API 必须用 Blender 自带 Python |
| 迁移 ComfyUI / CosyVoice / 模型权重 | 禁止 | 大型运行时保留原地 |
| 自动 TTS 配音 | 非目标 | 旁白作为可选输入，由外部生成 |
| 自动语音转字幕 | 非目标 | 字幕作为可选输入，由人工/外部生成 |
| 自动发布 / git push | 禁止 | 自动化目标是可重复构建，不是无审核发布 |
| 并入 `<REFERENCE_PROJECT>` | 禁止 | 另一套独立框架，边界不清前不合并 |

---

## 3. 数据契约 v1

### 3.1 通用规则

| 项目 | 约定 |
| --- | --- |
| 版本字段 | 每个 YAML / JSON 顶层必须有 `schema_version: 1` |
| 编码 | UTF-8，无 BOM；YAML 用 2 空格缩进，禁止 Tab |
| 路径 | 一律正斜杠 `/`；禁止绝对路径与 `..` 逃逸；不同字段的基准见下方"路径基准" |
| 时间 | 秒，浮点数，保留 3 位小数；帧为整数 |
| 命名 | slug 匹配 `^[a-z0-9]+(?:-[a-z0-9]+)*$`；镜头 id 为 `shot_<三位序号>` 或 `slide_<三位页码>`；场景文件 snake_case；类名 PascalCase |
| 未知字段 | v1 默认拒绝（校验失败），防止拼写错误被静默忽略 |
| 缺失可选字段 | 用 `null` 显式表示"无"，不要省略键 |

**路径基准**（按字段登记，不按文件统一）：

| 字段 | 基准目录 | 示例 |
| --- | --- | --- |
| `lesson.yaml` 的 `content.*` | `lessons/<slug>/` | `slides.md`、`assets/`、`subtitles.srt` |
| `lesson.yaml` 的 `narration.source` | `build/<slug>/narration/` | `narration.wav` |
| `lesson.yaml` 的 `compose.base_video` | `build/<slug>/` | `slides/recording.mp4` |
| `storyboard.yaml` 的 `shots[].scene` | 对应引擎工程根：Motion → `MotionStudio/`；Manim → `ManimSandbox/`；Blender → `BlenderStudio/` | `src/scenes/<slug>/<file>.tsx` |
| `storyboard.yaml` 的 `shots[].blend_task` | `BlenderStudio/` | `tasks/<slug>/<shot>.json` |
| `shots.json` 的 `shots[].source` | `build/<slug>/` | `animation/<file>.mp4` |
| `build-report.json` 的 `artifacts[].path` | `build/<slug>/` | `final/course-video.mp4` |

约束：新增字段必须先在上表登记基准，再实现校验与适配器；不允许"按文件统一基准"的隐含规则。

**数据格式归属**：

| 数据 | 格式 | 解析方 |
| --- | --- | --- |
| `lesson.yaml` | YAML | CourseControl |
| `storyboard.yaml` | YAML | CourseControl |
| `blend_task` 指向的 Blender 任务文件 | JSON | BlenderStudio |
| `shots.json` / `build-report.json` | JSON | CourseControl / Remotion |

Blender 内置 Python 不依赖 PyYAML；课程 YAML 由 CourseControl 解析后生成 JSON 任务，Blender 只读 JSON。

**路径合法性**（适用于所有 YAML / JSON 中的路径字符串）：

| 规则 | 处理 |
| --- | --- |
| 分隔符 | 只接受正斜杠 `/`；反斜杠与混合分隔符一律拒绝 |
| 绝对路径 | 拒绝以 `/`、盘符（`C:`）、盘符相对（`C:foo`）或 UNC（`//server`）开头的路径 |
| 上跳与空段 | 拒绝任何 `..` 段、`.` 段与空段（`//`） |
| 相对形式 | 只接受 `a/b/c` 形式的相对路径；末尾 `/` 仅允许目录字段 |
| 大小写 | 契约按大小写敏感比较；Windows 上存在性检查按文件系统的不区分大小写语义执行；仅大小写不一致时记 `path_case_mismatch` 警告，不判失败，以便未来跨平台 |
| 空格与中文 | 允许；适配器必须以参数数组调用外部程序，不得拼接 shell 字符串 |
| 转换时机 | 适配器在调用前把 `/` 转成 `\`；契约文件与构建报告中始终保留 `/` |

### 3.2 `lessons/<slug>/lesson.yaml`

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | int | 是 | 固定 `1` |
| `lesson_id` | string | 是 | 必须等于目录名 |
| `title_en` / `title_zh` | string | 是 | 课程标题 |
| `status` | enum | 是 | `draft` / `review` / `final` |
| `content.slides` | path | 是 | 通常 `slides.md` |
| `content.notes` | path | 是 | 通常 `lecture_notes.md` |
| `content.outline` | path\|null | 否 | `outline.md` 或 `null` |
| `content.storyboard` | path | 是 | `storyboard.yaml` |
| `content.assets` | path | 是 | `assets/` |
| `content.subtitles` | path\|null | 否 | `subtitles.srt` 或 `null` |
| `outputs.fps` | int | 是 | 成片帧率，本仓统一 `30` |
| `outputs.resolution` | [int,int] | 是 | 成片分辨率，本仓统一 `[1920, 1080]` |
| `outputs.slides_canvas` | [int,int] | 是 | Reveal 画布 `[1280, 720]` |
| `outputs.animation_canvas` | [int,int] | 是 | 动画画布 `[1920, 1080]` |
| `engines` | string[] | 是 | `motion_canvas` / `manim` / `blender` 的非空子集 |
| `compose.mode` | enum | 是 | `deck`（逐页静态图）或 `recording`（录屏为底） |
| `compose.base_video` | path\|null | 条件 | `recording` 模式必填，相对 `build/<slug>/` |
| `narration.enabled` | bool | 是 | 是否使用旁白音频 |
| `narration.source` | path\|null | 条件 | 相对 `build/<slug>/narration/` |
| `subtitles.enabled` | bool | 是 | 是否烧录/输出字幕 |
| `acceptance.notes_total_seconds` | number\|null | 否 | 来自交付清单的时长合计；未知写 `null` |
| `acceptance.duration_tolerance_seconds` | number | 否 | 缺省视为 `2`；单位秒 |
| `build.allow_manual_animation_export` | bool | 是 | Motion Canvas 无头渲染未解决前为 `true` |

示例（取自 `01-shell-for-ai-era` 的真实数据）：

```yaml
schema_version: 1
lesson_id: 01-shell-for-ai-era
title_en: The Missing Shell for Non-Programmers in the AI Era
title_zh: AI 时代的终端底座：非程序员掌控系统的第一道杠杆
status: draft

content:
  slides: slides.md
  notes: lecture_notes.md
  outline: outline.md
  storyboard: storyboard.yaml
  assets: assets/
  subtitles: null

outputs:
  fps: 30
  resolution: [1920, 1080]
  slides_canvas: [1280, 720]
  animation_canvas: [1920, 1080]

engines: [motion_canvas]

compose:
  mode: deck
  base_video: null

narration:
  enabled: false
  source: null

subtitles:
  enabled: false

acceptance:
  notes_total_seconds: 1870
  duration_tolerance_seconds: 2

build:
  allow_manual_animation_export: true
```

### 3.3 `lessons/<slug>/storyboard.yaml`

这是**需求**，不是成片清单：它把 `lecture_notes.md` 里"动画切入"的人类文字结构化，声明每个镜头属于哪一页、什么引擎、什么场景、预计多长。实际成片路径与实测时长由 `shots.json` 承载。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | int | 是 | `1` |
| `lesson` | string | 是 | 必须等于 `lesson_id` |
| `shots[]` | object[] | 是 | 至少 1 条 |
| `shots[].id` | string | 是 | 唯一；`shot_<序号>` |
| `shots[].slide` | int | 是 | 对应 `slides.md` 页序，从 1 开始 |
| `shots[].engine` | enum | 是 | `motion_canvas` / `manim` / `blender` |
| `shots[].scene` | string | 是 | 基准为对应引擎工程根。Motion：`src/scenes/<slug>/<file>.tsx`；Manim：`<slug>/<file>.py::<ClassName>`；Blender：`scenes/<slug>/<file>.blend` |
| `shots[].cue_seconds` | number | 是 | 相对本页开头的切入秒点，来自 `lecture_notes.md` |
| `shots[].expected_duration_s` | number\|null | 否 | 估计值，仅用于漂移告警；未知写 `null` |
| `shots[].blend_task` | path\|null | 条件 | 基准 `BlenderStudio/`，如 `tasks/<slug>/<shot>.json` |
| `shots[].note` | string\|null | 否 | 自由备注，不参与校验 |

示例（`01-shell-for-ai-era`，数值全部来自现有 `lecture_notes.md` 与交付清单）：

```yaml
schema_version: 1
lesson: 01-shell-for-ai-era

shots:
  - id: shot_002
    slide: 2
    engine: motion_canvas
    scene: src/scenes/01-shell-for-ai-era/gui_vs_cli_paths.tsx
    cue_seconds: 40
    expected_duration_s: 12.2
  - id: shot_004
    slide: 4
    engine: motion_canvas
    scene: src/scenes/01-shell-for-ai-era/terminal_shell_layers.tsx
    cue_seconds: 35
    expected_duration_s: 10.0
  - id: shot_006
    slide: 6
    engine: motion_canvas
    scene: src/scenes/01-shell-for-ai-era/argument_tokenization.tsx
    cue_seconds: 30
    expected_duration_s: 11.0
  - id: shot_008
    slide: 8
    engine: motion_canvas
    scene: src/scenes/01-shell-for-ai-era/path_lookup_flow.tsx
    cue_seconds: 45
    expected_duration_s: 11.9
  - id: shot_011
    slide: 11
    engine: motion_canvas
    scene: src/scenes/01-shell-for-ai-era/unix_pipeline_stream.tsx
    cue_seconds: 40
    expected_duration_s: 13.3
  - id: shot_012
    slide: 12
    engine: motion_canvas
    scene: src/scenes/01-shell-for-ai-era/redirection_mechanics.tsx
    cue_seconds: 35
    expected_duration_s: 13.0
  - id: shot_015
    slide: 15
    engine: motion_canvas
    scene: src/scenes/01-shell-for-ai-era/permission_shebang.tsx
    cue_seconds: 30
    expected_duration_s: 12.1
  - id: shot_019
    slide: 19
    engine: motion_canvas
    scene: src/scenes/01-shell-for-ai-era/pipeline_case_demo.tsx
    cue_seconds: 35
    expected_duration_s: 15.0
```

`01-transformer-demo` 的 `storyboard.yaml` 只有一条：

```yaml
schema_version: 1
lesson: 01-transformer-demo

shots:
  - id: shot_003
    slide: 3
    engine: motion_canvas
    scene: src/scenes/01-transformer-demo/attention-flow.tsx
    cue_seconds: 60
    expected_duration_s: null
```

### 3.4 `build/<slug>/shots.json`（生成物）

由 `course-control build` 生成，Remotion 只读它。它把 `storyboard.yaml` 的需求、实测视频时长、幻灯片画面合并成一条可渲染时间线。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema_version` | int | `1` |
| `lesson` | string | slug |
| `generated_at` | string | ISO 8601 带时区 |
| `timeline.fps` / `timeline.resolution` | int / [int,int] | 成片参数 |
| `timeline.total_duration_s` | number | 等于所有 `timeline_role=base` 片段时长之和 |
| `shots[]` | object[] | 按 `start_s` 升序 |
| `shots[].id` | string | `slide_###` 或 `shot_<序号>` |
| `shots[].kind` | enum | `slide` / `animation` |
| `shots[].slide` | int | 所属页 |
| `shots[].engine` | string\|null | 动画镜头必填 |
| `shots[].source` | path | 相对 `build/<slug>/` |
| `shots[].start_s` | number | 时间线起点 |
| `shots[].duration_s` | number | 实测时长（ffprobe）或页码预算 |
| `shots[].timeline_role` | enum | `base` 顺序拼接、决定总时长；`overlay` 叠在底稿时间线上，不延长总时长 |
| `shots[].presentation` | enum\|null | 仅 `overlay` 必填：`cutaway`（全屏替换底稿）、`picture_in_picture`（小窗叠加）、`transparent_overlay`（透明叠加）；`base` 写 `null` |
| `narration` | object\|null | `{path, duration_s}` |
| `subtitles` | object\|null | `{path, cues}` |

时间线模型：

- `timeline_role=base` 的片段顺序拼接，决定成片总长；`deck` 模式下每页一条 slide 片段，时长来自 notes；`recording` 模式下只有一条 base 片段，时长由 ffprobe 测量。
- `timeline_role=overlay` 的动画片段必须完整落在某条 base 片段内部：`start_s ≥ 父片段.start_s` 且 `start_s + duration_s ≤ 父片段.start_s + 父片段.duration_s`。
- `presentation` 只决定画面合成方式，不影响时间线：
  - `cutaway`：动画全屏替换底稿，底稿时间继续走，总时长不变（当前 `01-shell-for-ai-era` 的 8 个镜头都属于这一类）；
  - `picture_in_picture`：动画缩为小窗，底稿仍可见；
  - `transparent_overlay`：带 alpha 的动画透明叠加。
- 两个概念必须分开记录：Remotion 按 `timeline_role` 计算时长，按 `presentation` 决定渲染分支。

**父片段识别**（不新增 `parent_id` 字段）：

- `deck` 模式：overlay 与 base 通过相同的 `slide` 字段配对；每页**恰好一条** `timeline_role=base`、`kind=slide` 的片段；overlay 数量不限（0 到多条），但同一页的 overlay 之间不得重叠，且必须完整落在该页 base 区间内。
- `recording` 模式：**恰好一条** `kind=recording` 的 base 片段，所有 overlay 都挂在它下面；overlay 之间不得重叠。
- 以下情况 V-13 判 `fail`：页内 base 缺失或多于一条；recording 的 base 缺失或多于一条；overlay 越界；同一父片段下的 overlay 互相重叠。

**recording 模式的绝对时间换算**：

```text
页起点(N)   = Σ 第 1..N-1 页的时长预算（来自 lecture_notes.md）
绝对 start_s = 页起点(N) + cue_seconds
```

预算累计与录屏实测时长不一致时，必须报告偏差，不得静默使用估计值：notes 累计总时长与 ffprobe 实测录屏时长之差超过 `acceptance.duration_tolerance_seconds`（缺省 `2` 秒）时，V-20 判 `fail`，并在 `checks[]` 同时写出估计值与实测值。

V-20 的读取失败与偏差分开处理：

- `compose.mode=recording` 但 `compose.base_video=null` → 配置错误，V-02 判 `fail`；
- 录屏文件不存在或 ffprobe 无法解析 → V-20 判 `fail`，原因写 `probe_failed`，不得计为时长偏差；
- 某页缺少时长预算 → V-04 已在 `validate` 阶段判 `fail`，V-20 不再重复判定。

示例（节选，仅演示结构；`slide_002` 的 `start_s` / `duration_s` 是示意值，实际值来自 notes 时长与 ffprobe 测量）：

```json
{
  "schema_version": 1,
  "lesson": "01-shell-for-ai-era",
  "generated_at": "2026-11-01T12:00:00+08:00",
  "timeline": {
    "fps": 30,
    "resolution": [1920, 1080],
    "total_duration_s": 1870.0
  },
  "shots": [
    {
      "id": "slide_002",
      "kind": "slide",
      "slide": 2,
      "source": "slides/slide-002.png",
      "start_s": 64.0,
      "duration_s": 105.0,
      "timeline_role": "base",
      "presentation": null
    },
    {
      "id": "shot_002",
      "kind": "animation",
      "slide": 2,
      "engine": "motion_canvas",
      "source": "animation/gui_vs_cli_paths.mp4",
      "start_s": 104.0,
      "duration_s": 12.233,
      "timeline_role": "overlay",
      "presentation": "cutaway"
    }
  ],
  "narration": null,
  "subtitles": null
}
```

### 3.5 `build/<slug>/final/build-report.json`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema_version` | int | `1` |
| `lesson` | string | slug |
| `started_at` / `finished_at` | string | ISO 8601 |
| `toolchain` | object | `node` / `npm` / `python` / `uv` / `ffmpeg` / `blender` 实际版本 |
| `stages[]` | object[] | `{name, status, started_at, duration_ms, outputs[], warnings[], errors[]}` |
| `stages[].status` | enum | `pass` / `fail` / `skipped` / `not_run` / `not_applicable` |
| `checks[].status` | enum | 与 `stages[].status` 同一枚举 |
| `artifacts[]` | object[] | `{path, kind, size_bytes, probe}`，`path` 相对 `build/<slug>/` |
| `checks[]` | object[] | `{id, status, expected, actual, detail}` |
| `verdict` | enum | `pass` / `fail` / `incomplete` |
| `failures[]` | string[] | 失败原因，面向人阅读 |

判定规则：

- 任一 `stages[].status == fail` → `verdict = fail`。
- 无失败但存在 `skipped` / `not_run` 的必需阶段 → `verdict = incomplete`。
- 只有全部必需阶段与检查为 `pass` 时才允许 `verdict = pass`。

**状态词与适用性**：

| 状态 | 含义 | 对 verdict 的影响 |
| --- | --- | --- |
| `pass` | 执行且通过 | 无 |
| `fail` | 执行且失败 | `fail` |
| `skipped` | 适用但被跳过（人工导出、用户关闭的输入） | 必需阶段 → `incomplete` |
| `not_run` | 未执行 | 必需阶段 → `incomplete` |
| `not_applicable` | 当前配置下不适用 | 无 |

适用性由 `lesson.yaml` 推导：`engines` 不含 `motion_canvas` 时，Motion 相关阶段与 V-09 一律 `not_applicable`；`compose.mode=recording` 时 `capture_slides` 不适用；`narration.enabled=false` 或 `subtitles.enabled=false` 时对应检查不适用。`skipped` 与 `not_applicable` 不得混用：前者是"该做但没做"，后者是"根本不需要做"。

### 3.6 校验规则

| 编号 | 规则 | 失败级别 | 执行者 |
| --- | --- | --- | --- |
| V-01 | 目录名匹配 slug 正则，且 `lesson_id` 等于目录名 | error | validate |
| V-02 | 必需文件存在（`slides.md`、`lecture_notes.md`、`lesson.yaml`、`storyboard.yaml`），且条件必填字段满足（如 `recording` 模式必须提供 `compose.base_video`） | error | validate |
| V-03 | `slides.md` 页数等于 `lecture_notes.md` 的 `Slide N` 块数 | error | validate |
| V-04 | 每个 notes 块含四要素：时长预算、动画切入、技术核查、逐字口播 | error | validate |
| V-05 | `slides.md` 图片路径以 `/lessons/<slug>/assets/` 开头且文件存在 | error | validate |
| V-06 | `slides.md` 不含 `Notes:`、`$...$`、`<video>`、`[ANIMATION` | error | validate |
| V-07 | `storyboard.yaml` 镜头 id 唯一、页码在页数范围内、引擎在 `engines` 内 | error | validate |
| V-08 | 每个镜头引用的场景文件存在 | error | validate |
| V-09 | 仅当 `engines` 含 `motion_canvas`：场景已在 `src/project.ts` 注册；否则 `not_applicable` | error | validate |
| V-10 | 每条动画镜头有对应成片：自动渲染模式缺文件 → `fail`；人工导出尚未执行 → `skipped`；已导出且 ffprobe 通过 → `pass` | error（自动）/ skipped（人工未执行） | collect |
| V-11 | 实测时长与 `expected_duration_s` 偏差超过 20% 且超过 2 秒 | warning | collect |
| V-12 | 所有片段分辨率与帧率一致 | error | collect |
| V-13 | 时间线连续；`deck` 每页恰有一条 base、`recording` 恰有一条 base；overlay 数量不限，但须落在父片段内且互不重叠；`presentation` 与 `kind` 匹配 | error | compose |
| V-14 | 成片时长与 `acceptance.notes_total_seconds` 偏差 ≤ 容差；该值为 `null` 时 `not_applicable` | error | verify |
| V-15 | 成片含视频流；启用旁白时含音频流且音画时长差 ≤ 0.5 秒 | error | verify |
| V-16 | 字幕 cue 单调递增，最后一条结束时间 ≤ 成片时长 | error | verify |
| V-17 | `build-report.json` 完整；`verdict` 与各阶段状态一致 | error | verify |
| V-18 | 所有 `artifacts[].path` 均位于 `build/<slug>/` 内 | error | verify |
| V-19 | 阶段与检查的适用性判定一致：不适用写 `not_applicable`，适用但未执行写 `skipped` / `not_run` | error | verify |
| V-20 | `recording` 模式：notes 累计时长与录屏实测时长偏差 ≤ 容差（缺省 2 秒）；超出则 `fail`，并同时报告估计值与实测值；录屏缺失或 ffprobe 失败 → `fail`（`probe_failed`），不得计为时长偏差 | error | verify |
| V-21 | 所有声明路径符合 §3.1 路径合法性：相对、`/` 分隔、无 `..`、无绝对路径；仅大小写不一致时 `warning`（`path_case_mismatch`） | error / warning | validate |

### 3.7 契约演进

- 破坏性变更升 `schema_version`，并在 `shared/schemas/` 保留旧版本文件；不得原地改字段含义。
- 新增可选字段不升版本，但必须在本文与 `shared/schemas/` 同步。
- v1 的路径规则（相对谁、禁止绝对路径）不得放宽。

---

## 4. 目录迁移规则（R1）

### 4.1 前置

- R0 出口条件全部满足，工作区干净。
- 记录迁移前的 `git rev-parse HEAD`。
- 迁移期间不并行做其他改动。

### 4.2 精确映射

| 旧路径 | 新路径 | 方式 | 说明 |
| --- | --- | --- | --- |
| `CourseSlides/lessons/01-transformer-demo/` | `lessons/01-transformer-demo/` | `git mv` | 含 `assets/` |
| `CourseSlides/lessons/01-shell-for-ai-era/` | `lessons/01-shell-for-ai-era/` | `git mv` | 含 `assets/`、`outline.md` |
| `CourseSlides/lessons/` | — | 删除空目录 | 迁移后不得保留 |
| `CourseSlides/template/index.html` | 原路径 | 改内容 | 两处 Markdown 路径 |
| `CourseSlides/package.json` | 原路径 | 改内容 | `dev` 脚本 |
| 根 `index.html` | 新增 | 新建 | 仅做跳转，不是第二个渲染外壳 |
| `docs/*.md`、`CourseSlides/README.md`、`CourseSlides/docs/课件生成调用指南.md` | 原路径 | 改内容 | 路径与目录树描述 |
| `.gitignore` | 原路径 | 追加 `build/` | 产物不入库 |

`git mv` 对已跟踪文件有效；`01-shell-for-ai-era` 当前整体未跟踪，先 `git add` 再 `git mv`，或用普通 `mv` 后 `git add -A`。两种方式都必须保证提交历史里显示为 rename 或新增，不得出现"旧文件残留 + 新文件"。

### 4.3 文件级改写清单

**A. `CourseSlides/template/index.html`**

1. 第 26 行附近的静态挂载：

```html
<!-- 旧 -->
data-markdown="../lessons/01-transformer-demo/slides.md"
<!-- 新 -->
data-markdown="../../lessons/01-transformer-demo/slides.md"
```

2. 同文件 JS：

```js
// 旧
mount.setAttribute("data-markdown", `../lessons/${lesson}/slides.md`);
// 新
mount.setAttribute("data-markdown", `../../lessons/${lesson}/slides.md`);
```

3. 注释中的资源路径 `/lessons/01-transformer-demo/assets/diagram.svg` **保持不变**：它本来就是根路径，服务根改为工作区后仍然指向 `lessons/`。

**B. `CourseSlides/package.json`**

```json
// 旧
"dev": "live-server --port=8081 --entry-file=template/index.html --watch=lessons,template,css"
// 新
"dev": "live-server .. --port=8081 --entry-file=index.html --watch=lessons,CourseSlides/template,CourseSlides/css"
```

说明：npm 的 cwd 是 `CourseSlides/`，`..` 即工作区根；`--entry-file=index.html` 指向新增的根跳转页。live-server 源码会把 `--watch` 的每一项与根参数 `..` 做路径拼接（`live-server.js` 中 `path.join(dir, relativePath)`，`STATIC` 级别已确认），所以 `--watch` 必须写**相对工作区根**的路径。写成 `../lessons` 会拼成工作区外的目录，导致课件改动不触发刷新。

**C. 新增根 `index.html`（跳转页）**

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>CourseWorkspace</title>
  <script>
    window.location.replace("/CourseSlides/template/" + window.location.search);
  </script>
</head>
<body>
  <p>Redirecting to <a href="/CourseSlides/template/">CourseSlides/template/</a></p>
</body>
</html>
```

它只保留原有入口 URL `http://localhost:8081/?lesson=<slug>`，不加载 reveal、不渲染幻灯片。文档中所有 `localhost:8081` 地址因此**无需改写**。

**D. 文档路径改写**

以下文件中的 `CourseSlides/lessons/<slug>` 改为 `lessons/<slug>`，目录树中的 `lessons/` 从 `CourseSlides/` 子树移出：

| 文件 | 改写点 | 证据 |
| --- | --- | --- |
| `README.md` | 目录树、三类产物表、"日常动线" | 多处 |
| `docs/课件制作总指导.md` | 零、三仓表；五、规范速查 | 1 处显式 `CourseSlides/lessons` |
| `docs/课程交付清单模板.md` | "目录：`CourseSlides/lessons/...`" | 1 处 |
| `docs/交付清单-01-shell-for-ai-era.md` | "目录：`CourseSlides/lessons/...`" | 1 处 |
| `CourseSlides/README.md` | 目录结构、新建课件步骤 | 多处 |
| `CourseSlides/docs/课件生成调用指南.md` | 输出契约、目录约定 | 多处 |

改写只动路径与目录树，**不得改写正文其余内容**（§0.1）。改写后执行：

```powershell
rg -n "CourseSlides/lessons|CourseSlides\\\\lessons" --glob '!node_modules/**' .
```

期望输出为空。

**E. `.gitignore` 追加**

```gitignore
# 统一构建产物
build/
```

**F. 课程目录内新增文件**

- `lessons/<slug>/lesson.yaml`：按 §3.2 填写，数值取自现有清单，不新增事实。
- `lessons/<slug>/storyboard.yaml`：按 §3.3 填写，镜头与秒点必须与 `lecture_notes.md` 一致。

### 4.4 迁移步骤

1. 确认 R0 提交已完成（§1.6）；若未完成，停止并请用户处理，执行者不得代提交。
2. 创建 `lessons/`，用 `git add` + `git mv` 迁移两门课；确认 `CourseSlides/lessons/` 已空并删除。
3. 按 §4.3-A 改 `template/index.html` 两处。
4. 按 §4.3-B 改 `package.json`。
5. 新增根 `index.html`（§4.3-C）。
6. 按 §4.3-D 改 6 个文档；按 §4.3-E 改 `.gitignore`。
7. 新增两份 `lesson.yaml`、两份 `storyboard.yaml`（§4.3-F）。
8. 启动 `npm run dev`，逐项跑 §4.5 验证。
9. 提交 `R1: 课程数据独立到 lessons/`。

### 4.5 迁移验收

```powershell
# 1. 无旧路径残留
rg -n "CourseSlides/lessons" --glob '!node_modules/**' .        # 期望：无输出

# 2. 服务与页面（终端 A 启动服务并保持运行，终端 B 执行 curl）
cd CourseSlides
npm run dev
# 以下命令在另一个终端执行：
curl.exe -L -s -o NUL -w "%{http_code}`n" "http://localhost:8081/?lesson=01-shell-for-ai-era"        # 期望 200
curl.exe -L -s -o NUL -w "%{http_code}`n" "http://localhost:8081/lessons/01-shell-for-ai-era/slides.md"                # 期望 200
curl.exe -L -s -o NUL -w "%{http_code}`n" "http://localhost:8081/lessons/01-shell-for-ai-era/assets/terminal-shell-layers.svg"  # 期望 200
curl.exe -L -s -o NUL -w "%{http_code}`n" "http://localhost:8081/CourseSlides/node_modules/reveal.js/dist/reveal.js"     # 期望 200

# 3. 内容未被改动（对比迁移前后）
git diff --stat <R0哈希>..HEAD -- lessons/                     # 期望：只有 rename/新增，无正文增删

# 4. 动画工程不受影响
cd ../MotionStudio; npx tsc --noEmit                            # 期望：退出码 0
```

浏览器逐页检查两门课：页数分别为 8 与 20，图片正常加载，`?lesson=` 切换正常。

### 4.6 回滚

```powershell
git revert --no-edit <R1提交哈希>
```

回滚后重启 `npm run dev`，确认 `http://localhost:8081/?lesson=01-transformer-demo` 恢复。R1 之前不产生 `build/`，无需清理产物。

### 4.7 迁移后禁止出现的状态

- `CourseSlides/lessons/` 目录仍然存在（即使是空目录）。
- 任何文档、脚本中仍出现 `CourseSlides/lessons`。
- 根 `index.html` 变成第二个 reveal 外壳（加载 reveal、渲染幻灯片）。
- 课程 Markdown 正文出现非路径改动。
- `build/` 被提交进 git。

---

## 5. 阶段 PRD

### 5.1 R1 — 课程数据独立

**目标**：`lessons/` 成为课程内容唯一入口；CourseSlides 只消费；两门课在新位置正常渲染。

**前置**：R0 出口条件全部满足。

**任务**：

| 编号 | 任务 | 产物 |
| --- | --- | --- |
| T1.1 | 迁移两门课到 `lessons/` | 目录移动，无内容改动 |
| T1.2 | 改 `template/index.html` 两处 Markdown 路径 | 修改后文件 |
| T1.3 | 改 `package.json` dev 脚本；新增根跳转页 | 可用的 `http://localhost:8081/?lesson=<slug>` |
| T1.4 | 更新 6 个文档的路径与目录树 | 无旧路径残留 |
| T1.5 | 新增两份 `lesson.yaml` | 按 §3.2 |
| T1.6 | 新增两份 `storyboard.yaml` | 按 §3.3，与 notes 一致 |
| T1.7 | `.gitignore` 追加 `build/` | 产物不入库 |
| T1.8 | 跑 §4.5 验收并提交 | `R1: 课程数据独立到 lessons/` |

> R1 不再承担 R0 的提交动作；开工前置条件见 §1.6。

**出口验收**：§4.5 全部通过，且：

- [ ] 两门课的页数与 notes 块数不变（8/8、20/20）。
- [ ] 两门课在 1280×720 与 1600×900 下逐页无裁切。
- [ ] `slides.md` 的图片路径全部以 `/lessons/<slug>/assets/` 开头。
- [ ] `storyboard.yaml` 的镜头名与秒点与 `lecture_notes.md` 完全一致（8 条 + 1 条）。
- [ ] 修改 `slides.md` 后页面自动刷新（watch 覆盖 `lessons/`、`CourseSlides/template/`、`CourseSlides/css/`）。

**不做**：不改课程正文；不改 slug；不创建 `shared/`、`build/`、`assets/`；不引入 CourseControl。

**风险**：R0-01、R0-04、R0-08。

---

### 5.2 R2 — BlenderStudio

**目标**：通过后台命令生成一个可播放、可被 ffprobe 校验的 3D 视频，建立 Blender 工程的目录与配置边界。

**前置**：R1 验收通过。

**Spike（先做，结果决定实现）**：

1. 用 `--background --factory-startup --python` 跑一个程序化场景，验证 Blender 5.2 在无界面下能否出片。
2. 分别测试 `CYCLES`（CPU）与 `EEVEE`；记录可用引擎、单帧耗时、是否需要 GPU/OpenGL 上下文。
3. 记录 Blender 5.2 的实际 API（渲染引擎名、FFmpeg 输出参数）与任何与旧教程不一致之处。
4. 若后台渲染不可用，停止 R2 并向用户报告，不得改用截图拼帧冒充视频。

**任务**：

| 编号 | 任务 | 产物 |
| --- | --- | --- |
| T2.1 | 新建 `config/tools.yaml`，记录 `blender.exe`（不是 `blender-launcher.exe`）、超时、默认引擎 | 配置文件 |
| T2.2 | 新建 `BlenderStudio/README.md`，写明边界与调用方式 | 文档 |
| T2.3 | `BlenderStudio/scripts/render_smoke.py`：程序化 5 秒场景，1920×1080，30fps | 冒烟脚本 |
| T2.4 | `BlenderStudio/scripts/render_shot.py`：统一入口，接受 `--blend`、`--out`、`--fps`、`--res`、`--seconds`、`--engine` | 渲染脚本 |
| T2.5 | 新建 `scripts/blender-render.ps1`：读配置、拼命令、超时、日志、非零退出码透传 | 工作区入口 |
| T2.6 | 运行冒烟，产物写 `build/<slug>/blender/smoke.mp4`，日志写 `build/<slug>/logs/blender-smoke.log` | 视频 + 日志 |
| T2.7 | 记录实测引擎与版本到阶段报告 | 报告 |

`config/tools.yaml` 建议内容：

```yaml
schema_version: 1
blender:
  executable: "<BLENDER_EXE>"
  background: true
  timeout_seconds: 1800
  engine: BLENDER_EEVEE
  device: CPU
ffmpeg:
  ffmpeg: "ffmpeg"
  ffprobe: "ffprobe"
node:
  node: "node"
  npm: "npm"
python:
  uv: "uv"
```

`blender.engine` 是默认值；任务文件可用 `engine` 字段覆盖。默认 `BLENDER_EEVEE`；`CYCLES` 与 `BLENDER_WORKBENCH` 只作为显式选项，不作为默认。

调用约定：

```powershell
& "<BLENDER_EXE>" `
  --background --factory-startup `
  --python "BlenderStudio/scripts/render_smoke.py" `
  -- --out "build/01-shell-for-ai-era/blender/smoke.mp4" --fps 30 --res 1920x1080 --seconds 5
```

`render_shot.py` 职责：解析 `--` 之后的参数；设置帧率、分辨率、引擎、输出格式（FFmpeg / MPEG4 / H.264）；设定帧范围；渲染动画；任何异常以非零码退出。不得在脚本里硬编码 Blender 路径（由 PowerShell 入口传入）。

**出口验收**：

- [ ] `ffprobe` 显示：容器 `mp4`，视频流 `h264`，`1920×1080`，`30` fps，时长 `5.0 ± 0.2` 秒。
- [ ] 命令退出码 0，日志存在且包含 Blender 版本与引擎。
- [ ] 所有产物都在 `build/<slug>/blender/`，未写入其他工程目录。
- [ ] `BlenderStudio/` 内没有视频产物（`.blend`、`.py`、任务 YAML 除外）。

**不做**：不把 Blender 纳入 R4 之前的自动调度；不安装 `bpy`；不改 Blender 安装目录。

**风险**：R0-05。

---

### 5.3 R3 — RemotionStudio

**目标**：把 Blender、Motion Canvas、Manim 的成片与幻灯片画面、旁白、字幕编排成一条可渲染的时间线，输出 1920×1080 / 30fps 的成片。

**前置**：R2 验收通过（至少有一条真实 Blender 片段可供组合）。

**编排模式（本次新增的架构决定）**：

R0 审计发现工作区**没有幻灯片画面采集路径**（§1.5 R0-13）。因此 R3 必须显式支持两种模式，由 `lesson.yaml` 的 `compose.mode` 选择：

| 模式 | 底稿来源 | 适用 | 前置输入 |
| --- | --- | --- | --- |
| `deck` | 逐页静态图 `build/<slug>/slides/slide-###.png` | 无录屏、要可重复构建的成片 | 幻灯片截图（R3 提供最小采集脚本或人工导出） |
| `recording` | 一条录屏 `build/<slug>/slides/recording.mp4` | 沿用现有"录屏 + 插片"工作流 | 人工 OBS 录屏 |

两种模式下，动画都是 `timeline_role=overlay` 的插片，叠在底稿时间线上，不改变总时长；当前课程全部为 `presentation=cutaway`。

**S-R3-1 素材读取 spike（工程初始化后立即做，结果决定 T3.5 的实现）**

Remotion 的 `staticFile()` 面向 `public/`，而本仓素材在 `build/`。必须先验证 Windows 路径、含空格路径、中文路径与只读权限，并实际渲染出片，不能只查文档。结论二选一：

- **A. 直接引用**：`Img` / `OffthreadVideo` 的 `src` 使用 `staticFile()` 或 HTTP 可达路径；
- **B. staging**：构建前把所需素材复制或硬链接到 `RemotionStudio/public/staging/<slug>/`，`src` 用 `staticFile("staging/<slug>/...")`，渲染结束后由控制层清理；`public/staging/` 必须 gitignore。

失败判定：任一测试路径无法读取，或只在开发服务器下可用而 CLI 渲染失败，则该方案不可用，换另一方案。结论写入 `docs/决策记录-Remotion素材访问.md`。

**任务**：

| 编号 | 任务 | 产物 |
| --- | --- | --- |
| T3.1 | 初始化 `RemotionStudio/`，锁定 Remotion 版本；在 Node 24 下验证安装与渲染；把 `public/staging/` 加入本工程 `.gitignore`；记录实际版本 | 可运行的工程 |
| T3.2 | 跑 S-R3-1 spike，确定素材访问方案 | 结论 + 最小复现 |
| T3.3 | `remotion.config.ts`：H.264、`overwriteOutput`、并发数 | 配置 |
| T3.4 | `src/index.ts`、`src/Root.tsx`：注册 `CourseVideo` composition，输入 props 为 `shots.json` 内容 | 入口 |
| T3.5 | `src/compositions/CourseVideo.tsx`：按 `timeline_role` 排时间线，按 `presentation` 选渲染分支；`slide` 用 `Img`，`recording` 用 `OffthreadVideo`；`src` 路径按 S-R3-1 的结论解析 | 主合成 |
| T3.6 | `src/components/`、`src/transitions/`：`cutaway` / `picture_in_picture` / `transparent_overlay` 三种呈现；转场默认 0.3 秒可配置 | 组件 |
| T3.7 | `src/subtitles/Captions.tsx`：解析 SRT，按时间渲染；`subtitles.enabled=false` 时不加载 | 字幕组件 |
| T3.8 | `src/audio/Narration.tsx`：挂载旁白音频；缺省静音 | 音频组件 |
| T3.9 | `shared/design-tokens/tokens.json` + `src/styles/tokens.ts`：橙白令牌单一来源 | 共享令牌 |
| T3.10 | 幻灯片截图采集脚本（规格见下） | 截图 + manifest |
| T3.11 | 冒烟：2 页真实截图 + `build/<slug>/blender/smoke.mp4` | 预览成片 |
| T3.12 | 写 `RemotionStudio/README.md`：端口、命令、props 格式、staging 清理 | 文档 |

渲染命令：

```powershell
cd RemotionStudio
npx remotion render src/index.ts CourseVideo `
  ../build/<slug>/final/preview-remotion.mp4 `
  --props=../build/<slug>/shots.json
```

素材路径以 S-R3-1 的结论为准：直接引用时 `shots[].source` 相对 `build/<slug>/` 解析；staging 方案下由控制层先复制到 `public/staging/<slug>/`，渲染后清理。

**T3.10 幻灯片截图采集规格**

- 工具：Playwright + Chromium，作为浏览器自动化依赖安装在 `RemotionStudio`（R4 再决定是否抽成独立 `capture_slides` 适配器），不引入 Agent 框架。
- 输入：`http://localhost:8081/?lesson=<slug>`；固定视口 1920×1080（Reveal 画布 1280×720 按 1.5 倍缩放）。
- 等待条件：`document.fonts.ready`、图片 `complete`、Reveal 初始化完成；每次翻页后等待一次渲染帧。
- 遍历：用 `Reveal.slide(h, v)` 或 `Reveal.next()` 按线性顺序推进；垂直子页（`3b`）单独成图。
- 输出：`build/<slug>/slides/slide-<页码>.png`（子页如 `slide-003b.png`），以及 `build/<slug>/slides/capture-manifest.json`，记录页码、文件、分辨率、时间戳、来源（`auto` / `manual`）。
- 失败：任一页加载失败、空白页、尺寸不符，或文件数与页数不一致 → 阶段失败，不得生成通过报告。
- 人工替代：允许人工导出，但 manifest 必须标 `source: manual` 且文件数与页数一致；缺图按失败处理。

**出口验收**：

- [ ] `npx remotion studio` 在 `3000` 端口可用（或被占用时 `3001`），并记录实际端口。
- [ ] 冒烟成片：`1920×1080`、`30` fps、`h264`，时长等于 `shots.json` 的 `timeline.total_duration_s`（±0.2 秒）。
- [ ] 冒烟使用的两页底稿是 `01-shell-for-ai-era` 第 1、2 页经 T3.10 采集的真实截图，不是用 SVG 直接充当底稿。
- [ ] `cutaway` 片段全屏替换底稿且不改变总长；`picture_in_picture` 与 `transparent_overlay` 至少各用 1 秒测试片段验证一次。
- [ ] 截图页数与 `slides.md` 页数一致（含垂直子页），`capture-manifest.json` 完整；缺图时阶段失败。
- [ ] 素材读取按 S-R3-1 结论实现，并写入 `docs/决策记录-Remotion素材访问.md`。
- [ ] 关闭字幕与旁白时渲染不报错。
- [ ] `RemotionStudio/node_modules` 与 `public/staging/` 未被提交。
- [ ] 渲染不读取 `MotionStudio/`、`ManimSandbox/` 源码，只读 `build/`。

**不做**：不做自动语音识别；不做自动 TTS；不做云端渲染；不把 Remotion 变成第二个幻灯片渲染器。

**风险**：R0-09、R0-10、R0-13。

---

### 5.4 R4 — CourseControl

**目标**：一条命令触发适用阶段的构建，产物、日志、报告齐全；失败即停，不产生虚假通过。

**前置**：R3 验收通过。

**Motion Canvas 渲染 spike（阻塞项）**：

R0 已确认 Motion Canvas 3.17.2 没有 CLI 入口（§1.5 R0-02）。R4 开始前必须选定方案并记录到 `docs/决策记录-MotionCanvas渲染.md`：

| 方案 | 做法 | 判定 |
| --- | --- | --- |
| A. 浏览器驱动 | Playwright/Chromium 打开 `localhost:5173`，操作 RENDER | 可行性与稳定性待验证；引入 Playwright 依赖 |
| B. 自建 headless exporter | 用 Chromium 直接加载项目并调用渲染 API | 工作量大，需理解内部 API |
| C. 人工导出 + 校验（基线） | 用户手动导出 MP4 到 `build/<slug>/animation/`，控制层校验与收集 | 立即可用；报告标记 `manual` |

**基线决定**：若 A/B 在 spike 时限内未验证可行，采用 C。采用 C 时，`build` 的 animation 阶段状态为 `skipped`（原因 `manual_export_required`），最终 `verdict` 为 `incomplete`，**不得写 pass**。`lesson.yaml` 的 `build.allow_manual_animation_export` 控制是否允许该状态。V-10 在人工导出未执行时为 `skipped`，导出完成并通过 ffprobe 后为 `pass`；只有自动渲染模式下缺文件才是 `fail`。

**任务**：

| 编号 | 任务 | 产物 |
| --- | --- | --- |
| T4.1 | 初始化 `CourseControl/`（uv 项目，包名 `course_control`，依赖 pydantic、PyYAML、typer） | `pyproject.toml`、`uv.lock`、`.venv` |
| T4.2 | `contracts.py`：lesson / storyboard / shots / report 的 pydantic 模型；导出 JSON Schema 到 `shared/schemas/` | 模型与 schema |
| T4.3 | `validators/`：实现 V-01 ~ V-09 | 校验器 |
| T4.4 | `adapters/`：slides（截图采集）、motion_canvas、manim（`--media_dir build/<slug>/tmp/manim-media`）、blender、remotion、ffmpeg | 适配器 |
| T4.5 | `pipeline/`：阶段图 `validate → capture_slides → render(animation/blender) → collect → compose → verify`；按 `lesson.yaml` 计算适用性；阶段间失败即停 | 调度 |
| T4.6 | `report.py`：每阶段日志、`build-report.json`、`verdict` 规则 | 报告 |
| T4.7 | `cli.py`：`audit` / `validate` / `build` / `verify`，支持 `--lesson`、`--lesson-dir`、`--json` | CLI |
| T4.8 | `scripts/setup.ps1`、`scripts/check.ps1`、`scripts/build-lesson.ps1`（参数：`-Lesson`、`-LessonDir`（默认 `lessons/`）、`-SkipRender`、`-SkipCompose`） | 工作区入口 |
| T4.9 | 单元测试：校验器用 fixture 覆盖 V-01 ~ V-09；调度用 stub 适配器（ffmpeg `lavfi` 生成 1 秒色块）覆盖成功/失败/跳过 | `tests/` |
| T4.10 | 用 `lesson-smoke` 跑通完整构建；用 `lesson-blender-only` 验证 `not_applicable`；再注入错误验证 fail-closed | 报告样张 |
| T4.11 | 记录 Motion Canvas 方案决策 | 决策文档 |

Stage 图与输入输出：

| 阶段 | 输入 | 输出 | 失败处理 |
| --- | --- | --- | --- |
| `validate` | `lesson.yaml`、`storyboard.yaml`、Markdown | 校验结果 | 停 |
| `capture_slides` | `slides.md` + 本地 Reveal 服务 | `build/<slug>/slides/slide-###.png` + `capture-manifest.json` | 停（`recording` 模式为 `not_applicable`） |
| `render:animation` | storyboard 的 motion/manim 镜头 | `build/<slug>/animation/*.mp4`；Manim 原始产物在 `tmp/manim-media/` | 停（manual 模式下 skipped） |
| `render:blender` | storyboard 的 blender 镜头 + task YAML | `build/<slug>/blender/*.mp4` | 停 |
| `collect` | 成片 + ffprobe + 幻灯片画面 | `shots.json` | 停 |
| `compose` | `shots.json` → Remotion | `build/<slug>/remotion/`、`final/` | 停 |
| `verify` | 成片、字幕、报告 | `checks[]`、`verdict` | 产出失败报告 |

**阶段适用性**：`capture_slides` 仅在 `compose.mode=deck` 时执行；`render:animation` 的 Motion 部分仅在 `engines` 含 `motion_canvas` 时执行，Manim 部分仅在含 `manim` 时执行；`render:blender` 仅在含 `blender` 时执行。不适用写 `not_applicable`，不计入 `incomplete`。纯 Blender 课程不得因为没有 Motion Canvas 场景而失败。

**出口验收**：

- [ ] `.\scripts\build-lesson.ps1 -Lesson <fixture>` 一条命令跑完，退出码 0（fixture 全部阶段可自动完成时）。
- [ ] `build/<fixture>/final/build-report.json` 的 `verdict` 与其阶段状态一致。
- [ ] 删除任一必需成片后重跑：命令非零退出，报告 `verdict=fail`，下游阶段为 `skipped`，日志指明缺失文件。
- [ ] Motion Canvas 为 manual 模式时：`verdict=incomplete`，报告写明 `manual_export_required`，不写 pass。
- [ ] 每个阶段都有独立日志，日志含命令行、耗时、退出码。
- [ ] 所有写入都在 `build/<slug>/` 内（V-18）。
- [ ] Manim 渲染时 `--media_dir` 指向 `build/<slug>/tmp/manim-media`；构建前后 `ManimSandbox/media/` 的文件数与修改时间不变。
- [ ] 纯 Blender fixture 构建：Motion 相关阶段为 `not_applicable`，`verdict` 仍可为 `pass`。
- [ ] 单元测试全部通过。

**不做**：不做任务队列/守护进程；不引入 LangGraph 等编排框架；不做增量缓存（v1 全量构建）；不自动提交 git。

**风险**：R0-02、R0-03、R0-10。

---

### 5.5 R5 — 自动验收

**目标**：构建结束后自动检查文件、时长、帧率、分辨率、音画同步与字幕时轴，输出可机器读取的结论；验收对象用 fixture，真实课程按内容状态如实标记。

**前置**：R4 验收通过。

**任务**：

| 编号 | 任务 | 产物 |
| --- | --- | --- |
| T5.1 | 校验器覆盖 V-10 ~ V-21（V-21 在 `validate` 阶段执行）：ffprobe 解析、时间线连续性、时长容差、音画差、字幕轴、适用性一致性、录屏时间轴校准、路径合法性 | 校验器 |
| T5.2 | fixture 课程：`CourseControl/tests/fixtures/lesson-smoke/`（deck，2 页真实截图 + Blender 冒烟）与 `lesson-blender-only/`（纯 Blender，验证 `not_applicable`） | 可重复验收样本 |
| T5.3 | `check.ps1`：环境版本、工具路径、端口占用、契约校验、构建产物校验 | 工作区自检 |
| T5.4 | 更新 `docs/课件制作总指导.md` 与 `README.md`：加入 `build/` 产物、构建命令、验收含义 | 文档 |
| T5.5 | 对真实课程 `01-shell-for-ai-era` 跑一次完整构建，确认报告如实标记占位页与未导出动画 | 真实报告 |
| T5.6 | 提交 `R5: 自动验收与一键构建` | 提交 |

**旁白与字幕的适用性**：`enabled=false` 表示用户主动选择无声/无字幕，相关检查为 `not_applicable`；`enabled=true` 但源文件缺失，检查为 `fail`。两者不得混用，也不得把"用户没要旁白"写成"缺文件"。

**出口验收**：

- [ ] `lesson-smoke` 的 `verdict=pass`，且 `checks[]` 全部为 `pass`。
- [ ] `lesson-blender-only` 的 `verdict=pass`，Motion/Manim 相关阶段与检查为 `not_applicable`，不阻塞通过。
- [ ] 将 `narration.enabled` 改为 `true` 且删除音频源：verdict 为 `fail`；改回 `false`：对应检查为 `not_applicable`。
- [ ] 真实课程的报告不出现 `pass`：存在占位页、手动导出或缺失旁白时，`verdict` 必须是 `incomplete` 或 `fail`，并在 `failures[]` 说明原因。
- [ ] 验收报告包含每项检查的 `expected` 与 `actual`，人不用重跑就能判断。
- [ ] `check.ps1` 在缺少工具（例如 Blender 路径失效）时明确报错，不静默跳过。

**不做**：不评判课程内容质量（事实性、教学效果）；不做画面美学审查；不自动发布。

---

## 6. 测试与验收规范

### 6.1 分层

| 层 | 范围 | 是否需要渲染 | 何时跑 |
| --- | --- | --- | --- |
| L0 静态契约 | 文件存在、schema、页数、路径、禁用标记 | 否 | 每次改动 |
| L1 单引擎冒烟 | Blender 5 秒、Manim 1 个短场景、Motion 1 个场景 | 是 | R2/R3 |
| L2 组合 | fixture（截图底稿 + 2 镜）→ Remotion 成片 | 是 | R3/R4 |
| L3 全量 | 真实课程全部镜头 → 成片 + 报告 | 是（耗时长） | R5 与交付前 |

### 6.2 命令与期望

```powershell
# L0
uv run --project CourseControl course-control validate --lesson 01-shell-for-ai-era
# 期望：退出码 0；V-01 ~ V-09 pass；若 V-06/V-05 失败，如实列出

# L1 Blender
.\scripts\blender-render.ps1 -Lesson 01-shell-for-ai-era -Scene smoke
# 期望：build/01-shell-for-ai-era/blender/smoke.mp4 生成，ffprobe 校验通过

# L1 Manim（显式 media_dir，不写回 ManimSandbox/media）
cd ManimSandbox
uv run manim render -ql --media_dir ../build/01-transformer-demo/tmp/manim-media 01-transformer-demo/dot_product.py DotProduct
# 期望：build/01-transformer-demo/tmp/manim-media/videos/dot_product/480p15/DotProduct.mp4
# 注意：自动化不加 -p（-p 会尝试打开播放器）；--media_dir 已在 Manim 0.22 的 render 子命令中验证存在

# L2 fixture 组合
.\scripts\build-lesson.ps1 -Lesson lesson-smoke -LessonDir CourseControl/tests/fixtures/lesson-smoke
# 期望：verdict=pass，build-report.json 生成

# L3 真实课程
.\scripts\build-lesson.ps1 -Lesson 01-shell-for-ai-era
# 期望：按实际状态输出 pass / incomplete / fail；不得虚假 pass
```

### 6.3 成片验收矩阵

| 检查 | 方法 | 通过标准 | 失败级别 |
| --- | --- | --- | --- |
| 文件存在 | 读取 `final/` | `course-video.mp4`、`build-report.json` 存在；启用字幕时有 `course-subtitles.srt` | error |
| 路径合法性 | 契约解析 | 所有路径相对、`/` 分隔、无 `..`；绝对路径或反斜杠出现即失败 | error |
| 容器/编码 | `ffprobe -show_streams` | `mp4`，视频 `h264`，`yuv420p` | error |
| 分辨率 | ffprobe | `1920×1080` | error |
| 帧率 | ffprobe | `30` | error |
| 总时长 | ffprobe | 与 `timeline.total_duration_s` 差 ≤ 0.2 秒 | error |
| 课程时长 | ffprobe + notes | 与 `notes_total_seconds` 差 ≤ 容差（默认 2 秒） | error |
| 录屏时间轴 | notes 累计 vs ffprobe | `recording` 模式偏差 ≤ 容差；超出报 `fail` 并列出估计/实测 | error |
| 音画同步 | 音频流时长 | 若启用旁白，音频与视频时长差 ≤ 0.5 秒 | error |
| 字幕时轴 | 解析 SRT | 单调递增；最后结束 ≤ 视频时长；条数 > 0（启用时） | error |
| 呈现方式 | `shots.json` + 抽查帧 | `cutaway` 全屏替换且不延长总长；`picture_in_picture` / `transparent_overlay` 按预期叠加 | error |
| 适用性 | 读取报告 | 不适用的阶段写 `not_applicable`，适用但未执行写 `skipped` / `not_run` | error |
| 路径边界 | 报告 `artifacts[]` | 全部位于 `build/<slug>/` | error |
| 报告一致性 | 读取报告 | `verdict` 与阶段状态、检查状态一致 | error |
| 日志完整性 | 读取 `logs/` | 每个执行过的阶段一份日志，含命令与退出码 | error |

### 6.4 失败语义

| 情况 | 报告写法 | 退出码 |
| --- | --- | --- |
| 所有必需阶段与检查通过 | `verdict: pass` | 0 |
| 有阶段被跳过（manual 导出，或用户主动关闭的可选输入） | `verdict: incomplete`，`failures[]` 写明原因 | 0（可配置为 1） |
| 阶段或检查在当前配置下不适用 | `not_applicable`，不影响 `verdict` | 0 |
| 任一阶段或检查失败 | `verdict: fail`，`failures[]` 写明文件与命令 | 非 0 |
| 工具不存在或路径失效 | `fail`，不得跳过 | 非 0 |
| 用户中断 | `incomplete`，日志保留 | 非 0 |

### 6.5 证据要求

- 每个阶段报告必须包含：实际命令、工作目录、开始/结束时间、退出码、产物路径与大小。
- 时长与分辨率一律写实测值，不写场景代码里的估计值。
- 报告与聊天汇报必须使用同一套状态词；不得把 `skipped` 描述成"完成"。

---

## 7. 风险登记

| 编号 | 风险 | 触发条件 | 影响 | 缓解 | 责任阶段 |
| --- | --- | --- | --- | --- | --- |
| R-01 | 迁移破坏幻灯片路径 | 只搬目录未改模板/服务根 | 页面与图片 404 | §4.5 四组 curl + 逐页检查 | R1 |
| R-02 | Motion Canvas 无法自动渲染 | spike 未找到稳定方案 | 一键构建不完整 | 基线 C：人工导出 + 校验，报告标记 incomplete | R4 |
| R-03 | 单一 `project.ts` 导致渲染全部场景 | 尝试按课渲染 | 时长与产物混乱 | 每次导出后校验文件集合；R5 再评估拆分项目 | R4 |
| R-04 | Blender 后台渲染引擎不可用 | 无 GPU/OpenGL 上下文 | R2 无法产出视频 | 先测 CYCLES CPU；不可用则停止并报告 | R2 |
| R-05 | Blender 5.2 API 与教程不一致 | 直接照抄旧脚本 | 脚本报错 | spike 记录实际 API；脚本做版本检查 | R2 |
| R-06 | Remotion 与 Node 24 不兼容 | 安装或渲染失败 | R3 阻塞 | 记录实际支持的 Node 版本；必要时用独立 Node 版本管理，不改系统 | R3 |
| R-07 | 无幻灯片画面来源 | 未录屏、未截图 | 无法出完整成片 | `deck` / `recording` 双模式；把缺失写进报告 | R3 |
| R-08 | 无旁白/字幕输入 | 用户未提供 | 成片无音轨/无字幕 | 未启用 → `not_applicable`；启用但缺源文件 → `fail`（不得用 `skipped`） | R3/R5 |
| R-09 | 真实课程内容未完成 | 占位页、中文待补 | 不能 pass | 用 fixture 验收；真实课程如实 incomplete | R5 |
| R-10 | 产物误入 git | 忘记 ignore | 仓库膨胀 | `.gitignore` 加 `build/`；提交前 `git status` 检查 | R1 起 |
| R-11 | 适配器越界写入 | 脚本写死输出路径 | 工程互相污染 | 路径一律由控制层传入；V-18 校验 | R4 |
| R-12 | 构建报告虚假通过 | 缺输入时默认跳过 | 失去验收意义 | §6.4 失败语义；报告审查 | R4/R5 |
| R-13 | Manim 产物继续写回 `ManimSandbox/media/` | 适配器未传 `--media_dir` | 产物分散、V-18 失效 | 适配器强制传 `--media_dir build/<slug>/tmp/manim-media`；构建前后比对 `media/` 文件状态 | R4 |
| R-14 | Remotion 读不到 `build/` 外部素材 | `staticFile()` 只认 `public/` | R3 阻塞或渲染空白 | S-R3-1 spike；必要时 staging 到 `public/staging/` 并清理 | R3 |
| R-15 | 截图漂移（字体未加载、图片未就绪） | 未设等待条件 | 成片出现空白/半渲染页 | 固定视口、`document.fonts.ready`、逐页等待与校验；失败即停 | R3/R4 |

---

## 8. 交付给执行者的任务清单

按顺序勾选；每项完成后先跑对应验收，再进入下一项。

### R0

- [ ] 用户确认并提交当前工作区改动
- [ ] 记录提交哈希
- [ ] 复核 §1.2 版本事实

### R1

- [ ] T1.1 迁移 `CourseSlides/lessons/` → `lessons/`
- [ ] T1.2 改模板两处路径
- [ ] T1.3 改 dev 脚本 + 新增根跳转页
- [ ] T1.4 更新 6 个文档路径
- [ ] T1.5 新增两份 `lesson.yaml`
- [ ] T1.6 新增两份 `storyboard.yaml`
- [ ] T1.7 `.gitignore` 追加 `build/`
- [ ] T1.8 跑 §4.5 并提交

### R2

- [ ] Spike：后台渲染引擎验证并记录
- [ ] T2.1 `config/tools.yaml`
- [ ] T2.2 `BlenderStudio/README.md`
- [ ] T2.3 `render_smoke.py`
- [ ] T2.4 `render_shot.py`
- [ ] T2.5 `scripts/blender-render.ps1`
- [ ] T2.6 冒烟产物 + 日志
- [ ] T2.7 阶段报告并提交

### R3

- [ ] T3.1 初始化工程并验证 Node 24
- [ ] T3.2 S-R3-1 素材读取 spike，记录结论
- [ ] T3.3 `remotion.config.ts`
- [ ] T3.4 入口与 composition
- [ ] T3.5 `CourseVideo`（按 `timeline_role` / `presentation`）
- [ ] T3.6 三种呈现组件与转场
- [ ] T3.7 字幕组件
- [ ] T3.8 音频组件
- [ ] T3.9 共享令牌
- [ ] T3.10 截图采集脚本 + manifest
- [ ] T3.11 冒烟成片
- [ ] T3.12 README
- [ ] 出口验收并提交

### R4

- [ ] Motion Canvas 渲染 spike 与决策记录
- [ ] T4.1 ~ T4.7 控制层实现（含 `capture_slides` 阶段与适用性判定）
- [ ] T4.8 三个 PowerShell 入口
- [ ] T4.9 单元测试
- [ ] T4.10 fixture 构建 + fail-closed 验证 + 纯 Blender `not_applicable` 验证
- [ ] 出口验收并提交

### R5

- [ ] T5.1 verify 实现
- [ ] T5.2 fixture 课程（`lesson-smoke` + `lesson-blender-only`）
- [ ] T5.3 `check.ps1`
- [ ] T5.4 文档更新
- [ ] T5.5 真实课程报告
- [ ] 出口验收并提交

**遇到以下情况必须停下并报告，不得自行决定**：需要改写课程正文；需要删除或移动 `<AI_ROOT>` 内文件；需要改变端口约定；需要放宽任一验收标准；需要引入 §2.7 冻结清单中的工具。

---

## 附录 A：R0 文件清单

| 路径 | 用途 | 本次审计依据 |
| --- | --- | --- |
| `README.md` | 工作区总览、三工程分工、端口、隔离规则 | 阅读全文 |
| `docs/课件制作总指导.md` | 四阶段流水线、双文件契约、动画路由、本地模型 | 阅读全文 |
| `docs/课程交付清单模板.md` | 每课交付清单模板 | 阅读全文 |
| `docs/交付清单-01-shell-for-ai-era.md` | 本期实际交付状态 | 阅读全文 |
| `CourseSlides/README.md` | 幻灯片工程说明、目录、图片路径规则 | 阅读全文 |
| `CourseSlides/docs/课件生成调用指南.md` | 生成器调用与单页规范 | 阅读前 120 行 |
| `CourseSlides/template/index.html` | 唯一渲染外壳、lesson 切换 | 阅读全文 |
| `CourseSlides/package.json` | reveal 6.0.2、live-server、dev 脚本 | 阅读全文 |
| `MotionStudio/README.md` | 场景约定、编辑器使用、目录结构 | 阅读全文 |
| `MotionStudio/src/project.ts` | 9 个场景注册 | 阅读全文 |
| `MotionStudio/src/styles/mckinsey.ts` | 橙白令牌 | 阅读全文 |
| `MotionStudio/vite.config.ts` | motionCanvas + ffmpeg 插件 | 阅读全文 |
| `ManimSandbox/README.md` | uv 工作流、产物路径 | 阅读全文 |
| `ManimSandbox/pyproject.toml` | manim 0.22.0、Python 3.12 | 阅读全文 |
| `lessons`（迁移前 `CourseSlides/lessons/`） | 两门课 | 页数、块数、切口、素材 |

## 附录 B：术语

| 术语 | 含义 |
| --- | --- |
| 双文件契约 | `slides.md`（观众视图）+ `lecture_notes.md`（讲师手册）按页序一一对应 |
| 动画切口 | `lecture_notes.md` 中标注的"引擎 + 场景名 + 秒点"，是 `storyboard.yaml` 的来源 |
| 底稿 | 成片时间线的骨架：`deck` 模式为逐页静态图，`recording` 模式为一条录屏 |
| 插片 | `timeline_role=overlay` 的动画片段，覆盖在底稿上，不改变总时长；呈现方式由 `presentation` 决定 |
| fixture | 用于自动验收的最小课程样本，与真实课程内容解耦 |
| fail-closed | 任一必需步骤失败或缺失时停止并判失败，不以跳过代替成功 |
| manual_export_required | Motion Canvas 需人工导出时的阶段状态，最终 verdict 为 incomplete |
