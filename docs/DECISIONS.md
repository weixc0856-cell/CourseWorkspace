# 决策记录（ADR）

格式：每条只记录**已生效**的决策、理由与后果。历史细节见 `docs/archive/`。
状态：`accepted` / `superseded`。

| 编号 | 决策 | 状态 |
| --- | --- | --- |
| D-001 | 分层：内容 / 展示 / 动画 / 三维 / 合成 / 控制 / 共享 | accepted |
| D-002 | 双文件契约：`slides.md` 给观众，`lecture_notes.md` 给讲者 | accepted |
| D-003 | 课程内容独立到 `lessons/`，不归任何渲染工程 | accepted |
| D-004 | Motion Canvas 采用人工导出（无 CLI 导出） | accepted |
| D-005 | Remotion 通过 staging + `staticFile` 访问素材 | accepted |
| D-006 | 五状态语义：`skip ≠ pass` | accepted |
| D-007 | Blender v1（课程渲染任务）与 v2（场景任务）并存，分工明确 | accepted |
| D-008 | 本地模型调用统一经 `shared/ai_runtime` 的跨进程锁 | accepted |
| D-009 | 在线模型独立为 `ContentQA`，不与本地模型互相冒充 | accepted |
| D-010 | 上下文预算分档 16K / 32K，64K 仅硬上限 | accepted |
| D-011 | 文本模型 CPU-only；视觉模型允许 GPU，且与 ComfyUI 互斥 | accepted |
| D-012 | 取消 8082 备用端口约定 | accepted |
| D-013 | Manim 保活但不接入课程主流程 | accepted |
| D-014 | 真实课程内容缺失与人工步骤如实进入交付状态，不伪装自动化 | accepted |
| D-015 | IR v2 增量扩展 TEXT / CURVE / ORTHO，保持 `schema_version: 2` | accepted |
| D-016 | 二维标注通过 `shots.json` 的 `annotations[]` 传递，Remotion 负责渲染 | accepted |
| D-017 | 二维文字捆绑 Noto Sans SC（OFL）；Blender TEXT 仍用内置 Bfont | accepted |
| D-018 | 材质预设由控制层展开，Blender 只接收展开后的任务 | accepted |
| D-019 | 科学着色使用独立 shader，范围与单位必填，色标定义单一来源 | accepted |
| D-020 | 受限表达式由 `shared/scene_expr` 单实现，禁止 `eval` / `exec` | accepted |
| D-021 | 代码/终端会话采用三证据链 + Docker 受限执行 + V-23/V-24 | accepted |
| D-022 | VS Code 会话用 shell integration 执行、PrintWindow 录制 | accepted |
| D-023 | Python 工具链采用联网演示 + 离线验证；本机以 8899 端口本地 HTTP 索引演示 | accepted |
| D-024 | Manim 作为动画渲染引擎；FFT 为技术基线，Transformer 为产品基线 | accepted |
| D-025 | Rust 镜头先用 host VS Code + Git Bash；Docker Rust 镜像受阻再迁移 | accepted |
| D-028 | 本地 8080 优先；显式配置远程 OpenAI 兼容 API 时可在 busy/启动失败/锁超时后回退 | accepted |
| D-029 | 跟踪文件禁止本机绝对路径；本机路径只留在忽略的 `config/*.yaml` / `.env`，并维护 `.example` | accepted |
| D-030 | V1-D/E 先做只读适配与双向兼容层，不重写 Session runner 或 Remotion | accepted |

---

## D-001 分层架构

**背景**：早期幻灯片、动画、视频混在一个工程里，任何人改动都可能破坏另一个人的产物。

**决策**：内容（`lessons/`）、展示（`CourseSlides`）、动画（`MotionStudio` / `ManimSandbox`）、三维（`BlenderStudio`）、合成（`RemotionStudio`）、控制（`CourseControl`）、共享（`shared/`）分层；工程之间只通过文件契约交换数据。

**后果**：每个工程可独立验证；代价是契约变更需要同步多处。

## D-002 双文件契约

**背景**：口播稿混进幻灯片会导致观众看到讲稿，也让页数统计失真。

**决策**：`slides.md` 只放观众可见内容；`lecture_notes.md` 按 `### Slide N` 分块，每块四要素（时长预算、动画切入、技术核查、逐字口播）。

**后果**：页数可被程序校验（V-03/V-04）；作者需要维护两份文件。

