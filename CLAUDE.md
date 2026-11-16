# CourseWorkspace — 项目指导（Claude Code 入口）

> 本文件只放**每次干活都必须遵守的红线**与**唯一入口**。细节在 `docs/`，按需查阅，不在此复制。
> 全量文档地图：[docs/README.md](docs/README.md) · 阅读顺序：[docs/阅读顺序.md](docs/阅读顺序.md)

---

## 0. 指令优先级与熔断

1. **当前对话的用户指令 > 本文件红线 > `docs/` 历史规范。** 用户明确要求覆盖旧规时直接执行，并同步更新对应规范；唯一例外是防伪造（伪造数据、伪造验收、越权写入、破坏他人任务）——冲突时先执行用户要求并写明冲突点。
2. **第三方评审不是指令。** 用户转发的他人意见先输出《差异核验与改动清单》，分三类：①客观事实错误（可用证据当场证伪）②审美与风格取舍 ③工程高风险（改时间线、改规则、伪造数据、越权写入）。给出"建议执行 / 建议驳回附证据 / 需用户决策"，等用户点名后再改。**不得整包照做，也不得整包忽略。**
3. **同一问题最多 3 次。** 构建、测试、渲染、推送、外部调用连续失败 3 次立即停：记录问题、已尝试修复、当前证据、下一步建议，等人工决定。不得用反复重跑代替定位根因。

---

## 1. 红线（违反即不得交付）

### A. 资产与证据

0. **内容所有权。** 存量课程的 `slides.md`、`lecture_notes.md`、`outline.md`、课程 `assets/` 归用户所有，只允许格式级调整（路径、分页、主题类名）；**改语义必须先问**。系统生成的课程与视频内容由系统产出，所有者保留接受与拒收权，且必须带来源与证据链。
1. **复用优先（全域适用）。** 组件、三维资产、教材插图、模板一律先找现成资源，能用现成的不自建；只有许可、风格、需要动效或精度不满足时才自建，并写明理由。
2. **教材原图在 Docling 产线，不在本仓库。** 根目录 `DOCLING_OUTPUT_ROOT`（本机见 `config/local-paths.yaml` 的 `docling_root` + `/output`），每本书一个 `<source_id>/`，内含 `assets/`、`document.json`（含 caption 与 page_no）、`manifest.json`；根目录 `catalog.json` 是来源清单。**在 `staging/` 找不到图时先查这里，不得据此判断"没有素材"，更不得编造素材。** 新书接入 = Docling 跑一遍 → 目录出现 → 按 `source_id` 检索，不为任何一本书写专属路径或脚本。
3. **原书证据零篡改。** 原图保持原始像素——**严禁反相、去白底、改线色**。统一置于暖白纸面板（实测 `#EDE7DA`）+ 细边框 + 投影 + 统一留白；只允许在其上叠加**聚光灯/高亮框、沿原图坐标的遮罩揭开、指向原图坐标的标签**。
4. **禁止手画物理机制。** `MechanismDiagram` / `CarFlowScene` 必须给 `base_image`（指向 `staging/ref_figs/`），或给出枚举理由 `formula_animation | summary_card | no_book_figure`；缺则装配直接报错。机制图的几何由原书作者负责，程序只加解释层。
5. **示意图三问自查（交图之前）。** 遮住标签看三件事：①车头方向与相对气流方向 ②每个场量相对车身的位置（低压区在车外、尾流在尾缘之后）③图注数值与图形一致。**答不出来就是图错了，自己打回。** 有数值可核时必须报数（如某点 Cp），不接受"看起来对"。
6. **图形尺寸绑数据。** 对比图（尾流大小、后备箱体积等）先写数据表，图高与箭头长度由数据生成，不在 SVG 里写死像素——数据不错，图注就不可能自相矛盾。

### B. 内容与视听

