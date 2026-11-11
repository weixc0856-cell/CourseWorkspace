# 决策记录（ADR）

格式：每条只记录**已生效**的决策、理由与后果。历史细节见 `docs/archive/`。
状态：`accepted` / `superseded`。

| 编号 | 决策 | 状态 |
| --- | --- | --- |
| D-001 | 分层：内容 / 展示 / 动画 / 三维 / 合成 / 控制 / 共享 | accepted |
| D-002 | 双文件契约：`slides.md` 给观众，`lecture_notes.md` 给讲者 | accepted |
| D-003 | 课程内容独立到 `lessons/`，不归任何渲染工程 | accepted |
| D-004 | Motion Canvas 采用人工导出（无 CLI 导出） | superseded by D-054 |
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
| D-054 | Motion Canvas 用 core Renderer + 帧接收器无头导出 | accepted |

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

## D-004 Motion Canvas 人工导出（已由 D-054 取代）

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

## D-009 内容审查独立

**决策**：模型审查调用只出现在 `ContentQA`；它只读课程、只写 `build/<slug>/review/`，不影响构建 verdict。无凭据时 `blocked`，不降级到本地模型。

**后果**：内容审查可以独立演进；构建仍可离线复现。

**2026-11-08 补充**：默认后端已按 D-042 切到 Claude Code；`backend: api` 仍可显式启用。独立、只读与 `blocked` 语义不变。

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

**后果**：现有轨道行为不变；V1-B 已实现模型、Schema、整数时间换算与测试（`contracts_v1.py` / `timecode.py`，CourseControl 116 个用例）；V1-C 再迁移 E6 manifest；任何 `skip` 或人工 `pass` 不得写成自动通过。设计稿与示例见 `docs/课程生产统一契约V1.md`、`docs/contracts/examples/`，实施报告见本地归档 `docs/archive/V1/V1-B-实施报告.md`（不入库）。

## D-027 E6 V0 只读适配

**背景**：E6.1–E6.4 已产成片，但只有整段 `narration.wav`、没有 `lesson.yaml` / `storyboard.yaml`，也没有逐段旁白音频。直接生成 `LessonSpec` / `NarrationSpec` / `TimelineSpec` 需要伪造作者文件或音频。

**决策**：新增 `legacy_e6.py` 与 `e6-adapt`：只读 V0 manifest 与媒体，用 ffprobe、sha256、SRT 解析生成 `RenderManifest`；V0 `checks` 只进入 `legacy.manual_checks`，`manual_checks_trusted=false`；`RenderManifest.source=null` 仅允许在提供 `legacy.v0_manifest` 时使用；不修改 V0、不重渲染 E6。

**后果**：E6 产物可被 V1 描述，本地 36 条自动检查为 35 pass + 1 not_applicable；混合旁白与推断的段起点明确记录，不冒充完整规范化课程。后续如需 `NarrationSpec` / `TimelineSpec`，必须重新生成逐段音频或补作者文件后再迁移。

## D-028 本地优先、远程回退

**背景**：8080 同一时间只允许一个本地模型实例；用户其他项目或 `start_server.bat` 占用时，ModelingStudio 的完整流程会被阻塞。用户已有 DeepSeek API 环境变量，可作为 8080 被占用时的远端回退。

**决策**：在 `shared/ai_runtime` 增加 `remote.py` / `routing.py`。远程端点按 **OpenAI 兼容协议**实现，`provider` 可配置（DeepSeek 只是当前实例，也可是 openai-compatible 或其他实现）。本地 8080 始终先尝试；仅当 `config/model-routing.yaml` / `.env` 显式启用、key 环境变量存在、且失败原因属于 `busy` / `start_error` / `lock_timeout` / `missing_executable` 时切换。通用变量为 `REMOTE_PROVIDER` / `REMOTE_BASE_URL` / `REMOTE_MODEL` / `REMOTE_VISION_MODEL` / `REMOTE_API_KEY_ENV`，DeepSeek 兼容 `DEEPSEEK_*`。远程路由不持有 8080 锁；任务记录新增 `provider=local|remote`，并写实际模型。视觉阶段只有配置 `vision_model` 且 `supports_vision=true` 才回退，不把图片交给文本模型。密钥只从环境变量读取，不进入配置、日志、异常或健康输出。

**后果**：本地仍严格串行；远程调用可并行，但不冒充本地。远程不可达或无凭据时仍按 `blocked`/失败处理，不静默降级。默认远程模型为 `deepseek-flash`；该模型支持图像理解，视觉阶段也可回退。所有 DeepSeek 调用固定 `deepseek-flash`，`deepseek-v4-pro` 已禁用，配置层会拒绝。配置参考 `config/model-routing.example.yaml`，本机文件被 `.gitignore` 忽略。

## D-029 路径卫生与环境配置

**背景**：代码和文档中曾出现本机盘符与 Program Files 的绝对路径；虽然运行配置已忽略，但跟踪文件仍会暴露机器信息。

**决策**：跟踪文件只使用相对路径或 `<AI_ROOT>` / `<VOICE_REF_WAV>` 等占位符；本机路径只允许出现在被忽略的 `config/*.yaml`、`.env`、`ModelingStudio/config/workflow.yaml`。新增 `config/model-routing.example.yaml`、`.env.example`；`.gitignore` 改为忽略 `config/*.yaml`（保留 `*.example.yaml`）与 `.env*`。新增 `scripts/check_paths.py` / `check-paths.ps1` 并接入 `check.ps1`。

**后果**：干净克隆不包含本机路径；新增检查会在提交前拦截盘符或用户目录绝对路径。代码中的 Program Files 固定回退改为 `shutil.which` + `ProgramFiles` 环境变量，缺失时明确报错。

## D-030 V1-D/E 兼容层

**背景**：V1 模型已存在，但主链仍用秒制 `shots.json`，Session runner 仍写旧 `evidence.json`。直接替换消费者会重写 Remotion 与 runner。

**决策**：V1-E 新增 `v1_timeline.py`，在 `collect` 后写 `contracts/timeline.spec.json`，并提供 `shots_from_timeline` 回写；`TimelineVideo` 增加可选 `track` / `metadata`，`TimelineSpec` 增加可选 `metadata` 承载旧二维标注。V1-D 新增 `session_evidence_v1.py`，把现有 `evidence.json` 升级为 `EvidenceManifestV1`；缺失录屏不伪造，存在 `recording.json` + `session.mp4` 时记录 `recording_result_inferred=true`。

**后果**：V1 时间线与证据可被查询和校验，Remotion/Session runner 行为不变。`shots_from_timeline` 只支持整数帧率回写；V1 原生 Session/SessionSpec 与 Remotion 切换仍待后续评审。

## D-031 英文旁白与情绪控制（R1）

**背景**：课程默认旁白语言需要统一；VoxCPM2 的情绪/风格控制只在 `reference_only`（仅 reference_wav）路径生效，`prompt_wav + prompt_text` 的“ultimate cloning”会忽略括号提示。

**决策**：R1 起默认英文旁白；`narration.script.json` 的每个 segment 可带 `style`（如 `(warm, measured pace)`）；整课批处理默认 `reference_only`，`prompt_reference` 作为显式回退并记录 `style_applied=false`。单段 `narrate` 仍默认 `prompt_reference`，新增 `--mode reference_only`。情绪提示只进入 TTS 请求，不进入正文或字幕。

**后果**：英文语气可控，但相似度略低于 transcript-guided cloning；换英文参考音只需配置 `tts.voice_ref_en`，不改代码。

## D-032 时长权威与窗口（R1）

**背景**：页面预算、旁白实测、成片时长三者容易形成多套权威。

**决策**：`lesson.yaml.duration` 是唯一课程级契约；页面级按 `narration.timing` 单向选择：`planned` 读 `lecture_notes.md` 的 `时长预算`，`measured` 读 `narration.meta.json` 的实测页跨度。`collect` 写出冻结的 `shots.json` / `timeline.spec.json`，`verify` 不再反推。V-26 检查计划/实测/重复权威，V-27 检查成片窗口；越窗失败，不自动拉长。

**后果**：20 分钟课程可以按真实音频落时间线；内容不足时先补内容，不用停顿凑时长。

## D-033 输入摄取与人工批准门（R1）

**背景**：需要从用户提供的网页/文档生成课程候选，但不能让 AI 直接改写正式课程。

**决策**：新增 `ingest` / `digest` / `brief` / `outline` / `script` / `content-draft`，候选写入 `build/<slug>/authoring/candidates/`；`author-accept` 按 sha256 提升到 `lessons/<slug>/` 并写 `authoring/approval.json`。`narration-build` 与 `subtitles-build` 验证批准哈希；V-33 在 validate 阶段检查批准门。输入 v1 只支持 URL / Markdown / TXT。

**后果**：AI 可大幅提速草稿，但事实与措辞仍由人工批准；PDF/DOCX 与批量抓取延期。

## D-034 双语字幕与双版本成片（R1）

**背景**：用户要求字幕版与无字幕版；字幕版按 YouTube-B 的 ASS + ffmpeg 烧录方式。