## D-003 内容独立

**背景**：R1 之前课程在 `CourseSlides/lessons/`，内容被展示引擎"拥有"。

**决策**：迁移到根级 `lessons/`；任何渲染工程只读。

**后果**：更换展示引擎不影响内容；旧路径不再出现。

## D-004 Motion Canvas 人工导出

**背景**：Motion Canvas 3.17.2 没有 CLI 渲染入口，官方只提供编辑器 RENDER 按钮。

**备选**：Playwright 驱动编辑器（依赖 UI，易碎）；自建 headless exporter（逆向 API，维护成本高）。

**决策**：人工导出到 `build/<slug>/animation/<scene-stem>.mp4`，控制层只校验。缺失时 `skipped` + `incomplete`。

**后果**：纯 Motion 课程在导出前无法 `pass`；这是有意的，避免伪造通过。

## D-005 Remotion 素材访问

**背景**：Remotion 只能通过 `public/` 访问静态文件，而产物必须留在 `build/`。

**决策**：`stage-assets.mjs` 把 `shots.json` 声明的文件复制到 `public/staging/<slug>/`；合成成功清理，失败保留。路径经 `staticFile()` 解析。

**后果**：`build/` 仍是唯一产物源；staging 是唯一临时目录。

## D-006 五状态语义

**决策**：`pass` / `fail` / `skipped` / `not_run` / `not_applicable`；verdict 只能是 `pass` / `fail` / `incomplete`。

**后果**：报告必须解释每个非 pass 阶段；`incomplete` 不等于失败，但绝不算完成。

## D-007 Blender 双 Schema

**背景**：v1 是课程流水线的最小渲染任务（`output`、`format`、`resolution`、`fps`、`frames`、可选 `blend`）；v2 是完整场景描述（对象、材质、相机、灯光、GN、动画）。

**决策**：保留两代，按用途分工：

- v1：`BlenderStudio/tasks/<lesson>/*.json`，由 `render:blender` 阶段消费；
- v2：`BlenderStudio/tasks/scene-system/` 与 `ModelingStudio/tasks/`，由 `scene-run` 消费。

两代都有独立校验器；不合并，因为 v1 的极简契约是课程夹具的稳定接口。

**后果**：需要明确文档标注，避免新任务误用 v1。

## D-008 本地模型跨进程锁

**背景**：进程内互斥无法约束多个 Agent/项目同时调用 8080；用户要求严格串行。

**决策**：`shared/ai_runtime` 提供文件锁（原子创建 + PID + 陈旧回收），任务全程持锁；服务只由持锁者启动，且只停止自己启动的实例。

**后果**：并发调用会排队或 `blocked`；硬杀进程可能留下陈旧锁，由回收机制处理。

## D-009 在线模型独立

**决策**：在线模型调用只出现在 `ContentQA`；它只读课程、只写 `build/<slug>/review/`，不影响构建 verdict。无凭据时 `blocked`，不降级到本地模型。

**后果**：在线审查可以独立演进；构建仍可离线复现。

## D-010 上下文预算

**决策**：默认 16K，复杂任务 32K，硬上限 64K；请求前估算，超限抛错并要求拆分。

**后果**：长资料必须切分并保留来源；不允许静默截断。

## D-011 模型硬件

**背景**：全局约定文本模型 CPU-only；视觉模型需要 GPU 才能可用。

**决策**：文本模型（planner/coder）保持 `-ngl 0`；视觉模型保留现有 SYCL 配置（用户既有环境，不擅自修改）。ComfyUI 与 GPU 视觉模型不得同时运行。

**后果**：视觉阶段占用 A750；与 ComfyUI 的时间冲突由人工调度。

## D-012 取消 8082

**背景**：多份文档写“预览备用 8082”，代码从未实现。

**决策**：删除该约定；预览与截图统一使用 8081，端口被占用时截图复用现有实例。

## D-013 Manim 定位

**背景**：`ManimSandbox` 有 demo 与适配器，但当前没有课程使用。

**决策**：保留为可选能力与回归样例，不强行接入课程；接入需要新的 `storyboard` 镜头与真实验收。

## D-014 不伪装自动化

**决策**：人工导出、内容占位、凭据缺失、模型不可用都必须作为状态出现在报告与交付清单中。

**后果**：真实课程的 `incomplete` 是合法交付状态；补全责任在内容作者。