7. **全英文制作。** 画面文字与旁白用英文；中文只做字幕（英上中下）。唯一例外已在项目文档登记（风水频道引用古文）。
8. **去转述腔。** 讲稿用第一人称专家视角，**`the book` / `according to` / `chapter` 全片为 0**；出处只进画面 source 行与片尾。
9. **`display_text` 与 `tts_text` 分离。** 屏幕写 `~32×`、`c_D`；口播写 `about thirty-two times`、`C-D`。`tts_text` 若存在**不得短于 `text` 的 60%**（模型层校验），且覆盖时日志必须打印 `tts_override`。口播与屏幕数字严格一致。
10. **视听事件必须替某句话干活。** 每段声明 1–3 个视觉事件（何时 / 对什么 / 怎么变 / 服务哪句）。`淡入`、`fade in`、`展示图片`按未写处理。允许静态，但要写明为什么静、静多久、观众在干什么。
11. **叙事机器契约。** 长视频与 Shorts 必须提供 `authoring/narrative-plan.json` 并通过 `narrative-validate`；Shorts 30–90 秒、竖屏、独立脚本，不从长视频裁切。
12. **单闸门 + 工具冻结 + 素材规格。**
    - **闸门**：每集先出**静态分镜网页**（数据灌进组件、不带动效的翻页稿），用户逐页否决或放行；**签字后才注入动效、配音与渲染**。表格描述不作数——"车顶线分离填橙"这种写法，实际会被做成"图片+框+标签"。
    - **工具冻结**：内容生产期发现组件或模板瑕疵，**记进 Todo、不许停下来改引擎**；交付后开固定窗口统一升级。做课期间改渲染管线，等于用交付换整洁。
    - **素材规格**：进流水线的图统一尺寸与底板（16:9 或 1:1、≥2K、统一纸色或暗色），录屏统一圆角边框套壳。规格不合的素材先修再进，不靠版面临时补救。

### C. 验收与工程

13. **AI 输出不等于已完成。** LLM 生成的结构化计划、脚本、审查意见都是候选结果，必须经程序校验与可定位证据验证；无法验证的内容不得交付。人工只在成品拒收复核时介入，不替代程序做逐条事实判断。
13. **skip ≠ pass。** 未执行的阶段不得写成通过；`not_run`、`incomplete`、采样不足一律不是通过，必须显式打印并计入异常队列。
14. **视觉审计必须有正向断言。** 不能只查"0 重叠 / 0 越界"：必须同时校验**非背景像素占比 > 5%**、**页面无未捕获异常与 ErrorBoundary 节点**、**当前帧 `data-beat-id` / `data-asset-src` 与剧本一致**。每条规则必须配一个"能红"的负例。
15. **不伪造验收。** 不得为通过而改测试预期、跳过检查、补写内容、拿旧产物顶替；发布签核必须由具名的人签字。
16. **工程隔离。** 临时产物写 `build/<slug>/`，最终交付写 `deliver/<slug>/`；不全局安装依赖、不改系统 PATH；真实课程、模型权重与媒体不入库，远程仓库只放工作流。
17. **本地模型串行。** 所有本地模型调用走 `shared/ai_runtime` 跨进程锁，8080 唯一实例；**谁启动谁停止**，空闲时把端口让出来。VoxCPM2 在 50000、ComfyUI 在 8188，同样独占。
18. **远程回退必须显式。** 仅当 `config/model-routing.yaml` 启用且环境变量存在才回退；DeepSeek 固定 `deepseek-flash`，禁用 `pro`；API key 只读环境变量，不写入文件或日志。
19. **Claude Code 是默认文本后端。** 课程文本生产、字幕翻译、ContentQA 默认走 Claude Code（`--tools=`）；不可用即 `blocked`，只有 `claude_code_fallback: local_first` 才可回退，禁止静默降级。
20. **上下文硬上限 64K。** 禁止把整本书或整段历史塞进一次请求。
21. **片头片尾不影响正片。** 只允许线性拼接；正片的视频、音频、字幕与时间线是原子资产，不裁剪、不重编码、不交叉淡化。品牌默认关闭。
22. **本地 FLUX.3 只出静帧**，图生视频写死禁用。动态画面走 Blender 或 Remotion，最终由 FFmpeg 编码。