**决策**：字幕英文在上、简体中文在下；输出 SRT/ASS/VTT。`subtitles-build` 以实测音频段为边界规划 cue，逐 cue 翻译并校验条数；`subtitles-accept` 写 `lessons/<slug>/subtitles.srt`。Remotion 渲染干净母版 `final/course-video.mp4`，`adapters/burn.py` 用 ffmpeg `ass=` 烧录 `final/course-video-captioned.mp4`（QSV，失败回退 libx264）。Windows 路径必须写成 `ass='D\:/...'`。V-28/V-31 检查字幕版与 cue 契约。

**后果**：同一课程同时有干净版与字幕版；字幕同步依赖真实音频段边界，不做逐字 ASR 对齐。

## D-035 TimelineSpec 驱动 Remotion（R1）

**背景**：`shots.json` 仍是 Remotion 的唯一输入，V1 时间线只是并列视图。

**决策**：新增 `CourseTimeline` composition，直接读取 `contracts/timeline.spec.json`（整数帧、video/audio/subtitles/metadata）；`stage-assets.mjs --timeline` 按 TimelineSpec 收集素材；`adapters/remotion.py` 默认使用 `CourseTimeline`，旧课程可通过 `compose.renderer: legacy` 继续用 `shots.json`。`shots_from_timeline` 保留为回写兼容。

**后果**：合成由 V1 时间线驱动；旧路径仍可回退。E6/E6.5 的 standalone 产物不强行并入课程。

## D-036 Code2Video 只做镜头级接入

**背景**：Code2Video 的 27B 模型与 Skill 对动效镜头有价值，但部署成本高；我们的课程编排已由 CourseControl 承担。

**决策**：不部署 27B；把 `skills/code-video` 作为 `code_video` 镜头的生产方式。`ShotSpec.engine="code_video"`，`scene` 指向 `SPEC.md`；adapter 调 `capture.mjs`，要求 `VERIFY.md` 无 `| fail |`，产物进入 `build/<slug>/animation/`。Agent 使用 Claude Code + 显式配置模型。

**后果**：镜头级动效可确定性重放；最终合成仍由 TimelineSpec/Remotion 负责。Skill 生产化为 `CodeVideoStudio/`，保留 Apache 2.0 NOTICE。

## D-037 video-production-skill 只吸收规范

**背景**：该 MIT 项目的 10 步流程与 CourseControl 高度重合；直接安装会形成第二条编排流水线。

**决策**：不安装其运行时；吸收 job workspace、`manifest.json`、分段旁白/timings、抽帧 QC、归档/备份纪律，写入 `docs/课程生产交付物规范.md`。不采用 Kokoro TTS。

**后果**：交付与 QC 更完整，不增加运行依赖与编排分叉。

## D-038 HyperFrames 仅作为可选 HTML 渲染/lint 后端

**背景**：HyperFrames（Apache 2.0）与 Remotion 同为 headless Chrome + ffmpeg；POC 10 秒/300 帧渲染 27.1 s，`check` 能发现首帧空白与小字号问题。

**决策**：不替换 Remotion 最终合成，也不替换 Code2Video 默认 `capture.mjs`；仅保留为 HTML/GSAP 镜头的可选渲染与 lint 后端，是否接入由后续真实镜头对比决定。

**后果**：可用其 lint/check 提升画面质量；避免维护两套最终合成引擎。GSAP 商业许可需单独核查。

## D-039 VideoZero 作为 Motion Canvas 自动导出的候选（已由 D-054 取代）

**背景**：VideoZero（Apache 2.0）的 agent API 可以连接运行中的 Motion Canvas，执行 seek/screenshot/render；POC 证明默认 image-sequence exporter 可自动写出 3007 张 PNG，再由 ffmpeg 编码为 MP4。直接 FFmpeg exporter 在 Motion Canvas 3.17.2 上挂起。

**决策**：不作为纯 headless 方案；作为“图像序列自动导出 + 外部 ffmpeg”候选。需要 Vite FS allow/junction 适配和浏览器页面保持打开。主 MotionStudio 暂不改动，等内容稳定后再评审。

**后果**：现有 Motion Canvas 资产有自动导出路径；仍不是零人工、零浏览器依赖的方案。

## D-040 技术雷达机制

**背景**：此前按 Stars/知名度检索，漏掉 Code2Video 这类专项项目。

**决策**：新增 `docs/evaluations/技术雷达-视频生产.md`，按课程适用性 30%、成熟度 20%、Agent 适配 20%、集成成本 15%、许可 15% 评分；设置许可证不明、无复现案例、硬件不匹配、重复建设四条硬门槛。每轮 POC 记录真实产物与决策。

**后果**：外部项目先评估后接入；技术选型可追溯。

## D-041 Claude Code 作为受控外部代理，不进入 CourseControl 运行时

**背景**：在同一 8 秒 Code2Video SPEC 上对比本地 Qwen3-Coder、DeepSeek 纯 API、Claude Code 2.1.319（cc-switch → DeepSeek）与 DeepSeek Harness 0.2.2-rc.1。Claude Code 交付质量最高（8/8 must-have、15 KB、画面完整），dsh 接近但慢 52%、贵 34%；纯 API 合规但单薄；本地模型缺文案、文字重叠、构图过小。

**决策**：Claude Code 作为镜头代码/复杂版式的默认外部代理；通过 `claude -p` 在 `build/<slug>/agent/` 或镜头目录内受控执行，权限最小化，产物必须经 `capture.mjs` + `code_video_qc` + Contact Sheet + 人工批准。CourseControl 不把 Claude Code 作为库或流水线阶段依赖。纯 API 保留为远程回退与结构化短输出主力，调用显式 `thinking=disabled`；本地模型只做离线草稿；dsh 只作独立第二意见。

**后果**：交付质量与返工能力提升；默认依赖 cc-switch 代理，代理不可用时可直连 `https://api.deepseek.com/anthropic`（已实测），否则记录 `blocked`。Claude Code 的 `total_cost_usd` 只作参考，实际账单按 DeepSeek 价目计算。

## D-042 课程生产 AI 默认后端全量切换为 Claude Code

**背景**：四后端对比证明 Claude Code 在完整度、版式与返工能力上最好；用户要求全量切换。现有 authoring 为本地优先 + 远程回退，ContentQA 走独立 DeepSeek 客户端，ModelingStudio 走 8080/远程，Code2Video 由外部 Agent 生成镜头。

**决策**：
- 课程文本生产（brief/outline/script/content）、字幕翻译、ContentQA、ModelingStudio 文本规划默认走 Claude Code；Code2Video 镜头继续由 Claude Code Agent 生成。
- 文本阶段使用 `claude -p --tools=`（禁用全部工具）；镜头等 Agent 阶段才开放 `Read/Write/Edit/Glob/Grep`，且只允许在 `build/` 下的暂存目录工作。
- `config/claude-code.yaml` 保存非敏感路由配置；默认 `base_url=http://127.0.0.1:15721`（cc-switch），可切到 `https://api.deepseek.com/anthropic`。凭据只从环境变量注入。
- 任务记录新增 `provider=claude_code`；不可用时显式 `blocked`，只有 `claude_code_fallback: local_first` 才回退。
- ModelingStudio 的 vision 阶段（图像分析/修订）继续用本地/远程视觉模型，不交给纯文本 Claude Code。

**后果**：课程生产默认依赖 Claude Code CLI 与 cc-switch（或直连端点）；本地模型/纯 API 从“默认”降为“显式回退”。需要维护 `claude_code` 适配层与相应测试；Claude Code 的计价字段不可用于账务。

## D-043 Scene-first 合成模式（compose.mode=scene）

**背景**：deck 模式本质是“幻灯片 + 动画插入”，观众始终看到页面框架和项目符号，与 3B1B/Reducible 的镜头级叙事差距明显。

**决策**：新增 `compose.mode=scene`。每页先渲染一条全屏 ScenePage 视频（深色背景、逐句大字、公式/章节标识、无幻灯片框架），作为时间线 base；Manim/Blender 镜头作为 overlay 叠加。`capture_slides` 在 scene 模式下跳过，`collect` 从 `build/<slug>/scenes/manifest.json` 读取每页视频与时长。scene 页面仍由同一 `NarrationSpec` 驱动，字幕/音频/QC 不变。

**后果**：课程不再是 PPT 录屏；仍需后续补连续图解动画、音乐/音效和逐句 forced alignment，才能达到 3B1B 级。

## D-044 公式采用 LaTeX 单一源 + KaTeX/Manim 分工

**背景**：公式错误可能来自源、渲染、字体或最终合成；普通视频文字无法保证数学排版。

**决策**：公式统一保存为 `FormulaSpec.latex`；静态渲染用 KaTeX（HTML/PNG），数学动画用 Manim MathTex，Remotion 统一合成；不生成公式图片作为源。建立 `formula-validate` / `formula-render` / `formula-audit`，把源检查、编译、数学辅助检查、视觉抽帧分开记录。数学正确性与量纲仍由人工/来源确认，不能以编译成功代替。

**后果**：公式可追溯、可复现、可抽帧验收；新增 KaTeX/SymPy/antlr 本地依赖；Manim 仍需系统 LaTeX。

## D-045 科学图形先接入 SymPy + Matplotlib + SciencePlots

**背景**：公式/图表常同时出现；Manim 擅长动画但不应承担所有静态科学图。Plotly/Seaborn 对最终视频收益有限。

