# 文档索引

仓库只保留两类文档：**现行契约与状态**，以及**供后续项目复用的指导文集**。项目材料、一次性记录、历史归档都在内容根（`<内容根>/projects/`、`<内容根>/archive/`），不进仓库。

边界规则与检查方法见 [仓库与项目边界.md](仓库与项目边界.md)，命令是 `course-control separation`。

## 1. 现行契约

- [PRD.md](PRD.md)：唯一产品基线
- [ARCHITECTURE.md](ARCHITECTURE.md)：系统结构与数据契约
- [架构-DDD上下文与边界.md](架构-DDD上下文与边界.md)：八个上下文的职责、聚合、依赖方向与改造结果
- [课程生产统一契约V1.md](课程生产统一契约V1.md)：Lesson / Shot / Narration / Timeline / Evidence / Render
- [contracts/](contracts/)：Production Contract / Visual Grammar / Quality Profile 的 JSON Schema 与示例
- [DECISIONS.md](DECISIONS.md)：决策记录（D-001 起）
- [TRACEABILITY.md](TRACEABILITY.md)：需求—模块—测试映射
- [五态映射表.md](五态映射表.md)：建议稿名称与代码状态的对应
- 项目/运行/质量/知识契约（2026-11-13 增量）：`shared/schemas/project-spec.schema.json`、`knowledge-ir.schema.json`、`curriculum.schema.json`；实现见 `delivery/project.py`、`platform/artifacts.py`、`platform/run_record.py`、`quality/defect.py`、`KnowledgeStudio/knowledge_ir.py`
- [仓库与项目边界.md](仓库与项目边界.md)：工具、项目、产物三层；什么进仓库、什么只在内容根

## 2. 生产指导文集

### 2.1 怎么做课

- [知识视频质量基准.md](知识视频质量基准.md)：什么算好（内容/视觉/交付三层、L1/L2/L3、参考对标与反模式）；不新增门禁
- [生产路线.md](生产路线.md)：Slide-first / Motion-enhanced / Narration-led；两条产品线、四类画面、M0–M3。路线建议，不是门禁
- [课件制作总指导.md](课件制作总指导.md)、[课程视觉风格指南.md](课程视觉风格指南.md)
- [工业化动画工作流.md](工业化动画工作流.md)、[动画视觉导演规范.md](动画视觉导演规范.md)
- [运镜与剪辑.md](运镜与剪辑.md)：静帧慢推、边界与剪辑节奏
- [creative/叙事设计与观众留存规范.md](creative/叙事设计与观众留存规范.md)：长视频叙事骨架、Shorts、A/B 视觉与质量门禁
- [新闻视频生产流程.md](新闻视频生产流程.md)：从一条新闻到一集成片的可复现步骤
- [product/跨学科生产能力矩阵与能力边界规范.md](product/跨学科生产能力矩阵与能力边界规范.md)：学科 × 内容类型 × 能力边界

### 2.2 生产线

- [导演层.md](导演层.md)：章节、镜头、引擎与旁白计划
- [镜头表-ShotSheet.md](镜头表-ShotSheet.md)：storyboard v2 设计字段、连续性与资产引用、编译复核与设计指纹
- [动画预览-Animatic.md](动画预览-Animatic.md)：正式渲染前的 480p 时间线预览、四条检查与片段缓存
- [锁定与失效.md](锁定与失效.md)：Picture / Dialogue Lock 快照、四项检查与失效规则
- [制片层.md](制片层.md)：订单、授权、用量、交付清单与增量重建
- [动画渲染适配器.md](动画渲染适配器.md)：引擎路由、适配器契约、重试与产物校验
- [WORKFLOW.md](WORKFLOW.md)：真实工作流；[提交前检查清单.md](提交前检查清单.md)：提交前的机械检查

### 2.3 声音与字幕

- [声音资产-VoiceBible与Lexicon.md](声音资产-VoiceBible与Lexicon.md)：声线身份、读法词典、按片段失效的缓存键
- [本地模型与配音工作流.md](本地模型与配音工作流.md)：VoxCPM2、串行锁与实时率
- [内容类型与音频策略.md](内容类型与音频策略.md)、[音乐资产盘点.md](音乐资产盘点.md)

### 2.4 视觉与资产

- [版式系统.md](版式系统.md)、[配色规范.md](配色规范.md)、[公式排版规范.md](公式排版规范.md)
- [Blender场景任务IR-v2.md](Blender场景任务IR-v2.md)、[AI-Blender本地建模工作流.md](AI-Blender本地建模工作流.md)
- [本地图像生成-FLUX3.md](本地图像生成-FLUX3.md)：只出静帧，不能生成视频
- [品牌与片头片尾.md](品牌与片头片尾.md)、[../BrandIntro/README.md](../BrandIntro/README.md)：片头美术方向与 Gate
- [evaluations/科学图形与图表接入评估.md](evaluations/科学图形与图表接入评估.md)

