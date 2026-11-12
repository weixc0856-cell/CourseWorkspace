# 文档索引


> **2026-11-12 状态**：V1 收敛完成；`check.ps1` exit 0。本轮完成 CLI 拆分、字幕解析合并、媒体原语归位、内容根迁移（lessons / build / deliver / runtime / knowledge 移出程序目录），并把一次性记录移入本机归档；仓库只保留程序与在用文档。新增历史 / AI 时代基础 / 汽车空气动力学三个知识板块（本机开发，不入库）；统一英文成片与英上中下字幕；`build/` 为临时区、`deliver/` 为最终交付区。C-16 片头 DEFERRED。生产契约与验收见 [最终验收报告](stabilization/FINAL_ACCEPTANCE_REPORT.md)。
本目录按“现行契约 / 生产规范 / 评估与雷达 / 状态与验收 / 本地归档”组织。

## 1. 现行契约

- [PRD.md](PRD.md)：唯一产品基线
- [ARCHITECTURE.md](ARCHITECTURE.md)：系统结构与数据契约
- [架构-DDD上下文与边界.md](架构-DDD上下文与边界.md)：八个上下文的职责、聚合、依赖方向与改造结果
- [课程生产统一契约V1.md](课程生产统一契约V1.md)：Lesson / Shot / Narration / Timeline / Evidence / Render
- [DECISIONS.md](DECISIONS.md)：决策记录（D-001 起）
- [TRACEABILITY.md](TRACEABILITY.md)：需求—模块—测试映射
- [仓库与项目边界.md](仓库与项目边界.md)：工具、项目、产物三层；什么进仓库、什么只在内容根（`course-control separation`）

## 1.0.0 V1 全量修复与生产体系收敛（2026-11-10，现行）

- [stabilization/MASTER_REMEDIATION.md](stabilization/MASTER_REMEDIATION.md)：C-01～C-32 唯一问题台账；现状 VERIFIED 25 / FIXED 4 / DEFERRED 1（C-16）/ OPEN 0
- [stabilization/ARCHITECTURE_FINAL.md](stabilization/ARCHITECTURE_FINAL.md)：最终模块边界与权威链
- [stabilization/PRODUCTION_CONTRACT.md](stabilization/PRODUCTION_CONTRACT.md)：Page/Scene/Storyboard/Shot
- [stabilization/CONFIGURATION_STANDARD.md](stabilization/CONFIGURATION_STANDARD.md)：配置权威、继承与快照
- [stabilization/TASK_EXECUTION_STANDARD.md](stabilization/TASK_EXECUTION_STANDARD.md)：状态、检查点、resume、超时、并发
- [stabilization/QUALITY_STANDARD.md](stabilization/QUALITY_STANDARD.md)：四层结论、WARN 分类、字幕 QC、裁决
- [stabilization/VISUAL_STANDARD.md](stabilization/VISUAL_STANDARD.md)：品牌、2D/3D、镜头分类、新闻密度
- [stabilization/ASSET_GOVERNANCE.md](stabilization/ASSET_GOVERNANCE.md)：资产寻址、证据处置、vendor
- [stabilization/DOCUMENTATION_STANDARD.md](stabilization/DOCUMENTATION_STANDARD.md)：文档层级、状态标记、数字来源
- [stabilization/FINAL_ACCEPTANCE_REPORT.md](stabilization/FINAL_ACCEPTANCE_REPORT.md)：回归、故障注入与最终验收
- [audit/evidence-decisions.yaml](audit/evidence-decisions.yaml)：缺失证据的处置清单

## 1.0 多视觉语法生产架构（2026-11-10）

- [architecture/多视觉语法生产系统-审计.md](architecture/多视觉语法生产系统-审计.md)：现有契约、门禁、评分器的耦合与影响面（P0）
- [architecture/多视觉语法生产系统-设计.md](architecture/多视觉语法生产系统-设计.md)：四层架构、三份契约、Renderer Adapter、质量重构、迁移与风险
- [architecture/多视觉语法生产系统-样片验证.md](architecture/多视觉语法生产系统-样片验证.md)：四支真实渲染样片与机器结果
- 参考库与 Golden Sample：`<内容根>/references/`（3B1B / Primer / Yari 的参考记录与 golden.json，项目材料，不入库）；`course-control reference-compare` 优先从这里解析
- [architecture/样片-06-attention-sample.md](architecture/样片-06-attention-sample.md)：真实中文 62 秒课程样片、ASR/逐词字幕、参考对照与 180 s 捕获
- [contracts/](contracts/)：Production Contract / Visual Grammar / Quality Profile 的 JSON Schema 与 grammar 注册表

## 1.0.1 垂直领域（知识系列，2026-11-11）