**决策**：新增独立 `ScientificFigures` 环境，用 SymPy 做符号/公式辅助，Matplotlib 做静态图，SciencePlots 提供论文样式（默认 `science` + `no-latex`，避免 Windows 强制 LaTeX）。产物为 SVG/PDF/PNG，由 Remotion 合成。Plotly/Seaborn 暂缓，Manim 沿用。

**后果**：新增一个独立 Python 环境与依赖；不增加第二套编排；静态图与公式资产分离，便于复用和抽帧 QC。

## D-046 动画先建立视觉导演层，不继续扩充工具链

**背景**：Manim/Blender/Remotion 已具备，但“讲稿→视觉设计→动画执行”缺少设计层，导致动画只是基础淡入/移动。

**决策**：新增 `AnimationDirection` 契约与 `docs/动画视觉导演规范.md`。每个镜头先写学习意图、视觉隐喻、构图、焦点、镜头、运动、连续性、参考与验收，`direction-validate` 通过后才写渲染代码。90 秒向量竖切片按此执行；3 分钟基础版保留。本轮不引入新动画库。

**后果**：动画设计可评审、可追溯；渲染成功不再等于视觉验收通过。验收以观看最终成片为准，不设抽帧评审关卡（见 D-047）。

## D-047 取消抽帧/关键帧评审关卡

**背景**：R2 曾用“六帧关键帧评审（Gate 1）+ 成片抽帧（Gate 2）”作为动画验收门槛。静态帧无法反映运镜、缓动、节奏与音画同步，评审通过也不保证成片可用；反复抽帧、拼 Contact Sheet、写逐帧意见消耗的时间远大于收益。

**决策**：删除 `docs/评审-向量加法关键帧.md` 与只服务于该关卡的 `ManimSandbox/03-vector-intro/keyframes.py`；不再设 Gate 1/Gate 2 抽帧关卡。验收改为直接观看最终成片，按镜头整体判断；发现具体问题再定位到时间点修正。范围仅限动画/设计层的评审关卡；Code2Video 的 contact sheet、公式与科学图的成片检查属于自动证据，不在此列。

**后果**：动画验收回归“看成片”；FR-27 的证据改为成片切片与测试，不再引用关键帧评审。

## D-048 导演层作为独立设计层，先 handoff 不接 build

**背景**：教学结构在 brief/outline，视觉路由在 `engine_router`，镜头方向在 `animation_direction`，但缺少一层把批准输入收敛为可执行计划并做硬校验的模块。

**决策**：新增 `CourseControl/src/course_control/director/`。教学、视觉、分镜、旁白、连续性五个环节用确定性规则从批准输入生成计划；错误阻断，警告进入评审；输入 hash 不匹配只出 draft。复用现有契约与路由，不新增依赖。暂不接入 `pipeline.py`，先输出 `storyboard.director.yaml` 作为 handoff。

**后果**：计划可校验、可追溯；页面预算与 10 秒插入镜头的差距被 `asset_seconds`/`insert.short` 显式记录；下一步才决定用同一 ShotSpec 契约接 build，还是先补齐 slide 7/8/10 的场景。

## D-049 制片层独立于导演层，交付以证据为准

**背景**：导演层解决“怎么拍”，但缺少订单、资源授权、用量、交付清单与增量重建；把这些塞进导演会让创作决策和制片管理混在一起。

**决策**：新增 `CourseControl/src/course_control/producer/`。订单声明受众、时长、必须覆盖、授权与限额；`producer-run` 只自动执行 validate → director → package → state，不触发渲染、TTS、发布；交付包按文件存在性与 sha256 判定，全部 present 且订单人工批准才是 `delivered`。每个镜头保存内容/旁白/场景/方向四类指纹，`producer-affected` 输出受影响镜头与动作。

**后果**：交付状态可核查，missing 明确；制片层不读密钥；局部重渲染还需 build 支持 storyboard override，当前只到“指出受影响镜头”。

## D-050 版式作为导演职责，先模板后场景

**背景**：动画方向已经可用，但画面主体偏小、留白平均分散、说明文字偏淡；逐页改场景不可复用，也容易风格漂移。

**决策**：新增 `CourseControl/src/course_control/layout/`：`DesignSystem`（画布/安全边距/颜色/字号）、8 个 `LayoutTemplate`（归一化区域）、`LayoutValidator`（安全区/重叠/主视觉面积/容量/字幕保留带）。导演计划为每个镜头写模板与区域，引擎只能在区域内作画；Manim 场景共用 `ManimSandbox/common/design_system.py` 的 token。模板由规则映射选择，不让模型自由生成坐标。

**后果**：版式可校验、可复用；CrossAttention 与 Loss 先按 `process_flow` 重做并出前后对比；动画过程中的碰撞/遮挡仍未自动检测，留待下一轮。

## D-051 全局采用明亮科技编辑配色，语义色只表达对象

**背景**：课程需要知识讲解的可信感；暗黑科技风、荧光色与发光效果会降低可读性，也让不同课程风格漂移。麦肯锡与 Claude 报告的共同点是浅底、克制结构、少量强调色。

**决策**：默认主题为暖白纸面 `#FBFAF7` + 石墨 `#252A31/#2E3338` + 橙色重点 `#E8733B`；语义色固定为输入蓝 `#4A82B8`、处理青 `#42A69A`、输出紫 `#7A6FB0`、误差红 `#C75B55`。禁止深色默认背景、荧光色、发光/粒子、卡片套卡片。颜色写入 `DesignSystem` 与 Manim token，由 `test_color_system.py` 校验对比度与同步。

**后果**：三个新镜头与配色页已按新色重做；4 个旧黑底镜头待统一。语义色到图元级别的自动校验尚未实现。

## D-052 借鉴纪录片运镜：静帧慢推/平移，不引入音乐与生图

**背景**：参考片的核心质感来自静帧慢推、强编辑排版与声音；课程现有静态截图是硬切、无运动。音乐与生图是另外两块短板，不应混入本轮。

**决策**：新增 `MotionPolicy`（`lesson.yaml.motion`）与确定性 `slide_motion`；`collect` 写 `legacy_motion` 到时间线，Remotion `MotionImage` 执行缩放/平移。只作用于 slide 底图，缩放 ≥1.04、平移 ≤1.2%。音乐/音效、AI 生图、章节卡、dissolve 明确不纳入本轮。

**后果**：静态页面获得稳定的轻运镜；可直接用 `slides: static` 关闭。下一步才是音频床/ducking（需授权曲库）与生图模块。

## D-053 长序列模拟用 Three.js/CodeVideo，Blender 只做 hero 镜头

**背景**：Primer 用 Godot 做实时模拟；我们的 Blender POC 在 720p30、91 个 agent 下约 0.8 s/帧，30 秒要 12 分钟。按此外推，15 分钟 1080p30 约 13 小时/遍，1440p60 约 20–40 小时/遍，返工不可接受。CodeVideoStudio 已有 Three.js + `window.seek(t)` 的确定性捕获，且验证过 900/900 帧哈希一致。

**决策**：`SimulationSpec` 固化模拟输入；长序列用 Three.js / CodeVideoStudio 渲染，Blender 负责 hero 镜头、材质、灯光与特写；不引入 Godot。Blender 侧只保留“数据 → 场景”的任务。

**后果**：Three.js 镜头模板已落地（`CodeVideoStudio/shots/primer-rps`）：同一 30 秒 900 帧 **45.7 秒**、双次 capture sha256 一致；Blender 约 12 分钟。`adapters/code_video.py` 可按 `ShotSpec.inputs.simulation_spec` 自动生成数据并完成 capture + QC（`lesson-simulation` 夹具 PASS）。导演层 `visual_kind: simulation` 路由 code_video、带 inputs、校验 spec 存在，夹具计划为 ready。Blender 场景脚本继续作为高质感备选，模拟数据与引擎解耦。

## D-054 Motion Canvas 无头导出用 core Renderer + 帧接收器

**背景**：Motion Canvas 3.17.2 的 core / ffmpeg / vite-plugin / ui 包都没有 bin，没有官方 CLI；`@motion-canvas/ffmpeg` 的 exporter 依赖 Vite `import.meta.hot` WebSocket 与编辑器进程。直接放弃编辑器后，需要验证 core `Renderer` 能否在无 UI 页面中驱动完整场景。

**调查**：
- 官方稳定接口是 core 的 `Renderer`、`Stage`、`PlaybackManager`；`RendererSettings` 接受 `exporter.name`，exporter 从 project plugin 的 `exporters()` 注册。
- 官方 ImageExporter / FFmpegExporterClient 都通过 Vite HMR 发帧；FFmpeg exporter 在 3.17.2 曾出现挂起（D-039），不作为主路径。
- 自建无头页 `MotionStudio/headless.html` + `src/headless.js`：`bootstrap` 构造 project，注册自定义 exporter，把每帧 PNG POST 到 Node 帧接收器；Node 端 ffmpeg 编码。
- `scripts/render-headless.mjs` 启动 Vite（4173）、帧接收器（4174）、Playwright/Chrome，等待页面完成，ffprobe 验证并写 meta。
- 实测 `attention-flow` 1920×1080/30fps/142 帧；连续 3 次 SHA256 完全一致；第 30 帧注入异常时不产 MP4、meta 为 `failed_as_injected`。

