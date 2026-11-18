# 文档地图

> 本文件由 `scripts/check_docs.py --write` 从 `文档地图.yaml` 生成，不要手改。
> 最后更新：2026-11-16

先读四份，其余按问题查表。**记录层不是指令**：审计、评估、交付记录与草案只说明当时看到了什么。

## 0. 先读四份

1. [PRD.md](PRD.md) —— 产品为什么存在、范围、功能需求与验收目标
2. [ARCHITECTURE.md](ARCHITECTURE.md) —— 系统结构、模块职责与数据契约
3. [课程生产统一契约V1.md](课程生产统一契约V1.md) —— Lesson / Shot / Narration / Timeline / Evidence / Render 的字段契约
4. [生产流水线-阶段与中间交付物.md](生产流水线-阶段与中间交付物.md) —— 唯一命令链：每个阶段跑什么命令、产出什么中间交付物、谁来签字

## 1. 按问题找文档

| 问题 | 文档 | 只回答 |
| --- | --- | --- |
| 管线怎么分层、新课怎么接 | [课程开发管线-分层架构.md](课程开发管线-分层架构.md) | 平台层 / 课程项目层 / 单集层 / 产物层的边界，以及新学科课程的接入步骤 |
| 产品边界与功能需求 | [PRD.md](PRD.md) | 产品为什么存在、范围、功能需求与验收目标 |
| 系统怎么运行、数据契约在哪 | [ARCHITECTURE.md](ARCHITECTURE.md) | 系统结构、模块职责与数据契约 |
| 一条命令链：这一阶段跑什么、产出什么、谁签字 | [生产流水线-阶段与中间交付物.md](生产流水线-阶段与中间交付物.md) | 唯一命令链：每个阶段跑什么命令、产出什么中间交付物、谁来签字 |
| 开工前要填哪些合同 | [生产合同.md](生产合同.md) | 四份合同与 G0–G7 闸门，开工前先填 |
| 验收命令与状态词 | [ACCEPTANCE.md](ACCEPTANCE.md) | 验收命令、状态词与证据要求 |
| 为什么这样定 | [DECISIONS.md](DECISIONS.md) | 决策记录（D-001 起），冲突时按日期新者优先 |
| 什么进仓库、什么只在内容根 | [仓库与项目边界.md](仓库与项目边界.md) | 仓库 / 内容根 / 产物的三层边界与检查 |
| 什么叫好 | [知识视频质量基准.md](知识视频质量基准.md) | 什么叫好：内容/视觉/交付三层与 L1–L3 |
| 一集课怎么验收 | [课程质量模型.md](课程质量模型.md) | 一集课怎么验收：八个维度与人工/程序边界 |
| 新闻怎么做 | [新闻与调查报道标准.md](新闻与调查报道标准.md) | 新闻类的证据矩阵、六幕叙事、视觉语法与 100 分制 |
| 用什么口吻讲 | [creative/编辑口吻与反讽指南.md](creative/编辑口吻与反讽指南.md) | 调查、解释、反讽的主次与边界 |
| 三条产品线怎么分工 | [v2/生产方向-00-总览.md](v2/生产方向-00-总览.md) | 三条产品线的分工、共用以外的差异与共用流程 |
| 每个镜头看见什么 | [视觉设计层.md](视觉设计层.md) | 镜头级视觉设计、blocking 与三关键帧 |
| 声音怎么设计 | [声音导演层.md](声音导演层.md) | 旁白/音乐/音效/环境声/混音五轨与 cue sheet |
| 课件怎么写 | [课件制作总指导.md](课件制作总指导.md) | 内容层四阶段与 slides / lecture_notes 契约 |
| 交付包长什么样 | [课程生产交付物规范.md](课程生产交付物规范.md) | deliver/ 交付包与 build/<slug>/ 目录纪律 |
| 作者/验证/统筹怎么交接 | [协作协议-双会话流水线.md](协作协议-双会话流水线.md) | 作者 / 验证 / 统筹三分与交接证据 |