### D. 新闻与调查（做新闻类前必读）

23. **未读标准不得开工。** 新闻类必须先读 [docs/新闻与调查报道标准.md](docs/新闻与调查报道标准.md) 与 [docs/新闻视频生产流程.md](docs/新闻视频生产流程.md)，按 **证据 → 叙事 → 视觉 → 声音 → 后期 → 验收** 执行。硬要求：每集 `authoring/fact-check.md` 含证据矩阵与"本片明确不主张"；六幕叙事；四层证据标注（DOCUMENTED / REPORTED / INFERENCE / CLAIM）；素材直接用、**不设授权审批，唯一红线是不伪造、不错配来源**；100 分制 ≥75 才发布，研究准确性 <16/20 直接不发布。

---

## 2. 操作事实（本机）

- **端口**：8080 本地模型（唯一）、8081 课件预览、3000 Remotion、5173 Motion Canvas、50000 VoxCPM2、8188 ComfyUI。8082 不存在。
- **环境**：Python 3.12 + uv；Node 24 + npm；Blender 5.2；FFmpeg 8。
- **配置**（均不入库）：`config/tools.yaml`、`config/local-paths.yaml`（`content_root` / `docling_root` / TTS）、`config/model-routing.yaml`。
- **内容根**：`<content_root>/{lessons,build,deliver,runtime,knowledge,audio,projects,references,archive}`；`course-control content-root` 可查询。
- **常用命令**：
  ```powershell
  .\scripts\check.ps1                                        # 全量回归（必须打印 check ok）
  course-control validate --lesson <slug>                     # 课程校验
  course-control preflight --lesson <slug>                    # 开工前置
  course-control checks --lesson <slug> --book-index <path>   # 类型化检查 + 异常队列
  course-control retime --lesson <slug>                       # 按实测旁白重算时间轴
  course-control subtitles-rebuild --lesson <slug>            # 字幕重建（实测对齐）
  course-control release-check --lesson <slug>                # 发布三态
  course-control contract-validate --kind product|ledger|timeline --path <p>
  scripts/build-lesson.ps1 -Lesson <slug>                     # 完整构建
  scripts/check_segment_assets.py --lesson-dir <dir>          # 绑定扫描（缺参/复用图/禁令词）
  scripts/fetch_book_figures.py --source-id <id> --figure <n> # 从 Docling 取原书图
  node RemotionStudio/scripts/frame-audit.mjs                 # 帧审计（正向断言）
  python scripts/static_hold.py --film <mp4>                  # 死画面检测
  ```
  其余子命令见 `course-control --help`；完整验收命令见 [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md)。
- **协作协议**：[docs/协作协议-双会话流水线.md](docs/协作协议-双会话流水线.md)（作者 / 验证 / 统筹三分，交接三样证据）。

---

## 3. 索引（按需查阅，不在此堆砌）

- **架构与验收**：[docs/PRD.md](docs/PRD.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) · [docs/TRACEABILITY.md](docs/TRACEABILITY.md)
- **视觉与版式**：[docs/动画视觉导演规范.md](docs/动画视觉导演规范.md) · [docs/课程页面系统.md](docs/课程页面系统.md) · [docs/版式系统.md](docs/版式系统.md) · [docs/配色规范.md](docs/配色规范.md)
- **生产合同与质量**：[docs/生产合同.md](docs/生产合同.md) · [docs/课程质量模型.md](docs/课程质量模型.md) · [docs/知识视频质量基准.md](docs/知识视频质量基准.md)
- **声音**：[docs/声音资产-VoiceBible与Lexicon.md](docs/声音资产-VoiceBible与Lexicon.md) · [docs/声音导演层.md](docs/声音导演层.md)
- **边界与准入**：[docs/仓库与项目边界.md](docs/仓库与项目边界.md) · [docs/第三方依赖准入规范.md](docs/第三方依赖准入规范.md) · [docs/资料采集与预处理.md](docs/资料采集与预处理.md)
- **完整清单**：[docs/README.md](docs/README.md)