**决策**：Motion Canvas 的生产导出改为无头自动路径；`adapters/motion_canvas.py` 自动调用、最多重试 2 次、ffprobe 校验分辨率/帧率/帧数。失败即 `fail`，不再写 `skipped + incomplete`。编辑器只用于制作/预览；合法旧人工导出可作为缓存复用。端口 4173/4174 专用于无头导出，不占用 5173 编辑器端口。

**后果**：Motion Canvas 从生产执行人工节点变为自动节点。仍依赖本机 Chrome/Playwright 与 Vite，属于浏览器渲染而非纯 Node 渲染；不引入 VideoZero、不引入第二套编辑器 UI 自动化。真实课程需要重跑才能把历史 `incomplete` 更新为新的构建结论。

## D-055 独立代码审核用 ReviewRunner，默认隔离本机 Codex 配置

**背景**：课程生产需要独立第二意见，但 Codex 使用本机 `~/.codex` 配置时会加载多个 MCP 服务器、插件与模型目录；实测一次简单请求 `input_tokens=19238`，且配置告警混入输出。项目硬上限是 64K，不能依赖模型 catalog 的更大上下文。

**决策**：新增独立 `ReviewRunner/`（不进入生产主链，不接 `check.ps1` 门禁，不自动 apply）。默认用 `codex exec --ignore-user-config` 加显式 provider 配置：`base_url/model/api_key_env` 来自 `config/model-routing.yaml`，key 只由子进程从环境变量读取，不进入 argv/日志/manifest。审核输入全部来自 Git 对象，落在临时目录，运行前后校验 SHA256；输出按执行轴与审核轴分别记录，`production_effect: none`。隔离实测基线 14,243 tokens，因此系统预留 18,000、文件内容预算 35,536；用户配置模式保留 24,000/29,536。超出预算直接 `BLOCKED`，不静默缩减范围。

**后果**：本机 MCP 与插件默认不参与审核；宿主 skill frontmatter 告警作为噪声过滤并计数。Windows 沙箱隔离强度未验证，工具只声称“临时目录 + 前后哈希”，不声称绝对沙箱。Phase 1 只做代码审查，Docs/Course 仅保留隐私门与接口；Course 外发必须逐次授权。

## D-056 五条质量防线 P0 落地；5 分钟校准课与 Shorts 分开

**背景**：差距审查确认五条质量防线中 Q1 只有单模型候选审查、Q2 基本没有、Q3 缺全片音视频检查、Q5 只按文件存在性判定；真实课程 `01-transformer-demo` 的交付仍为 `blocked`。规范要求先打通一门真实课程闭环，再扩展模块。

**决策**：
1. 新建本地校准课 `05-transformer-5min`，从已批准的 `01-transformer-demo` 第 1、3、5 页逐字取用，只做分页与编号调整；旁白复用同参数缓存，12 段全部命中；审批记录写 `user-instruction` 与 subset 来源，不冒充新的语义审查。该课程属于**短课/校准片**，不是 YouTube Shorts。
2. 在 `CourseControl` 内新增 `narrative.py`、`audio_mix.py`、`media_qc.py`、`quality.py` 与四个 CLI 命令：`narrative-validate`、`audio-mix`、`media-qc`、`quality-report`；不新建 TeachingQA/MediaQA 顶层工程。
3. 长视频必须提供 `authoring/narrative-plan.json`（六段骨架）；Shorts 使用 `video_form: short`、30–90 秒、9:16、独立脚本。方法论文档为 `docs/creative/叙事设计与观众留存规范.md`。
4. BGM 只消费本地授权库：曲目缺失、许可未知、CC BY 缺署名一律 blocked；混音固定 sidechain ducking + `loudnorm I=-16:TP=-1.5`。
5. 质量状态保持五维独立；`BUILD_PASS`、`QUALITY_PASS`、`RELEASE_APPROVED` 三层分离，最后一层必须有人工批准文件。叙事结构通过只把 Q2 记为 WARN，不证明教学有效。

**后果**：5 分钟校准课可以跑通旁白、字幕、两种动画、BGM、全片 QC 与质量报告；ASR/强制对齐仍未接入，因此“字幕与语音一致”保持 INCOMPLETE。Shorts 不通过裁切长视频生成，后续单独建课。

## D-057 校准课改为动画驱动的 scene 模式；deck 模式不再用于机制解释

**背景**：5 分钟校准课首版使用 `compose.mode: deck`，3 页幻灯片占 94% 时长，只有两段 8–10 秒的 Manim cutaway。实测音轨与 `narration.wav` 零偏移、字幕与 ASR 覆盖 0.992，说明时间轴没有漂移；问题在视觉契约：静态 PPT 无法承担机制解释，动画内容与旁白段落也没有语义对齐。

**决策**：
1. 新增 292 秒连续 Manim 动画 `ManimSandbox/05-transformer-5min/attention_5min.py`，按 12 段旁白实测时间编排 12 个 beat；每个 beat 的动画、停顿与转场相加等于该段旁白时长。
2. 校准课切到 `compose.mode: scene`，`scenes/manifest.json` 的 `base_file` 指向 `animation/attention_5min.mp4`；`collect` 在 scene + base_file 模式下不再把 storyboard 镜头当覆盖层叠加。
3. Manim 适配器增加缓存：目标 MP4 比源场景新时直接复用，避免重建时重复渲染 5 分钟动画。
4. 机制解释类课程默认用 scene/动画作为底；deck 模式只用于以静态图文为主、允许逐页阅读的内容。

**后果**：5 分钟课从“幻灯片 + 两段短片”变为连续动画；字幕/旁白时间轴沿用 ASR 对齐结果。代价是 Manim 渲染时间显著增加，因此加入缓存并要求后续 scene 模式课程先做低分辨率预渲染。

## D-058 运行时版式检查逐 beat 执行，并可作为渲染硬门禁

**背景**：连续动画把 `enforce(self)` 放在 `construct` 末尾，此时所有对象已淡出，检查对象为空；旧检查也只比较文字与文字，且适配器从不设置 `STRICT_LAYOUT=1`。结果 `RNN` 被回环箭头穿过、`V2–V5` 被求和箭头穿过都没有报错。

**决策**：新增 `check_now(scene, label)`，在每个 beat 结束、淡出之前检查；增加文字/无关图形穿过的检测（排除标签自身容器与高亮框包含）；`BuildOptions.strict_layout` 控制 Manim 适配器传 `STRICT_LAYOUT=1`，开启后版式问题直接让渲染失败。校准课已开启。

**后果**：场景作者必须在每个 beat 调用检查；旧的单次 `enforce` 保留但只作为末尾兜底，不能替代逐 beat 检查。scene 模式不再绕过版式门禁。

## D-059 校准课迁移到样片架构：MovingCameraScene + 实测时钟 + 逐动画相机漂移

**背景**：D-057 的 12 beat 连续动画已经对齐旁白，但仍是普通 `Scene` + 硬编码 beat 时长，平均 24 秒一个 beat；成片 QC 记录 69 个 ≥1.5 s 的冻结区间。2 分钟样片 `06-attention-3b1b` 的架构是 `MovingCameraScene`、每镜头 8–12 秒、用相机运动填满旁白空档。

**决策**：
1. `attention_5min.py` 重写为 27 个镜头：每段旁白按固定比例切成 2–3 个镜头，切点写在场景的 `SUBDIVISIONS`；时间轴单一来源是实测旁白 `build/<lesson>/narration/narration.meta.json`（段落起点/时长/页面终点），缺失时才回退到内置的 292.38 s 常量。
2. 每个镜头结束、画面最满时调用 `check_now`；镜头内的剩余旁白时间由相机推拉覆盖，不再出现 `wait` 定格。
3. 覆写 `Scene.play`：凡是不包含相机动画的 play，自动附带 1.4 %/s 的相机缩放漂移，在 13.0–14.2 画幅之间往返。实测低于约 1.2 %/s 时 `freezedetect(n=0.002,d=1.5)` 仍判定为冻结。（**该条已被 D-060 撤回**：用户反馈无动机缩放导致眩晕。）
4. `common/scene_checks.py` 排除相机画框 `ScreenRectangle` 与完全透明的文字（淡出对象不是版式问题），并在重叠信息中附带包围盒，便于定位。
5. 语义图表保持在 y ≥ ≈-1.5：双语字幕按 ASS `n2@890` 烧录，字幕块占住画面底部约 1.9 个单位；原本在字幕带内的读数、柱状图、评分矩阵与结论行整体上移，8b 的装饰性标签直接删除。

**后果**：27 个镜头全部通过严格版式检查，零时长溢出，动画总长 292.398 s；1080p 动画与成片 `media-qc` 的冻结区间都从 69 降到 2，剩余两处都在镜头开场的近空白过渡。代价是每个 play 多一条相机动画，动画缓存整体失效一次；低分辨率预览仍是首选验证手段。

## D-060 撤回补偿性相机漂移；用导演节拍与字幕分层解决静止与遮挡

**背景**：D-059 用“每个 play 附带 1.4 %/s 相机缩放”把冻结指标压到 2 段，但这不是导演设计：观众看到的是无动机的持续缩放与移动，产生眩晕。同一版成片还有两个问题：底部灰色说明行与烧录字幕重复；双语字幕块与图表下半部重叠。