## D-015 IR v2 增量扩展 TEXT / CURVE / ORTHO

**背景**：P1a 需要文字、曲线与正交相机，而 IR v2 原本只有 9 种图元、`MESH`/`EMPTY` 两类对象和透视相机。

**评估**：新增对象类型 `TEXT`/`CURVE`、对象子结构 `text`/`curve`、相机字段 `projection`/`ortho_scale`，以及 `scene.text_objects`/`scene.curves`/`scene.cameras` 三条验收检查，均为增量变更：旧任务缺省值不变，原有 5 个合法与 6 个非法夹具结论不变，双端一致性测试通过。

**决策**：保持 `schema_version: 2`，不升 v3；字段与取值范围写入 [Blender 场景任务 IR v2](Blender场景任务IR-v2.md) §5.1.1 与 §6。

**后果**：旧任务与 `base_blend` 路径无需迁移；后续若修改既有字段语义或收紧既有校验，仍须升版本并提供迁移说明。

## D-016 二维标注契约

**背景**：PBR 评估（Q4）已定：二维标题、图例、单位说明不得硬编码在 Remotion 组件里。

**决策**：`storyboard.yaml` 新增可选 `annotations`；`collect` 按页面预算与 `cue_seconds` 解析为绝对时间，写入 `shots.json.annotations[]`；Remotion 只渲染该字段，不读取课程内容。

**后果**：标注随 `shots.json` 进入产物与报告；`verify` 新增 V-22。旧 `storyboard.yaml` / `shots.json` 不带该字段时按空列表处理，`schema_version` 保持 1。

## D-017 二维字体捆绑

**背景**：Remotion 之前只依赖系统字体栈，中文与拉丁字形的可用性和度量随机器变化，`NFR-01 可复现` 因此有隐患。

**决策**：只读使用 Noto Sans SC（SIL Open Font License 1.1）的 Regular，vendor 到 `RemotionStudio/public/fonts/`，由 `@remotion/fonts` 的 `loadFont` 在渲染前加载；`design-tokens` 的 `fonts.sans` 增加该家族。Blender TEXT 仍用内置 Bfont，不加载外部字体。

**后果**：二维字幕与标注跨机器一致；字体文件（约 1.1 MB + 13 KB）入库并携带 OFL 许可证。只捆绑 400 字重，粗体为合成粗体。

## D-018 材质预设展开

**背景**：常用材质应当复用，但 Blender 内置校验器不应重复实现预设查找，也不应让任务文件包含两份真值。

**决策**：`preset` 是控制层概念；`scene-validate` 与 `scene-run` 在双端校验前调用 `scene_presets.expand_task`，Blender 只接收展开后的 `shader` + `params`。manifest 记录预设来源、源任务哈希与展开任务哈希。

**后果**：预设可独立演进；未知预设、预设与 `shader`/`params` 混用都会在校验期失败。旧任务不受影响。

## D-019 科学着色语义

**背景**：云图必须让颜色与物理量一一对应；由模型推测范围或单位会让画面变成错误陈述。

**决策**：`scientific_colormap` 是独立 shader，不继承 PBR 参数；`source_attribute`、`min_value`、`max_value`、`units`、`colormap` 全部必填，不提供 `auto`；色标定义只在 `shared/colormaps.json`，Blender 与 Remotion 共用。点属性由声明式字段 `axis` / `distance` / `noise` 生成，不接受任意表达式。

**后果**：缺元数据直接校验失败；色标与材质不会出现两套颜色；P4 只扩展字段来源，P5 只替换数据源。

## D-020 受限表达式

**背景**：参数化曲面与表达式属性需要在控制层和 Blender 内置校验器中得到一致结论；两侧各写一份 AST 白名单必然漂移，而 `eval` / `exec` 违反工程红线。

**决策**：新增纯标准库包 `shared/scene_expr`，控制层通过 uv 路径依赖引用，Blender 通过 `shared/scene_expr/src` 加入 `sys.path`；表达式只做 AST 白名单校验与递归解释，不调用 `eval`。

**后果**：双端共用同一实现；表达式上限、函数白名单与求值错误只有一处定义。旧任务不受影响。

## D-021 代码/终端会话证据链

**背景**：代码与终端课程需要真实执行、可断言、可录制，不能用录屏代替正确性。