- [verticals/知识系列课程生产总纲.md](verticals/知识系列课程生产总纲.md)：把一个领域接进现有系统的通用规范（来源分层、选题准入、语法映射、资产准入、许可、接入清单）
- [verticals/README.md](verticals/README.md)：领域索引与本机方案路径
- 领域方案（经济学、历史、AI 时代基础、汽车空气动力学）属于课程开发内容，只在本机 `<内容根>/projects/<domain>/`，不入库；本索引不链接。

## 1.0.2 交付分区与资料采集（2026-11-11）

- [课程生产交付物规范.md](课程生产交付物规范.md)：`build/<slug>/` 临时区、`deliver/<slug>/` 最终交付区、manifest 与 QC
- [stabilization/DELIVERY_CONTRACT.md](stabilization/DELIVERY_CONTRACT.md)：`package` / `package-verify` 的交付契约（D-085）
- [资料采集与预处理.md](资料采集与预处理.md)：PDF 与 YouTube 来源进入本机 Docling 区，生成 Markdown/JSON 与 catalog
- [知识视频质量基准.md](知识视频质量基准.md)：内容 / 视觉 / 交付三层；L1 必须、L2 分块努力、L3 长期探索
- [DECISIONS.md](DECISIONS.md)：D-084 英文成片与英上中下字幕；D-085 临时区与最终交付区

## 1.0.3 内容根迁移（2026-11-12，设计稿）

- [内容根迁移方案.md](内容根迁移方案.md)：把 `lessons`、`build`、`deliver`、`runtime`、`knowledge`、`assets` 移出程序目录；含代码改动点、执行步骤、回滚与第二阶段（引擎课程目录）边界。

## 1.0.4 工业化生产流程 V2.0（2026-11-12，已采纳，逐步落地）

- [v2/工业化生产流程V2.0-建议稿.md](v2/工业化生产流程V2.0-建议稿.md)：生产线八阶段、六个工作包（WP-0～WP-5）、执行顺序 P0～P6 与各阶段验收标准（D-089）
- [v2/P0-基线审计.md](v2/P0-基线审计.md)：建议稿与现有代码的逐条对照、实测缺陷清单、文档不一致范围与落地顺序
- [v2/P5-全链路验证.md](v2/P5-全链路验证.md)：a01 试点跑到哪、被什么挡住（字幕 QC 与过期构建报告）

## 1.1 许可与贡献

- [LICENSE](../LICENSE)：AGPL-3.0-or-later
- [NOTICE](../NOTICE)：第三方许可
- [CONTRIBUTING.md](../CONTRIBUTING.md)：贡献与 CLA
- [第三方依赖准入规范.md](第三方依赖准入规范.md)：复用优先、口碑/活跃度校核、更新节奏与依赖登记表

## 1.2 产品能力边界

- [product/跨学科生产能力矩阵与能力边界规范.md](product/跨学科生产能力矩阵与能力边界规范.md)：学科 × 内容类型 × 能力边界（产品认知文档，不产生开发需求）

## 2. 生产规范