**决策**：
1. 删除 `Scene.play` 的相机漂移覆写与 `zoom_fill`；全片相机固定在 14.22 画幅。需要镜头运动时再按“全景 → 推近 → 拉远”的动机单独设计，不以填满时间为目的。
2. 删除 21 条底部 `caption()`（与旁白/字幕重复）；每个镜头改为“指认式”视觉动作（逐行扫亮、逐层高亮、轮流压暗/恢复、分开再合并），并写入 `ManimSandbox/05-transformer-5min/beats.md` 作为导演节拍表。
3. `Subtitles.bottom_margin` 可配置（默认 190 px，本课 60 px）：ASS 锚点从 `height-190` 改为 `height-bottom_margin`，双语字幕块整体下沉，图形主体回到字幕带之上。
4. 冻结指标只作为技术检查，不再用运镜凑数；接受镜头末尾 ≤1.5 s 的停顿。

**后果**：成片不再有无动机运镜，字幕与图形分层，镜头内等待时间从最长 8.4 s 降到 ≤2 s（多数 ≤1.5 s）。`media-qc` 的冻结区间为 59 段（WARN）：`freezedetect(n=0.002)` 把稀疏线段生长、慢淡入都算作冻结，原来的 2 段是相机漂移把整帧“推”过阈值的结果；不为此重新加入假运动。3B1B 式“同一场景图持续变形”仍需把句子行、focus token、分数矩阵做成跨镜头长寿命对象，并把图表放大到覆盖更多画幅，见 `docs/evaluations/样片-注意力-3B1B差距与路线.md` 第 6 节。

## D-061 后处理复用 three.js 官方 addons；捕获增加 GPU/JPEG 显式开关

**背景**：P1 要给衰老模拟镜头加景深、泛光、调色与颗粒。第一版自写了 `postfx.js`（自研五段式合成链）。自研 shader 没有经过社区验证，且同样的效果在 three.js r160 官方 addons 里已有成熟实现（`EffectComposer`、`BokehPass`、`UnrealBloomPass`、`FilmPass`、`VignetteShader`、`ColorCorrectionShader`、`OutputPass`、`FXAAShader`）。按 D-062 的准入规则，删除自研模块，改为 vendored 官方 addons。

**决策**：
1. 后处理链全部使用 three.js r160 官方 addons（版本与已 vendored 的 `three.module.js` 一致），文件放在 `CodeVideoStudio/shots/primer-aging/vendor/three/addons/`，`index.html` 用 import map 把 `three` 指回本地核心。链序：`RenderPass → BokehPass → UnrealBloomPass → ColorCorrection → FilmPass → Vignette → OutputPass → FXAA`。
2. 保留唯一一处自定义逻辑：`FilmPass` 自带累加时钟，渲染前把 `time` 覆盖为 `t`，保证整片仍是 `t` 的纯函数。
3. `capture.mjs` 增加 `--gpu`（宿主 GPU 光栅，默认仍 SwiftShader）与既有 `--jpeg`；适配器读镜头目录下的 `capture.json` 决定是否传这两个开关，未知键直接失败。每个开启的镜头必须在 `VERIFY.md` 重新验证确定性。
4. 不改变课程内容与 HUD 布局；后处理只作用于世界片。

**实测（1080p，1920×1080）**：

| 路径 | 捕获耗时 | 全片（4,362 帧） |
| --- | --- | --- |
| SwiftShader + PNG（原路径） | 777 ms/帧 | ≈56 min，超适配器 1800 s 上限 |
| 宿主 GPU（A750 / ANGLE D3D11）+ PNG | 352 ms/帧 | ≈26 min |
| 宿主 GPU + JPEG 中间帧 | 36 ms/帧 | ≈3 min |

分项成本（SwiftShader，仅渲染）：基准 68 ms；Bokeh 约 252 ms、Bloom 119 ms、Vignette 54 ms、FXAA 45 ms、调色 8 ms、颗粒 <1 ms。

JPEG 中间帧代价：同一帧与 PNG 路径成片对比 PSNR 40.34 dB vs 40.56 dB（差 0.2 dB）。JPEG 输入是全范围 `yuvj420p`，必须在 ffmpeg 里用 `scale=in_range=pc:out_range=tv` 转有限范围并标 `-color_range tv`；否则镜头 QC 会因 `pix_fmt yuvj420p` 直接失败（首轮重建即因此中断）。确定性：GPU 路径两次 30 帧捕获 sha256 一致（`b99e2782…`）。

**后果**：后处理可在 3 分钟内整体重渲，景深不再受性能预算挤压；代价是捕获结果依赖宿主 GPU 驱动，`capture.json` 与 `VERIFY.md` 必须成对维护。未启用该开关的镜头行为不变。

## D-062 第三方依赖准入：复用优先、负面效果否决、更新要校核

**背景**：本轮出现两次“要不要自己写”的判断：一是后处理 shader，二是为性能改渲染路径。自写实现缺少验证、维护成本和回归风险都由本项目承担；但盲目引入同样会带来许可、体积、确定性和维护停滞问题。

**决策**：
1. 能由成熟实现完成的，不自己写；自写仅限：无对应实现、许可不兼容、或与本项目数据契约冲突且有实测证据。
2. 引入前按 `docs/第三方依赖准入规范.md` 的检查表逐项核：上游身份、SPDX 许可、口碑（star/fork/open issues）、近 6 个月活跃度、与既有版本的契约一致性、负面效果实测。
3. **负面效果一票否决**：引入后若造成性能回退、产物不可确定性复现、许可污染或离线不可用，直接 pass 掉或降级为显式开关。
4. 依赖登记表记录锁定版本、来源、校核日期与判定；每次迭代开始重新取数（`gh api` / `npm view`），落后 ≥2 个 minor 版本必须开升级任务或写明不升级理由。
5. 版本一致优先于“用最新”：three 核心与 addons 必须同版本；当前锁定 r160，落后上游 0.187.0，升级作为独立任务并需重跑 `VERIFY.md`。

**后果**：不再出现未登记的即兴依赖；依赖带来的收益与代价都有实测数字。代价是每个新依赖多一道评估工序，且升级需要回归验证。

## D-063 品牌层独立于内容生产，复用既有色板，片头片尾在成片之后拼接

**背景**：需要一套可复用的频道片头片尾（课程 3.5 s 片头 / 12 s 片尾、新闻 6 s 片尾、竖屏 1 s 签名）。外部方案提出独立色值（`#F7F7F8` / `#18191C` / `#F25F22`）与 Space Grotesk / Inter / JetBrains Mono 字体组合。

**决策**：
1. 视觉主品牌 `WAYNE`，副标题 `ENGINEERING & COMPUTATION`；频道名继续用 `Wayne-CFD`。
2. 品牌色角色映射到 `shared/design-tokens/tokens.json`（paper / ink / orange / border），**不引入第二套 hex**；字体只用已打包的 Noto Sans SC（新增 Latin 600/700 子集），不新增字体依赖。
3. 品牌资产放在 `RemotionStudio/src/brand/`，配置放 `shared/design-tokens/brand.json`，Remotion 与 `CourseControl` 读同一份文件。
4. 品牌阶段在 compose / burn（可选）之后运行，产出 `final/course-video-delivery.mp4`；不改 `shots.json`、`timeline.spec.json`、旁白或字幕；`verify` 以 V-36 重新计算 `body + brand`。
5. 新闻不开片头（第一句口播即开场）；竖屏只用 `short_signature`；时长越界、分辨率不匹配直接报错。
6. 拼接先 `-c copy`，校验失败回退重编码，模式写进 `final/brand.json`。

**后果**：片头片尾与课件共享同一色板与字体，不会在剪辑点出现色差；代价是品牌不能使用第三方字体个性，并且组件固定 1920×1080 / 1080×1920，4K 需要后续参数化。

## D-064 教材知识库用页级事实 + SQLite FTS5，claim 验证保持 pending

**背景**：需要把上千页教材变成可按章节调用、按知识点生产的本地知识库，且每节课有可追溯的原文依据。

**决策**：
1. 新建独立工程 `KnowledgeStudio`，按“原件 → 页 → 单元 → 索引 → 检索 → 证据”分层；不把教材管理塞进 Producer / Director。
2. 第一版不引入向量库/RAG 框架：目录、章节、页码是明确结构，SQLite（标准库）+ FTS5 + Markdown + JSON 足够，且可复现；语义检索后续只作为补充。
3. 检索是确定性的词法匹配，按 `max_pages` 截断，只读需要的页；返回 0 页视为失败，不是成功。
4. 每条引用指向 PDF 页并记录页哈希；claim 只能引用本次检索读过的页，`verification` 固定 `pending`，工具不自动标 `verified`。
5. 新增依赖 `pypdf==6.9.2`（BSD-3-Clause）。7.0.0 于 2026-11-06 发布，过于新，暂不升级；扫描件走 `import-text`，OCR 不在本模块。
6. 导出只写 lesson 的 `authoring/sources/KS-*.md` 与 `sources.ks-*.yaml` 片段，不修改 `sources.yaml`；`knowledge/` 全部本地，`local_only` 默认 true。

**后果**：课程生产在进入 LLM 之前就限定了阅读范围与引用来源；代价是中文检索依赖按字拆分的 FTS 短语，同义词与跨语言召回仍需人工扩词或后续语义补充。