**决策**：会话由 `SessionSpec` 描述；Docker 内 `container_runner` 执行并分离 stdout/stderr；宿主 `session_runner` 断言并写 `result.json`；mintty + gdigrab `hwnd` 录制 `session.mp4`；`validation.json` 给出 V-23（执行）与 V-24（录制）。V1 以 VoxCPM2 生成旁白，固定 timesteps=10，不做 draft profile。

**后果**：执行、展示、视觉证据分离；录屏失败不掩盖执行失败，反之亦然。8080 不在本能力范围内。

## D-022 VS Code 会话

**背景**：VS Code 的 Electron 窗口在 gdigrab 下为黑屏，且外部脚本无法稳定向编辑器打字。

**决策**：仓库内 `CourseDemo` 扩展通过 `TerminalShellIntegration.executeCommand` 执行命令，立即消费 `read()`，以 `onDidEndTerminalShellExecution.exitCode` 为退出码（`undefined` 判失败）；录制改用 `PrintWindow` 逐帧 + ffmpeg rawvideo，不再依赖 gdigrab/ddagrab 的区域捕获。

**后果**：执行证据来自被录制的同一终端；录制与执行解耦。VS Code 版本需支持 shell integration（本机 1.145.1 已验证）。

## D-023 Python 工具链与离线验证

**背景**：pip/uv/venv 课程需要展示安装过程，同时证明产物不依赖网络。本机 Docker 容器到 PyPI 的 TLS 被代理/TUN 阻断，真实联网演示暂时不可用。

**决策**：`SessionSpec` 增加 `offline_commands`：在线容器（`network: bridge`）完成 venv 与安装，第二个 `network: none` 容器挂同一 `/work` 执行导入断言，V-25 检查离线结果。联网演示使用本机 8899 的只读 wheelhouse HTTP 索引（容器经 `host.docker.internal` 真实下载），不伪装成公网 PyPI；`trim` 按命令起止时间剪掉等待区间。

**后果**：安装、离线可运行与等待剪辑都有真实证据；真实公网 PyPI 仍受本机代理/TUN 限制，需要时再解决。

## D-024 Manim 动画轨道

**背景**：3Blue1Brown/Reducible 风格需要确定性数学动画，不是录屏。

**决策**：Manim 只作为渲染引擎；FFT 作为技术基线（验证坐标系、曲线、时间轴、输出），Transformer 作为产品基线（复杂概念拆解），最终仍进入 Remotion/FFmpeg 合成。复刻定义为表现手法与结构对齐，不逐帧复制。

**后果**：动画轨道与代码录屏轨道解耦；E5 基线已渲染，E6 尚未开始。

## D-025 Rust 执行环境

**背景**：E4 需要真实 cargo 执行；本机 Docker Hub/镜像加速器 TLS 握手超时，无法拉取 Rust 镜像。

**决策**：E4 先用 host VS Code + Git Bash（Rust 1.97）执行并录制，保留 `SessionSpec` 契约；Docker Rust 镜像可用后切回容器，不改课程镜头。

**后果**：Rust 镜头有真实执行证据，但隔离级别低于 Docker；报告中明确标注 `kind: host`。

## D-026 课程生产统一契约 V1

**背景**：课程、Manim、Session、E6 各自用秒/毫秒/帧描述时间；课程报告、session 证据、E6 manifest 是三套事实。直接统一会重写稳定轨道，继续放任则无法跨轨道验收。

**决策**：新增规范化契约层 V1（`LessonSpec / ShotSpec / NarrationSpec / TimelineSpec / EvidenceManifest / RenderManifest`），作为 `lesson.yaml`、`storyboard.yaml` 之上的只读规范化视图；时间线以整数帧为唯一事实，毫秒只出现在 WAV/SRT/FFmpeg 边界，秒只保留在旧契约并由适配器一次换算；所有素材用 `AssetRef`（路径 + sha256 + bytes + kind + origin + version）；E6 V0 manifest 只读适配，人工 `checks` 不进入 V1 自动检查。V1 不替换作者文件，不重写 Manim/Session/Blender 核心。

**后果**：现有轨道行为不变；V1-B 已实现模型、Schema、整数时间换算与测试（`contracts_v1.py` / `timecode.py`，CourseControl 116 个用例）；V1-C 再迁移 E6 manifest；任何 `skip` 或人工 `pass` 不得写成自动通过。设计稿与示例见 `docs/课程生产统一契约V1.md`、`docs/contracts/examples/`，实施报告见 `docs/V1-B-实施报告.md`。

