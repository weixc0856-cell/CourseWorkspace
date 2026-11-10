# 文档索引

本目录按“现行契约 / 生产规范 / 评估与雷达 / 状态与验收 / 本地归档”组织。

## 1. 现行契约

- [PRD.md](PRD.md)：唯一产品基线
- [ARCHITECTURE.md](ARCHITECTURE.md)：系统结构与数据契约
- [课程生产统一契约V1.md](课程生产统一契约V1.md)：Lesson / Shot / Narration / Timeline / Evidence / Render
- [DECISIONS.md](DECISIONS.md)：决策记录（D-001 起）
- [TRACEABILITY.md](TRACEABILITY.md)：需求—模块—测试映射

## 1.0.0 V1 全量修复与生产体系收敛（2026-11-10，现行）

- [stabilization/MASTER_REMEDIATION.md](stabilization/MASTER_REMEDIATION.md)：C-01～C-30 唯一问题台账与最终裁决
- [stabilization/DECISIONS.md](stabilization/DECISIONS.md)：本轮裁决索引与被取代说法
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
- [architecture/实施记录-P1-P4.md](architecture/实施记录-P1-P4.md)：生产契约、语法档、质量分层、转场/逐词/分块的落地与未完成项
- [architecture/references/](architecture/references/)：参考库（Yari / 3B1B / Primer）
- [architecture/golden/golden.json](architecture/golden/golden.json)：各语法的 Golden Sample 与渲染哈希
- [architecture/样片-06-attention-sample.md](architecture/样片-06-attention-sample.md)：真实中文 62 秒课程样片、ASR/逐词字幕、参考对照与 180 s 捕获
- [contracts/](contracts/)：Production Contract / Visual Grammar / Quality Profile 的 JSON Schema 与 grammar 注册表

## 1.0.1 垂直领域（知识系列，2026-11-10）

- [verticals/知识系列课程生产总纲.md](verticals/知识系列课程生产总纲.md)：把一个领域接进现有系统的通用规范（来源分层、选题准入、语法映射、资产准入、许可、接入清单）
- [verticals/README.md](verticals/README.md)：领域方案索引与状态
- [verticals/economics/经济学系列-第一季生产方案.md](verticals/economics/经济学系列-第一季生产方案.md)：首个实例（v0.1 草案，未执行）

## 1.1 许可与贡献

- [LICENSE](../LICENSE)：AGPL-3.0-or-later
- [NOTICE](../NOTICE)：第三方许可
- [CONTRIBUTING.md](../CONTRIBUTING.md)：贡献与 CLA
- [第三方依赖准入规范.md](第三方依赖准入规范.md)：复用优先、口碑/活跃度校核、更新节奏与依赖登记表

## 1.2 产品能力边界

- [product/跨学科生产能力矩阵与能力边界规范.md](product/跨学科生产能力矩阵与能力边界规范.md)：学科 × 内容类型 × 能力边界（产品认知文档，不产生开发需求）

## 2. 生产规范

- 内容与课程：[课件制作总指导.md](课件制作总指导.md)、[课程视觉风格指南.md](课程视觉风格指南.md)、[课程生产交付物规范.md](课程生产交付物规范.md)、[课程交付清单模板.md](课程交付清单模板.md)
- 导演/制片：[导演层.md](导演层.md)、[制片层.md](制片层.md)、[动画渲染适配器.md](动画渲染适配器.md)
- 版式/配色/运镜：[版式系统.md](版式系统.md)、[配色规范.md](配色规范.md)、[运镜与剪辑.md](运镜与剪辑.md)、[动画视觉导演规范.md](动画视觉导演规范.md)
- 品牌：[品牌与片头片尾.md](品牌与片头片尾.md)：WAYNE 标识、三种内容形态的片头片尾、流水线位置与 V-33
- [品牌片头-3D桌面戏-设计.md](品牌片头-3D桌面戏-设计.md)：12 秒独立 3D 桌面片头设计稿 v1.1（Gate 1 粗剪已出）
- [../BrandIntro/README.md](../BrandIntro/README.md)：片头美术方向工程（参考板、角色/场景概念、美术 Gate）
- 教材知识库：[KnowledgeStudio.md](KnowledgeStudio.md)：PDF 拆页、目录校准、提取质检、按页检索、claim 引用与 QA
- 公式与图形：[公式排版规范.md](公式排版规范.md)、[科学图形与图表接入评估.md](evaluations/科学图形与图表接入评估.md)
- 音频：[内容类型与音频策略.md](内容类型与音频策略.md)、[音乐资产盘点.md](音乐资产盘点.md)、[本地模型与配音工作流.md](本地模型与配音工作流.md)
- 三维：[Blender场景任务IR-v2.md](Blender场景任务IR-v2.md)、[AI-Blender本地建模工作流.md](AI-Blender本地建模工作流.md)
- 流程：[工业化动画工作流.md](工业化动画工作流.md)、[WORKFLOW.md](WORKFLOW.md)、[提交前检查清单.md](提交前检查清单.md)
- 新闻视频：[新闻视频生产流程.md](新闻视频生产流程.md)：从一条新闻到一集成片的可复现步骤（Type-C 样片 nvda-gpu-control）
- 创作方法：[creative/叙事设计与观众留存规范.md](creative/叙事设计与观众留存规范.md)：长视频叙事骨架、Shorts、A/B 视觉与质量门禁
- 研发审核：[ReviewRunner/README.md](../ReviewRunner/README.md)：独立只读第二意见（Phase 1 只做代码审查）