## D-065 多视觉语法生产系统：质量统一、语法分档、镜头为生产基元

**背景**：目标参考视频（亚里《AI 配音怎么选？》，12:28）采用 3–6 秒硬切、每拍换构图、无长寿命对象的语法。现有 `beats.py` + `animation_score.py` 把 5–16 秒长镜头、长寿命对象 ≥50%、8–12 秒理想节奏写成了通用质量定义，导致该风格结构性只能拿约 55/100，低于 85 分发布线。问题不在模型、语言、音色或渲染器，而在契约把艺术语法与质量标准焊在一起。

**决策**：
1. 确立 **One Production System, Multiple Visual Grammars**：统一生产基础设施，允许多种视觉语法；风格不是质量。
2. 四层解耦：内容表达目标（purpose） / 视觉语法（逐镜头 grammar + techniques） / 渲染能力（renderer registry） / 质量验收（Hard + Grammar + Metrics + Human）。
3. 三份契约：Production Contract（Course → Lesson → Sequence → Shot）、Style Profile（只描述视觉语言）、Quality Profile（统一质量要求，按语法选择检测方式）。
4. Shot 成为生产、渲染、验收、重渲的第一等公民；Page 只在 deck/scene 模式保留，不再是视频生产的唯一时间基元。
5. 质量门禁分层：Hard 不可豁免；Grammar 可豁免但须书面理由与批准人；Metrics 只报告；人工审美验收是发布决定。**废止统一 85 分发布线**。
6. 长镜头语法（`long_take`）保持现有阈值与 94.7 分基线，仅从“唯一标准”降为“一个 profile”。
7. 兼容优先：`beats.yaml` 不写 grammar 时按 long_take 解释；deck/scene/recording 行为不变；新增能力全部可选；失败显式 blocked，不静默换引擎。
8. 本轮只做审计、架构设计与四支真实样片验证，**不修改生产代码**；施工按 P1–P4 分阶段，每阶段以真实渲染收尾。

**后果**：评分器不再把某一种艺术偏好伪装成通用质量标准；代价是必须维护多个 grammar profile，且人工签核不可省略。冻结检测等历史指标降为 metric，需重标定后才能再作门禁。

## D-066 多视觉语法生产系统 P1–P4 落地

**背景**：D-065 只定义了目标架构。目标参考片（短切、每拍换构图、无长寿命对象）需要把“镜头”变成第一等生产单位，并把质量拆成硬约束、语法约束、指标与人工签核。

**决策**：
1. 新增 `production.py`：Lesson → Sequence → Shot，镜头 `duration_s` 是唯一时间权威；新增 `compose.mode=shots`，`deck/scene/recording` 保持不变。
2. 新增 `shared/grammars/visual-grammars.yaml` 与 `grammar.py`：7 个语法；`beats.py` 按镜头 grammar 校验，未写 grammar 时仍按 `long_take`，旧节拍表行为不变。
3. 新增 `quality_gates.py` 与 `quality-gate`：Hard 不可豁免，Grammar 可书面豁免，Metrics 只报告，Human 必须签核；`animation-score` 降为指标工具（`release_gate=metric_only`），统一 85 分线废止。
4. 镜头转场进入契约与时间线（`hard_cut/fade/dissolve/match_cut/wipe`），只改视觉、不改时间基。
5. 逐词字幕：`Subtitles.mode=word` 消费 `asr-align` 的 `words`，V-16 按 word 模式检查；burn-in 不支持 word，显式报错。
6. 长片捕获：`capture.mjs --chunk-seconds` 分块渲染后无损拼接；adapter 对 >120 s 镜头自动启用。
7. 参考驱动：`reference.py` + `references/*.json` + `golden/golden.json` + `reference-compare`；composition/hierarchy/typography 固定 human_review。
8. 兼容优先：旧模式、旧节拍表、旧字幕路径、旧评分输出键全部保留；未知 grammar/renderer/capability 一律 blocked。

**后果**：质量判定不再是单一分数；代价是每门课需要声明 grammar（可缺省）、每个 grammar 需要维护 profile，且发布必须人工签核。shots 模式与逐词字幕尚未完成端到端渲染验证，状态记为 PARTIAL。

## D-067 品牌画面全英文、片尾只做 CTA、正片为原子资产并核验音频对齐

**背景**：审片指出片头出现分类编号与中文副题、片尾把课程元数据与下一课全部堆上屏、片头淡出后再接正片；同时怀疑正片音频在片头里抢跑。

**核查**：对成品音频执行 `silencedetect`：0–3.085 s 静音，第一句人声出现在片头结束后的 85 ms（原片开头的自然停顿），正片音画整体后移，未发现抢跑。片头尾部空白与片尾信息堆砌成立。

**决策**：
1. 品牌画面只允许英文；`Branding` 删除 `series` / `next_title` / `episode` / `BrandSegment.subtitle`，写入即校验失败；文案固定 `Thanks for watching.` / `Subscribe for more deep dives.`。
2. 课程片头 3.0 s：顶部 lockup + 居中英文单集标题；末帧保持标题卡，正片硬切。不做淡出、不做纸面遮罩、不出现分类编号或中文字幕。
3. 课程/新闻片尾只保留 lockup + 致谢 + CTA；新闻保留英文栏目与真实日期。删除 `NEXT`、课程标题、中文口号与重复订阅标签。
4. 正片是原子资产：不裁剪、不交叉淡化、不提前播放；品牌只做 `片头 → 正片 → 片尾` 线性 concat。
5. 拼接后程序核验音频对齐：片头静音轨音频时长与视频差 ≤ 1 帧；正片首段非静音 `body_first` 与成片 `actual` 的差 ≤ 0.2 s；结果写入 `brand.json.audio_alignment`，V-36 遇 `fail` 直接失败。
6. 移除 CJK 700 注入与字体文件：品牌帧不再需要中文粗体，避免合成粗体与多余字体包。

**后果**：品牌帧信息密度显著降低，但片头/片尾各自只承担一个任务；中文课程标题不再进入品牌画面，依赖必填的 `title_en`。D-063 中 3.5 s 时长、分类标签与元数据相关描述由本条取代。

## D-068 品牌拼接必须经 MPEG-TS 重封装，并用帧间距门禁

**背景**：审片发现成片前 20 秒画面快闪、音画字幕对不上。定位：直接对 MP4 段做 `concat -c copy`，两段 timescale 不同，concat 没有重缩放映时间戳——正片所有帧被压到 2.921 s 起、每帧只递增 11 微秒。文件时长、DTS 单调与音频都正常，所以先前的时长/音轨检查全部通过。

**决策**：
1. 不再直接 copy 拼接 MP4：每段先 remux 为 MPEG-TS（`-c copy -bsf:v h264_mp4toannexb`），按**视频流时长**写 concat 的 `duration`，再 remux 为 MP4；编码帧与音频样本仍复制，不重编码。
2. 新增 `video_timing` 门禁：读取全部视频 PTS 排序，`clustered_intervals`（间距 < 半帧）> 2，或唯一帧数与 `时长 × fps` 相差 > 2%，判 `fail` 并回退重编码；V-36 同样拒绝。
3. 结论：时长、DTS 单调、音频对齐不足以证明画面正确；必须单独校验显示时间戳的帧间距。
4. 抽样逐字节核验：正片第 30 帧与成片第 120 帧 `framemd5` 相同；正片音频包 `data_hash` 序列在成片中逐一对应。

**后果**：交付时长 307.367 s、9221 帧，帧间距正常（clustered 1，为片段边界被显式 duration 截短的 12 ms，在阈值内）。代价是每段多一次 TS 重封装（copy，秒级）和临时文件。

## D-069 片尾主轴按像素对齐，标签不得依附局部文本

**背景**：片尾里 `ENGINEERING & COMPUTATION` 与细线只对齐了 `WAYNE` 文本，整组视觉中心右移约 40 px；而致谢句在全屏中心，上下不在一条轴上。

**决策**：
1. 新增 `CenteredLockup`：`[W 图标] + [WAYNE]` 作为整体行居中，图标按字标中心对齐；tagline 居中于整组宽度，不依附 WAYNE。
2. 细线、致谢、CTA 各自独立居中，全部由 `flex-direction: column; align-items: center` 约束，不使用局部 `text-align` 猜测。
3. 抵消字距在末字后留下的空隙（tagline `marginRight: -0.22em`），否则墨迹中心偏左 2–3 px。
4. 新增 `scripts/brand-centers.py`：对渲染静帧逐行扫描非背景像素，输出每个内容带的墨迹 `center_x`，偏差 > 1 px 即 exit 1。

**后果**：片尾 5 个内容带中心为 959.5/959.5/959.5/959.0/959.0，全部在 1 px 内。片尾是同一套组件，新闻片尾与竖屏签名同步获得居中约束。

## D-070 垂直领域接入：品牌帧移除内容分类标签，领域方案只写内容

**背景**：接入经济学内容线时发现 `shared/design-tokens/brand.json` 的 `content_kinds` 各带一个人读标签（ENGINEERING COURSES / ENGINEERING EXPLAINED / INDUSTRY BRIEFING）。这套标签把频道钉在工程语义上：经济学找不到合适标签，每接一个新领域都要改一次品牌契约。