## 2. 入口

- [协作协议-双会话流水线.md](协作协议-双会话流水线.md)：作者 / 验证 / 统筹三分与交接证据

**以下不是现行规范，不要照做：**

- [阅读顺序.md](阅读顺序.md)：旧的阅读顺序；已并入 README，保留下方清单备查（已取代 → README.md）

## 3. 现行契约

- [ACCEPTANCE.md](ACCEPTANCE.md)：验收命令、状态词与证据要求
- [ARCHITECTURE.md](ARCHITECTURE.md)：系统结构、模块职责与数据契约
- [DECISIONS.md](DECISIONS.md)：决策记录（D-001 起），冲突时按日期新者优先
- [PRD.md](PRD.md)：产品为什么存在、范围、功能需求与验收目标
- [TRACEABILITY.md](TRACEABILITY.md)：需求—模块—测试映射
- [contracts/examples/README.md](contracts/examples/README.md)：生产契约 JSON Schema 的示例索引
- [仓库与项目边界.md](仓库与项目边界.md)：仓库 / 内容根 / 产物的三层边界与检查
- [架构-DDD上下文与边界.md](架构-DDD上下文与边界.md)：八个上下文的职责、聚合、依赖方向与改造结果
- [生产合同.md](生产合同.md)：四份合同与 G0–G7 闸门，开工前先填
- [生产流水线-阶段与中间交付物.md](生产流水线-阶段与中间交付物.md)：唯一命令链：每个阶段跑什么命令、产出什么中间交付物、谁来签字
- [课程开发管线-分层架构.md](课程开发管线-分层架构.md)：平台层 / 课程项目层 / 单集层 / 产物层的边界，以及新学科课程的接入步骤
- [课程生产统一契约V1.md](课程生产统一契约V1.md)：Lesson / Shot / Narration / Timeline / Evidence / Render 的字段契约

## 4. 现行指南