## 3. 评估与雷达（`evaluations/`）

- [技术雷达-视频生产.md](evaluations/技术雷达-视频生产.md)
- [评估-Code2Video接入.md](evaluations/评估-Code2Video接入.md)
- [评估-DeepSeek Harness.md](evaluations/评估-DeepSeek%20Harness.md)
- [评估-四后端对比.md](evaluations/评估-四后端对比.md)
- [评估-Codex审核.md](evaluations/评估-Codex审核.md)
- [评估-PBR与科学可视化接入.md](evaluations/评估-PBR与科学可视化接入.md)
- [评估-Primer模拟视频POC.md](evaluations/评估-Primer模拟视频POC.md)
- [评估-代码镜头与执行验证.md](evaluations/评估-代码镜头与执行验证.md)
- [评估-动画音频口播-整合.md](evaluations/评估-动画音频口播-整合.md)
- [科学图形与图表接入评估.md](evaluations/科学图形与图表接入评估.md)
- [课程复刻差距与稳定工作流.md](evaluations/课程复刻差距与稳定工作流.md)
- [样片-注意力-3B1B差距与路线.md](evaluations/样片-注意力-3B1B差距与路线.md)
- [配色方案-学科适配.md](evaluations/配色方案-学科适配.md)
- [评估-Primer-3D-hero-v2.md](evaluations/评估-Primer-3D-hero-v2.md)
- [复刻-Primer衰老模拟-计划.md](evaluations/复刻-Primer衰老模拟-计划.md)
- [评估-Blender写实渲染能力.md](evaluations/评估-Blender写实渲染能力.md)
- [FRONTEND_ASSESSMENT.md](evaluations/FRONTEND_ASSESSMENT.md)

## 4. 状态与验收

- [PROJECT_STATUS.md](PROJECT_STATUS.md)：当前状态与 PRD 盘点
- [ACCEPTANCE.md](ACCEPTANCE.md)：验收规则、命令与证据
- [项目差距清单.md](项目差距清单.md)：P0–P2 缺口
- [课程质量保障体系-差距审查.md](课程质量保障体系-差距审查.md)：五条质量防线的实现差距与 P0/P1 路线

## 4.1 项目审计（2026-11-10）

- [audit/EXECUTIVE_SUMMARY.md](audit/EXECUTIVE_SUMMARY.md)：一页结论
- [audit/PROJECT_REALITY_AUDIT.md](audit/PROJECT_REALITY_AUDIT.md)：项目现状、模块核对、成熟度、文档偏差
- [audit/ARCHITECTURE_CONFLICTS.md](audit/ARCHITECTURE_CONFLICTS.md)：架构矛盾、规则冲突、优先级
- [audit/AUTOMATION_CAPABILITY_MATRIX.md](audit/AUTOMATION_CAPABILITY_MATRIX.md)：A0–A4 自动化等级与恢复能力
- [audit/SUPPORTED_CAPABILITIES.md](audit/SUPPORTED_CAPABILITIES.md)：内容与软件开发的能力边界
- [audit/OUTPUT_QUALITY_ASSESSMENT.md](audit/OUTPUT_QUALITY_ASSESSMENT.md)：真实成片的内容/视觉/声音/交付质量
- [audit/NEXT_STAGE_ROADMAP.md](audit/NEXT_STAGE_ROADMAP.md)：必须做、值得做、保留、停止、未来

## 4.2 Production Stabilization（2026-11-10）

- [stabilization/PRODUCTION_CONTRACT.md](stabilization/PRODUCTION_CONTRACT.md)：两种生产模式、单一权威、导演/build 接入
- [stabilization/QUALITY_STATE_MACHINE.md](stabilization/QUALITY_STATE_MACHINE.md)：BUILD/VERIFY/QUALITY/REVIEW/RELEASE 状态与签核
- [stabilization/ANIMATION_QUALITY_MODEL.md](stabilization/ANIMATION_QUALITY_MODEL.md)：结构/像素/人工三分，D-071 与评分修正
- [stabilization/DELIVERY_CONTRACT.md](stabilization/DELIVERY_CONTRACT.md)：`package` / `package-verify`、哈希与缺项失败
- [stabilization/MIGRATION_PLAN.md](stabilization/MIGRATION_PLAN.md)：R0–R5 状态、未完成项、回滚与待批准事项
- [stabilization/SESSION_2026-11-10.md](stabilization/SESSION_2026-11-10.md)：本轮实际改动、01 结果、矛盾点修复状态与操作教训

## 5. 本地归档（不入远程）

- [archive/README.md](archive/README.md)：归档索引
- `docs/archive/**` 除 README 外由 `.gitignore` 排除；干净克隆中不存在。