**决策**：
1. **品牌帧不承载内容分类标签。** 片头片尾只有 lockup、单集英文标题、致谢与 CTA；内容归属由标题与封面承担。新闻的动态栏目与真实日期是内容字段，保留。
2. 删除 `brand.json` 的 `content_kinds.*.label`，`content_kinds` 只保留 intro/outro 路由；`branding.py` 校验、Remotion 品牌组件与快照测试同步修改，label 出现即报错。
3. 新领域**不新增 `content_kind`**，不 fork 品牌；领域方案只写内容、来源、选题、资产与验收（`docs/verticals/`），不改引擎、语法、门禁与品牌。
4. 实施顺序：先完成标签移除并跑通品牌回归，再开经济学样片；在此之前经济学生产不启用 `branding`。

**实施状态**：决定已记录，**代码未改**。改动点见本机 `docs/verticals/economics/经济学系列-第一季生产方案.md` §1（不入库）。

**后果**：品牌语义不再随内容线扩张；D-067 关于分类标签的约束继续有效并扩展到数据层。

## D-071 质量以交付为准，运动语法阈值降为诊断指标

**背景**：现有 `beats.yaml` 与 `quality-gate` 把镜头时长、动作间隔、长寿命对象比例、冻结段数当成放行条件，实际效果是"必须做满几秒动画""每 4 秒必须有一个动作"。这类约束与解释质量无关，还会把讲得清楚的长镜头拆碎。

**决策**：
1. 发布条件只有三条：**把问题讲明白、把画面做好、把交付做硬**。其余指标都是它们的代理，不是替代。
2. 语法阈值（单镜时长、动作密度、长寿命比例、冻结段数）**只报告，不作放行**；`quality-gate` 的 grammar 层可逐条 `--waive` 并写明理由。
3. `beats-validate` 的硬失败只保留结构缺陷（旁白覆盖漏洞、镜头重叠、越界、配色对比度）；时长与动作密度类改为 warning。
4. 新增门禁必须是**可证明的缺陷**（解码失败、帧数不符、音画漂移、字幕缺失、文件哈希不符），不是审美偏好；不新增"秒数/帧数"型硬约束。
5. 人工看片与签字不可替代：自动化只能证明产物符合契约，不能证明讲得对、看得下去。

**实施状态**：**2026-11-10 已实施**。`beats.py` 拆为 errors/warnings，`beats-validate` 只对 errors exit 1；`quality_gates` 的 grammar 失败不再阻断，warnings 单独报告；`animation-score` 去掉无相机/冻结豁免的免费分。详见 `docs/stabilization/ANIMATION_QUALITY_MODEL.md`。

**后果**：`animation-score` 与语法归档退为诊断工具；发布结论回到"三条真实约束 + 人工签核"。


---

## D-072 Production Stabilization：两种生产单元、质量状态机与标准交付包

**背景**：审计（`docs/audit/`）发现同一门课有多套镜头/时间表示，质量结论有四种语义，交付包没有哈希与缺项失败。继续加功能会让"通过"更不可信。

**决策**：

1. **两种生产单元**：`deck`/`scene` 以 Page 为权威（`storyboard.yaml`）；`shots` 以 Shot 为权威（`authoring/production.yaml`）。导演计划、节拍表、`shots.json`、`TimelineSpec` 是视图，不是第二套权威。
2. **导演计划显式接入**：`build --storyboard-source director` 读取 `storyboard.director.yaml`；默认仍读 storyboard/production。`plan-audit` 只读报告计数差异。
3. **质量状态分离**：`BUILD_PASS`、`VERIFY_PASS`、`VERIFY_WARN`、`VERIFY_INCOMPLETE`、`VERIFY_FAIL`、`QUALITY_VERIFIED`、`REVIEW_APPROVED`、`RELEASE_APPROVED`。`WARN` 展示但不阻断；`SKIP`/`INCOMPLETE` 不得当作 `pass`；发布需要 review + release 两次带哈希的签核。
4. **标准交付包**：`course-control package` 复制已生成资产到 `build/<slug>/package/`，每个文件记录 SHA-256；缺必需项失败；`package-verify` 可独立复核。`build-report` 增加 `run_id` 与 artifact `sha256`。
5. **字幕**：显式 `subtitles.bilingual`；V-31 覆盖 burn-in 与 Remotion；中文行宽按显示宽度（CJK=1、拉丁=0.5）；`subtitles-rewrap` 只改行宽与过短 cue 合并，不改语义。
6. **渲染器 QC**：`verify_media` 统一 Manim/Motion/Blender 的分辨率/帧率/时长检查；CodeVideo 保持原有完整 QC。

**后果**：05 的评分从 100 降到 84.7；nvda/06 的 `INCOMPLETE` 阻止发布；01 的字幕草稿被重排并接受；05/06 生成可复核交付包。代价是发布前多两次人工签核，且旧课程需要重新构建才能获得 `run_id`。

**实施记录**：`docs/stabilization/MIGRATION_PLAN.md`。

**后续**：D-085 将最终交付包移到 `deliver/<slug>/`；`build/<slug>/` 只作临时区。D-072 第 4 条中 `build/<slug>/package/` 的路径表述由 D-085 取代。

## D-073 配置解析一次、快照不可变、指纹进入 resume

**背景**：课程时长、字幕语言、合成模式、模型路由分散在 `lesson.yaml` 与五个 `config/*.yaml`；模块各自读取，导致同一门课出现四个时长值，且无法判断哪次构建用了哪套配置。

**决策**：
1. 每次 build 调用一次 `resolve_config`，把生效值、来源文件、来源 SHA-256、冲突与警告写入 `build/<slug>/logs/config-resolution.json`。
2. 快照不覆盖、不合并后续修改；配置变化产生新指纹。
3. `build-report.config_fingerprint` 记录本次指纹；resume 只复用指纹相同的检查点。
4. 冲突分级：字幕语言声明不符、课程/新闻带 BGM、DeepSeek 非 flash、实测时长越界为 blocking；目标时长偏差与时间线偏差为 warning。
5. 环境变量只记录"是否存在"，不记录值。

**后果**：05 的 target 293 / measured 292.38 / timeline 292.37 / beats 286.08 有唯一解释；新增配置项必须同时更新 `CONFIGURATION_STANDARD.md` 与测试。

**实施状态**：**2026-11-10 已实施**。`config_resolve.py`、`config-resolve` 命令、`test_config_resolve.py`。

## D-074 Build 阶段检查点与顶层 resume

**背景**：构建在第一个失败阶段返回，重跑从零开始；"阶段完成"没有输入/输出哈希，无法安全跳过。

**决策**：
1. 每个可复用阶段写 `runtime/checkpoints/<stage>.json`，记录配置指纹、输入哈希、输出哈希与 run_id。
2. 复用条件：状态 pass、指纹相同、输入哈希相同、输出存在且哈希相同。任一不满足即重跑。
3. `--resume` 复用全部有效检查点；`--resume-from <stage>` 复用之前阶段，强制重跑该阶段及其后。
4. 每次运行写 `runtime/last-run.json`，记录 reused / replayed / invalid 原因；`build-report` 写 `resumed` 与 `reused_stages`。
5. `validate` 与 `verify` 每次运行，不缓存。

**后果**：中断后可只重跑受影响阶段；输出被删或被改不会被当作有效。已知限制：尚未在 01 的 20 分钟构建上做真实杀进程注入。

**实施状态**：**2026-11-10 已实施**。`checkpoint.py`、`pipeline.py`、`test_checkpoint.py`。

## D-075 Blender 任务统一入口，两代 Schema 并存但不可混淆

**背景**：v1 课程任务与 v2 场景 IR 使用不同校验器；调用方按目录猜测格式，未知字段可能被静默忽略。

**决策**：
1. `blender_task.load_blender_task` 是唯一入口，按 `schema_version` 分派。
2. v1 使用严格模型，未知字段拒绝；输出必须在 `build/<lesson>/blender/`，blend 必须在工作区内。
3. v2 继续使用 `validate_scene_task`，保留 IR 校验与输出路径约束。
4. 未知版本直接失败并列出支持版本；不提供"猜格式"回退。
5. v2 不进入课程默认链路，除非课程显式引用。

**后果**：`BlenderStudio/tasks/01-transformer-demo/stack_explode.json` 等 v1 任务在渲染前完成输入验证。

**实施状态**：**2026-11-10 已实施**。`blender_task.py`、`blender-task-validate`、`test_blender_task.py`。

## D-076 V1 时间线的 legacy 字段必须登记，未登记即失败

**背景**：Remotion 仍读取 `timeline.spec.json` 中的 `legacy_*` 字段；没有清单，新增字段会形成第二套契约。

**决策**：
1. `legacy_registry.py` 为每个字段登记消费者、替代字段、退出目标与原因。
2. V-43 扫描 `timeline.spec.json`，发现未登记 `legacy_*` 即失败。
3. 退出顺序：先迁移消费者，再删除字段；迁移完成前字段保留，不并行维护第二套业务逻辑。

**后果**：桥接层可枚举、可审计。当前 9 个字段全部登记。

**实施状态**：**2026-11-10 已实施**。`legacy_registry.py`、`verify.py` V-43、`test_legacy_registry.py`。

## D-077 缺失证据必须分类，未分类即失败

**背景**：文档引用 88–90 个已不存在的 `build/` 路径；无法区分"该恢复"与"历史记录"。