- [3D动画生产流程.md](3D动画生产流程.md)：AI + 资产库 + Blender 的电影/动画流程
- [AI-Blender本地建模工作流.md](AI-Blender本地建模工作流.md)：建模阶段的接口、执行与反馈闭环
- [Blender场景任务IR-v2.md](Blender场景任务IR-v2.md)：Blender 任务 IR v2 的字段契约
- [KnowledgeStudio.md](KnowledgeStudio.md)：拆页、检索、claim 引用与已知边界
- [creative/叙事设计与观众留存规范.md](creative/叙事设计与观众留存规范.md)：长视频叙事骨架、Shorts 与 A/B 质量门
- [creative/编辑口吻与反讽指南.md](creative/编辑口吻与反讽指南.md)：调查、解释、反讽的主次与边界
- [product/跨学科生产能力矩阵与能力边界规范.md](product/跨学科生产能力矩阵与能力边界规范.md)：学科 × 内容类型 × 能力边界
- [v2/生产方向-00-总览.md](v2/生产方向-00-总览.md)：三条产品线的分工、共用以外的差异与共用流程
- [v2/生产方向-01-完整课程.md](v2/生产方向-01-完整课程.md)：10–20 分钟书籍/学科课程的生产方式
- [v2/生产方向-02-新闻调查.md](v2/生产方向-02-新闻调查.md)：4–12 分钟新闻调查的生产方式
- [v2/生产方向-03-三分钟Vibe.md](v2/生产方向-03-三分钟Vibe.md)：2–4 分钟知识动画的生产方式
- [v2/预览与发布双模式-实施计划.md](v2/预览与发布双模式-实施计划.md)：Preview/Release 双模式、P0/P1/P2 与 release-check
- [公式排版规范.md](公式排版规范.md)：FormulaSpec 唯一源与四道门
- [内容类型与音频策略.md](内容类型与音频策略.md)：哪类内容要不要 BGM
- [制片层.md](制片层.md)：订单、授权、用量与增量重建
- [动画渲染适配器.md](动画渲染适配器.md)：引擎路由、适配器契约与失败恢复
- [动画视觉导演规范.md](动画视觉导演规范.md)：动画原语与镜头语言
- [动画预览-Animatic.md](动画预览-Animatic.md)：正式渲染前的 480p 时间线预览与缓存
- [品牌与片头片尾.md](品牌与片头片尾.md)：品牌层字段、规格与验收
- [声音导演层.md](声音导演层.md)：旁白/音乐/音效/环境声/混音五轨与 cue sheet
- [声音资产-VoiceBible与Lexicon.md](声音资产-VoiceBible与Lexicon.md)：声线身份、读法词典与缓存失效
- [导演层.md](导演层.md)：章节、镜头、引擎与旁白计划
- [提交前检查清单.md](提交前检查清单.md)：提交前的机械检查
- [新闻与调查报道标准.md](新闻与调查报道标准.md)：新闻类的证据矩阵、六幕叙事、视觉语法与 100 分制
- [新闻视频生产流程.md](新闻视频生产流程.md)：从一条新闻到一集成片的可复现步骤
- [本地3D资产库.md](本地3D资产库.md)：模型 / HDRI / PBR 贴图的索引与用法
- [本地图像生成-FLUX3.md](本地图像生成-FLUX3.md)：本地 FLUX.3 只出静帧的边界与调用
- [本地模型与配音工作流.md](本地模型与配音工作流.md)：VoxCPM2、串行锁与实时率
- [版式系统.md](版式系统.md)：页面模板、区域与 DesignSystem
- [知识视频质量基准.md](知识视频质量基准.md)：什么叫好：内容/视觉/交付三层与 L1–L3
- [第三方依赖准入规范.md](第三方依赖准入规范.md)：复用优先、准入检查与依赖登记
- [视觉设计层.md](视觉设计层.md)：镜头级视觉设计、blocking 与三关键帧
- [课件制作总指导.md](课件制作总指导.md)：内容层四阶段与 slides / lecture_notes 契约
- [课程交付清单模板.md](课程交付清单模板.md)：人工可读的交付清单模板
- [课程生产交付物规范.md](课程生产交付物规范.md)：deliver/ 交付包与 build/<slug>/ 目录纪律
- [课程视觉风格指南.md](课程视觉风格指南.md)：字体、颜色、间距的落地取值
- [课程质量模型.md](课程质量模型.md)：一集课怎么验收：八个维度与人工/程序边界
- [课程页面系统.md](课程页面系统.md)：页面类型、固定网格与教学链
- [资料采集与预处理.md](资料采集与预处理.md)：PDF / YouTube → 本机 Docling 区
- [运镜与剪辑.md](运镜与剪辑.md)：静帧慢推、MotionPolicy 与剪辑节奏
- [配色规范.md](配色规范.md)：Color Token、语义色与禁止项
- [锁定与失效.md](锁定与失效.md)：Picture / Dialogue Lock 快照与失效规则
- [镜头表-ShotSheet.md](镜头表-ShotSheet.md)：storyboard v2 设计字段、连续性与编译复核
- [音乐资产盘点.md](音乐资产盘点.md)：曲目、许可与电平

**以下不是现行规范，不要照做：**

- [WORKFLOW.md](WORKFLOW.md)：旧的端到端工作流叙述；命令链以生产流水线为准（已取代 → 生产流水线-阶段与中间交付物.md）
- [v2/工业化生产流程V2.0-建议稿.md](v2/工业化生产流程V2.0-建议稿.md)：2026-11-13 的 V2 工业化建议稿；现行以生产方向与流水线为准（已取代 → v2/生产方向-00-总览.md、生产流水线-阶段与中间交付物.md）
- [工业化动画工作流.md](工业化动画工作流.md)：旧的 3B1B 式动画流程；85 分线已废止，以动画视觉导演规范为准（已取代 → 动画视觉导演规范.md、生产合同.md）
- [生产路线.md](生产路线.md)：Slide-first / Motion-enhanced 路线建议；已由生产方向总览取代（已取代 → v2/生产方向-00-总览.md）