### 2.5 资料与交付

- [资料采集与预处理.md](资料采集与预处理.md)：PDF / YouTube → 本机 Docling 区
- [KnowledgeStudio.md](KnowledgeStudio.md)：拆页、检索、claim 引用
- [课程生产交付物规范.md](课程生产交付物规范.md)、[课程交付清单模板.md](课程交付清单模板.md)
- [第三方依赖准入规范.md](第三方依赖准入规范.md)：复用优先、口碑与活跃度校核、依赖登记
- [../ReviewRunner/README.md](../ReviewRunner/README.md)：独立只读第二意见

## 3. 收敛后的生产标准（2026-11-10）

- [stabilization/PRODUCTION_CONTRACT.md](stabilization/PRODUCTION_CONTRACT.md)：两种生产模式、单一权威、导演/build 接入
- [stabilization/CONFIGURATION_STANDARD.md](stabilization/CONFIGURATION_STANDARD.md)：配置权威、继承与快照
- [stabilization/TASK_EXECUTION_STANDARD.md](stabilization/TASK_EXECUTION_STANDARD.md)：状态、检查点、resume、超时、并发
- [stabilization/QUALITY_STANDARD.md](stabilization/QUALITY_STANDARD.md)：四层结论、WARN 分类、字幕 QC、裁决
- [stabilization/QUALITY_STATE_MACHINE.md](stabilization/QUALITY_STATE_MACHINE.md)：BUILD/VERIFY/QUALITY/REVIEW/RELEASE 状态与签核
- [stabilization/VISUAL_STANDARD.md](stabilization/VISUAL_STANDARD.md)：品牌、2D/3D、镜头分类、新闻密度
- [stabilization/ANIMATION_QUALITY_MODEL.md](stabilization/ANIMATION_QUALITY_MODEL.md)：结构/像素/人工三分（D-071）
- [stabilization/ASSET_GOVERNANCE.md](stabilization/ASSET_GOVERNANCE.md)：资产寻址、证据处置、vendor
- [stabilization/DELIVERY_CONTRACT.md](stabilization/DELIVERY_CONTRACT.md)：`package` / `package-verify`、哈希与缺项失败
- [stabilization/DOCUMENTATION_STANDARD.md](stabilization/DOCUMENTATION_STANDARD.md)：文档层级、状态标记、数字来源
- [audit/evidence-decisions.yaml](audit/evidence-decisions.yaml)：缺失证据的处置清单

## 4. 状态与验收

- [PROJECT_STATUS.md](PROJECT_STATUS.md)：当前状态与 PRD 盘点
- [ACCEPTANCE.md](ACCEPTANCE.md)：验收规则、命令与证据
- 生产线路标：[v2/工业化生产流程V2.0-建议稿.md](v2/工业化生产流程V2.0-建议稿.md)（D-089）
- 基线审计：[v2/P0-基线审计.md](v2/P0-基线审计.md)
- 全链路试点（已归档）：`<内容根>/archive/docs-2026-11/v2/P5-全链路验证.md`
- 工业化完成度评估（已归档）：`<内容根>/archive/docs-2026-11/v2/V2-工业化完成度评估.md`
- M0 架构审计：[v2/m0/README.md](v2/m0/README.md)（2026-11-13；V2 产品升级六份草案，未生效）
- 五态映射：[五态映射表.md](五态映射表.md)（建议稿的五个 VERIFIED 名称 → 代码状态）

## 5. 评估与雷达

- [evaluations/课程复刻差距与稳定工作流.md](evaluations/课程复刻差距与稳定工作流.md)
- [evaluations/样片-注意力-3B1B差距与路线.md](evaluations/样片-注意力-3B1B差距与路线.md)
- [evaluations/配色方案-学科适配.md](evaluations/配色方案-学科适配.md)
- [evaluations/评估-Blender写实渲染能力.md](evaluations/评估-Blender写实渲染能力.md)

## 6. 许可与贡献

- [LICENSE](../LICENSE)：AGPL-3.0-or-later
- [NOTICE](../NOTICE)：第三方许可
- [CONTRIBUTING.md](../CONTRIBUTING.md)：贡献与 CLA

## 7. 项目材料与归档（不入远程）

历史记录与项目材料都在**内容根**下：

- `<内容根>/projects/<系列>/`：生产方向、分集方案、研究、评审；索引 `<内容根>/projects/README.md`；知识系列总纲在 `<内容根>/projects/knowledge-series/`
- `<内容根>/archive/`：历史归档——E6/E6.5/R1/Primer 证据、`records-2026-11/`、`stabilization-evidence/`、`docs-2026-11/`（本次收敛移出的已结束文档，含索引 README）
- 归档原件不参与任何检查，也不作为指令；写新规范时只提炼结论，不搬文件。