- 质量基准：[知识视频质量基准.md](知识视频质量基准.md)：什么算好（内容/视觉/交付三层、L1/L2/L3、参考对标与反模式）；不新增门禁
- 主生产路线：[生产路线.md](生产路线.md)：Slide-first / Motion-enhanced / Narration-led；Explainer 与 Course 两条产品线、四类画面、M0–M3 里程碑。路线建议，不是契约或门禁，交付质量仍按质量基准判定
- 内容与课程：[课件制作总指导.md](课件制作总指导.md)、[课程视觉风格指南.md](课程视觉风格指南.md)、[课程生产交付物规范.md](课程生产交付物规范.md)、[课程交付清单模板.md](课程交付清单模板.md)
- 导演/制片：[导演层.md](导演层.md)、[制片层.md](制片层.md)、[动画渲染适配器.md](动画渲染适配器.md)
- 预览：[动画预览-Animatic.md](动画预览-Animatic.md)：正式渲染前的 480p 时间线预览，四条检查与片段缓存
- 声音：[声音资产-VoiceBible与Lexicon.md](声音资产-VoiceBible与Lexicon.md)：声线身份、读法词典、按片段失效的缓存键
- 镜头表：[镜头表-ShotSheet.md](镜头表-ShotSheet.md)：storyboard v2 设计字段、连续性与资产引用、编译复核与设计指纹
- 锁定：[锁定与失效.md](锁定与失效.md)：Picture / Dialogue Lock 快照、四项检查与失效规则
- 版式/配色/运镜：[版式系统.md](版式系统.md)、[配色规范.md](配色规范.md)、[运镜与剪辑.md](运镜与剪辑.md)、[动画视觉导演规范.md](动画视觉导演规范.md)
- 品牌：[品牌与片头片尾.md](品牌与片头片尾.md)：WAYNE 标识、三种内容形态的片头片尾、流水线位置与 V-33
- [品牌片头-3D桌面戏-设计.md](品牌片头-3D桌面戏-设计.md)：12 秒独立 3D 桌面片头设计稿 v1.1（Gate 1 粗剪已出）
- [../BrandIntro/README.md](../BrandIntro/README.md)：片头美术方向工程（参考板、角色/场景概念、美术 Gate）
- 资料采集：[资料采集与预处理.md](资料采集与预处理.md)：PDF 与 YouTube 来源进入本机 Docling 区，处理后 Markdown/JSON 与 catalog；原始文件不入库
- 教材知识库：[KnowledgeStudio.md](KnowledgeStudio.md)：PDF 拆页、目录校准、提取质检、按页检索、claim 引用与 QA
- 公式与图形：[公式排版规范.md](公式排版规范.md)、[科学图形与图表接入评估.md](evaluations/科学图形与图表接入评估.md)
- 音频：[内容类型与音频策略.md](内容类型与音频策略.md)、[音乐资产盘点.md](音乐资产盘点.md)、[本地模型与配音工作流.md](本地模型与配音工作流.md)
- 三维：[Blender场景任务IR-v2.md](Blender场景任务IR-v2.md)、[AI-Blender本地建模工作流.md](AI-Blender本地建模工作流.md)
- 图像生成：[本地图像生成-FLUX3.md](本地图像生成-FLUX3.md)：本地 ComfyUI 8188 + FLUX.3，**只出静帧，不能生成视频**；提示词、调用与 2.5D 用法
- 流程：[工业化动画工作流.md](工业化动画工作流.md)、[WORKFLOW.md](WORKFLOW.md)、[提交前检查清单.md](提交前检查清单.md)
- 新闻视频：[新闻视频生产流程.md](新闻视频生产流程.md)：从一条新闻到一集成片的可复现步骤（Type-C 样片 nvda-gpu-control）
- 创作方法：[creative/叙事设计与观众留存规范.md](creative/叙事设计与观众留存规范.md)：长视频叙事骨架、Shorts、A/B 视觉与质量门禁
- 研发审核：[ReviewRunner/README.md](../ReviewRunner/README.md)：独立只读第二意见（Phase 1 只做代码审查）

## 3. 评估与雷达（`evaluations/`）

- [科学图形与图表接入评估.md](evaluations/科学图形与图表接入评估.md)
- [课程复刻差距与稳定工作流.md](evaluations/课程复刻差距与稳定工作流.md)
- [样片-注意力-3B1B差距与路线.md](evaluations/样片-注意力-3B1B差距与路线.md)
- [配色方案-学科适配.md](evaluations/配色方案-学科适配.md)
- [评估-Blender写实渲染能力.md](evaluations/评估-Blender写实渲染能力.md)

## 4. 状态与验收

- [PROJECT_STATUS.md](PROJECT_STATUS.md)：当前状态与 PRD 盘点
- [ACCEPTANCE.md](ACCEPTANCE.md)：验收规则、命令与证据

## 4.1 项目审计（已归档）

2026-11-10 的七份审计报告已移出仓库，保留在本机 `<内容根>/archive/records-2026-11/audit/`；其中可执行的结论已收进 [stabilization/MASTER_REMEDIATION.md](stabilization/MASTER_REMEDIATION.md)。

## 4.2 Production Stabilization（2026-11-10）

- [stabilization/PRODUCTION_CONTRACT.md](stabilization/PRODUCTION_CONTRACT.md)：两种生产模式、单一权威、导演/build 接入
- [stabilization/QUALITY_STATE_MACHINE.md](stabilization/QUALITY_STATE_MACHINE.md)：BUILD/VERIFY/QUALITY/REVIEW/RELEASE 状态与签核
- [stabilization/ANIMATION_QUALITY_MODEL.md](stabilization/ANIMATION_QUALITY_MODEL.md)：结构/像素/人工三分，D-071 与评分修正
- [stabilization/DELIVERY_CONTRACT.md](stabilization/DELIVERY_CONTRACT.md)：`package` / `package-verify`、哈希与缺项失败

## 5. 项目材料与本地归档（不入远程）

历史记录与项目材料都在**内容根**下，不在仓库里：

- `<内容根>/archive/`：历史归档——决策、E6/E6.5/R1/Primer 证据、`records-2026-11/`（2026-11-12 收敛时移出的 24 份一次性记录）、`stabilization-evidence/`
- `<内容根>/projects/<系列>/`：各系列的生产方向、分集方案、混合动效流程；索引 `<内容根>/projects/README.md`
- 仓库只保留现行权威文档与可复用规范；归档原件不参与任何检查。