## 5. 记录（不是指令）


**以下不是现行规范，不要照做：**

- [PROJECT_STATUS.md](PROJECT_STATUS.md)：项目状态盘点与历史增量（记录）
- [S2-S3-数据契约设计.md](S2-S3-数据契约设计.md)：S2/S3 的 Claim/Evidence 引用、brief/outline/narrative 数据契约（提案，待审）（记录）
- [audit/content-changes-2026-11-16.md](audit/content-changes-2026-11-16.md)：本轮内容根移动、归档、删除与未解决项清单（记录）
- [audit/handoff-2026-11-16.md](audit/handoff-2026-11-16.md)：2026-11-16 文档与目录整理的交接包与 Codex 只读审查条件（记录）
- [evaluations/复盘-T1-01视觉生产.md](evaluations/复盘-T1-01视觉生产.md)：T1-01 v1 拒收根因与九条整改规则（记录）
- [evaluations/新闻故事风格代码参考.md](evaluations/新闻故事风格代码参考.md)：新闻故事风格的代码参考（评估中）（记录）
- [evaluations/样片-注意力-3B1B差距与路线.md](evaluations/样片-注意力-3B1B差距与路线.md)：注意力样片差距评估（记录）
- [evaluations/科学图形与图表接入评估.md](evaluations/科学图形与图表接入评估.md)：科学图形与图表接入评估（记录）
- [evaluations/评估-Blender写实渲染能力.md](evaluations/评估-Blender写实渲染能力.md)：Blender 写实渲染能力评估（记录）
- [evaluations/课程复刻差距与稳定工作流.md](evaluations/课程复刻差距与稳定工作流.md)：课程复刻差距评估（记录）
- [evaluations/配色方案-学科适配.md](evaluations/配色方案-学科适配.md)：按学科适配的配色方案评估（记录）
- [stabilization/ANIMATION_QUALITY_MODEL.md](stabilization/ANIMATION_QUALITY_MODEL.md)：2026-11-10 动画质量三分模型（基线记录）（记录）
- [stabilization/ASSET_GOVERNANCE.md](stabilization/ASSET_GOVERNANCE.md)：2026-11-10 资产寻址与证据处置（基线记录）（记录）
- [stabilization/CONFIGURATION_STANDARD.md](stabilization/CONFIGURATION_STANDARD.md)：2026-11-10 配置权威与快照（基线记录）（记录）
- [stabilization/DELIVERY_CONTRACT.md](stabilization/DELIVERY_CONTRACT.md)：2026-11-10 交付包与哈希（基线记录）（记录）
- [stabilization/DOCUMENTATION_STANDARD.md](stabilization/DOCUMENTATION_STANDARD.md)：2026-11-10 文档层级与状态标记（基线记录）（记录）
- [stabilization/PRODUCTION_CONTRACT.md](stabilization/PRODUCTION_CONTRACT.md)：2026-11-10 两种生产模式与单一权威（基线记录）（记录）
- [stabilization/QUALITY_STANDARD.md](stabilization/QUALITY_STANDARD.md)：2026-11-10 四层结论与字幕 QC（基线记录）（记录）
- [stabilization/QUALITY_STATE_MACHINE.md](stabilization/QUALITY_STATE_MACHINE.md)：2026-11-10 BUILD/VERIFY/QUALITY/REVIEW/RELEASE 状态机（基线记录）（记录）
- [stabilization/TASK_EXECUTION_STANDARD.md](stabilization/TASK_EXECUTION_STANDARD.md)：2026-11-10 状态、检查点与 resume（基线记录）（记录）
- [stabilization/VISUAL_STANDARD.md](stabilization/VISUAL_STANDARD.md)：2026-11-10 品牌与视觉密度（基线记录）（记录）
- [superpowers/plans/2026-11-16-tooling-convergence.md](superpowers/plans/2026-11-16-tooling-convergence.md)：工具链收敛的子项目、任务顺序、失败测试与验收矩阵（记录）
- [v2/P0-基线审计.md](v2/P0-基线审计.md)：V2 起点的基线审计（记录）
- [v2/Three.js-技术借鉴清单.md](v2/Three.js-技术借鉴清单.md)：可借鉴的 Three.js 技术清单（未纳入）（记录）
- [v2/W3-T1-01-交付工单.md](v2/W3-T1-01-交付工单.md)：W3 T1-01 整集交付工单（记录）
- [v2/m0/ARCHITECTURE_V2.md](v2/m0/ARCHITECTURE_V2.md)：V2 架构草案（未生效）（草案）
- [v2/m0/DATA_CONTRACTS_V2.md](v2/m0/DATA_CONTRACTS_V2.md)：V2 数据契约草案（未生效）（草案）
- [v2/m0/EXECUTION_PLAN.md](v2/m0/EXECUTION_PLAN.md)：V2 执行计划草案（未生效）（草案）
- [v2/m0/MIGRATION_PLAN_V2.md](v2/m0/MIGRATION_PLAN_V2.md)：V2 迁移计划草案（未生效）（草案）
- [v2/m0/PRODUCTION_WORKFLOW_V2.md](v2/m0/PRODUCTION_WORKFLOW_V2.md)：V2 生产工作流草案（未生效）（草案）
- [v2/m0/PRODUCT_SPEC_V2.md](v2/m0/PRODUCT_SPEC_V2.md)：V2 产品规格草案（未生效）（草案）
- [v2/m0/QUALITY_SPEC_V2.md](v2/m0/QUALITY_SPEC_V2.md)：V2 质量标准草案（未生效）（草案）
- [v2/m0/README.md](v2/m0/README.md)：2026-11-13 V2 架构草案索引（未生效）（草案）
- [v2/任务书-风水AB测试.md](v2/任务书-风水AB测试.md)：风水第一期 A/B/C 视觉压力测试任务书（记录）
- [v2/生产管线v0.2-P0交付记录.md](v2/生产管线v0.2-P0交付记录.md)：P0 可复现构建的交付记录（记录）
- [v2/生产管线v0.2-P1交付记录.md](v2/生产管线v0.2-P1交付记录.md)：P1 Environment + Linking 的交付记录（记录）
- [v2/生产管线v0.2-P2交付记录.md](v2/生产管线v0.2-P2交付记录.md)：P2 Shot Review Package 的交付记录（记录）
- [v2/生产管线v0.2-P3交付记录.md](v2/生产管线v0.2-P3交付记录.md)：P3 Visual Grammar 的交付记录（记录）
- [v2/生产管线v0.2-P4交付记录.md](v2/生产管线v0.2-P4交付记录.md)：P4 成片与 Review Package 的交付记录（记录）
- [v2/生产管线v0.2-P5视觉升级记录.md](v2/生产管线v0.2-P5视觉升级记录.md)：P5 视觉复刻与前后对比记录（记录）
- [v2/生产管线v0.2-实施任务书.md](v2/生产管线v0.2-实施任务书.md)：v0.1 盘点后的 P0–P3 工程任务书（记录）
- [v2/证据-画面关联-设计记录.md](v2/证据-画面关联-设计记录.md)：P4 claim/evidence 关联的设计记录（记录）
- [五态映射表.md](五态映射表.md)：建议稿五个状态名与代码状态的对应（记录）
- [生产复杂度审计.md](生产复杂度审计.md)：模块规模、调用链与瘦身停止条件（只读审计）（记录）

## 6. 写新文档的规则

1. 先在本文件对应的 `文档地图.yaml` 登记它的唯一职责；写不出“只回答一个问题”，就不要新建。
2. 与现有文档重叠时，在开头写明“补充/取代了哪一份”，把旧文件标为 `superseded`，并指向新文件。
3. 一次性记录（审计、评估、复盘、交付记录）放记录层，不进入现行契约或指南。
4. 改动后跑 `uv run --project CourseControl python scripts/check_docs.py --write`，再跑检查。