## D-027 E6 V0 只读适配

**背景**：E6.1–E6.4 已产成片，但只有整段 `narration.wav`、没有 `lesson.yaml` / `storyboard.yaml`，也没有逐段旁白音频。直接生成 `LessonSpec` / `NarrationSpec` / `TimelineSpec` 需要伪造作者文件或音频。

**决策**：新增 `legacy_e6.py` 与 `e6-adapt`：只读 V0 manifest 与媒体，用 ffprobe、sha256、SRT 解析生成 `RenderManifest`；V0 `checks` 只进入 `legacy.manual_checks`，`manual_checks_trusted=false`；`RenderManifest.source=null` 仅允许在提供 `legacy.v0_manifest` 时使用；不修改 V0、不重渲染 E6。

**后果**：E6 产物可被 V1 描述，本地 36 条自动检查为 35 pass + 1 not_applicable；混合旁白与推断的段起点明确记录，不冒充完整规范化课程。后续如需 `NarrationSpec` / `TimelineSpec`，必须重新生成逐段音频或补作者文件后再迁移。

## D-028 本地优先、远程回退

**背景**：8080 同一时间只允许一个本地模型实例；用户其他项目或 `start_server.bat` 占用时，ModelingStudio 的完整流程会被阻塞。用户已有 DeepSeek API 环境变量，可作为 8080 被占用时的远端回退。

**决策**：在 `shared/ai_runtime` 增加 `remote.py` / `routing.py`。本地 8080 始终先尝试；仅当 `config/model-routing.yaml` 显式启用、key 环境变量存在、且失败原因属于 `busy` / `start_error` / `lock_timeout` / `missing_executable` 时切换到远程 OpenAI 兼容端点。远程路由不持有 8080 锁；任务记录新增 `provider=local|remote`，并写实际模型。视觉阶段只有配置 `vision_model` 且 `supports_vision=true` 才回退，不把图片交给文本模型。密钥只从环境变量读取，不进入配置、日志、异常或健康输出。

**后果**：本地仍严格串行；远程调用可并行，但不冒充本地。远程不可达或无凭据时仍按 `blocked`/失败处理，不静默降级。配置参考 `config/model-routing.example.yaml`，本机文件被 `.gitignore` 忽略。

## D-029 路径卫生与环境配置

**背景**：代码和文档中曾出现本机盘符与 Program Files 的绝对路径；虽然运行配置已忽略，但跟踪文件仍会暴露机器信息。

**决策**：跟踪文件只使用相对路径或 `<AI_ROOT>` / `<VOICE_REF_WAV>` 等占位符；本机路径只允许出现在被忽略的 `config/*.yaml`、`.env`、`ModelingStudio/config/workflow.yaml`。新增 `config/model-routing.example.yaml`、`.env.example`；`.gitignore` 改为忽略 `config/*.yaml`（保留 `*.example.yaml`）与 `.env*`。新增 `scripts/check_paths.py` / `check-paths.ps1` 并接入 `check.ps1`。

**后果**：干净克隆不包含本机路径；新增检查会在提交前拦截盘符或用户目录绝对路径。代码中的 Program Files 固定回退改为 `shutil.which` + `ProgramFiles` 环境变量，缺失时明确报错。

## D-030 V1-D/E 兼容层

**背景**：V1 模型已存在，但主链仍用秒制 `shots.json`，Session runner 仍写旧 `evidence.json`。直接替换消费者会重写 Remotion 与 runner。

**决策**：V1-E 新增 `v1_timeline.py`，在 `collect` 后写 `contracts/timeline.spec.json`，并提供 `shots_from_timeline` 回写；`TimelineVideo` 增加可选 `track` / `metadata`，`TimelineSpec` 增加可选 `metadata` 承载旧二维标注。V1-D 新增 `session_evidence_v1.py`，把现有 `evidence.json` 升级为 `EvidenceManifestV1`；缺失录屏不伪造，存在 `recording.json` + `session.mp4` 时记录 `recording_result_inferred=true`。

**后果**：V1 时间线与证据可被查询和校验，Remotion/Session runner 行为不变。`shots_from_timeline` 只支持整数帧率回写；V1 原生 Session/SessionSpec 与 Remotion 切换仍待后续评审。
