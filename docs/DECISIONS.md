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

**后果**：现有轨道行为不变；V1-B 已实现模型、Schema、整数时间换算与测试（`contracts_v1.py` / `timecode.py`，CourseControl 116 个用例）；V1-C 再迁移 E6 manifest；任何 `skip` 或人工 `pass` 不得写成自动通过。设计稿与示例见 `docs/课程生产统一契约V1.md`、`docs/contracts/examples/`，实施报告见 `docs/V1-B-实施报告.md`。

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

## D-039 VideoZero 作为 Motion Canvas 自动导出的候选

**背景**：VideoZero（Apache 2.0）的 agent API 可以连接运行中的 Motion Canvas，执行 seek/screenshot/render；POC 证明默认 image-sequence exporter 可自动写出 3007 张 PNG，再由 ffmpeg 编码为 MP4。直接 FFmpeg exporter 在 Motion Canvas 3.17.2 上挂起。

**决策**：不作为纯 headless 方案；作为“图像序列自动导出 + 外部 ffmpeg”候选。需要 Vite FS allow/junction 适配和浏览器页面保持打开。主 MotionStudio 暂不改动，等内容稳定后再评审。

**后果**：现有 Motion Canvas 资产有自动导出路径；仍不是零人工、零浏览器依赖的方案。

## D-040 技术雷达机制

**背景**：此前按 Stars/知名度检索，漏掉 Code2Video 这类专项项目。

**决策**：新增 `docs/技术雷达-视频生产.md`，按课程适用性 30%、成熟度 20%、Agent 适配 20%、集成成本 15%、许可 15% 评分；设置许可证不明、无复现案例、硬件不匹配、重复建设四条硬门槛。每轮 POC 记录真实产物与决策。

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