**决策**：
1. `docs/audit/evidence-decisions.yaml` 按最长前缀给每个缺失路径一个处置：retained / regenerable / retired_poc / historical / stale_ref / external。
2. `scripts/check_evidence.py` 输出分类报告；未分类缺失路径使检查失败。
3. 不批量删除文档引用，不补空文件；先分类，再按处置修复。
4. 规则变化必须有理由与所有者。

**后果**：2026-11-10 引用 182、缺失 90、全部已分类、未分类 0。

**实施状态**：**2026-11-10 已实施**。

## D-078 八类镜头能力是生产边界

**背景**：视觉生产逐镜头手写，没有能力清单；新增模板靠直觉，无法判断哪些能力经过验证。

**决策**：
1. `shared/grammars/shot-taxonomy.yaml` 固定 8 类：concept、mechanism、comparison、data、structure、transformation、narrative、summary。
2. 每类必须有输入契约、视觉目标、适用/禁用场景、动画规则、质量检查、真实样片。
3. 样片只有同时具备 `SPEC.md`、`VERIFY.md` 且无 `| fail |` 才算验证。
4. Agent 可以组合类型，不得发明未登记能力；新增类型先补契约与样片。
5. 镜头模板服务知识解释，不以模板数量为目标。

**后果**：`shot-taxonomy` 命令同时检查契约完整性与样片覆盖；当前 8 类全部有已验证样片。

**实施状态**：**2026-11-10 已实施**。Agent 生成对照实验仍未做。

## D-079 WARN 分类与统一裁决队列

**背景**：WARN 把"可接受提示"和"必须人工判断"混在一起；ContentQA、cross-review、teaching QA 各自产出，没有裁决记录。

**决策**：
1. `quality-report` 为每个 WARN 标注 `warning_class`：`human_review` 或 `blocking`。
2. `blocking` 使 `quality-gate.verification_status=incomplete`、`releasable=false`；`human_review` 只置 `NEEDS_HUMAN_REVIEW=true`。
3. `review/decisions.json` 是唯一裁决队列，取值 accepted / rejected / fixed / deferred。
4. 未裁决、unknown 值、accepted、deferred 都使 Q1 保持 WARN；全部 rejected/fixed 才 PASS。
5. 不新增第六个审查器。

**后果**：审查意见有可追溯的人工裁决；自动化仍不批准发布。

**实施状态**：**2026-11-10 已实施**。`review_decisions.py`、`review-status`、`review-decide`、`test_review_decisions.py`。

## D-080 外部资产进入交付包，three.js 只保留一份

**背景**：BGM 与声线参考在工作区外；换机后无法复核。three.js 在 5 个镜头目录各有一份 5 万行副本。

**决策**：
1. 资产用 `asset_id + sha256 + origin + license_status` 描述；绝对路径只作本机映射。
2. `package` 把外部资产复制到 `assets/external/`，写入 `manifest.external_assets[]`；缺失即失败。
3. `CodeVideoStudio/vendor/three/three.module.js` 是唯一 checked-in 副本。
4. 镜头目录的副本由 `vendor-sync` 或 `render:code_video` 生成，`.gitignore` 排除。
5. `vendor-check` 校验副本哈希；升级只改 vendor 一处。

**后果**：交付包自包含；three.js 从 5 份降为 1 份。

**实施状态**：**2026-11-10 已实施**。`assets.py`、`vendor.py`、`test_assets.py`、`test_vendor.py`。

## D-081 探针与生产入口分离

**背景**：Remotion Root 同时注册生产合成与 POC 探针，生产构建可能误用未验证 composition。

**决策**：
1. `src/index.ts` / `src/Root.tsx` 只注册生产 composition：CourseVideo、CourseTimeline、ScenePage 与四种品牌片段。
2. 探针移至 `src/probes/`，使用 `src/probes/index.ts` 独立入口。
3. `ChapterCard`、`BrandPreview` 属于探针，不进入生产入口。
4. 基准脚本引用探针入口时必须写明。

**后果**：生产入口暴露的 composition 从 14 个降到 7 个；`tsc --noEmit` 通过。

**实施状态**：**2026-11-10 已实施**。

## D-082 C-16 片头延期，不阻塞 V1

**背景**：20 秒工作室原型已完成颜色/层次修正并重渲，但 Gate 3 仍未通过：角色比例偏小，品牌 W 与角色动作未形成同一叙事；视觉概念与 3D 角色设计尚不成熟。

**决策**：
1. C-16 标记为 `DEFERRED`，本轮不再修改片头。
2. 保留 `BrandIntro/` 设计记录、`CodeVideoStudio/shots/brand-intro` 源码、角色资产与 Gate 3 前后帧；不删除有效资产。
3. 片头不进入生产默认链路，不以 Gate 3 阻塞 V1 课程生产。
4. 后续单独重新设计片头，不在当前方案上继续打补丁。

**后果**：V1 以课程生产、内容、质量与交付为主；品牌片头作为独立项目重启。

**实施状态**：**2026-11-10 已记录**。

## D-083 知识视频质量基准：以成片质量为准，不以时长或动画类型作为契约

**背景**：内容线扩展到经济学与 AI 产业后，需要一套跨领域的质量参照。此前的视觉与动画规范分散在总纲、视觉指南、工业化工作流与 D-071 中，缺少“什么算好”的统一基准，容易把参考频道的风格当成目标，也容易把镜头时长、动作密度重新写成门禁。

**决策**：
1. 建立 `docs/知识视频质量基准.md`：参考频道只校准知识质量、教学逻辑与视觉表达；对标不等于复刻，不按“像不像”评分。
2. 质量分 L1（必须达到）、L2（每集挑 1–2 个段落努力）、L3（长期探索）；发布只认 L1 与“把问题讲明白、把画面做好、把交付做硬”。
3. 视觉语法按知识对象选，不按频道选；品牌视觉与场景视觉分两层，权威仍是 `shared/design-tokens/themes.json`。
4. 验收只加内容、视觉、交付三层，映射到现有 `quality-gate`、`media-qc`、V-31/V-44、`package-verify` 与人工签核；不新增 `FR-*` / `NFR-*`、模块、语法、评分器或门禁。
5. 每集写一份 `acceptance-standard.md`，首个实例为本机 AI 经济系列 E01（`runtime/course-content/`，不入库）。
6. **镜头时长、动画类型、语法选择不得写成契约或验收条件**；它们只是制作手段，D-071 继续有效。

**后果**：知识系列有了统一质量口径；领域方案只写内容与证据，不再各自发明质量标准；成片验收回到画面、证据与人工签核。

**实施状态**：**2026-11-11 已记录**。基准文档已写入 `docs/`；E01 标准为 `design`，证据未采集，未进入生产。

## D-084 所有视频英文制作，字幕英上中下

**背景**：各垂直领域方案把语言写成待定，脚本、配音、字幕链路容易反复；已有课程也存在中文旁白或中文字幕的历史配置。

**决策**：
1. 所有新生产视频的画面文字与旁白用英文；英文稿直接写，不从中文逐句翻译。
2. 中文只做字幕与文章版本；默认不做中文配音。需要中文配音的单集必须显式批准，不进入默认链路。
3. 字幕固定英文在上、中文在下；术语按全季术语表统一；行宽、CPS、cue 数按 V-31 / V-44 检查。
4. 规则适用于长视频与 Shorts；不新增运行时字段或门禁，验收时人工核对。
5. 已有课程若用于正式发布，先核对语言与字幕；不符合的重做或补字幕，不静默保留。

**后果**：脚本、TTS、字幕与审片统一按英文主产品执行；中文版本基于同一知识结构重写，不做逐句直译。

**实施状态**：**2026-11-11 已记录**。质量基准、知识系列总纲、叙事规范、视觉指南、三个垂直领域方案与本机课程方案已同步；未新增代码检查。

## D-085 构建临时区与最终交付区分开

**背景**：最终交付分散在 `build/<slug>/final/`、`build/<slug>/package/`、`build/<slug>/delivery/`，引擎缓存又在 `RemotionStudio/public/staging/`、`ManimSandbox/media/`、`MotionStudio/output/`、`CodeVideoStudio/shots/*/out/`。清理与归档容易误删，或把中间产物当成交付。

**决策**：
1. `build/<slug>/` 是唯一临时区：可删除、可重建；不承载最终交付。
2. `deliver/<slug>/` 是唯一最终交付区：`course-control package` 默认输出到这里，含 master、captioned、字幕、报告、证据、review、metadata、manifest 与 checklist。
3. 制片清单从 `build/<slug>/delivery/` 改名到 `build/<slug>/producer/`，避免与最终交付混淆。
4. 引擎缓存归入 `build/_engine-cache/`；Remotion 的 `public/staging` 是渲染器要求的临时镜像，构建结束清理，不作为事实源。
5. `deliver/` 与 `build/` 一样不入库。
6. `scripts/organize-build.ps1` 负责迁移：`package/` → `deliver/`，`delivery/` → `producer/`，可选 `-EngineCaches`；不删除任何交付。

**后果**：清理 `build/` 不会删除最终交付；交付包可独立校验、归档；旧路径由迁移脚本处理。

**实施状态**：**2026-11-11 已实施**。`package` / `producer` 路径、tests、`.gitignore`、迁移脚本与现有产物已更新。
